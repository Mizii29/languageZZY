#include "zzy_native/prepare.hpp"
#include "zzy_native/program_dump.hpp"
#include "zzy_native/execution.hpp"
#include "zzy_native/spec_runner.hpp"
#ifdef ZZY_NATIVE_FUNCTION_VM
#include "zzy_native/integer_dispatch.hpp"
#endif
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
int cli(const std::vector<std::string>& argv,bool& json,zzy::ResourcePolicy& policy,std::atomic<bool>& cancel) {
    if(argv.size()==3&&argv[0]=="__spec-worker"&&(argv[2]=="json"||argv[2]=="text")) {
        json=argv[2]=="json";
        return zzy::specs::worker(zzy::widen(argv[1]),json,cancel);
    }
#ifdef ZZY_NATIVE_SQLITE
    constexpr auto sqlite_enabled="true";
#else
    constexpr auto sqlite_enabled="false";
#endif
#ifdef ZZY_NATIVE_GUI
    constexpr auto gui_enabled="true";
#else
    constexpr auto gui_enabled="false";
#endif
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
    bool help=false,gui=false;
#ifdef ZZY_NATIVE_FUNCTION_VM
    std::optional<std::string> engine;
#endif
    std::optional<double> timeout;
    for(std::size_t i=0;i<argv.size();++i) {
        const auto& arg=argv[i];
        if(options && arg=="--") {options=false;continue;}
        if(options && arg=="--help") {help=true;continue;}
#ifdef ZZY_NATIVE_GUI
        if(options&&arg=="--gui") {gui=true;continue;}
#endif
#ifdef ZZY_NATIVE_FUNCTION_VM
        if(options&&(arg=="--engine"||arg.find("--engine=")==0)) {
            if(arg=="--engine"&&i+1==argv.size()) throw zzy::FrontendError("E401","missing run engine");
            engine=arg=="--engine"?argv[++i]:arg.substr(9);
            if(*engine!="auto" && *engine!="ast") throw zzy::FrontendError("E401","expected run engine auto or ast");
            continue;
        }
#endif
        if(options&&(arg=="--timeout"||arg.find("--timeout=")==0)) {
            if(arg=="--timeout"&&i+1==argv.size())throw zzy::FrontendError("E401","missing test timeout");
            const auto value=arg=="--timeout"?argv[++i]:arg.substr(10);
            std::istringstream number(value);number.imbue(std::locale::classic());
            double seconds=0;
            if(!(number>>std::noskipws>>seconds)||number.peek()!=EOF||!std::isfinite(seconds)||seconds<=0)
                throw zzy::FrontendError("E401","test timeout must be finite and positive");
            timeout=seconds;
            continue;
        }
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
    if(help) {
        std::cout<<"zzy-native 0.0.0-n5-dev\nAvailable: info, source-info FILE, lex FILE, run FILE, check FILE, program-info FILE, test FILE|DIR\n"
                 <<"Options (before or after command): --limits FILE --diagnostic-format text|json\n"
                 <<"run executes core ZZY; unported host capabilities report E402\n"
                 <<"test accepts --timeout SECONDS (default: 10)\n"
                 <<"check prepares an immutable Program without executing user code\n";
#ifdef ZZY_NATIVE_GUI
        std::cout<<"Use run FILE --gui to enable Sketch windows\n";
#endif
#ifdef ZZY_NATIVE_FUNCTION_VM
        std::cout<<"run accepts --engine auto|ast (default: auto)\n";
#endif
        return 0;
    }
    if(arguments.empty())throw zzy::FrontendError("E401","missing command; use --help");
    const auto& command=arguments[0];
    if(gui&&command!="run")throw zzy::FrontendError("E401","--gui requires run");
    if(timeout&&command!="test")throw zzy::FrontendError("E401","--timeout requires test");
#ifdef ZZY_NATIVE_FUNCTION_VM
    if(engine&&command!="run")throw zzy::FrontendError("E401","--engine requires run");
#endif
    if(command=="--version" && arguments.size()==1) {std::cout<<"0.0.0-n5-dev\n";return 0;}
    if(limits) policy=zzy::load_policy(zzy::widen(*limits));
    if(command=="test") {
        if(arguments.size()!=2)throw zzy::FrontendError("E401","invalid command or arguments; use --help");
        return zzy::specs::collect(zzy::widen(arguments[1]),policy,timeout.value_or(10),json,cancel);
    }
    if(!((command=="info" && arguments.size()==1) || ((command=="source-info" || command=="lex" || command=="check" || command=="program-info" || command=="run") && arguments.size()==2)))
        throw zzy::FrontendError("E401","invalid command or arguments; use --help");
    zzy::FrontendMeter meter(policy,cancelled);
    if(command=="info") {
        meter.write(std::cout,"{\"schema_version\":1,\"backend\":\"native-ast\",\"stage\":\"N5\","
            "\"version\":\"0.0.0-n5-dev\",\"cxx_standard\":17,\"pointer_bits\":"+std::to_string(sizeof(void*)*8)+
            ",\"compiler\":"+zzy::quote(compiler())+",\"crt\":"+zzy::quote(crt())+
            ",\"supported_commands\":[\"info\",\"source-info\",\"lex\",\"check\",\"program-info\",\"run\",\"test\"],\"python_fallback\":false,\"unicode_version\":\"15.0.0\","
            "\"sqlite_enabled\":"+sqlite_enabled+",\"sketch_headless\":true,\"sketch_native_gui\":"+gui_enabled+
            ",\"test_enabled\":true"+
            ",\"policy_status\":\"frontend and core execution limits enforced; program cache configuration only\",\"resource_policy\":"+
            policy.canonical_json()+",\"resource_fingerprint\":"+zzy::quote(policy.fingerprint())+"}\n");
        return 0;
    }
    if(command=="check" || command=="program-info") {
        const auto program=zzy::prepare(zzy::widen(arguments[1]),meter);
        if(command=="program-info") zzy::dump_program(program,meter,std::cout);
        return 0;
    }
    if(command=="run") {
        const auto program=zzy::prepare(zzy::widen(arguments[1]),meter);
#ifdef ZZY_NATIVE_FUNCTION_VM
        zzy::IntegerDispatch dispatch;
#endif
        zzy::ExecutionContext context(program,policy,cancelled,std::cout,std::cerr,json,&std::cin);
#ifdef ZZY_NATIVE_GUI
        if(gui)context.enable_sketch_gui();
#endif
        try {
#ifdef ZZY_NATIVE_FUNCTION_VM
            if(!engine || *engine=="auto") dispatch.attach(context,policy,cancel,true);
#endif
            context.execute();
            return 0;
        }
        catch(const zzy::RuntimeError& error) {context.failure(zzy::runtime_diagnostic(program.data(),error,json));return 1;}
        catch(const std::bad_alloc&) {std::cerr<<zzy::render_frontend(zzy::FrontendError("E211","allocation failed; phase=execution"),json);return 1;}
        catch(const zzy::Cancelled&) {throw;}
        catch(...) {std::cerr<<zzy::render_frontend(zzy::FrontendError("","native internal error; phase=execution"),json,"internal_error");return 1;}
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
        return cli(arguments,json,policy,cancelled);
    } catch(const zzy::FrontendError& error) {report(error);return 2;}
    catch(const zzy::Cancelled&) {report(zzy::FrontendError("","cancelled"),"cancelled");return 130;}
    catch(const std::bad_alloc&) {report(zzy::FrontendError("E211","allocation failed; phase=frontend"));return 2;}
    catch(...) {report(zzy::FrontendError("","native internal error; phase=frontend"),"internal_error");return 2;}
}
