#include "zzy_native/protocol.hpp"
#include <iostream>
#include <sstream>

int main() {
    zzy::configure_streams();
    if(static_cast<int>(zzy::Exit::success)!=0 || static_cast<int>(zzy::Exit::execution)!=1 ||
       static_cast<int>(zzy::Exit::frontend)!=2 || static_cast<int>(zzy::Exit::cancelled)!=130) return 1;
    if(zzy::quote("a\n\"\\\t\x01")!="\"a\\n\\\"\\\\\\t\\u0001\"") return 1;
    std::ostringstream stream;
    zzy::diagnostic(stream,"E402","unsupported","capability=run");
    const std::string expected="{\"schema_version\":1,\"kind\":\"error\",\"code\":\"E402\",\"file\":null,\"span\":null,\"message\":\"unsupported\",\"notes\":[\"capability=run\"]}\n";
    if(stream.str()!=expected) return 1;
    std::cout<<"protocol: 3 checks passed\n";
    return 0;
}
