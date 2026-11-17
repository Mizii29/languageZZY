#pragma once
#include "protocol.hpp"
#include "utf8.hpp"
#include <optional>
#include <utility>
namespace zzy {
struct Position {std::size_t line,column;};
struct Span {Position start,end;};
inline std::string position_json(Position p) {return "{\"line\":"+std::to_string(p.line)+",\"column\":"+std::to_string(p.column)+"}";}
inline std::string span_json(const Span& s) {return "{\"start\":"+position_json(s.start)+",\"end\":"+position_json(s.end)+"}";}
struct FrontendError final : std::runtime_error {
    std::string code;
    std::optional<std::string> file;
    std::optional<Span> span;
    FrontendError(std::string c,std::string message,std::optional<std::string> f={},std::optional<Span> s={})
        : std::runtime_error(std::move(message)),code(std::move(c)),file(std::move(f)),span(s) {}
};
inline std::string one_line(std::string s) {
    std::string out;
    for(char c:s) {if(c=='\n') out+="\\n";else if(c=='\r') out+="\\r";else out+=c;}
    return out;
}
inline std::string render_frontend(const FrontendError& error,bool json,const std::string& kind="error") {
    auto file=error.file;
    auto message=decode_utf8(error.what()).text;
    if(message.size()>4096) message.resize(4096);
    if(file && decode_utf8(*file).text.size()>1024) file.reset();
    const auto encode=[&](const std::u32string& text) {
        const auto utf8=encode_utf8(text);
        if(json) return "{\"schema_version\":1,\"kind\":"+quote(kind)+",\"code\":"+(error.code.empty()?"null":quote(error.code))+
            ",\"file\":"+(file?quote(*file):"null")+",\"span\":"+(error.span?span_json(*error.span):"null")+
            ",\"message\":"+quote(utf8)+",\"notes\":[]}\n";
        auto where=file?one_line(*file):"<cli>";
        if(error.span) where+=":"+std::to_string(error.span->start.line)+":"+std::to_string(error.span->start.column);
        return where+": "+(error.code.empty()?kind:error.code)+" "+one_line(utf8)+"\n";
    };
    auto result=encode(message);
    if(result.size()<=4096) return result;
    if(encode(U"\u2026").size()>4096) file.reset();
    std::size_t low=0,high=message.size();
    while(low<high) {
        const auto mid=low+(high-low+1)/2;
        if(encode(message.substr(0,mid)+U"\u2026").size()<=4096) low=mid;else high=mid-1;
    }
    return encode(message.substr(0,low)+U"\u2026");
}
}
