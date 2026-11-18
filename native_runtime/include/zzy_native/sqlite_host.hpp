#pragma once
#ifdef ZZY_NATIVE_SQLITE
#include "windows_files.hpp"
#include <winsqlite/winsqlite3.h>
#include <chrono>
#include <cstring>
#include <thread>

namespace zzy::sqlite_host {
struct Failure : std::exception {};
inline void require_ok(int status) {
    if(status==SQLITE_NOMEM) throw std::bad_alloc();
    if(status!=SQLITE_OK) throw Failure{};
}
// A bounded, internal C API table. No language value supplies a DLL or symbol.
struct Api {
    HMODULE module=nullptr;
#define ZZY_SQLITE_API(X) \
    X(open_v2) X(close) X(close_v2) X(libversion) X(libversion_number) X(sourceid) \
    X(limit) X(busy_handler) X(progress_handler) X(set_authorizer) X(get_autocommit) \
    X(prepare_v2) X(step) X(finalize) X(bind_parameter_count) X(bind_null) X(bind_int64) \
    X(bind_double) X(bind_text) X(column_count) X(column_type) X(column_int64) X(column_double) \
    X(column_text) X(column_bytes) X(errcode)
#define ZZY_DECLARE_SQLITE(name) decltype(&sqlite3_##name) name=nullptr;
    ZZY_SQLITE_API(ZZY_DECLARE_SQLITE)
#undef ZZY_DECLARE_SQLITE
    template<class Function> void bind(Function& destination,const char* name) {
        const auto address=GetProcAddress(module,name);
        if(!address) throw Failure{};
        static_assert(sizeof(destination)==sizeof(address));
        std::memcpy(&destination,&address,sizeof(address));
    }
    Api() {
        wchar_t directory[MAX_PATH+1];
        const auto size=GetSystemDirectoryW(directory,MAX_PATH+1);
        if(!size || size>MAX_PATH) throw Failure{};
        const auto path=std::wstring(directory,size)+L"\\winsqlite3.dll";
        module=LoadLibraryExW(path.c_str(),nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
        if(!module) throw Failure{};
        try {
#define ZZY_BIND_SQLITE(name) bind(name,"sqlite3_" #name);
            ZZY_SQLITE_API(ZZY_BIND_SQLITE)
#undef ZZY_BIND_SQLITE
#undef ZZY_SQLITE_API
            if(libversion_number()<3029000) throw Failure{};
        } catch(...) {FreeLibrary(module);module=nullptr;throw;}
    }
    ~Api() {if(module) FreeLibrary(module);}
    Api(const Api&)=delete;
    Api& operator=(const Api&)=delete;
};
struct Statement {
    Api& api;sqlite3_stmt* value=nullptr;
    explicit Statement(Api& a):api(a) {}
    ~Statement() {if(value) api.finalize(value);}
    Statement(const Statement&)=delete;
    Statement& operator=(const Statement&)=delete;
};
struct Connection {
    Lease reservation;
    Api api;
    sqlite3* value=nullptr;
    std::atomic<bool>& cancelled;
    DWORD thread=GetCurrentThreadId();
    std::chrono::steady_clock::time_point deadline{},busy_deadline{};
    bool timed=false;
    Connection(const std::shared_ptr<HeapState>& heap,NodeId site):reservation(heap,{1,1,0},site),cancelled(heap->cancelled) {}
    void check_thread() const {if(thread!=GetCurrentThreadId()) throw std::logic_error("SQLite connection used on another thread");}
    static int progress(void* context) noexcept {
        const auto& c=*static_cast<Connection*>(context);
        return c.cancelled.load(std::memory_order_relaxed) || (c.timed && std::chrono::steady_clock::now()>=c.deadline);
    }
    static int busy(void* context,int count) noexcept {
        auto& c=*static_cast<Connection*>(context);
        if(count==0) c.busy_deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(250);
        if(progress(context) || std::chrono::steady_clock::now()>=c.busy_deadline) return 0;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
        return 1;
    }
    static int authorize(void*,int action,const char*,const char* second,const char*,const char*) noexcept {
        if(action==SQLITE_TRANSACTION || action==SQLITE_SAVEPOINT || action==SQLITE_ATTACH ||
           action==SQLITE_DETACH || action==SQLITE_PRAGMA) return SQLITE_DENY;
        if(action==SQLITE_FUNCTION && second) {
            constexpr char denied[]="load_extension";
            std::size_t i=0;
            for(;second[i] && i<sizeof(denied)-1;++i) {
                const char ch=second[i]>='A' && second[i]<='Z'?static_cast<char>(second[i]+('a'-'A')):second[i];
                if(ch!=denied[i]) return SQLITE_OK;
            }
            if(i==sizeof(denied)-1 && !second[i]) return SQLITE_DENY;
        }
        return SQLITE_OK;
    }
    void plain(const char* sql) {
        check_thread();Statement statement(api);
        require_ok(api.prepare_v2(value,sql,-1,&statement.value,nullptr));
        if(!statement.value) throw Failure{};
        const auto status=api.step(statement.value);
        if(status!=SQLITE_DONE) {require_ok(status);throw Failure{};}
    }
    void clear_guards() noexcept {if(value) {api.set_authorizer(value,nullptr,nullptr);api.progress_handler(value,0,nullptr,nullptr);}timed=false;}
    bool close() noexcept {
        if(!value) return true;
        clear_guards();api.busy_handler(value,nullptr,nullptr);
        if(!api.get_autocommit(value)) {
            try {plain("ROLLBACK");}catch(...) {}
        }
        if(api.close(value)!=SQLITE_OK) return false;
        value=nullptr;reservation.release();return true;
    }
    ~Connection() {if(!close() && value) {api.close_v2(value);value=nullptr;}}
};
}
#endif
