#include "zzy_native/protocol.hpp"
#include "zzy_native/policy.hpp"
#include <iostream>
#include <string>
#include <vector>

namespace {
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
int cli(int argc,char** argv) {
    bool json=false;
    std::vector<std::string> arguments;
    for(int i=1;i<argc;++i) {
        std::string arg=argv[i];
        if(arg=="--diagnostic-format") {
            if(i+1>=argc || (std::string(argv[i+1])!="json" && std::string(argv[i+1])!="text")) {
                zzy::diagnostic(std::cerr,"E401","invalid diagnostic format","expected text or json",json);return 2;
            }
            json=std::string(argv[++i])=="json";
        } else arguments.push_back(arg);
    }
    if(arguments.empty() || arguments[0]=="--help") {
        std::cout << "zzy-native 0.0.0-n0\nAvailable: info, --help, --version\n"
                  << "Not implemented: source-info, lex, check, run, test (E402; no Python fallback)\n";
        return 0;
    }
    const auto& command=arguments[0];
    if(command=="--version" && arguments.size()==1) {std::cout<<"0.0.0-n0\n";return 0;}
    if(command=="info" && arguments.size()==1) {
        std::cout << "{\"schema_version\":1,\"backend\":\"native-ast\",\"stage\":\"N0\","
                  << "\"version\":\"0.0.0-n0\",\"cxx_standard\":17,\"pointer_bits\":"<<sizeof(void*)*8
                  << ",\"compiler\":"<<zzy::quote(compiler())<<",\"crt\":"<<zzy::quote(crt())
                  << ",\"supported_commands\":[\"info\"],\"python_fallback\":false,"
                  << "\"policy_status\":\"declared; language execution unavailable\",\"resource_policy\":"
                  << zzy::default_policy << ",\"resource_fingerprint\":"<<zzy::quote(zzy::default_policy_sha)<<"}\n";
        return 0;
    }
    if(command=="source-info" || command=="lex" || command=="check" || command=="run" || command=="test") {
        zzy::diagnostic(std::cerr,"E402","capability is not implemented by this backend","capability="+command,json);return 2;
    }
    zzy::diagnostic(std::cerr,"E401","invalid command or arguments","use --help",json);return 2;
}
}
int main(int argc,char** argv) {
    try {return cli(argc,argv);}
    catch(const std::bad_alloc&) {zzy::diagnostic(std::cerr,"E211","allocation failed","phase=frontend");return 2;}
    catch(...) {zzy::diagnostic(std::cerr,"","native internal error","phase=frontend",true,"internal_error");return 2;}
}
