#include "zzy_native/execution.hpp"
#include "zzy_native/prepare.hpp"
#include <chrono>
#include <filesystem>
#include <fstream>
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
    struct Folder {
        std::filesystem::path path=std::filesystem::temp_directory_path()/
            (L"ZZY N4 \u6587\u4ef6 "+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64()));
        Folder() {require(std::filesystem::create_directory(path),"cannot create probe folder");}
        ~Folder() {std::error_code ignored;std::filesystem::remove_all(path,ignored);}
        std::filesystem::path file(const wchar_t* name) const {return path/name;}
        std::size_t temporary_files() const {
            std::size_t count=0;
            for(const auto& entry:std::filesystem::directory_iterator(path))
                if(entry.path().filename().wstring().compare(0,5,L".zzy-")==0) ++count;
            return count;
        }
    };
    static std::string bytes(const std::filesystem::path& path) {
        std::ifstream stream(path,std::ios::binary);require(bool(stream),"cannot read probe file");
        return {std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()};
    }
    static void seed(const std::filesystem::path& path,std::string_view raw) {
        std::ofstream stream(path,std::ios::binary);stream.write(raw.data(),static_cast<std::streamsize>(raw.size()));
        stream.close();require(bool(stream),"cannot seed probe file");
    }
    static void files() {
        Folder folder;ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;
        const auto program=parse("io.read_text(\"a\");",p,cancel);
        ExecutionContext c(program,p,cancel,out,err);c.initialize();const auto site=c.program.root;
        const auto target=folder.file(L"\u6587\u4ef6 \U0001f600.txt"),source=folder.file(L"source.txt");
        const auto path=c.string(narrow(target.wstring()),site),source_path=c.string(narrow(source.wstring()),site);
        auto read=[&] {return c.file_library("io.read_text",{path},site);};
        auto get=[&](const Value& value) {require(c.object(value).flag,"unexpected failure Result");return c.heap.pin(c.object(value).edges[0]);};
        require(!c.object(read()).flag,"missing path accepted");
        seed(target,"\xc0\xaf");require(!c.object(read()).flag,"invalid encoding accepted");
        const std::u32string points=U"\ufeff\u4e2d\U0001f600\r\n\t";
        const auto payload=c.string(points,site);
        require(get(c.file_library("io.write_text",{path,payload},site)).same(c.null_),"write_text did not return Null");
        require(bytes(target)=="\xef\xbb\xbf\xe4\xb8\xad\xf0\x9f\x98\x80\r\n\t","UTF-8 bytes, BOM or line ending");
        require(c.object(get(read())).characters==points,"file roundtrip changed text");
        std::string split(65535,'a');split+="\xf0\x9f\x98\x80";
        seed(target,split);
        require(c.object(get(read())).characters.back()==U'\U0001f600',"UTF-8 across the read chunk boundary");
        seed(source,"new");
        require(get(c.file_library("io.replace_file",{source_path,path},site)).same(c.null_),"replace_file did not return Null");
        require(bytes(target)=="new" && !std::filesystem::exists(source),"replacement did not move the source");
        const auto atom=c.string(U"\u4e2d",site);
        for(std::uint64_t cap:{2,3,4}) {
            c.heap.state->policy.limits["io_payload_bytes"]=cap;
            seed(target,"old");
            try {
                (void)get(c.file_library("io.write_atomic",{path,atom},site));
                require(cap>=3 && bytes(target)=="\xe4\xb8\xad","atomic byte boundary");
            } catch(const RuntimeError& e) {require(cap==2 && e.code=="E211" && bytes(target)=="old","wrong write boundary");}
            seed(target,"\xe4\xb8\xad");
            try {require(c.object(get(read())).characters==U"\u4e2d" && cap>=3,"read byte boundary");}
            catch(const RuntimeError& e) {require(cap==2 && e.code=="E211","wrong read boundary");}
            require(!folder.temporary_files(),"temporary file leaked");
        }
        c.heap.state->policy.limits["io_payload_bytes"]=p.limits.at("io_payload_bytes");
        for(const auto key:{"runtime_slots","runtime_payload_bytes"}) {
            c.heap.collect();const auto before=c.heap.state->used;
            c.heap.state->policy.limits[key]=std::string(key)=="runtime_slots"?before.slots:before.payload;
            seed(target,"old");
            bool failed=false;
            try {(void)c.file_library("io.write_atomic",{path,atom},site);}
            catch(const RuntimeError& e) {failed=e.code=="E211";}
            if(!failed || bytes(target)!="old" || folder.temporary_files())
                throw std::runtime_error(std::string("allocation failure crossed file commit: ")+key+" failed="+std::to_string(failed));
            c.heap.state->policy.limits[key]=ResourcePolicy{}.limits.at(key);
            c.heap.collect();require(c.heap.state->used==before,"file allocation failure leaked quota");
        }
        seed(target,"old");c.heap.state->fail_allocation=true;
        bool allocation_failed=false;
        try {(void)c.file_library("io.write_atomic",{path,atom},site);}
        catch(const std::bad_alloc&) {allocation_failed=true;}
        require(allocation_failed && bytes(target)=="old" && !folder.temporary_files(),"bad_alloc crossed file commit");
        c.cleanup();released(c);
    }
    static void file_commit() {
        using file_detail::Step;
        struct BrokenWriter {
            int failure;unsigned writes=0;
            bool write(HANDLE file,const char* data,DWORD count,DWORD& written) {
                if(failure==0 && writes++==1) {SetLastError(ERROR_WRITE_FAULT);return false;}
                return file_detail::SystemWriter{}.write(file,data,count,written);
            }
            bool close(FileHandle& file) {
                if(failure==1) {SetLastError(ERROR_INVALID_HANDLE);return false;}
                return file_detail::SystemWriter{}.close(file);
            }
        };
        Folder folder;const auto target=folder.file(L"state.json");
        const auto path=extended_path(target.wstring());
        seed(target,"old");
        const std::string data(65537,'x');
        for(int phase=0;phase<2;++phase) {
            try {file_detail::write(path,data,true,[](Step){},BrokenWriter{phase});throw std::logic_error("missing injected failure");}
            catch(const file_detail::Failure& error) {
                require(std::string(error.what()).find(phase==0?"cannot write":"cannot close")!=std::string::npos,"wrong injected fault");
            }
            require(bytes(target)=="old" && !folder.temporary_files(),"fault corrupted data or leaked temp");
        }
        {
            FileHandle lock(CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr));
            require(bool(lock),"cannot acquire real Windows sharing lock");
            try {file_detail::write(path,data,true,[](Step){});throw std::logic_error("locked replacement succeeded");}
            catch(const file_detail::Failure& error) {require(std::string(error.what()).find("cannot replace")!=std::string::npos,"did not reach Windows replacement");}
            require(bytes(target)=="old" && !folder.temporary_files(),"locked replacement leaked or corrupted");
            require(lock.close() && lock.close(),"repeated close did not succeed");
        }
        ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;
        const auto program=parse("io.read_text(\"a\");",p,cancel);
        for(const auto boundary:{Step::write,Step::close,Step::commit}) {
            ExecutionContext c(program,p,cancel,out,err);c.initialize();
            try {
                file_detail::write(path,data,true,[&](Step step){if(step==boundary){cancel=true;c.point();}});
                throw std::logic_error("cancellation was not propagated");
            } catch(const Cancelled&) {require(bytes(target)=="old" && !folder.temporary_files(),"cancel leaked or committed");}
            c.cleanup();released(c);cancel=false;
        }
        // Interleave two genuine writers before either commits. The inner
        // writer commits first while the outer temp is still exclusively open.
        file_detail::write(path,"outer",true,[&](Step step){
            if(step==Step::close) {
                require(folder.temporary_files()==1 && bytes(target)=="old","first write published too early");
                file_detail::write(path,"inner",true,[&](Step second){
                    if(second==Step::close) require(folder.temporary_files()==2,"temporary names collided");
                });
                require(bytes(target)=="inner" && folder.temporary_files()==1,"first commit was not visible");
            }
        });
        require(bytes(target)=="outer" && !folder.temporary_files(),"last successful replacement did not win");
        ExecutionContext next(program,p,cancel,out,err);next.initialize();
        const auto result=next.file_library("io.write_atomic",{next.string(narrow(target.wstring()),next.program.root),
            next.string("next",next.program.root)},next.program.root);
        require(next.object(result).flag && bytes(target)=="next","next request did not recover");
        next.cleanup();released(next);
    }
    static void json() {
        ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;
        const auto program=parse(R"(io.print(data.stringify([1,1.0,(true),(null)]));)",p,cancel);
        ExecutionContext c(program,p,cancel,out,err);c.initialize();
        const auto site=c.program.root;
        auto decode=[&](const std::string& text){return c.json_library("data.parse",c.string(text,site),site);};
        auto get=[&](const Value& result){require(c.object(result).flag,"unexpected JSON failure");return c.heap.pin(c.object(result).edges[0]);};
        const auto items=get(decode("[0,-0,1.0,-1e-9999,5e-324,9007199254740993,true,null]"));
        const auto& a=c.object(items);
        require(c.heap.state->get(a.edges[1]).kind=="Int" && c.heap.state->get(a.edges[2]).kind=="Float","numeric tag changed");
        require(std::signbit(c.heap.state->get(a.edges[3]).real) && c.heap.state->get(a.edges[3]).real==0.0,"signed underflow lost");
        require(c.heap.state->get(a.edges[4]).real==std::numeric_limits<double>::denorm_min(),"subnormal rounded incorrectly");
        const auto encoded=c.json_library("data.stringify",items,site);
        require(c.object(get(encoded)).characters==U"[0,0,1.0,-0.0,5e-324,9007199254740993,true,null]","strict numeric layout");
        require(!c.object(decode(R"({"x":"\u0000","x":null})")).flag,"duplicate key accepted");
        require(!c.object(decode("[-]")).flag && !c.object(decode("[0,]")).flag,"invalid JSON accepted");
        const auto input=c.string("[[0]]",site);
        for(std::uint64_t cap:{1,2,3}) {
            c.heap.state->policy.limits["value_depth"]=cap;
            c.heap.collect();const auto before=c.heap.state->used;
            try {require(c.object(c.json_library("data.parse",input,site)).flag && cap>=2,"JSON parse depth");}
            catch(const RuntimeError& e) {require(cap==1 && e.code=="E211","wrong depth diagnostic");}
            c.heap.collect();require(c.heap.state->used==before,"JSON partial data or buffer leaked");
        }
        const auto long_input=c.string(std::u32string(3000000,U' ')+U"0",site);
        c.heap.collect();const auto before=c.heap.state->used;
        std::atomic<bool> started{false},ready{false};
        std::thread stop([&]{ready=true;while(!started) std::this_thread::yield();cancel=true;});
        while(!ready) std::this_thread::yield();
        bool cancelled=false;
        // Repeat if an optimized call finishes before the other thread gets
        // scheduled. Cancellation must come from that real thread, not a timer
        // assumption about how long a single operation takes.
        try {started=true;for(;;) (void)c.json_library("data.parse",long_input,site);}
        catch(const Cancelled&) {cancelled=true;}
        catch(...) {stop.join();throw;}
        stop.join();cancel=false;c.heap.collect();
        require(cancelled && c.heap.state->used==before,"JSON cancellation leaked");
        const auto long_text=c.string(std::u32string(3000000,U'x'),site);
        c.heap.collect();const auto encoding_before=c.heap.state->used;
        started=false;ready=false;cancelled=false;
        std::thread stop_encoding([&]{ready=true;while(!started) std::this_thread::yield();cancel=true;});
        while(!ready) std::this_thread::yield();
        try {started=true;for(;;) (void)c.json_library("data.stringify",long_text,site);}
        catch(const Cancelled&) {cancelled=true;}
        catch(...) {stop_encoding.join();throw;}
        stop_encoding.join();cancel=false;c.heap.collect();
        require(cancelled && c.heap.state->used==encoding_before,"JSON encoding cancellation leaked");
        c.cleanup();released(c);
        ExecutionContext next(program,p,cancel,out,err);next.execute();released(next);
        require(out.str()=="(^_^)([1,1.0,true,null])\n" && err.str().empty(),"JSON next request did not recover");
    }
    static void sketch_geometry() {
        ResourcePolicy p;std::atomic<bool> cancel{false};std::ostringstream out,err;
        const auto program=parse("io.print(sketch.heading(sketch.pen(sketch.canvas(8,8,\"next\"),\"p\")));",p,cancel);
        ExecutionContext c(program,p,cancel,out,err);c.initialize();
        const auto site=c.program.root;
        auto intv=[&](int v){return c.integer(BigInt(v),site);};
        auto invoke=[&](const std::string& op,std::vector<Value> args){return c.sketch_library("sketch."+op,args,site);};
        const auto canvas=invoke("canvas",{intv(40),intv(40),c.string("probe",site)});
        const auto pen=invoke("pen",{canvas,c.string("p",site)});
        auto& d=*c.heap.native<sketch::CanvasRef>(canvas).doc;
        auto& state=d.pens.at("p").state;
        const auto step=intv(10);c.heap.collect();
        const auto initial=c.heap.state->used;
        std::exception_ptr thread_error;
        std::thread foreign([&] {
            try {(void)invoke("heading",{pen});}
            catch(...) {thread_error=std::current_exception();}
        });
        foreign.join();
        require(thread_error!=nullptr,"foreign thread read the sketch document");
        try {std::rethrow_exception(thread_error);}
        catch(const RuntimeError& e) {require(e.code=="E203","foreign thread diagnostic");}
        require(state.position==sketch::XY{} && d.objects.empty() && c.heap.state->used==initial,
                "foreign thread changed the document or resources");
        c.heap.state->policy.limits["runtime_objects"]=initial.objects;
        try {invoke("forward",{pen,step});throw std::runtime_error("geometry object limit accepted");}
        catch(const RuntimeError& e) {require(e.code=="E211","geometry resource diagnostic");}
        require(d.objects.empty() && state.position==sketch::XY{} && d.undo.empty() && d.next_id==1,"failed geometry changed the document");
        require(c.heap.state->used==initial,"failed geometry leaked a reservation");
        c.heap.state->policy.limits["runtime_objects"]=p.limits.at("runtime_objects");
        invoke("forward",{pen,step});
        require(d.objects.size()==1 && state.position==sketch::XY{10.,0.} && d.next_id==2,"next drawing command did not recover");
        const auto drawing=c.heap.state->used;
        cancel=true;
        try {invoke("undo",{canvas});throw std::runtime_error("cancelled undo ran");}
        catch(const Cancelled&) {}
        cancel=false;
        require(d.objects.size()==1 && d.undo.size()==1 && d.redo.empty() && c.heap.state->used==drawing,"cancelled undo changed state or kept quota");
        c.object(canvas).frozen=true;
        try {invoke("forward",{pen,step});throw std::runtime_error("frozen canvas alias changed");}
        catch(const RuntimeError& e) {require(e.code=="E203","frozen canvas alias diagnostic");}
        c.object(canvas).frozen=false;
        invoke("undo",{canvas});require(d.objects.empty() && state.position==sketch::XY{} && d.next_id==2,"undo failed or rewound ID");
        invoke("clear_history",{canvas});c.heap.collect();
        require(d.undo.empty() && d.redo.empty() && c.heap.state->used==initial,"clear_history retained geometry or delta charge");
        c.cleanup();released(c);
        ExecutionContext next(program,p,cancel,out,err);next.execute();released(next);
        require(out.str()=="0.0\n" && err.str().empty(),"next sketch request did not recover");
    }
    static void sketch_replay() {
        ResourcePolicy policy;
        std::atomic<bool> cancel{false};
        std::ostringstream output,errors;
        const auto code=parse("1;",policy,cancel);
        ExecutionContext c(code,policy,cancel,output,errors);
        c.initialize();
        {
            SketchHost host{c,c.program.root};
            const auto call=[&](const std::string& name,const std::vector<Value>& args) {return host.invoke("sketch."+name,args);};
            const auto canv=call("canvas",{host.integer(200),host.integer(100),host.string("replay")});
            const auto pen=call("pen",{canv,host.string("p")});
            auto& doc=*c.heap.native<sketch::CanvasRef>(canv,c.program.root).doc;
            call("forward",{pen,host.integer(12)});
            call("begin_group",{canv,host.string("corner")});
            call("left",{pen,host.integer(90)});
            call("forward",{pen,host.integer(15)});
            call("end_group",{canv});
            call("clear",{canv});
            call("undo",{canv});
            const auto used=c.heap.state->used;
            {
                SketchReplay replay(host,doc);
                require(replay.position()==0&&replay.scene().objects.empty(),"bad start/redo leaked into replay");
                replay.seek(1);
                require(replay.scene().objects.size()==1&&replay.scene().pens.at("p").state.position==sketch::XY{12,0},"bad first replay frame");
                replay.seek(replay.size());
                require(replay.position()==replay.size()&&replay.scene().objects.size()>=2,"bad last replay frame");
                replay.seek(0);
                require(replay.scene().objects.empty()&&doc.objects.size()==2&&doc.redo.size()==1,"replay edited live document");
                cancel=true;
                try {replay.seek(1);throw std::logic_error("replay ignored cancellation");}catch(const Cancelled&) {}
                cancel=false;
            }
            require(c.heap.state->used==used,"replay leaked quota");
        }
        c.cleanup();
        released(c);
    }
};
}
int main(int argc,char** argv) {
    const std::map<std::string,void(*)()> cases={{"callbacks",zzy::ExecutionProbe::callbacks},{"identity",zzy::ExecutionProbe::identity},
        {"budgets",zzy::ExecutionProbe::budgets},{"cancellation",zzy::ExecutionProbe::cancellation},{"text",zzy::ExecutionProbe::text_boundaries},
        {"files",zzy::ExecutionProbe::files},{"file-commit",zzy::ExecutionProbe::file_commit},{"json",zzy::ExecutionProbe::json},
        {"sketch-geometry",zzy::ExecutionProbe::sketch_geometry},{"sketch-replay",zzy::ExecutionProbe::sketch_replay}};
    try {if(argc!=2 || !cases.count(argv[1])) throw std::runtime_error("nonempty named selection required");cases.at(argv[1])();std::cout<<argv[1]<<": PASS\n";return 0;}
    catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
