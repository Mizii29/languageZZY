#pragma once
#include <cstdint>
#include <ostream>
#include <stdexcept>
#include <string>
#include <string_view>

namespace zzy {
enum class Exit : int { success=0, execution=1, frontend=2, cancelled=130 };
struct Cancelled final {};
struct LimitExceeded final : std::runtime_error {
    std::string key;
    explicit LimitExceeded(std::string name) : std::runtime_error("resource limit exceeded"), key(std::move(name)) {}
};
inline std::string quote(std::string_view value) {
    constexpr char hex[]="0123456789abcdef";
    std::string out="\"";
    for(unsigned char c:value) {
        switch(c) {
        case '"':out+="\\\"";break;
        case '\\':out+="\\\\";break;
        case '\n':out+="\\n";break;
        case '\r':out+="\\r";break;
        case '\t':out+="\\t";break;
        default:
            if(c<32) {out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}
            else out+=static_cast<char>(c);
        }
    }
    return out+'"';
}
inline void diagnostic(std::ostream& stream, const std::string& code,
                       const std::string& message, const std::string& note, bool json=true,
                       const std::string& kind="error") {
    if(json) {
        stream << "{\"schema_version\":1,\"kind\":" << quote(kind) << ",\"code\":"
               << (code.empty()?"null":quote(code)) << ",\"file\":null,\"span\":null,\"message\":"
               << quote(message) << ",\"notes\":[" << quote(note) << "]}\n";
    } else stream << (code.empty()?kind:code) << ' ' << message << '\n' << note << '\n';
}
}
