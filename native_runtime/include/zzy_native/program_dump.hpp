#pragma once
#include "literals.hpp"
#include <iomanip>
#include <locale>
#include <sstream>
namespace zzy {
inline std::string node_id(NodeId id) {return id==no_node?"null":std::to_string(id);}
inline std::string reference_json(const Reference& ref) {
    return "{\"kind\":"+quote(ref.kind)+",\"symbol\":"+(ref.builtin.empty()?node_id(ref.symbol):quote(ref.builtin))+
        ",\"key\":"+(ref.builtin.empty()?std::to_string(ref.key):quote(ref.builtin))+"}";
}
template<class T> inline std::string ids_json(const std::vector<T>& ids) {
    std::string out="[";for(auto id:ids) {if(out.size()>1) out+=',';out+=std::to_string(id);}return out+"]";
}
inline void dump_program(const Program& program,FrontendMeter& meter,std::ostream& stream) {
    const auto& p=program.data();
    const auto write=[&](const std::string& text){meter.write(stream,text+"\n");};
    write("{\"record\":\"program\",\"schema_version\":1,\"root\":"+std::to_string(p.root)+",\"node_count\":"+
        std::to_string(p.nodes.size())+",\"module_count\":"+std::to_string(p.graph.size())+",\"execution\":false}");
    for(const auto& module:p.graph) {
        std::string exports="{";
        for(const auto& item:module.exports) {if(exports.size()>1) exports+=',';exports+=quote(item.first)+":"+node_id(item.second);}
        write("{\"record\":\"module\",\"root\":"+node_id(module.root)+",\"file\":"+quote(display_path(module.source->path))+
            ",\"sha256\":"+quote(sha256(module.source->raw,[&]{meter.safe_point();}))+",\"exports\":"+exports+"}}");
    }
    for(NodeId id=0;id<p.nodes.size();++id) {
        const auto& n=p.nodes[id];std::string annotations="[",labels="[";
        for(const auto& t:n.annotation.names) {if(annotations.size()>1) annotations+=',';annotations+=quote(spelling(t));}
        for(const auto& s:n.labels) {if(labels.size()>1) labels+=',';labels+=quote(s);}
        write("{\"record\":\"node\",\"id\":"+node_id(id)+",\"kind\":"+quote(n.kind)+",\"file\":"+quote(display_path(n.token.source->path))+
            ",\"token\":"+quote(spelling(n.token))+",\"token_kind\":"+quote(n.token.kind)+",\"token_span\":"+span_json(token_span(n.token))+
            ",\"span\":"+span_json(n.token.source->span(n.start,n.end))+",\"depth\":"+std::to_string(n.depth)+",\"children\":"+ids_json(n.children)+
            ",\"text\":"+quote(n.text)+",\"flag\":"+(n.flag?"true":"false")+",\"annotation\":"+annotations+"],\"labels\":"+labels+"]"+
            ",\"auxiliary\":"+(n.auxiliary?quote(n.auxiliary->value.value_or(spelling(*n.auxiliary))):"null")+"}");
    }
    for(const auto& item:p.references) write("{\"record\":\"reference\",\"node\":"+node_id(item.first)+",\"binding\":"+reference_json(item.second)+"}");
    for(const auto& item:p.symbols) {
        const auto& s=item.second;
        write("{\"record\":\"symbol\",\"node\":"+node_id(item.first)+",\"owner\":"+node_id(s.owner)+",\"slot\":"+
            (s.owner==no_node?"null":std::to_string(s.slot))+",\"mutable\":"+(s.mutable_binding?"true":"false")+",\"cell\":"+(s.cell?"true":"false")+"}");
    }
    for(const auto& item:p.functions) {
        const auto& fn=item.second;std::string captures="[",blocks="{";
        for(const auto& cap:fn.captures) {if(captures.size()>1) captures+=',';captures+="{\"symbol\":"+node_id(cap.symbol)+",\"source\":"+reference_json(cap.source)+"}";}
        for(const auto& b:fn.blocks) {if(blocks.size()>1) blocks+=',';blocks+=quote(std::to_string(b.first))+":"+ids_json(b.second);}
        write("{\"record\":\"function\",\"node\":"+node_id(item.first)+",\"locals\":"+ids_json(fn.locals)+",\"captures\":"+captures+"],\"blocks\":"+blocks+"}}");
    }
    for(const auto& item:p.annotations) {
        const auto& a=item.second;std::string fields="[";
        for(const auto& f:a.fields) {if(fields.size()>1) fields+=',';fields+=quote(f);}
        write("{\"record\":\"annotation\",\"node\":"+node_id(item.first)+",\"builtin\":"+quote(a.builtin)+",\"binding\":"+
            (a.builtin.empty()?reference_json(a.binding):"null")+",\"fields\":"+fields+"]}");
    }
    for(const auto& item:p.numbers) {
        const auto& n=item.second;std::ostringstream real;real.imbue(std::locale::classic());real<<std::setprecision(17)<<n.real;
        write("{\"record\":\"number\",\"node\":"+node_id(item.first)+",\"kind\":"+quote(n.floating?"Float":"Int")+",\"decimal\":"+
            quote(n.floating?real.str():LiteralNat(n.words).decimal())+"}");
    }
    for(const auto& item:p.quantities) {
        const auto& q=item.second;
        write("{\"record\":\"quantity\",\"node\":"+node_id(item.first)+",\"numerator\":"+quote(LiteralNat(q.numerator).decimal())+
            ",\"denominator\":"+quote(LiteralNat(q.denominator).decimal())+",\"dimensions\":["+std::to_string(q.length)+","+std::to_string(q.time)+"]}");
    }
    for(const auto& item:p.machines) {
        std::string edges="[";
        for(const auto& e:item.second.edges) {if(edges.size()>1) edges+=',';edges+="["+quote(e.first.first)+","+quote(e.first.second)+","+quote(e.second)+"]";}
        write("{\"record\":\"machine\",\"node\":"+node_id(item.first)+",\"edges\":"+edges+"]}");
    }
    for(const auto& item:p.imports) write("{\"record\":\"import\",\"node\":"+node_id(item.first)+",\"root\":"+node_id(item.second)+"}");
}
}
