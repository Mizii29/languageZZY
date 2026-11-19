#pragma once
#include "execution.hpp"

namespace zzy {
// Internal native protocol bridge. Never registers a language namespace.
struct WebRuntime {
    static ResourcePolicy policy() {ResourcePolicy p;p.limits.at("io_payload_bytes")=65536;return p;}
    static void begin(ExecutionContext& c) {c.initialize();}
    static void initialize(ExecutionContext& c) {
        try {c.block(c.program.root,[]{});c.drain();}
        catch(RuntimeError& error) {c.unwind(&error);throw;}catch(...) {c.unwind(nullptr);throw;}
    }
    static Value parse(ExecutionContext& c,const std::string& bytes) {
        auto text=c.string(bytes,no_node);
        return ExecutionContext::JsonReader(c,no_node,c.object(text).characters,true).read();
    }
    static std::string encode(ExecutionContext& c,const Value& v) {
        auto text=ExecutionContext::JsonWriter(c,no_node,true).write(v);return encode_utf8(c.object(text).characters);
    }
    static RuntimeNode& node(ExecutionContext& c,const Value& v) {return c.object(v);}
    static Value string(ExecutionContext& c,const std::string& s) {return c.string(s,no_node);}
    static Value map(ExecutionContext& c) {return c.make("Map",{1,0,0},no_node);}
    static void put(ExecutionContext& c,const Value& m,const std::string& key,const Value& v) {auto k=string(c,key);c.map_insert(m,key,k,v,no_node);}
    static Value array(ExecutionContext& c,const std::vector<Value>& values) {return c.array(values,no_node);}
    static Value null(ExecutionContext& c) {return c.null_;}
    static Value get(ExecutionContext& c,const Value& m,const std::string& key) {
        const auto& n=c.object(m);const auto it=std::find(n.names.begin(),n.names.end(),key);
        if(it==n.names.end()) return {};
        return c.heap.pin(n.edges[(n.kind=="Map"?2:1)*static_cast<std::size_t>(it-n.names.begin())+1]);
    }
    static Value invoke(ExecutionContext& c,NodeId function,const Value& request) {
        Value result;auto fn=c.globals.at(function).raw;
        try {c.call(fn,{request},function,[&](Value v){result=std::move(v);},{function});c.drain();return result;}
        catch(RuntimeError& error) {c.unwind(&error);throw;}catch(...) {c.unwind(nullptr);throw;}
    }
    static void freeze(ExecutionContext& c) {
        const auto reject=[&](const std::string& kind) {throw RuntimeError("E303","cannot publish shared module: "+kind,c.program.root);};
        // Check every module's persistent binding, including globals referenced by
        // shape default expressions rather than the shape's stored edge graph.
        for(const auto& item:c.globals) if(c.program.symbols.at(item.first).mutable_binding) reject("mutable binding");
        c.heap.collect();
        std::vector<Handle> pending;
        std::set<std::uint64_t> visited;
        for(const auto& item:c.globals) pending.push_back(item.second.raw.ref());
        while(!pending.empty()) {
            c.point();
            const auto handle=pending.back();pending.pop_back();
            if(!visited.insert(handle.id).second) continue;
            const auto& n=c.heap.state->get(handle);
            if(n.kind=="Namespace") reject("namespace alias");
            pending.insert(pending.end(),n.edges.begin(),n.edges.end());
        }
        for(const auto& item:c.heap.state->nodes) {
            c.point();
            const auto& n=*item.second;
            if(n.kind=="Cell" || n.kind=="Lazy" || n.kind=="Native") reject(n.kind);
        }
        for(auto& item:c.heap.state->nodes) item.second->frozen=true;
    }
    static void attach(ExecutionContext& c,const ExecutionContext& shared) {
        c.heap.state->shared=shared.heap.state;
        for(const auto& item:shared.globals) {
            const auto& b=item.second;ExecutionContext::Type type{b.type.name,{}};
            if(b.type.nominal) type.nominal=c.heap.pin(b.type.nominal.ref());
            c.globals.emplace(item.first,ExecutionContext::Binding{c.heap.pin(b.raw.ref()),std::move(type),Lease(c.heap.state,{0,1,0})});
        }
        for(const auto& item:shared.modules) c.modules.emplace(item.first,c.heap.pin(item.second.ref()));
        for(const auto& item:shared.builtins) c.builtins.insert_or_assign(item.first,c.heap.pin(item.second.ref()));
    }
    static std::string float_literal(double value) {return ExecutionContext::float_text(value);}
};
}
