#include "zzy_native/prepare.hpp"
#include "zzy_native/program_dump.hpp"
#include <functional>
#include <iostream>
#include <sstream>
#include <type_traits>

namespace {
void require(bool value,const char* message) {if(!value) throw std::runtime_error(message);}
template<class F> void error(const char* code,F action,const char* key="") {
    try {action();}catch(const zzy::FrontendError& e) {
        require(e.code==code,"wrong diagnostic code");require(std::string(e.what()).find(key)!=std::string::npos,"wrong diagnostic key");return;
    }
    throw std::runtime_error("expected frontend diagnostic");
}
zzy::Program parse(const std::string& text,zzy::FrontendMeter& meter) {
    zzy::AstBuilder ast(meter);const auto source=std::make_shared<const zzy::Source>(L"program-test.zzy",text);
    const auto tokens=zzy::Lexer(source,meter).scan();const auto root=zzy::Parser(tokens,meter,ast).parse();
    zzy::ProgramData data;data.root=root;zzy::Resolver(ast.nodes,data,meter).resolve(root);data.nodes=std::move(ast.nodes);
    return zzy::Program(std::move(data));
}
struct State {zzy::ResourcePolicy policy;std::atomic<bool> cancel{false};zzy::FrontendMeter meter{policy,cancel};};
zzy::NodeId named(const zzy::ProgramData& p,const std::string& kind,const std::string& text) {
    for(std::size_t i=0;i<p.nodes.size();++i) if(p.nodes[i].kind==kind && zzy::spelling(p.nodes[i].token)==text) return i;
    throw std::runtime_error("missing AST node");
}
void ast() {
    State s;const auto program=parse("(zno) x := 1+2*3;",s.meter);const auto& p=program.data();
    require(p.nodes.size()==7 && p.root==6 && p.nodes[6].depth==4,"fixed AST size/root/depth");
    require(p.nodes[4].kind=="add" && p.nodes[4].children==std::vector<zzy::NodeId>{0,3},"fixed precedence");
    require(p.nodes[3].kind=="binary" && p.nodes[3].children==std::vector<zzy::NodeId>{1,2},"fixed multiplication");
    const auto span=zzy::token_span(p.nodes[4].token);
    require(span.start.line==1 && span.start.column==13 && span.end.column==14,"fixed operator location");
    static_assert(std::is_const_v<std::remove_reference_t<decltype(program.data())>>,"const published data");
    static_assert(std::is_const_v<std::remove_reference_t<decltype(program.data().nodes[0])>>,"const AST");
    auto copy=program;require(&copy.data()==&program.data(),"copy shares readonly Program");
}
void captures() {
    State s;const auto program=parse(
        "(zyes) g:=0; (addnew) outer(p:(Int))->(Function){(zyes) x:=p;"
        "(addnew) middle()->(Function){(return) (addnew)()=>x+g+outer;} (return) middle;}",s.meter);
    const auto& p=program.data();const auto outer=named(p,"function","outer"),middle=named(p,"function","middle");
    const auto lambda=named(p,"lambda","(addnew)"),x=named(p,"binding","x"),g=named(p,"binding","g");
    const auto& a=p.functions.at(outer);const auto& b=p.functions.at(middle);const auto& c=p.functions.at(lambda);
    require(a.locals.size()==3 && a.captures.size()==1 && a.captures[0].symbol==g,"outer layout");
    require(b.captures.size()==3 && c.captures.size()==3,"transitive capture count");
    require(b.captures[0].source.kind=="local" && b.captures[0].source.key==1 && b.captures[0].symbol==x,"local capture source");
    require(b.captures[1].source.kind=="capture" && b.captures[1].source.key==0,"transitive global capture");
    require(b.captures[2].source.kind=="self" && b.captures[2].symbol==outer,"captured function self");
    for(std::size_t i=0;i<3;++i) require(c.captures[i].source.kind=="capture" && c.captures[i].source.key==i,"lambda capture order");
    require(p.symbols.at(x).cell && p.symbols.at(g).cell && !p.symbols.at(outer).cell,"mutable Cell markers only");
    require(a.blocks.begin()->second==std::vector<std::size_t>{0,1,2},"declaration-order block clearing slots");
}
void scopes() {
    State s;
    error("E302",[&]{parse("(zno) x:=1;{(zno) x:=x;}",s.meter);});
    error("E302",[&]{parse("{(zno) x:=1;} x;",s.meter);});
    error("E301",[&]{parse("(addnew) f(x,x){}",s.meter);});
    error("E304",[&]{parse("(while)(true){(addnew) f(){(break);}}",s.meter);});
    error("E304",[&]{parse("(addnew) f()->(Result){(zno) x:=(zzz)((^_^)(1)?);}",s.meter);});
    error("E302",[&]{parse("(addnew) f(f:f){}",s.meter);});
    error("E103",[&]{parse("{(shape) T {}}",s.meter);});
    error("E103",[&]{parse("{(use)\"m.zzy\"(as)m;}",s.meter);});
    error("E103",[&]{parse("{(spec)\"x\"{}}",s.meter);});
    const auto valid=parse("(zno) x:(Bool):=1;x<-\"runtime only\";len(1,2);(zif?:)3{1+\"a\";}(shape) S{value:(Int):=1/0;}",s.meter);
    require(!valid.data().nodes.empty(),"check must not typecheck or execute expressions");
}
void purity() {
    State s;
    parse("[1]?>{(keep):math.abs(@)>0;(order):@;(take):len([1]);(yield):str(@);};",s.meter);
    parse("{(zno) f:=len; f(1);}",s.meter);
    error("E307",[&]{parse("{(zno) math:=1;[1]?>{(yield):math.abs(@);};}",s.meter);});
    error("E307",[&]{parse("(zno) f:=len;[1]?>{(yield):f(@);};",s.meter);});
    error("E307",[&]{parse("[1]?>{(take):@;(yield):@;};",s.meter);});
    error("E307",[&]{parse("[1]?>{(yield):(zzz)(@);};",s.meter);});
    error("E307",[&]{parse("1~>@(@);",s.meter);});
    error("E103",[&]{parse("1~>len(1);",s.meter);});
    error("E307",[&]{parse("1~>len(@,(@));",s.meter);});
}
void literals() {
    State s;const auto program=parse("18446744073709551616;0.125;1.25::m;250::cm;0.0::ms;(machine) M{a--\"go\"-->b;}",s.meter);
    const auto& p=program.data();require(p.numbers.begin()->second.words==std::vector<std::uint32_t>{0,0,1},"no Int64 truncation");
    require(p.quantities.size()==3 && p.machines.size()==1,"static quantity/machine count");
    auto it=p.quantities.begin();require(zzy::LiteralNat(it->second.numerator).decimal()=="5" && zzy::LiteralNat(it->second.denominator).decimal()=="4","exact 1.25 m");
    ++it;require(zzy::LiteralNat(it->second.numerator).decimal()=="5" && zzy::LiteralNat(it->second.denominator).decimal()=="2","scaled 250 cm");
    ++it;require(it->second.numerator.empty() && it->second.denominator==std::vector<std::uint32_t>{1},"zero quantity canonicalization");
    error("E305",[&]{parse("(machine) M{a--\"x\"-->b;a--\"x\"-->c;}",s.meter);});
    error("E306",[&]{parse("1::unknown;",s.meter);});
    error("E208",[&]{parse(std::string(310,'9')+".0;",s.meter);});
    parse("(?_?)0{9007199254740993=>{}9007199254740992.0=>{}(true)=>{}1=>{}}",s.meter);
    error("E103",[&]{parse("(?_?)0{1=>{}1.0=>{}}",s.meter);});
    error("E103",[&]{parse("(?_?)0{-0=>{}0.0=>{}}",s.meter);});
}
void budgets() {
    State s;s.policy.limits["ast_nodes_total"]=3;
    require(parse("1;",s.meter).data().nodes.size()==3,"exact AST capacity");
    error("E211",[&]{parse("1;2;",s.meter);},"ast_nodes_total");
    s.policy.limits["ast_nodes_total"]=500000;s.policy.limits["syntax_depth"]=3;
    parse("(zno)x:=1+2;",s.meter);
    error("E211",[&]{parse("(zno)x:=1+2+3;",s.meter);},"syntax_depth");
    s.policy.limits["syntax_depth"]=64;s.policy.limits["integer_bits"]=4;
    parse("15;0;1.0;",s.meter);error("E211",[&]{parse("16;",s.meter);},"integer_bits");
    parse("0.0::one;",s.meter);error("E211",[&]{parse("0.00000::one;",s.meter);},"integer_bits");
    require(s.meter.source_total==0 && s.meter.module_count==0,"in-memory parsing has no source fees");
}
struct Files {
    std::wstring directory;std::vector<std::wstring> paths;
    Files() {
        wchar_t temp[MAX_PATH+1]{};require(GetTempPathW(MAX_PATH,temp)!=0,"temp path");
        directory=std::wstring(temp)+L"ZZY N2 "+std::to_wstring(GetCurrentProcessId())+L" "+std::to_wstring(GetTickCount64());
        require(CreateDirectoryW(directory.c_str(),nullptr)!=0,"create test folder");
    }
    void write(const wchar_t* file,const std::string& text) {
        const auto path=directory+L"\\"+file;
        zzy::FileHandle h(CreateFileW(path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr));
        require(static_cast<bool>(h),"open fixture");DWORD size=0;
        require(WriteFile(h.get(),text.data(),static_cast<DWORD>(text.size()),&size,nullptr)!=0 && size==text.size(),"write fixture");
        if(std::find(paths.begin(),paths.end(),path)==paths.end()) paths.push_back(path);
    }
    std::wstring path(const wchar_t* file) const {return directory+L"\\"+file;}
    ~Files() {for(const auto& p:paths) DeleteFileW(p.c_str());RemoveDirectoryW(directory.c_str());}
};
void graph() {
    Files f;f.write(L"main.zzy","(use)\"left.zzy\"(as)l;(use)\"right.zzy\"(as)r;l.fn; r.fn;");
    f.write(L"left.zzy","(use)\"leaf.zzy\"(as)m;(addnew) fn(){(return)m.x;}");
    f.write(L"right.zzy","(use)\"LEAF.zzy\"(as)m;(shape) T{v:=m.noSuchField;} ");
    f.write(L"leaf.zzy","(zyes) hidden:=io.input();(addnew) x(){(return)hidden;}(machine) M{a--\"x\"-->a;}");
    State s;const auto program=zzy::prepare(f.path(L"main.zzy"),s.meter);const auto& p=program.data();
    require(p.graph.size()==4 && p.imports.size()==4,"complete diamond graph");
    require(s.meter.source_total==0 && s.meter.module_count==0,"source preparation charges returned");
    zzy::NodeId first=zzy::no_node;
    for(const auto& m:p.graph) if(m.source->path.find(L"leaf.zzy")!=std::wstring::npos) {
        require(m.exports.size()==2 && m.exports.count("x") && m.exports.count("M") && !m.exports.count("hidden"),"static exports only");first=m.root;
    }
    require(first!=zzy::no_node,"leaf snapshot present");unsigned aliases=0;
    for(const auto& edge:p.imports) if(edge.second==first) ++aliases;
    require(aliases==2,"canonical alias shares module identity");
    const auto original=p.graph[0].source->raw;f.write(L"leaf.zzy","(zno) changed:=1;");
    require(p.graph[0].source->raw==original,"source snapshot not live file");
    const auto updated=zzy::prepare(f.path(L"main.zzy"),s.meter);
    require(updated.data().graph[0].source->raw!=original,"no implicit process cache");
    f.write(L"leaf.zzy","(use)\"main.zzy\"(as)m;");
    error("E303",[&]{zzy::prepare(f.path(L"main.zzy"),s.meter);});
    require(s.meter.source_total==0 && s.meter.module_count==0,"error graph fees returned");
    f.write(L"leaf.zzy","(zno) x:=missing;");error("E302",[&]{zzy::prepare(f.path(L"main.zzy"),s.meter);});
    f.write(L"main.zzy","(use)\"absent.zzy\"(as)m;missing;");
    error("E302",[&]{zzy::prepare(f.path(L"main.zzy"),s.meter);});
    f.write(L"main.zzy","(use)\"leaf.zzy\"(as)m;");s.policy.limits["module_count"]=1;
    error("E303",[&]{zzy::prepare(f.path(L"main.zzy"),s.meter);},"module_count");
}
struct Observation {const zzy::Program* program;std::string output;std::exception_ptr failure;};
DWORD WINAPI observe(void* raw) {
    auto& job=*static_cast<Observation*>(raw);
    try {State request;std::ostringstream out;zzy::dump_program(*job.program,request.meter,out);job.output=out.str();}
    catch(...) {job.failure=std::current_exception();}return 0;
}
void readonly() {
    State s;const auto program=parse("(zno)x:=1;(addnew)f(){(return)x;}",s.meter);
    Observation a{&program,{},{}},b{&program,{},{}};
    zzy::FileHandle first(CreateThread(nullptr,0,observe,&a,0,nullptr)),second(CreateThread(nullptr,0,observe,&b,0,nullptr));
    require(static_cast<bool>(first) && static_cast<bool>(second),"observation threads started");
    require(WaitForSingleObject(first.get(),10000)==WAIT_OBJECT_0 && WaitForSingleObject(second.get(),10000)==WAIT_OBJECT_0,"observation threads joined");
    if(a.failure) std::rethrow_exception(a.failure);
    if(b.failure) std::rethrow_exception(b.failure);
    require(a.output==b.output && !a.output.empty(),"concurrent readonly snapshot observation is deterministic");
    // This is observation only, not N3 execution-context isolation evidence.
}
void metadata() {
    require(std::size(zzy::static_hosts)==103,"all frozen host descriptors");std::size_t pure=0;
    for(const auto& host:zzy::static_hosts) {require(!host.name.empty() && !host.description.empty(),"complete static descriptor");if(host.pure) ++pure;}
    require(pure==7 && zzy::static_pure("unit.make") && !zzy::static_pure("io.print"),"fixed pure host metadata");
}
void cancellation() {
    State s;s.cancel=true;
    try {parse("1;",s.meter);throw std::runtime_error("cancel not observed");}catch(const zzy::Cancelled&) {}
    s.cancel=false;require(parse("1;",s.meter).data().nodes.size()==3,"next preparation recovers");
    Files f;f.write(L"main.zzy","1;");s.cancel=true;
    try {zzy::prepare(f.path(L"main.zzy"),s.meter);throw std::runtime_error("prepare cancel not observed");}catch(const zzy::Cancelled&) {}
    require(s.meter.source_total==0 && s.meter.module_count==0,"cancel fees returned");
}
}
int main(int argc,char** argv) {
    zzy::configure_streams();
    const std::pair<const char*,std::function<void()>> cases[]={{"ast",ast},{"captures",captures},{"scopes",scopes},{"purity",purity},
        {"literals",literals},{"budgets",budgets},{"graph",graph},{"readonly",readonly},{"metadata",metadata},{"cancellation",cancellation}};
    unsigned count=0;
    try {
        if(argc>2) throw std::runtime_error("one selector only");
        for(const auto& test:cases) if(argc==1 || std::string(argv[1])==test.first) {test.second();++count;std::cout<<test.first<<": passed\n";}
        require(count>0,"no Program cases selected");std::cout<<"program: "<<count<<" cases passed\n";return 0;
    }catch(const std::exception& e) {std::cerr<<"Program test failed: "<<e.what()<<'\n';return 1;}
}
