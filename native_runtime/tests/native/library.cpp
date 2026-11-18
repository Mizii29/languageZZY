#include "zzy_native/execution.hpp"
#include "zzy_native/prepare.hpp"
#include <chrono>
#include <iostream>
#include <sstream>
#include <thread>

namespace zzy {
struct ExecutionProbe {
    static void require(bool condition,const char* message) {if(!condition) throw std::runtime_error(message);}
    static Program parse(const std::string& text,const ResourcePolicy& p,std::atomic<bool>& cancel) {
        FrontendMeter meter(p,cancel);AstBuilder ast(meter);auto source=std::make_shared<const Source>(L"library fixture.zzy",text);
        const auto tokens=Lexer(source,meter).scan();const auto root=Parser(tokens,meter,ast).parse();
        ProgramData data;data.root=root;Resolver(ast.nodes,data,meter).resolve(root);data.nodes=std::move(ast.nodes);return Program(std::move(data));
    }
    static void released(const ExecutionContext& c) {
        require(c.heap.state->used==Charge{} && c.heap.state->roots.empty() && c.heap.state->nodes.empty(),"heap leaked");
        require(c.calls.empty() && c.tasks.empty() && c.modules.empty() && c.builtins.empty() && !c.frame,"execution state leaked");
        c.heap.state->close();require(c.heap.state->used==Charge{},"repeated close");
    }
    static void callbacks() {
        for(int failure=0;failure<4;++failure) {
            ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;
            const auto body=failure==0?"1/0":failure==1?"array.push(a,x)":failure==2?R"("not bool")":"x";
            const auto call_program=parse("(zno) a:=[1,2,3];(addnew) f(x){(return)"+std::string(body)+";}array.filter(a,f);",p,cancel);
            ExecutionContext actual(call_program,p,cancel,out,err);actual.initialize();
            const auto root=actual.program.root;const auto& children=actual.ast(root).children;
            actual.statement(children[0],[]{});actual.drain();actual.statement(children[1],[]{});actual.drain();
            const auto source=actual.globals.at(children[0]).raw;
            const auto expression=actual.ast(children[2]).children[0];
            const auto callback=actual.globals.at(children[1]).raw;
            actual.array_library("array.filter",{source,callback},expression,[](Value){});
            if(failure==3) cancel=true;
            try {actual.drain();throw std::runtime_error("missing callback failure");}
            catch(RuntimeError& e) {
                require(e.code==(failure==0?"E205":failure==1?"E206":"E201"),"callback diagnostic");
                actual.unwind(&e);
            } catch(const Cancelled&) {require(failure==3,"unexpected cancel");actual.unwind(nullptr);}
            require(actual.object(source).active==0 && actual.object(source).edges.size()==3,"active iteration or mutation leaked");
            actual.cleanup();released(actual);cancel=false;
            const auto next=parse("io.print(array.sum([1,2,3]));",p,cancel);ExecutionContext good(next,p,cancel,out,err);good.execute();
            require(out.str()=="6\n" && err.str().empty(),"next request recovery");released(good);
        }
    }
    static void identity() {
        ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;const auto program=parse("array.sorted([1]);",p,cancel);
        ExecutionContext c(program,p,cancel,out,err);c.initialize();const auto expression=c.ast(c.ast(c.program.root).children[0]).children[0];
        auto first=c.string("same",expression),second=c.string("same",expression),low=c.string("a",expression);
        auto source=c.array({first,low,second},expression);Value result;
        c.array_library("array.sorted",{source},expression,[&](Value v){result=v;});
        const auto& edges=c.object(result).edges;
        require(edges[0]==low.ref() && edges[1]==first.ref() && edges[2]==second.ref(),"unstable sorting or lost element identity");
        require(c.object(source).edges[0]==first.ref() && !source.same(result),"source reordered");
        const auto definition=c.builtin("array.Stats",expression);
        require(definition.same(c.builtin("array.Stats",expression)),"definition is not request scoped");
        auto old=definition;c.cleanup();released(c);
        ExecutionContext next(program,p,cancel,out,err);next.initialize();
        require(!old.same(next.builtin("array.Stats",expression)),"nominal definition shared across requests");next.cleanup();released(next);
    }
    static void budgets() {
        ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;const auto program=parse("array.sorted([1]);",p,cancel);
        for(std::uint64_t bound:{13,14,15}) {
            p.limits["runtime_slots"]=bound;ExecutionContext c(program,p,cancel,out,err);c.initialize();
            const auto expression=c.ast(c.ast(c.program.root).children[0]).children[0];
            auto source=c.array({c.integer(BigInt(3),expression),c.integer(BigInt(1),expression),c.integer(BigInt(2),expression)},expression);
            const auto before=c.heap.state->used;
            try {c.array_library("array.sorted",{source},expression,[](Value){});throw std::runtime_error("sort unexpectedly fit");}
            catch(const RuntimeError& e) {
                // 2 built-in slots + 3 source slots + 9 workspace = 14; result needs another 3.
                require(e.code=="E211","wrong quota error");
                c.heap.collect();require(c.heap.state->used==before && c.object(source).active==0,"partial reservations retained");
            }
            c.cleanup();released(c);
        }
        for(std::uint64_t cap:{16,17,18}) {
            p.limits["runtime_slots"]=cap;ExecutionContext c(program,p,cancel,out,err);c.initialize();
            const auto expression=c.ast(c.ast(c.program.root).children[0]).children[0];
            auto source=c.array({c.integer(BigInt(3),expression),c.integer(BigInt(1),expression),c.integer(BigInt(2),expression)},expression);
            try {c.array_library("array.sorted",{source},expression,[](Value){});require(cap>=17,"over-limit sort accepted");}
            catch(const RuntimeError& e) {require(cap==16 && e.code=="E211","sort L-1/L/L+1");}
            c.cleanup();released(c);
        }
    }
    static void cancellation() {
        ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;
        const auto program=parse(R"(text.split("a","b");)",p,cancel);ExecutionContext c(program,p,cancel,out,err);c.initialize();
        const auto expression=c.ast(c.ast(c.program.root).children[0]).children[0];
        const auto text=c.string(std::u32string(3000000,U'a'),expression),needle=c.string(std::u32string(100000,U'a')+U'b',expression);
        const auto before=c.heap.state->used;std::atomic<bool> started{false};
        std::thread interrupter([&] {while(!started.load()) std::this_thread::yield();std::this_thread::sleep_for(std::chrono::milliseconds(2));cancel=true;});
        bool cancelled=false;
        try {started=true;c.text_library("text.split",{text,needle},expression);}
        catch(const Cancelled&) {cancelled=true;}
        catch(...) {interrupter.join();throw;}
        interrupter.join();require(cancelled && c.heap.state->used==before,"text scan did not cancel or leaked");
        c.cleanup();released(c);cancel=false;
        ExecutionContext next(program,p,cancel,out,err);next.execute();released(next);
    }
    static void text_boundaries() {
        ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;
        const auto program=parse(R"(text.join([],"-");)",p,cancel);
        for(const auto& operation:{"join","split","safe_int_digits","safe_int_bits"}) for(int delta:{-1,0,1}) {
            ExecutionContext c(program,p,cancel,out,err);c.initialize();
            const auto site=c.ast(c.ast(c.program.root).children[0]).children[0];
            std::vector<Value> args;std::string name,key;std::uint64_t usage=0;
            if(std::string(operation)=="join") {name="text.join";key="text_codepoints";usage=5;args={c.array({c.string("ab",site),c.string("cd",site)},site),c.string("-",site)};}
            else if(std::string(operation)=="split") {name="text.split";key="container_items";usage=3;args={c.string("a,,b",site),c.string(",",site)};}
            else {name="text.safe_int";key=std::string(operation)=="safe_int_bits"?"integer_bits":"numeric_digits";usage=key=="integer_bits"?4:3;args={c.string(key=="integer_bits"?"8":"123",site)};}
            c.heap.state->policy.limits[key]=static_cast<std::uint64_t>(static_cast<std::int64_t>(usage)+delta);
            const auto before=c.heap.state->used;
            try {const auto result=c.text_library(name,args,site);require(delta>=0,"text capacity overrun");require(bool(result),"missing result");}
            catch(const RuntimeError& e) {require(delta==-1 && e.code=="E211" && std::string(e.what()).find(key)!=std::string::npos,"text boundary");}
            c.heap.collect();require(c.heap.state->used==before,"text temporary space leaked");c.cleanup();released(c);
        }
    }
};
}
int main(int argc,char** argv) {
    const std::map<std::string,void(*)()> cases={{"callbacks",zzy::ExecutionProbe::callbacks},{"identity",zzy::ExecutionProbe::identity},
        {"budgets",zzy::ExecutionProbe::budgets},{"cancellation",zzy::ExecutionProbe::cancellation},{"text",zzy::ExecutionProbe::text_boundaries}};
    try {if(argc!=2 || !cases.count(argv[1])) throw std::runtime_error("nonempty named selection required");cases.at(argv[1])();std::cout<<argv[1]<<": PASS\n";return 0;}
    catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
