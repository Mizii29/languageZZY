#pragma once
#include "ast.hpp"
#include <cstdint>
namespace zzy {
struct Reference {
    std::string kind;
    NodeId symbol=no_node;
    std::size_t key=0;
    std::string builtin;
};
struct Symbol {NodeId owner=no_node;std::size_t slot=0;bool mutable_binding=false,cell=false;};
struct Capture {Reference source;NodeId symbol;};
struct FunctionPlan {
    std::vector<NodeId> locals;
    std::vector<Capture> captures;
    std::map<NodeId,std::vector<std::size_t>> blocks;
};
// Literal data are frontend constants, not runtime Value/Quantity instances.
struct NumericLiteral {
    bool floating=false;
    std::vector<std::uint32_t> words;
    double real=0;
};
struct QuantityLiteral {
    std::vector<std::uint32_t> numerator,denominator;
    int length=0,time=0;
};
struct AnnotationPlan {std::string builtin;Reference binding;std::vector<std::string> fields;};
struct MachinePlan {std::map<std::pair<std::string,std::string>,std::string> edges;std::set<std::string> states;};
struct ModulePlan {
    NodeId root=no_node;
    std::shared_ptr<const Source> source;
    std::map<std::string,NodeId> exports;
};
struct ProgramData {
    NodeId root=no_node;
    std::vector<AstNode> nodes;
    std::map<NodeId,Reference> references;
    std::map<NodeId,Symbol> symbols;
    std::map<NodeId,FunctionPlan> functions;
    std::map<NodeId,AnnotationPlan> annotations;
    std::map<NodeId,NumericLiteral> numbers;
    std::map<NodeId,QuantityLiteral> quantities;
    std::map<NodeId,MachinePlan> machines;
    std::vector<ModulePlan> graph;
    std::map<NodeId,NodeId> imports;
};
// Publication moves a uniquely owned builder into a const allocation. Only a
// const view escapes: no mutable aliases, request data, or process cache.
class Program final {
    std::shared_ptr<const ProgramData> data_;
public:
    explicit Program(ProgramData data):data_(std::make_shared<const ProgramData>(std::move(data))) {}
    const ProgramData& data() const {return *data_;}
};
}
