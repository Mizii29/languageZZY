#include "zzy_native/execution.hpp"
#include "zzy_native/prepare.hpp"
#include <filesystem>
#include <future>
#include <iostream>
#include <sstream>

namespace zzy {
struct ExecutionProbe {
    static void require(bool yes,const char* message) {if(!yes) throw std::runtime_error(message);}
    struct Folder {
        std::filesystem::path path=std::filesystem::temp_directory_path()/
            (L"ZZY SQLite 中文 "+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64()));
        Folder() {require(std::filesystem::create_directory(path),"temporary directory exists");}
        ~Folder() {std::error_code ignored;std::filesystem::remove_all(path,ignored);}
        std::string name() const {return narrow((path/L"state.sqlite3").wstring());}
    };
    static Program parse(const std::string& text) {
        ResourcePolicy p;std::atomic<bool> cancel{false};FrontendMeter meter(p,cancel);AstBuilder ast(meter);
        auto source=std::make_shared<const Source>(L"SQLite fixed fixture.zzy",text);
        auto tokens=Lexer(source,meter).scan();const auto root=Parser(tokens,meter,ast).parse();
        ProgramData data;data.root=root;Resolver(ast.nodes,data,meter).resolve(root);data.nodes=std::move(ast.nodes);
        return Program(std::move(data));
    }
    static std::string transaction(const std::string& path,const std::string& body) {
        return "(addnew) work(){"+body+"}io.print(db.transaction(\""+path+"\",work));";
    }
    static void released(const ExecutionContext& c) {
        require(!c.database && c.heap.state->closed && c.heap.state->used==Charge{} && c.heap.state->nodes.empty() &&
            c.heap.state->roots.empty() && c.tasks.empty() && c.calls.empty() && !c.frame,"SQLite request state leaked");
    }
    static std::string run(const Program& program,ResourcePolicy policy={},const std::string& code="") {
        std::atomic<bool> cancel{false};std::ostringstream out,err;ExecutionContext c(program,policy,cancel,out,err);
        try {c.execute();require(code.empty(),"missing SQLite failure");}
        catch(const RuntimeError& error) {require(error.code==code,"wrong SQLite failure");}
        released(c);c.cleanup();released(c);require(err.str().empty(),"unexpected diagnostic output");return out.str();
    }
    static Program query(const std::string& path,const std::string& sql) {
        return parse(transaction(path,"(return) (^_^)(db.query(\""+sql+"\",[]));"));
    }
    static void initialize(const Folder& folder) {
        require(run(query(folder.name(),"CREATE TABLE t(v INTEGER UNIQUE)"))=="(^_^)([])\n","cannot initialize database");
    }
    static void lifecycle() {
        require(!GetModuleHandleW(L"winsqlite3.dll"),"SQLite eagerly loaded");
        require(run(parse("io.print(42);"))=="42\n" && !GetModuleHandleW(L"winsqlite3.dll"),"core loaded SQLite");
        Folder folder;initialize(folder);
        const auto count=query(folder.name(),"SELECT count(*) FROM t");
        require(run(query(folder.name(),"INSERT INTO t VALUES(1)"))=="(^_^)([])\n","commit result");
        require(run(count)=="(^_^)([[1]])\n","committed row missing");
        require(run(parse(transaction(folder.name(),"db.query(\"INSERT INTO t VALUES(2)\",[]);(return) (T_T)(\"declined\");")))==
            "(T_T)(declined)\n","failure Result changed");
        run(parse(transaction(folder.name(),"db.query(\"INSERT INTO t VALUES(3)\",[]);1/0;(return) (^_^)(0);")),{},"E205");
        run(parse(transaction(folder.name(),"db.query(\"INSERT INTO t VALUES(4)\",[]);(return) 0;")),{},"E201");
        run(parse(transaction(folder.name(),"db.query(\"INSERT INTO t VALUES(5)\",[]);db.query(\"INSERT INTO t VALUES(1)\",[]);(return) (^_^)(0);")),{},"E401");
        require(run(count)=="(^_^)([[1]])\n","failure did not roll back");
        ResourcePolicy short_output;short_output.limits["stdout_bytes"]=1;
        run(query(folder.name(),"INSERT INTO t VALUES(6)"),short_output,"E211");
        require(run(count)=="(^_^)([[2]])\n","post-commit failure undid committed data");
        require(!GetModuleHandleW(L"winsqlite3.dll"),"SQLite module lease leaked");
        const auto old=folder.path/L"state.sqlite3",moved=folder.path/L"renamed.sqlite3";
        std::filesystem::rename(old,moved);std::filesystem::rename(moved,old);
        ResourcePolicy policy;std::atomic<bool> cancel{false};auto heap=std::make_shared<HeapState>(policy,cancel);
        {sqlite_host::Connection c(heap,no_node);sqlite_host::require_ok(c.api.open_v2(folder.name().c_str(),&c.value,
            SQLITE_OPEN_READWRITE|SQLITE_OPEN_NOMUTEX,nullptr));
            std::cout<<"SQLite "<<c.api.libversion()<<" sourceid="<<c.api.sourceid()<<'\n';
            require(c.close() && c.close() && heap->used==Charge{},"repeated close or reservation leaked");}
        heap->close();
    }
    struct SignalBuffer : std::stringbuf {
        std::promise<void> ready;bool sent=false;
        int sync() override {if(!sent) {sent=true;ready.set_value();}return std::stringbuf::sync();}
    };
    static void cancellation() {
        Folder folder;initialize(folder);std::atomic<bool> cancel{false};ResourcePolicy p;SignalBuffer buffer;
        auto ready=buffer.ready.get_future();std::ostream out(&buffer);std::ostringstream err;
        const auto program=parse(transaction(folder.name(),"db.query(\"INSERT INTO t VALUES(1)\",[]);io.print(\"ready\");"
            "db.query(\"WITH RECURSIVE n(x) AS(VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n\",[]);(return) (^_^)(0);"));
        auto task=std::async(std::launch::async,[&] {
            ExecutionContext c(program,p,cancel,out,err);bool stopped=false;
            try {c.execute();}catch(const Cancelled&) {stopped=true;}
            released(c);return stopped;
        });
        if(ready.wait_for(std::chrono::seconds(5))!=std::future_status::ready) {cancel=true;(void)task.get();throw std::runtime_error("transaction did not reach cancellation probe");}
        std::this_thread::sleep_for(std::chrono::milliseconds(20));cancel=true;
        require(task.get(),"SQLite progress callback did not propagate cancellation");
        require(buffer.str()=="ready\n" && err.str().empty(),"cancelled transaction printed a result");
        require(run(query(folder.name(),"SELECT count(*) FROM t"))=="(^_^)([[0]])\n","cancel did not roll back or next request failed");
        run(query(folder.name(),"WITH RECURSIVE n(x) AS(VALUES(1) UNION ALL SELECT x+1 FROM n) SELECT sum(x) FROM n"),{},"E401");
        require(run(query(folder.name(),"INSERT INTO t VALUES(2)"))=="(^_^)([])\n","request after timeout failed");
    }
    static void concurrency() {
        Folder folder;initialize(folder);ResourcePolicy p;std::atomic<bool> cancel{false};
        auto heap=std::make_shared<HeapState>(p,cancel);
        {
            sqlite_host::Connection hold(heap,no_node);sqlite_host::require_ok(hold.api.open_v2(folder.name().c_str(),&hold.value,
                SQLITE_OPEN_READWRITE|SQLITE_OPEN_NOMUTEX,nullptr));hold.plain("BEGIN IMMEDIATE");
            auto denied=std::async(std::launch::async,[&]{run(query(folder.name(),"INSERT INTO t VALUES(1)"),{},"E401");});
            denied.get();require(hold.close() && heap->used==Charge{},"held transaction leaked");
        }
        heap->close();
        const auto program=query(folder.name(),"INSERT INTO t VALUES((SELECT count(*)+1 FROM t))");
        std::promise<void> start;auto gate=start.get_future().share();std::vector<std::future<std::string>> writers;
        for(int i=0;i<4;++i) writers.push_back(std::async(std::launch::async,[&]{gate.wait();return run(program);}));
        start.set_value();for(auto& writer:writers) require(writer.get()=="(^_^)([])\n","concurrent request failed");
        require(run(query(folder.name(),"SELECT v FROM t ORDER BY v"))=="(^_^)([[1], [2], [3], [4]])\n","concurrent transactions lost or shared data");
        require(!GetModuleHandleW(L"winsqlite3.dll"),"concurrent module handles leaked");
    }
    static void resources() {
        Folder folder;initialize(folder);ResourcePolicy p;std::atomic<bool> cancel{false};
        const auto program=parse(transaction(folder.name(),"db.query(\"INSERT INTO t VALUES(1)\",[]);(return) (^_^)(0);"));
        for(const auto key:{"runtime_objects","runtime_slots","runtime_payload_bytes","bad_alloc"}) {
            std::ostringstream out,err;ExecutionContext c(program,p,cancel,out,err);c.initialize();
            const auto site=c.program.root;
            auto sql=c.string("SELECT v FROM t",site),params=c.array({},site);
            c.database=std::make_shared<sqlite_host::Connection>(c.heap.state,site);
            sqlite_host::require_ok(c.database->api.open_v2(folder.name().c_str(),&c.database->value,
                SQLITE_OPEN_READWRITE|SQLITE_OPEN_NOMUTEX,nullptr));
            c.database->plain("BEGIN IMMEDIATE");c.database->plain("INSERT INTO t VALUES(1)");
            const auto used=c.heap.state->used;
            if(std::string(key)=="bad_alloc") c.heap.state->fail_allocation=true;
            else c.heap.state->policy.limits[key]=std::string(key)=="runtime_objects"?used.objects:
                std::string(key)=="runtime_slots"?used.slots:used.payload;
            bool failed=false;
            try {(void)c.database_query({sql,params},site);}catch(const std::bad_alloc&) {failed=true;}catch(const RuntimeError& e) {failed=e.code=="E211";}
            require(failed,"allocation failure was not injected");sql={};params={};c.cleanup();released(c);
            require(run(query(folder.name(),"SELECT count(*) FROM t"))=="(^_^)([[0]])\n","resource failure committed or connection survived");
        }
        const auto live=std::make_shared<HeapState>(p,cancel);live->policy.limits["runtime_slots"]=0;
        bool denied=false;try {sqlite_host::Connection c(live,no_node);}catch(const RuntimeError& e) {denied=e.code=="E211";}
        require(denied && live->used==Charge{} && !GetModuleHandleW(L"winsqlite3.dll"),"connection reservation was not atomic");live->close();
    }
};
}
int main(int argc,char** argv) {
    const std::map<std::string,void(*)()> cases={{"lifecycle",zzy::ExecutionProbe::lifecycle},{"cancellation",zzy::ExecutionProbe::cancellation},
        {"concurrency",zzy::ExecutionProbe::concurrency},{"resources",zzy::ExecutionProbe::resources}};
    try {if(argc!=2 || !cases.count(argv[1])) throw std::runtime_error("nonempty named selection required");cases.at(argv[1])();std::cout<<argv[1]<<": PASS\n";return 0;}
    catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
