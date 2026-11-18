#pragma once
#include "literals.hpp"
#include "host_metadata.hpp"
namespace zzy {
class Resolver {
    const std::vector<AstNode>& nodes;
    ProgramData& output;
    FrontendMeter& meter;
    struct Scope {std::map<std::string,std::optional<Reference>> names;std::vector<NodeId> declarations;};
    struct Context {NodeId node;std::size_t parent;FunctionPlan plan;};
    std::vector<Scope> scopes{1};
    std::vector<Context> contexts;
    std::size_t function=no_node,loops=0;
    const AstNode& node(NodeId id) const {return nodes.at(id);}
    std::string name(NodeId id) const {return spelling(node(id).token);}
    Reference reference(NodeId symbol,std::size_t context) {
        auto& info=output.symbols.at(symbol);
        if(context==no_node) return {"global",symbol,0,{}};
        auto& ctx=contexts.at(context);
        if(symbol==ctx.node && node(ctx.node).kind=="function") return {"self",symbol,0,{}};
        if(info.owner==ctx.node) return {"local",symbol,info.slot,{}};
        auto& captures=ctx.plan.captures;
        for(std::size_t i=0;i<captures.size();++i) if(captures[i].symbol==symbol) return {"capture",symbol,i,{}};
        const auto source=reference(symbol,ctx.parent);
        const auto index=captures.size();captures.push_back({source,symbol});
        if(info.mutable_binding) info.cell=true;
        return {"capture",symbol,index,{}};
    }
    Reference lookup(const Token& token) {
        const auto text=spelling(token);
        for(auto it=scopes.rbegin();it!=scopes.rend();++it) {
            const auto found=it->names.find(text);if(found==it->names.end()) continue;
            if(found->second) {
                const auto& binding=*found->second;
                return binding.builtin.empty()?reference(binding.symbol,function):binding;
            }
            break;
        }
        fail_at(token,"E302","name is undeclared, initializing, or unimplemented: "+text);
    }
    void declare(NodeId id,bool mutable_binding=false,bool initialized=false) {
        const auto text=name(id);
        if(scopes.back().names.count(text)) fail_at(node(id).token,"E301","duplicate declaration: "+text);
        const auto owner=function==no_node?no_node:contexts.at(function).node;
        const auto slot=function==no_node?0:contexts.at(function).plan.locals.size();
        if(function!=no_node) contexts.at(function).plan.locals.push_back(id);
        output.symbols.emplace(id,Symbol{owner,slot,mutable_binding,false});
        scopes.back().declarations.push_back(id);
        scopes.back().names.emplace(text,initialized?std::optional<Reference>{{"global",id,0,{}}}:std::nullopt);
    }
    void initialize(NodeId id) {scopes.back().names.at(name(id))=Reference{"global",id,0,{}};}
    void annotation(NodeId id) {
        const auto& a=node(id).annotation;if(a.empty()) return;
        AnnotationPlan plan;
        if(a.builtin) {const auto text=spelling(a.names[0]);plan.builtin=text.substr(1,text.size()-2);}
        else {plan.binding=lookup(a.names[0]);for(std::size_t i=1;i<a.names.size();++i) plan.fields.push_back(spelling(a.names[i]));}
        output.annotations.emplace(id,std::move(plan));
    }
    void block(NodeId id,NodeId loop=no_node,const std::vector<NodeId>& parameters={},NodeId payload=no_node) {
        frontend_stack_point();const auto context=function;scopes.emplace_back();
        for(auto parameter:parameters) declare(parameter,true,true);
        if(payload!=no_node) declare(payload,false,true);
        if(loop!=no_node) declare(loop,false,true);
        for(auto child:node(id).children) statement(child);
        if(context!=no_node) {
            std::vector<std::size_t> slots;
            for(auto symbol:scopes.back().declarations) {
                const auto& info=output.symbols.at(symbol);
                if(info.owner==contexts.at(context).node) slots.push_back(info.slot);
            }
            contexts.at(context).plan.blocks.emplace(id,std::move(slots));
        }
        scopes.pop_back();
    }
    void resolve_function(NodeId id) {
        frontend_stack_point();const auto& n=node(id);
        std::vector<NodeId> parameters(n.children.begin(),n.children.end()-1);
        for(auto p:parameters) annotation(p);
        if(n.kind!="lazy") annotation(id);
        if(n.kind=="function") initialize(id);
        const auto previous=function,previous_loops=loops;
        function=contexts.size();contexts.push_back({id,previous,{}});loops=0;
        if(n.kind=="function") block(n.children.back(),no_node,parameters);
        else {
            scopes.emplace_back();for(auto p:parameters) declare(p,true,true);
            expression(n.children.back());scopes.pop_back();
        }
        output.functions.emplace(id,std::move(contexts.at(function).plan));
        function=previous;loops=previous_loops;
    }
    std::string pattern_key(NodeId id,bool negative=false) const {
        const auto& n=node(id);
        if(n.kind=="unary") return pattern_key(n.children[0],n.token.kind=="MINUS"?!negative:negative);
        if(n.kind=="integer" || n.kind=="float") return "number:"+numeric_pattern(output.numbers.at(id),negative);
        if(n.kind=="bool") return std::string("bool:")+(n.flag?"true":"false");
        return n.kind+":"+n.text;
    }
    NodeId ungroup(NodeId id) const {while(node(id).kind=="group") id=node(id).children[0];return id;}
    void pure_call(NodeId id) {
        const auto callee=ungroup(node(id).children[0]);const auto& c=node(callee);bool valid=false;
        if(c.kind=="name") {const auto ref=lookup(c.token);valid=ref.builtin=="len" || ref.builtin=="str";}
        else if(c.kind=="field") {
            const auto& base=node(ungroup(c.children[0]));
            if(base.kind=="name") {
                const auto ref=lookup(base.token);
                valid=!ref.builtin.empty() && static_pure(ref.builtin+"."+c.text);
            }
        } else {
            auto base=callee;
            while(node(base).kind=="field" || node(base).kind=="group") base=node(base).children[0];
            if(node(base).kind=="name") lookup(node(base).token);
        }
        if(!valid) fail_at(c.token,"E307","query call is not an actual whitelisted native binding");
    }
    void expression(NodeId root,bool current=false,bool pure=false) {
        frontend_stack_point();std::vector<NodeId> pending{root};
        while(!pending.empty()) {
            meter.safe_point();const auto id=pending.back();pending.pop_back();const auto& n=node(id);
            if(pure) {
                const std::set<std::string> allowed={"integer","float","string","bool","null","quantity","name","current",
                    "group","field","index","array","unary","add","binary","call"};
                if(!allowed.count(n.kind)) fail_at(n.token,"E307","expression is not allowed in a query clause");
                if(n.kind=="call") pure_call(id);
            }
            if(n.kind=="current") {if(!current) fail_at(n.token,"E307","@ is only allowed as a query current item or direct pipeline slot");continue;}
            if(n.kind=="query") {
                expression(n.children[0]);
                for(std::size_t i=1;i<n.children.size();++i) {const auto& clause=node(n.children[i]);expression(clause.children[0],clause.kind!="take",true);}
                continue;
            }
            if(n.kind=="pipe") {
                expression(n.children[0]);const auto& call=node(n.children[1]);std::size_t slots=0;
                for(std::size_t i=1;i<call.children.size();++i) if(node(call.children[i]).kind=="current") ++slots;
                if(slots!=1) fail_at(n.token,"E103","pipeline requires exactly one direct @ argument");
                for(std::size_t child_index=0;child_index<call.children.size();++child_index) {
                    const auto child=call.children[child_index];
                    if(child_index>0 && node(child).kind=="current") continue;
                    std::vector<NodeId> scan{child};
                    while(!scan.empty()) {
                        meter.safe_point();const auto item=scan.back();scan.pop_back();
                        if(node(item).kind=="current") fail_at(node(item).token,"E307","@ is forbidden in other pipeline expressions");
                        for(auto part:node(item).children) scan.push_back(part);
                    }
                    expression(child);
                }
                continue;
            }
            if(n.kind=="propagate") {
                const auto fn=function==no_node?no_node:contexts.at(function).node;
                if(fn==no_node || node(fn).kind!="function" || node(fn).annotation.empty() ||
                    !node(fn).annotation.builtin || node(fn).annotation.names[0].kind!="TYPE_RESULT")
                    fail_at(n.token,"E304","? requires an explicitly Result-annotated named function");
            }
            if(n.kind=="quantity") output.quantities.emplace(id,quantity_literal(n,meter));
            if(n.kind=="lambda" || n.kind=="lazy") {resolve_function(id);continue;}
            if(n.kind=="name") output.references.emplace(id,lookup(n.token));
            if(n.kind=="integer" || n.kind=="float") output.numbers.emplace(id,numeric_literal(n,meter));
            for(auto it=n.children.rbegin();it!=n.children.rend();++it) pending.push_back(*it);
        }
    }
    void statement(NodeId id) {
        frontend_stack_point();meter.safe_point();const auto& n=node(id);
        if(n.kind=="binding") {declare(id,n.flag);annotation(id);expression(n.children[0]);initialize(id);}
        else if(n.kind=="function") {declare(id);resolve_function(id);}
        else if(n.kind=="use") {
            if(scopes.size()!=1 || function!=no_node) fail_at(n.token,"E103","use is only allowed at file top level");
            declare(id,false,true);
        } else if(n.kind=="machine") {
            if(scopes.size()!=1) fail_at(n.token,"E103","machine is only allowed at file top level");
            declare(id,false,true);MachinePlan plan;
            if(n.children.empty()) fail_at(n.token,"E305","machine requires at least one edge");
            for(auto edge:n.children) {
                const auto& e=node(edge);const auto& labels=e.labels;
                if(labels[1].empty() || plan.edges.count({labels[0],labels[1]})) fail_at(e.token,"E305","empty event or duplicate transition");
                plan.edges.emplace(std::make_pair(labels[0],labels[1]),labels[2]);plan.states.insert(labels[0]);plan.states.insert(labels[2]);
            }
            output.machines.emplace(id,std::move(plan));
        } else if(n.kind=="spec") {
            if(scopes.size()!=1 || function!=no_node) fail_at(n.token,"E103","spec is only allowed at file top level");
            block(n.children[0]);
        } else if(n.kind=="match") {
            expression(n.children[0]);std::set<std::string> patterns,tags;bool wildcard=false;
            for(std::size_t i=1;i<n.children.size();++i) {
                const auto& arm=node(n.children[i]);const auto pattern=arm.children[0];const auto& p=node(pattern);
                if(wildcard) fail_at(p.token,"E103","wildcard must be last and unique");
                if(p.kind=="wildcard") wildcard=true;
                else if(p.kind=="payload_pattern") {if(!tags.insert(p.text).second) fail_at(p.token,"E103","duplicate Result tag");}
                else {expression(p.children[0]);if(!patterns.insert(pattern_key(p.children[0])).second) fail_at(p.token,"E103","duplicate equal constant pattern");}
                block(arm.children[1],no_node,{},p.kind=="payload_pattern"?pattern:no_node);
            }
        } else if(n.kind=="return") {
            if(function==no_node) fail_at(n.token,"E304","return requires a function");
            for(auto child:n.children) expression(child);
        } else if(n.kind=="shape") {
            if(scopes.size()!=1) fail_at(n.token,"E103","shape is only allowed at file top level");
            declare(id,false,true);std::set<std::string> fields;
            for(auto field:n.children) {
                if(!fields.insert(name(field)).second) fail_at(node(field).token,"E301","duplicate shape field");
                annotation(field);for(auto value:node(field).children) expression(value);
            }
        } else if(n.kind=="block") block(id);
        else if(n.kind=="for" || n.kind=="while") {
            expression(n.children[0]);++loops;block(n.children[1],n.kind=="for"?id:no_node);--loops;
        } else if(n.kind=="if") {
            for(auto child:n.children) {if(node(child).kind=="block") block(child);else expression(child);}
        } else if(n.kind=="break" || n.kind=="continue") {
            if(!loops) fail_at(n.token,"E304","break/continue requires a loop in the current function");
        } else for(auto child:n.children) expression(child);
    }
public:
    Resolver(const std::vector<AstNode>& ns,ProgramData& result,FrontendMeter& m):nodes(ns),output(result),meter(m) {
        for(const auto& name:{"io","array","text","math","data","unit","sketch","db","len","str","range","wake"})
            scopes[0].names.emplace(name,Reference{"global",no_node,0,name});
    }
    void resolve(NodeId root) {for(auto child:node(root).children) statement(child);}
};
}
