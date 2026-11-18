#pragma once
#include "lexer.hpp"
#include <limits>
#include <map>
#include <set>
namespace zzy {
using NodeId=std::size_t;
inline constexpr NodeId no_node=std::numeric_limits<NodeId>::max();
inline std::string spelling(const Token& t) {
    const auto& offsets=t.source->decoded.byte_offsets;
    return t.source->raw.substr(offsets.at(t.start),offsets.at(t.end)-offsets.at(t.start));
}
inline Span token_span(const Token& t) {return t.source->span(t.start,t.end);}
[[noreturn]] inline void fail_at(const Token& t,const std::string& code,const std::string& message) {
    throw FrontendError(code,message,display_path(t.source->path),token_span(t));
}
// Host stack exhaustion is separate from the language's configurable syntax budget.
inline void frontend_stack_point() {
    ULONG_PTR low=0,high=0;GetCurrentThreadStackLimits(&low,&high);
    const auto here=reinterpret_cast<ULONG_PTR>(&low);
    if(here>low && here-low<65536) throw FrontendError("E211","host stack resource exhausted; phase=frontend");
}
struct Annotation {
    std::vector<Token> names;
    bool builtin=false;
    bool empty() const {return names.empty();}
};
struct AstNode {
    std::string kind;
    Token token;
    std::vector<NodeId> children;
    Annotation annotation;
    std::string text;
    bool flag=false;
    std::optional<Token> auxiliary;
    std::vector<std::string> labels;
    std::size_t depth=0,start=0,end=0;
};
class AstBuilder {
    FrontendMeter& meter_;
public:
    std::vector<AstNode> nodes;
    explicit AstBuilder(FrontendMeter& meter):meter_(meter) {}
    NodeId add(std::string kind,const Token& token,std::vector<NodeId> children={},std::string text="",
               Annotation annotation={},bool flag=false,std::optional<Token> auxiliary={},
               std::vector<std::string> labels={},std::optional<std::size_t> end={}) {
        std::size_t depth=0,start=token.start,finish=token.end;
        for(auto id:children) {
            const auto& child=nodes.at(id);depth=std::max(depth,child.depth+1);
            start=std::min(start,child.start);finish=std::max(finish,child.end);
        }
        meter_.check("syntax_depth",depth,display_path(token.source->path),token_span(token));
        meter_.check("ast_nodes_total",nodes.size()+1,display_path(token.source->path),token_span(token));
        meter_.safe_point();
        nodes.push_back({std::move(kind),token,std::move(children),std::move(annotation),std::move(text),flag,
                         std::move(auxiliary),std::move(labels),depth,start,std::max(finish,end.value_or(token.end))});
        return nodes.size()-1;
    }
};
}
