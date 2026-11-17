#include "zzy_native/heap_prototype.hpp"
#include <windows.h>
#include <tlhelp32.h>
#include <iostream>
#include <string>
#include <vector>

namespace {
std::atomic<bool> interrupted{false};
BOOL WINAPI on_interrupt(DWORD kind) {
    if(kind==CTRL_C_EVENT || kind==CTRL_BREAK_EVENT){interrupted.store(true);return TRUE;}
    return FALSE;
}
struct Snapshot {
    HANDLE value;
    explicit Snapshot(DWORD flags):value(CreateToolhelp32Snapshot(flags,0)) {
        if(value==INVALID_HANDLE_VALUE)throw std::runtime_error("snapshot failed");
    }
    ~Snapshot() {CloseHandle(value);}
};
std::string utf8(const wchar_t* value) {
    const int count=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value,-1,nullptr,0,nullptr,nullptr);
    if(!count)throw std::runtime_error("module name conversion failed");
    std::string result(static_cast<std::size_t>(count),'\0');
    if(!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value,-1,&result[0],count,nullptr,nullptr))
        throw std::runtime_error("module name conversion failed");
    result.pop_back();return result;
}
int dependencies() {
    Snapshot modules(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32);
    MODULEENTRY32W module{};module.dwSize=sizeof(module);
    if(!Module32FirstW(modules.value,&module))throw std::runtime_error("module enumeration failed");
    std::cout<<"{\"pid\":"<<GetCurrentProcessId()<<",\"modules\":[";
    bool first=true;
    do {if(!first)std::cout<<',';first=false;std::cout<<zzy::quote(utf8(module.szModule));}
    while(Module32NextW(modules.value,&module));
    Snapshot processes(TH32CS_SNAPPROCESS);
    PROCESSENTRY32W process{};process.dwSize=sizeof(process);
    if(!Process32FirstW(processes.value,&process))throw std::runtime_error("process enumeration failed");
    std::cout<<"],\"children\":[";first=true;
    do {if(process.th32ParentProcessID==GetCurrentProcessId()) {
        if(!first)std::cout<<',';
        first=false;std::cout<<"{\"pid\":"<<process.th32ProcessID<<",\"name\":"<<zzy::quote(utf8(process.szExeFile))<<'}';
    }}while(Process32NextW(processes.value,&process));
    std::cout<<"]}\n";return 0;
}
void cleaned(zzy::prototype::Heap& heap) {
    heap.close();heap.close();
    if(!(heap.used()==zzy::prototype::Amount{}))throw std::runtime_error("cleanup counters not zero");
    std::cout<<"{\"objects\":0,\"slots\":0,\"payload\":0}\n";
}
int probe(const std::string& mode) {
    if(mode=="dependencies")return dependencies();
    if(mode!="success" && mode!="resource" && mode!="cancel" && mode!="error" && mode!="wait" && mode!="wait-timeout") {
        zzy::diagnostic(std::cerr,"E401","unknown lifecycle probe","probe-only");return 2;
    }
    zzy::prototype::Heap heap({1,1,4});
    try {
        auto array=heap.allocate(zzy::prototype::Kind::array);heap.edge(array.get(),array.get());
        if(mode=="wait-timeout") {
            std::cout<<"READY\n"<<std::flush;
            for(;;)Sleep(10); // Only the external N0 timeout harness terminates this probe.
        }
        if(mode=="wait") {
            if(!SetConsoleCtrlHandler(on_interrupt,TRUE))throw std::runtime_error("console handler failed");
            std::cout<<"READY\n"<<std::flush;
            while(!interrupted.load())Sleep(10);
            heap.cancel();
        }
        if(mode=="cancel")heap.cancel();
        if(mode=="resource" || mode=="cancel" || mode=="wait") {
            auto extra=heap.allocate(zzy::prototype::Kind::array);
        }
        if(mode=="error")throw std::runtime_error("injected internal error");
        cleaned(heap);return 0;
    } catch(const zzy::Cancelled&) {
        cleaned(heap);zzy::diagnostic(std::cerr,"","execution cancelled","probe cleanup complete",true,"cancelled");return 130;
    } catch(const zzy::LimitExceeded& error) {
        cleaned(heap);zzy::diagnostic(std::cerr,"E211","resource limit exceeded","limit="+error.key);return 1;
    } catch(...) {
        cleaned(heap);zzy::diagnostic(std::cerr,"","native internal error","probe cleanup complete",true,"internal_error");return 1;
    }
}
}
int main(int argc,char** argv) {
    try{zzy::configure_streams();return probe(argc==2?argv[1]:"");}
    catch(...){zzy::diagnostic(std::cerr,"","probe failed","probe-only",true,"internal_error");return 1;}
}
