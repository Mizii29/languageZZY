#include "zzy_native/execution.hpp"
#include "zzy_native/prepare.hpp"
#include <iostream>
#include <sstream>

namespace zzy {
struct ExecutionProbe {
    static Program parse(const std::string& text,const ResourcePolicy& p,std::atomic<bool>& cancel) {
        FrontendMeter meter(p,cancel);AstBuilder ast(meter);
        auto source=std::make_shared<const Source>(L"N3 fixture.zzy",text);
        auto tokens=Lexer(source,meter).scan();const auto root=Parser(tokens,meter,ast).parse();
        ProgramData data;data.root=root;Resolver(ast.nodes,data,meter).resolve(root);data.nodes=std::move(ast.nodes);
        return Program(std::move(data));
    }
    static void require(bool yes,const char* message) {if(!yes) throw std::runtime_error(message);}
    static void cleaned(const ExecutionContext& c) {
        require(c.heap.state->closed && c.heap.state->used==Charge{} && c.heap.state->nodes.empty() && c.heap.state->roots.empty(),"request heap not released");
        require(c.calls.empty() && c.tasks.empty() && c.globals.empty() && c.modules.empty() && !c.frame,"request state not released");
    }
    static void cancel_and_reuse() {
        struct CancelOnFlush : std::stringbuf {
            std::atomic<bool>& cancel;
            explicit CancelOnFlush(std::atomic<bool>& c):cancel(c) {}
            int sync() override {cancel=true;return std::stringbuf::sync();}
        };
        ResourcePolicy policy;std::atomic<bool> setup{false};std::ostringstream error;
        const auto program=parse("(zno) a:=[];array.push(a,a);(addnew) f()->(Int){io.print(\"ready\");(return) 7;}"
                                 "(zno) l:=(zzz)(f());wake(l);io.print(42);",policy,setup);
        const auto bad=parse("(zno) a:=[];array.push(a,a);(for) x (in) a {1/0;}",policy,setup);
        for(int i=0;i<40;++i) {
            std::atomic<bool> old{false};CancelOnFlush stream(old);std::ostream output(&stream);
            ExecutionContext cancelled(program,policy,old,output,error);
            try {cancelled.execute();throw std::runtime_error("missing cancel");}catch(const Cancelled&) {}
            require(old && stream.str()=="ready\n","expected cancellation during Lazy call");cleaned(cancelled);
            std::atomic<bool> fresh{false};std::ostringstream next;
            ExecutionContext fails(bad,policy,fresh,next,error);
            try {fails.execute();throw std::runtime_error("missing runtime error");}catch(const RuntimeError& e) {require(e.code=="E205","wrong failure");}
            cleaned(fails);
            ExecutionContext succeeds(program,policy,fresh,next,error);succeeds.execute();
            require(next.str()=="ready\n42\n" && old && !fresh,"requests share mutable state or cancellation");cleaned(succeeds);
        }
    }
    static void lazy() {
        ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;
        const auto program=parse("(zno) broken:=(zzz)(1/0);(zno) good:=(zzz)(40+2);",p,cancel);
        ExecutionContext c(program,p,cancel,out,err);c.initialize();c.block(c.program.root,[] {});c.drain();
        const auto broken_id=c.ast(c.program.root).children[0],good_id=c.ast(c.program.root).children[1];
        auto broken=c.globals.at(broken_id).raw,good=c.globals.at(good_id).raw;
        const auto first_site=c.ast(broken_id).children[0],second_site=c.ast(good_id).children[0];
        require(c.object(broken).state=="NEW" && c.object(good).state=="NEW","initial Lazy state");
        NodeId origin=no_node;std::string first;
        try {c.wake(broken,first_site,[](Value) {});require(c.object(broken).state=="RUNNING","running state");c.drain();throw std::runtime_error("missing Lazy error");}
        catch(RuntimeError& e) {c.unwind(&e);require(e.code=="E205" && e.notes.size()==1,"first wake note");origin=e.site;first=e.notes[0];}
        require(c.object(broken).state=="FAILED","ordinary error cached");
        try {c.wake(broken,second_site,[](Value) {});throw std::runtime_error("cached error missing");}
        catch(const RuntimeError& e) {require(e.site==origin && e.notes.size()==1 && e.notes[0]!=first,"cached origin and current wake note");}
        c.wake(good,second_site,[](Value) {});cancel=true;
        try {c.drain();throw std::runtime_error("missing Lazy cancellation");}catch(const Cancelled&) {c.unwind(nullptr);}
        require(c.object(good).state=="NEW" && !c.object(good).failure,"cancel must reset Lazy");
        cancel=false;c.wake(good,second_site,[&](Value v){require(c.object(v).integer==BigInt(42),"retry result");});c.drain();
        require(c.object(good).state=="READY","retry cached");c.cleanup();cleaned(c);
    }
    static void repeated_cycles() {
        ResourcePolicy p;p.limits["runtime_objects"]=13;p.limits["runtime_slots"]=60;p.limits["runtime_payload_bytes"]=512;
        std::atomic<bool> c{false};std::ostringstream out,err;
        const auto program=parse("(addnew) drop()->(Null){(zyes) n:=[];(addnew) read()->(Array){(return) n;}"
          "(zno) m:=data.map();data.set(m,\"cycle\",read);array.push(n,m);}"
          "(for) i (in) 0..<150 {drop();}io.print(\"ok\");",p,c);
        ExecutionContext request(program,p,c,out,err);request.execute();
        require(out.str()=="ok\n" && request.heap.state->peak.objects==13,"expected quota-triggered collection during live request");cleaned(request);
    }
    static void input() {
        ResourcePolicy p;std::atomic<bool> c{false};
        const auto program=parse("io.print(io.input(\"? \"));io.print(io.input(\"\"));io.print(io.input(\"\"));",p,c);
        for(std::uint64_t bound:{5,6,7}) {
            p.limits["io_payload_bytes"]=bound;std::istringstream in("\xf0\x9f\x98\x80\r\n\n");
            std::ostringstream out,err;ExecutionContext request(program,p,c,out,err,false,&in);
            try {request.execute();require(bound>=6 && out.str()=="? \xf0\x9f\x98\x80\n\nnull\n","UTF-8 input/EOF");}
            catch(const RuntimeError& e) {require(bound==5 && e.code=="E211" && std::string(e.what()).find("io_payload_bytes")!=std::string::npos && out.str()=="? ","input boundary");}
            cleaned(request);
        }
        std::istringstream in("\xf0\x80");std::ostringstream out,err;ExecutionContext request(program,p,c,out,err,false,&in);
        try {request.execute();throw std::runtime_error("invalid stdin accepted");}catch(const RuntimeError& e) {require(e.code=="E401","invalid input classification");}
        cleaned(request);
    }
    static void resources() {
        ResourcePolicy p;std::atomic<bool> c{false};
        const auto program=parse("(@_@) 42;",p,c);
        const std::string expected=R"({"schema_version":1,"kind":"trace","code":null,"file":"N3 fixture.zzy","span":{"start":{"line":1,"column":7},"end":{"line":1,"column":9}},"message":"42","notes":[]})" "\n";
        for(int delta:{1,0,-1}) {
            const auto cap=static_cast<std::uint64_t>(static_cast<std::int64_t>(expected.size())+delta);
            ResourcePolicy policy;policy.limits["stderr_bytes"]=cap;std::ostringstream out,err;
            ExecutionContext request(program,policy,c,out,err,true);
            try {request.execute();require(delta>=0 && err.str()==expected,"trace byte boundary or rendering");}
            catch(const RuntimeError& e) {require(delta==-1 && e.code=="E211" && e.site==no_node && std::string(e.what()).find("stderr_bytes")!=std::string::npos && err.str().empty(),"stderr emitted partial record");}
            cleaned(request);
        }
        for(auto name:{"program_cache_entries","program_cache_bytes"}) {
            std::set<std::string> fingerprints;
            for(int n:{2,3,4}) {
                auto configured=PolicyParser("{\"policy_version\":1,\"limits\":{\""+std::string(name)+"\":"+std::to_string(n)+"}}").parse();
                require(configured.limits.at(name)==static_cast<std::uint64_t>(n),"cache configuration not preserved");
                fingerprints.insert(configured.fingerprint());
            }
            require(fingerprints.size()==3,"cache configuration missing from policy identity");
        }
    }
};
}
int main(int argc,char** argv) {
    const std::map<std::string,void(*)()> cases={{"recovery",zzy::ExecutionProbe::cancel_and_reuse},{"lazy",zzy::ExecutionProbe::lazy},
        {"cycles",zzy::ExecutionProbe::repeated_cycles},{"input",zzy::ExecutionProbe::input},{"resources",zzy::ExecutionProbe::resources}};
    try {if(argc!=2 || !cases.count(argv[1])) throw std::runtime_error("nonempty named selection required");cases.at(argv[1])();std::cout<<argv[1]<<": PASS\n";return 0;}
    catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
