#pragma once
#include "execution.hpp"
#include "prepare.hpp"
#include <filesystem>
#include <fstream>
#include <chrono>
#include <iostream>
#include <charconv>

namespace zzy::specs {
namespace fs=std::filesystem;
constexpr DWORD worker_pass=41,worker_fail=42;
inline void fail(const std::string& message) {throw FrontendError("E401",message);}
struct Handle {
    HANDLE value=nullptr;
    explicit Handle(HANDLE h=nullptr):value(h) {}
    Handle(const Handle&)=delete;
    Handle& operator=(const Handle&)=delete;
    ~Handle(){if(value&&value!=INVALID_HANDLE_VALUE)CloseHandle(value);}
};
struct Directory {
    fs::path path;
    Directory() {
        wchar_t root[32768]{};
        const auto length=GetTempPathW(32768,root);
        if(!length||length>=32768)fail("cannot locate spec temporary directory");
        static std::atomic<unsigned> sequence{0};
        for(unsigned i=0;i<128;++i) {
            path=fs::path(root)/(L"ZZY spec "+std::to_wstring(GetCurrentProcessId())+L" "+
                std::to_wstring(GetTickCount64())+L" "+std::to_wstring(sequence++));
            if(CreateDirectoryW(path.c_str(),nullptr))return;
            if(GetLastError()!=ERROR_ALREADY_EXISTS)break;
        }
        fail("cannot create spec temporary directory");
    }
    bool clear() noexcept {
        for(unsigned attempt=0;attempt<100;++attempt) {
            std::error_code error;fs::remove_all(path,error);
            const bool remains=fs::exists(path,error);
            if(!error&&!remains)return true;
            Sleep(10);
        }
        return false;
    }
    ~Directory(){clear();}
};
inline std::wstring executable() {
    std::wstring name(32768,L'\0');
    const auto length=GetModuleFileNameW(nullptr,name.data(),static_cast<DWORD>(name.size()));
    if(!length||length>=name.size())fail("cannot locate native executable");
    name.resize(length);return name;
}
inline std::wstring argument(const std::wstring& value) {
    std::wstring out=L"\"";std::size_t backslashes=0;
    for(auto ch:value) {
        if(ch==L'\\'){++backslashes;continue;}
        out.append(ch==L'"'?2*backslashes+1:backslashes,L'\\');backslashes=0;out+=ch;
    }
    out.append(2*backslashes,L'\\');return out+L"\"";
}
inline void put(std::ostream& output,const std::string& value) {
    const auto size=static_cast<std::uint64_t>(value.size());
    output.write(reinterpret_cast<const char*>(&size),sizeof(size));
    output.write(value.data(),static_cast<std::streamsize>(size));
    if(!output)fail("cannot write spec snapshot");
}
struct Reader {
    std::istream& input;
    std::uint64_t remaining;
    std::string get(std::uint64_t maximum) {
        std::uint64_t length=0;
        input.read(reinterpret_cast<char*>(&length),sizeof(length));
        if(!input||remaining<sizeof(length)||length>remaining-sizeof(length)||length>maximum)
            fail("invalid spec snapshot");
        remaining-=sizeof(length)+length;
        std::string out(static_cast<std::size_t>(length),'\0');
        input.read(out.data(),static_cast<std::streamsize>(length));
        if(!input)fail("truncated spec snapshot");
        return out;
    }
};
inline void bundle(const fs::path& path,const Program& program,const SourceSnapshot& snapshot,
                   const ResourcePolicy& policy,NodeId selected) {
    std::ofstream output(path,std::ios::binary);
    put(output,"ZZY-SPEC-1");
    std::string limits="{\"policy_version\":1,\"limits\":{";
    bool first=true;
    for(const auto& [name,value]:policy.limits) {
        if(!first)limits+=',';
        first=false;limits+=quote(name)+":"+std::to_string(value);
    }
    put(output,limits+"}}");
    put(output,narrow(current_directory()));
    put(output,narrow(program.data().nodes[program.data().root].token.source->path));
    put(output,std::to_string(selected));
    put(output,std::to_string(snapshot.files.size()));
    for(const auto& [name,raw]:snapshot.files){put(output,narrow(name));put(output,raw);}
    put(output,std::to_string(snapshot.aliases.size()));
    for(const auto& [name,target]:snapshot.aliases){put(output,narrow(name));put(output,narrow(target));}
    output.close();if(!output)fail("cannot close spec snapshot");
}
inline std::uint64_t count(const std::string& text,std::uint64_t maximum) {
    std::uint64_t value=0;
    const auto parsed=std::from_chars(text.data(),text.data()+text.size(),value);
    if(parsed.ec!=std::errc{}||parsed.ptr!=text.data()+text.size()||value>maximum)fail("invalid spec snapshot count");
    return value;
}
inline int worker(const std::wstring& path,bool json,std::atomic<bool>& cancel) {
    std::ifstream input(fs::path(path),std::ios::binary);
    // Snapshot is an internal bounded transport, never language source.
    Reader reader{input,fs::file_size(path)};
    constexpr std::uint64_t max_path_bytes=32767*4;
    if(reader.get(10)!="ZZY-SPEC-1")fail("invalid spec snapshot header");
    auto policy=PolicyParser(reader.get(65536)).parse();
    diagnostic_directory=widen(reader.get(max_path_bytes));
    const auto entry=widen(reader.get(max_path_bytes));
    const auto selected=count(reader.get(20),policy.limits.at("ast_nodes_total"));
    SourceSnapshot snapshot;
    const auto files=count(reader.get(20),policy.limits.at("module_count"));
    std::uint64_t bytes=0;
    for(std::uint64_t i=0;i<files;++i) {
        auto name=widen(reader.get(max_path_bytes));
        auto raw=reader.get(std::min(policy.limits.at("source_file_bytes"),policy.limits.at("source_total_bytes")-bytes));
        bytes+=raw.size();
        if(!snapshot.files.emplace(std::move(name),std::move(raw)).second)fail("duplicate snapshot source");
    }
    const auto aliases=count(reader.get(20),2*policy.limits.at("ast_nodes_total"));
    for(std::uint64_t i=0;i<aliases;++i) {
        auto name=widen(reader.get(max_path_bytes));auto target=widen(reader.get(max_path_bytes));
        if(!snapshot.files.count(target)||!snapshot.aliases.emplace(std::move(name),std::move(target)).second)
            fail("invalid snapshot source alias");
    }
    if(input.peek()!=std::char_traits<char>::eof())fail("trailing spec snapshot bytes");
    FrontendMeter meter(policy,cancel);
    const auto program=Preparation(meter,&snapshot).load(entry);
    const auto& data=program.data();
    if(selected>=data.nodes.size()||data.nodes[static_cast<NodeId>(selected)].kind!="spec"||
        std::find(data.nodes[data.root].children.begin(),data.nodes[data.root].children.end(),selected)==data.nodes[data.root].children.end())
        fail("invalid selected spec");
    ExecutionContext context(program,policy,cancel,std::cout,std::cerr,json,&std::cin);
    try {context.execute(static_cast<NodeId>(selected));return worker_pass;}
    catch(const RuntimeError& error){context.failure(runtime_diagnostic(data,error,json));return worker_fail;}
    catch(const Cancelled&){throw;}
    catch(const std::bad_alloc&){std::cerr<<render_frontend(FrontendError("E211","spec allocation failed"),json);return worker_fail;}
    catch(...){std::cerr<<render_frontend(FrontendError("","native spec internal error"),json,"internal_error");return worker_fail;}
}
struct Result {DWORD status=1;bool timeout=false,overflow=false;std::string output,error;};
inline void stop_job(HANDLE job,DWORD status) {
    if(!TerminateJobObject(job,status))fail("cannot terminate spec process job");
    for(unsigned attempt=0;attempt<500;++attempt) {
        JOBOBJECT_BASIC_ACCOUNTING_INFORMATION information{};
        if(!QueryInformationJobObject(job,JobObjectBasicAccountingInformation,&information,sizeof(information),nullptr))
            fail("cannot query spec process job");
        if(information.ActiveProcesses==0)return;
        Sleep(10);
    }
    fail("spec process job did not exit");
}
inline Result run(const fs::path& snapshot,const fs::path& cwd,const ResourcePolicy& policy,
                  double timeout,bool json,std::atomic<bool>& cancel) {
    FileHandle frozen(CreateFileW(snapshot.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,0,nullptr));
    if(!frozen)fail("cannot lock spec snapshot");
    SECURITY_ATTRIBUTES security{sizeof(security),nullptr,TRUE};
    HANDLE out_read=nullptr,out_write=nullptr,err_read=nullptr,err_write=nullptr;
    if(!CreatePipe(&out_read,&out_write,&security,0))fail("cannot create spec output pipe");
    Handle output(out_read),output_child(out_write);
    if(!CreatePipe(&err_read,&err_write,&security,0))fail("cannot create spec error pipe");
    Handle errors(err_read),errors_child(err_write);
    if(!SetHandleInformation(out_read,HANDLE_FLAG_INHERIT,0)||
       !SetHandleInformation(err_read,HANDLE_FLAG_INHERIT,0))fail("cannot isolate spec pipe");
    Handle stdin_file(CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,OPEN_EXISTING,0,nullptr));
    if(stdin_file.value==INVALID_HANDLE_VALUE)fail("cannot open isolated spec input");
    Handle job(CreateJobObjectW(nullptr,nullptr));
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if(!job.value||!SetInformationJobObject(job.value,JobObjectExtendedLimitInformation,&limits,sizeof(limits)))
        fail("cannot configure spec process job");
    STARTUPINFOEXW startup{};
    startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;
    startup.StartupInfo.hStdOutput=out_write;startup.StartupInfo.hStdError=err_write;startup.StartupInfo.hStdInput=stdin_file.value;
    SIZE_T size=0;InitializeProcThreadAttributeList(nullptr,2,0,&size);
    std::vector<unsigned char> storage(size);
    startup.lpAttributeList=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
    if(!InitializeProcThreadAttributeList(startup.lpAttributeList,2,0,&size))fail("cannot initialize spec handles");
    struct Attributes {LPPROC_THREAD_ATTRIBUTE_LIST value;~Attributes(){DeleteProcThreadAttributeList(value);}} attributes{startup.lpAttributeList};
    HANDLE inherited[]={out_write,err_write,stdin_file.value};
    if(!UpdateProcThreadAttribute(startup.lpAttributeList,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,inherited,sizeof(inherited),nullptr,nullptr))
        fail("cannot isolate spec handles");
    // Assign at creation so a parent terminated during launch cannot orphan a suspended worker.
    if(!UpdateProcThreadAttribute(startup.lpAttributeList,0,PROC_THREAD_ATTRIBUTE_JOB_LIST,&job.value,sizeof(job.value),nullptr,nullptr))
        fail("cannot attach spec process job");
    const auto image=executable();
    auto command=argument(image)+L" __spec-worker "+argument(snapshot.wstring())+(json?L" json":L" text");
    PROCESS_INFORMATION process{};
    if(!CreateProcessW(image.c_str(),command.data(),nullptr,nullptr,TRUE,
        CREATE_NO_WINDOW|EXTENDED_STARTUPINFO_PRESENT,nullptr,cwd.c_str(),&startup.StartupInfo,&process))
        fail("cannot start native spec");
    Handle child(process.hProcess),thread(process.hThread);
    CloseHandle(output_child.value);output_child.value=nullptr;
    CloseHandle(errors_child.value);errors_child.value=nullptr;
    Result result;
    const auto read=[&](HANDLE pipe,std::string& target,std::uint64_t maximum) {
        DWORD available=0;
        if(!PeekNamedPipe(pipe,nullptr,0,nullptr,&available,nullptr)) {
            if(GetLastError()==ERROR_BROKEN_PIPE)return;
            fail("cannot inspect spec pipe");
        }
        char buffer[8192];
        while(available) {
            DWORD length=0;
            if(!ReadFile(pipe,buffer,std::min<DWORD>(available,sizeof(buffer)),&length,nullptr)||!length)fail("cannot read spec output");
            if(length>maximum-target.size()){result.overflow=true;return;}
            target.append(buffer,length);available-=length;
        }
    };
    const auto started=std::chrono::steady_clock::now();
    for(;;) {
        if(cancel.load()) {stop_job(job.value,130);frozen.close();throw Cancelled{};}
        read(out_read,result.output,policy.limits.at("stdout_bytes"));
        read(err_read,result.error,policy.limits.at("stderr_bytes")+4096);
        const auto state=WaitForSingleObject(child.value,10);
        if(state==WAIT_OBJECT_0) {
            read(out_read,result.output,policy.limits.at("stdout_bytes"));
            read(err_read,result.error,policy.limits.at("stderr_bytes")+4096);
            if(!GetExitCodeProcess(child.value,&result.status))fail("cannot read spec exit code");
            break;
        }
        if(state==WAIT_FAILED)fail("cannot wait for native spec");
        result.timeout=!result.overflow&&std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count()>=timeout;
        if(result.timeout||result.overflow)break;
    }
    stop_job(job.value,1);
    frozen.close();
    return result;
}
inline int collect(const std::wstring& path,const ResourcePolicy& policy,double timeout,
                   bool json,std::atomic<bool>& cancel) {
    std::vector<fs::path> files;
    struct Collection {Program program;SourceSnapshot snapshot;};
    std::vector<Collection> collections;
    struct Spec {std::size_t collection;NodeId node;};
    std::vector<Spec> jobs;
    FrontendMeter total(policy,cancel),output(policy,cancel);
    std::uint64_t diagnostics=0;
    bool diagnostic_exhausted=false;
    const auto report=[&](const std::string& record) {
        if(diagnostic_exhausted)return;
        if(record.size()>policy.limits.at("stderr_bytes")-diagnostics) {
            diagnostic(std::cerr,"E211","resource limit exceeded: stderr_bytes","limit="+
                std::to_string(policy.limits.at("stderr_bytes")),json);
            diagnostic_exhausted=true;
            return;
        }
        std::cerr.write(record.data(),static_cast<std::streamsize>(record.size()));
        diagnostics+=record.size();
    };
    std::size_t collection_errors=0,passed=0,failed=0,timed_out=0;
    try {
        std::error_code status;
        if(!fs::is_directory(path,status))files.push_back(path);
        else {
            for(const auto& file:fs::recursive_directory_iterator(path)) {
                total.safe_point();
                if(file.path().extension()==L".zzy"&&file.is_regular_file()) {
                    total.check("module_count",files.size()+1,display_path(path));
                    files.push_back(file.path());
                }
            }
            std::sort(files.begin(),files.end());
        }
    } catch(const fs::filesystem_error&) {
        ++collection_errors;
        report(render_frontend(FrontendError("E401","cannot enumerate spec directory",display_path(path)),json));
    } catch(const FrontendError& e) {++collection_errors;report(render_frontend(e,json));}
    for(const auto& file:files) {
        try {
            FrontendMeter meter(policy,cancel);SourceSnapshot snapshot;
            auto program=Preparation(meter,nullptr,&snapshot.aliases).load(file.wstring());
            for(const auto& module:program.data().graph) {
                total.check("source_total_bytes",total.source_total+module.source->raw.size());
                total.check("module_count",total.module_count+1);
                total.source_total+=module.source->raw.size();++total.module_count;
                snapshot.files.emplace(module.source->path,module.source->raw);
                snapshot.aliases.insert_or_assign(module.source->path,module.source->path);
            }
            const auto index=collections.size();
            for(auto node:program.data().nodes[program.data().root].children)
                if(program.data().nodes[node].kind=="spec")jobs.push_back({index,node});
            collections.push_back({std::move(program),std::move(snapshot)});
        } catch(const FrontendError& e) {++collection_errors;report(render_frontend(e,json));}
    }
    if(jobs.empty()&&!collection_errors){++collection_errors;report(render_frontend(FrontendError("E401","no specs collected"),json));}
    const auto summary_line=[&](std::size_t pass,std::size_t failures,std::size_t timeouts) {
        return "{\"schema_version\":1,\"tests\":"+std::to_string(jobs.size())+
            ",\"passed\":"+std::to_string(pass)+",\"failed\":"+std::to_string(failures)+
            ",\"timed_out\":"+std::to_string(timeouts)+",\"collection_errors\":"+std::to_string(collection_errors)+"}\n";
    };
    const auto summary_reserve=summary_line(jobs.size(),jobs.size(),jobs.size()).size();
    if(!collection_errors)for(const auto& spec:jobs) {
        const auto& collection=collections[spec.collection];
        const auto& node=collection.program.data().nodes[spec.node];
        const auto file=display_path(node.token.source->path);
        try {
            Directory transport,work;
            const auto snapshot=transport.path/L"snapshot.bin";
            bundle(snapshot,collection.program,collection.snapshot,policy,spec.node);
            const auto result=run(snapshot,work.path,policy,timeout,json,cancel);
            if(!transport.clear()||!work.clear())fail("cannot clean spec temporary directories");
            const auto remaining=policy.limits.at("stdout_bytes")-output.stdout_used;
            if(result.timeout) {
                ++timed_out;
                report(render_frontend(FrontendError("E211","spec timeout: "+node.text,file),json));
            } else if(result.overflow||(!result.output.empty()&&
                      (remaining<summary_reserve||result.output.size()>remaining-summary_reserve))) {
                ++failed;
                report(render_frontend(FrontendError("E211","spec output limit exceeded: "+node.text,file),json));
            } else {
                output.write(std::cout,result.output);
                if(!result.error.empty())report(result.error);
                if(result.status!=worker_pass&&result.status!=worker_fail)
                    report(render_frontend(FrontendError("E401","spec worker exited unexpectedly: "+std::to_string(result.status),file),json));
                if(result.status==worker_pass&&!diagnostic_exhausted)++passed;else ++failed;
            }
        } catch(const FrontendError& e) {
            ++failed;
            report(render_frontend(e,json));
        }
    }
    try {output.write(std::cout,summary_line(passed,failed,timed_out));}
    catch(const FrontendError& e) {report(render_frontend(e,json));return 1;}
    return !jobs.empty()&&passed==jobs.size()&&!collection_errors?0:1;
}
}
