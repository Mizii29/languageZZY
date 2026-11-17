#include "zzy_native/lexer.hpp"
#include <iostream>
#include <vector>
namespace {
std::atomic<bool> cancelled{false};
static_assert(std::atomic<bool>::is_always_lock_free,"console handler requires lock-free cancellation");
BOOL WINAPI console_handler(DWORD signal) {
    if(signal==CTRL_C_EVENT || signal==CTRL_BREAK_EVENT) {cancelled.store(true,std::memory_order_relaxed);return TRUE;}
    return FALSE;
}
const char* compiler() {
#if defined(__clang__)
    return "clang " __clang_version__;
#elif defined(_MSC_VER)
    return "MSVC";
#elif defined(__GNUC__)
    return "GCC " __VERSION__;
#else
    return "unverified";
#endif
}
const char* crt() {
#if defined(_MSC_VER) && defined(_DEBUG)
    return "MSVC /MDd (debug runtime, not redistributable)";
#elif defined(_MSC_VER)
    return "MSVC /MD (VC Redistributable required)";
#elif defined(__MINGW32__)
    return "MinGW msvcrt; static libgcc/libstdc++ (prototype only)";
#else
    return "unverified";
#endif
}
int cli(const std::vector<std::string>& argv,bool& json,zzy::ResourcePolicy& policy) {
    bool options=true;
    for(std::size_t i=0;i<argv.size() && options;++i) {
        if(argv[i]=="--") options=false;
        else {
            std::string format;
            if(argv[i]=="--diagnostic-format" && i+1<argv.size()) format=argv[i+1];
            else if(argv[i].find("--diagnostic-format=")==0) format=argv[i].substr(20);
            if(format=="json" || format=="text") json=format=="json";
        }
    }
    std::vector<std::string> arguments;
    std::optional<std::string> limits;
    options=true;
    bool help=false;
    for(std::size_t i=0;i<argv.size();++i) {
        const auto& arg=argv[i];
        if(options && arg=="--") {options=false;continue;}
        if(options && arg=="--help") {help=true;continue;}
        if(options && (arg=="--diagnostic-format" || arg.find("--diagnostic-format=")==0)) {
            std::string format;
            if(arg=="--diagnostic-format") {if(i+1==argv.size()) throw zzy::FrontendError("E401","missing diagnostic format");format=argv[++i];}
            else format=arg.substr(20);
            if(format!="text" && format!="json") throw zzy::FrontendError("E401","expected diagnostic format text or json");
        } else if(options && (arg=="--limits" || arg.find("--limits=")==0)) {
            if(arg=="--limits") {if(i+1==argv.size()) throw zzy::FrontendError("E401","missing limits file");limits=argv[++i];}
            else limits=arg.substr(9);
            if(limits->empty()) throw zzy::FrontendError("E401","missing limits file");
        } else {
            if(options && arg.size()>1 && arg[0]=='-' && arg!="--help" && arg!="--version") throw zzy::FrontendError("E401","unknown option");
            arguments.push_back(arg);
        }
    }
    if(help || arguments.empty()) {
        std::cout<<"zzy-native 0.0.0-n1\nAvailable: info, source-info FILE, lex FILE, --help, --version\n"
                 <<"Options (before or after command): --limits FILE --diagnostic-format text|json\n"
                 <<"Not implemented: check, run, test (E402; no Python fallback)\n"
                 <<"GCC validation only; formal CMake/CTest/install acceptance pending\n";
        return 0;
    }
    const auto& command=arguments[0];
    if(command=="--version" && arguments.size()==1) {std::cout<<"0.0.0-n1\n";return 0;}
    if(command=="check" || command=="run" || command=="test") {
        zzy::diagnostic(std::cerr,"E402","capability is not implemented by this backend","capability="+command,json);return 2;
    }
    if(!((command=="info" && arguments.size()==1) || ((command=="source-info" || command=="lex") && arguments.size()==2)))
        throw zzy::FrontendError("E401","invalid command or arguments; use --help");
    if(limits) policy=zzy::load_policy(zzy::widen(*limits));
    zzy::FrontendMeter meter(policy,cancelled);
    if(command=="info") {
        meter.write(std::cout,"{\"schema_version\":1,\"backend\":\"native-ast\",\"stage\":\"N1\","
            "\"version\":\"0.0.0-n1\",\"cxx_standard\":17,\"pointer_bits\":"+std::to_string(sizeof(void*)*8)+
            ",\"compiler\":"+zzy::quote(compiler())+",\"crt\":"+zzy::quote(crt())+
            ",\"supported_commands\":[\"info\",\"source-info\",\"lex\"],\"python_fallback\":false,\"unicode_version\":\"15.0.0\","
            "\"policy_status\":\"frontend limits enforced; AST/execution/cache unavailable\",\"resource_policy\":"+
            policy.canonical_json()+",\"resource_fingerprint\":"+zzy::quote(policy.fingerprint())+"}\n");
        return 0;
    }
    zzy::SourceLoader sources(meter);
    const auto source=sources.load(zzy::widen(arguments[1]));
    if(command=="source-info") meter.write(std::cout,source->info(policy,[&]{meter.safe_point();}));
    else {
        // Scan succeeds completely before any token is published.
        const auto tokens=zzy::Lexer(source,meter).scan();
        for(const auto& token:tokens) meter.write(std::cout,token.record());
    }
    return 0;
}
}
int wmain(int argc,wchar_t** argv) {
    bool json=false;zzy::ResourcePolicy policy;
    const auto report=[&](const zzy::FrontendError& error,const std::string& kind="error") {
        auto rendered=zzy::render_frontend(error,json,kind);
        if(kind=="error" && rendered.size()>policy.limits.at("stderr_bytes"))
            rendered=zzy::render_frontend(zzy::FrontendError("E211","resource limit exceeded: stderr_bytes, limit="+
                std::to_string(policy.limits.at("stderr_bytes"))+", requested="+std::to_string(rendered.size())),json);
        std::cerr<<rendered;std::cerr.flush();
    };
    try {
        zzy::configure_streams();
        // Clear an inherited ignore-Ctrl+C flag before installing our handler.
        if(!SetConsoleCtrlHandler(nullptr,FALSE)) throw std::runtime_error("cannot configure cancellation");
        if(!SetConsoleCtrlHandler(console_handler,TRUE)) throw std::runtime_error("cannot install cancellation handler");
        std::vector<std::string> arguments;
        for(int i=1;i<argc;++i) arguments.push_back(zzy::narrow(argv[i]));
        return cli(arguments,json,policy);
    } catch(const zzy::FrontendError& error) {report(error);return 2;}
    catch(const zzy::Cancelled&) {report(zzy::FrontendError("","cancelled"),"cancelled");return 130;}
    catch(const std::bad_alloc&) {report(zzy::FrontendError("E211","allocation failed; phase=frontend"));return 2;}
    catch(...) {report(zzy::FrontendError("","native internal error; phase=frontend"),"internal_error");return 2;}
}
