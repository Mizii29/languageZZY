#pragma once
#include "web_runtime.hpp"

namespace zzy::web {
using RouteKey=std::pair<std::string,std::string>;
inline bool response_status(int status) {
    return status>=200 && status<=599 && status!=204 && status!=205 && status!=304;
}
struct Route {
    NodeId function=no_node,request=no_node;
    std::map<int,NodeId> responses;
};
using Routes=std::map<RouteKey,Route>;
struct Violation {std::string path,reason;};
struct Field {
    std::string name,kind;
    NodeId nested=no_node;
    std::optional<std::string> literal;
};
struct Layout {std::vector<Field> fields;std::size_t depth=1;};
inline const std::map<std::string,std::string> json_types={
    {"Int","integer"},{"Float","number"},{"String","string"},{"Bool","boolean"},
    {"Null","null"},{"Array","array"},{"Map","object"}};
[[noreturn]] inline void config_error(const std::string& message) {throw FrontendError("E401",message);}
[[noreturn]] inline void resource_error(const std::string& key) {throw RuntimeError("E211","resource limit exceeded: "+key);}
inline std::string child_path(const std::string& path,const std::string& key) {
    const auto chars=decode_utf8(key).text;
    auto identifier=!chars.empty() && unicode::contains(unicode::identifier_start,chars.front());
    for(auto cp:chars) identifier=identifier && unicode::contains(unicode::identifier_continue,cp);
    auto result=path+(identifier?"."+key:"["+quote(key)+"]");
    if(quote(result).size()>4096) resource_error("contract_path_bytes");
    return result;
}
inline std::string schema_ref(NodeId id) {
    return "{\"$ref\":\"#/components/schemas/Shape"+std::to_string(id)+"\"}";
}
inline std::string content_schema(const std::string& schema) {
    return "{\"application/json\":{\"schema\":"+schema+"}}";
}
inline void comma(std::string& output,bool& first) {
    if(!first) output+=',';
    first=false;
}
inline std::string error_schema(int status,const Route& route) {
    static const std::map<int,std::string> codes={
        {400,R"("invalid_json","invalid_request","unexpected_body","disconnected")"},
        {405,R"("method_not_allowed")"},{408,R"("body_timeout")"},
        {413,R"("body_too_large","resource_limit")"},
        {415,R"("unsupported_media_type","unsupported_encoding")"},{431,R"("metadata_too_large")"},
        {500,R"("invalid_response","zzy_error","internal_error")"},
        {503,R"("busy","resource_limit")"},{504,R"("request_timeout")"}
    };
    std::string variants;
    const auto ordinary=codes.find(status);
    if(ordinary!=codes.end()) {
        variants=R"({"type":"object","properties":{"code":{"enum":[)"+ordinary->second+
            R"(]}},"required":["code"],"additionalProperties":false})";
    }
    const std::string contract=status==422 && route.request!=no_node?"contract_input":
        status==500 && !route.responses.empty()?"contract_response":"";
    if(!contract.empty()) {
        if(!variants.empty()) variants+=',';
        variants+=R"({"type":"object","properties":{"code":{"const":)"+quote(contract)+
            R"(},"path":{"type":"string"},"reason":{"enum":["type","missing","unknown"]}},"required":["code","path","reason"],"additionalProperties":false})";
    }
    if(variants.empty()) return {};
    return R"({"type":"object","properties":{"error":{"anyOf":[)"+variants+
        R"(]}},"required":["error"],"additionalProperties":false})";
}
class Contracts {
    const ProgramData& program;
    std::atomic<bool>& cancelled;
    std::map<NodeId,Layout> layouts;
    std::set<NodeId> compiling;
    std::size_t field_count=0;
    void point() const {if(cancelled.load()) throw Cancelled{};}
    const AstNode& ast(NodeId id) const {return program.nodes.at(id);}
    NodeId top_level(NodeId root,const std::string& name) const {
        for(auto id:ast(root).children) {
            const auto& n=ast(id);
            if((n.kind=="shape" || n.kind=="use") && spelling(n.token)==name) return id;
        }
        config_error("unknown static shape: "+name);
    }
    NodeId follow(NodeId id,const std::vector<std::string>& names) const {
        for(const auto& name:names) {
            if(id==no_node || ast(id).kind!="use") config_error("contract annotation must refer to a static shape");
            id=top_level(program.imports.at(id),name);
        }
        if(id==no_node || ast(id).kind!="shape") config_error("contract requires a static shape definition");
        return id;
    }
    NodeId named(const std::string& name) {
        auto dot=name.find('.');
        auto id=top_level(program.root,name.substr(0,dot));
        std::vector<std::string> members;
        while(dot!=std::string::npos) {
            const auto start=dot+1;
            dot=name.find('.',start);
            members.push_back(name.substr(start,dot==std::string::npos?dot:dot-start));
        }
        id=follow(id,members);
        compile(id);
        return id;
    }
    static bool object_kind(const RuntimeNode& n) {return n.kind=="Map" || n.kind=="Shape";}
    static std::string text(ExecutionContext& c,const Value& value) {
        const auto& node=WebRuntime::node(c,value);
        if(node.kind!="String") config_error("contract shape name must be String");
        return encode_utf8(node.characters);
    }
    std::string literal(NodeId id,const std::string& expected) const {
        bool sign=false,negative=false;
        while(ast(id).kind=="group" || ast(id).kind=="unary") {
            const auto& node=ast(id);
            if(node.kind=="unary") {
                if(sign || (node.token.kind!="PLUS" && node.token.kind!="MINUS")) config_error("contract default must be a scalar literal");
                sign=true;
                negative=node.token.kind=="MINUS";
            }
            id=node.children.front();
        }
        const auto& node=ast(id);
        if(expected=="Int" && node.kind=="integer") {
            BigInt value(program.numbers.at(id).words);
            if(negative) value.negate();
            if(!json_detail::safe_http_int(value)) config_error("contract default outside safe Int range");
            return value.decimal();
        }
        if(expected=="Float" && node.kind=="float") {
            const auto value=program.numbers.at(id).real;
            return WebRuntime::float_literal(negative?-value:value);
        }
        if(!sign && expected=="Bool" && node.kind=="bool") return node.flag?"true":"false";
        if(!sign && expected=="Null" && node.kind=="null") return "null";
        if(!sign && expected=="String" && node.kind=="string") return quote(node.text);
        config_error("contract default must be a matching scalar literal");
    }
    const Layout& compile(NodeId id) {
        point();
        if(const auto found=layouts.find(id);found!=layouts.end()) return found->second;
        if(!compiling.insert(id).second) config_error("recursive shape contract");
        if(compiling.size()>64) resource_error("contract_depth");
        Layout layout;
        for(auto field_id:ast(id).children) {
            point();
            if(++field_count>4096) resource_error("contract_fields");
            const auto& node=ast(field_id);
            const auto annotation=program.annotations.find(field_id);
            if(annotation==program.annotations.end()) config_error("contract field needs type annotation: "+spelling(node.token));
            const auto& type=annotation->second;
            Field field{spelling(node.token),type.builtin,no_node,{}};
            if(type.builtin.empty()) {
                field.nested=follow(type.binding.symbol,type.fields);
                layout.depth=std::max(layout.depth,1+compile(field.nested).depth);
                if(layout.depth>64) resource_error("contract_depth");
            } else if(!json_types.count(type.builtin)) config_error("unsupported contract type: "+type.builtin);
            if(!node.children.empty()) field.literal=literal(node.children.front(),field.kind);
            layout.fields.push_back(std::move(field));
        }
        compiling.erase(id);
        return layouts.emplace(id,std::move(layout)).first->second;
    }
public:
    Contracts(const ProgramData& p,std::atomic<bool>& stop):program(p),cancelled(stop) {}
    void bind(ExecutionContext& c,const Value& config,Routes& routes) {
        const auto& root=WebRuntime::node(c,config);
        if(root.kind!="Map") config_error("contracts must be a JSON object");
        for(const auto& key:root.names) {
            point();
            const auto split=key.find(' ');
            if(split==std::string::npos || key.find(' ',split+1)!=std::string::npos) config_error("invalid route contract key");
            auto route=routes.find({key.substr(0,split),key.substr(split+1)});
            if(route==routes.end()) config_error("contract refers to unknown route: "+key);
            const auto contract=WebRuntime::get(c,config,key);
            const auto& entry=WebRuntime::node(c,contract);
            if(entry.kind!="Map") config_error("route contract must be an object");
            for(const auto& field:entry.names) {
                const auto value=WebRuntime::get(c,contract,field);
                if(field=="request") {
                    if(route->first.first!="POST") config_error("request contract requires POST");
                    route->second.request=named(text(c,value));
                } else if(field=="responses") {
                    const auto& responses=WebRuntime::node(c,value);
                    if(responses.kind!="Map") config_error("responses contract must be an object");
                    for(const auto& status:responses.names) {
                        if(status.size()!=3 || !std::all_of(status.begin(),status.end(),[](char ch){return ch>='0' && ch<='9';}) ||
                           !response_status(std::stoi(status))) config_error("invalid response contract status");
                        route->second.responses.emplace(std::stoi(status),named(text(c,WebRuntime::get(c,value,status))));
                    }
                } else config_error("unknown route contract field: "+field);
            }
            if(route->second.request==no_node && route->second.responses.empty()) config_error("empty route contract");
        }
    }
    Value convert(ExecutionContext& c,NodeId id,const Value& value,const std::string& path="body",std::size_t depth=1) const {
        c.heap.state->check("value_depth",depth);
        const auto& node=WebRuntime::node(c,value);
        if(!object_kind(node)) throw Violation{path,"type"};
        const auto& fields=layouts.at(id).fields;
        for(const auto& key:node.names) {
            c.heap.state->point();
            if(std::none_of(fields.begin(),fields.end(),[&](const Field& f){return f.name==key;})) throw Violation{child_path(path,key),"unknown"};
        }
        auto result=WebRuntime::map(c);
        for(const auto& field:fields) {
            const auto target=child_path(path,field.name);
            auto child=WebRuntime::get(c,value,field.name);
            if(!child) {
                if(!field.literal) throw Violation{target,"missing"};
                child=WebRuntime::parse(c,*field.literal);
            }
            if(field.nested!=no_node) child=convert(c,field.nested,child,target,depth+1);
            else if(WebRuntime::node(c,child).kind!=field.kind) throw Violation{target,"type"};
            WebRuntime::put(c,result,field.name,child);
        }
        return result;
    }
    std::string openapi(const Routes& routes) const {
        constexpr std::size_t max_bytes=1U<<20;
        std::string output=R"({"openapi":"3.1.1","info":{"title":"ZZY shape contracts","version":"1"},"paths":{)";
        std::map<std::string,std::map<std::string,const Route*>> paths;
        for(const auto& [key,route]:routes) paths[key.second][key.first=="GET"?"get":"post"]=&route;
        bool first_path=true;
        std::size_t ordinal=0;
        for(const auto& [path,operations]:paths) {
            comma(output,first_path);
            output+=quote(path)+":{";
            bool first_operation=true;
            for(const auto& [method,route]:operations) {
                point();
                comma(output,first_operation);
                output+=quote(method)+R"(:{"operationId":)"+quote(method+"_"+spelling(ast(route->function).token)+"_"+std::to_string(ordinal++));
                if(route->request!=no_node) output+=R"(,"requestBody":{"required":true,"content":)"+content_schema(schema_ref(route->request))+"}";
                output+=R"(,"responses":{"default":{"description":"Uncontracted response or adapter error"})";
                for(int status:{200,400,405,408,413,415,422,431,500,503,504}) {
                    if(status==200 || route->responses.count(status)) continue;
                    const auto schema=error_schema(status,*route);
                    if(!schema.empty()) output+=","+quote(std::to_string(status))+R"(:{"description":"Adapter error or uncontracted business response"})";
                }
                for(const auto& [status,shape]:route->responses) {
                    auto schema=schema_ref(shape);
                    const auto adapter=error_schema(status,*route);
                    if(!adapter.empty()) schema="{\"anyOf\":["+schema+","+adapter+"]}";
                    output+=","+quote(std::to_string(status))+R"(:{"description":"Business body contract or documented adapter error","content":)"+content_schema(schema)+"}";
                    if(output.size()>max_bytes) resource_error("openapi_bytes");
                }
                output+="}}";
            }
            output+='}';
            if(output.size()>max_bytes) resource_error("openapi_bytes");
        }
        output+=R"(},"components":{"schemas":{)";
        bool first_layout=true;
        for(const auto& [id,layout]:layouts) {
            comma(output,first_layout);
            output+=quote("Shape"+std::to_string(id))+R"(:{"type":"object","additionalProperties":false,"x-zzy-type":"shape-layout-as-Map","properties":{)";
            bool first_field=true;
            for(const auto& field:layout.fields) {
                point();
                comma(output,first_field);
                output+=quote(field.name)+":";
                if(field.nested!=no_node) output+=schema_ref(field.nested);
                else {
                    output+="{\"type\":"+quote(json_types.at(field.kind))+",\"x-zzy-type\":"+quote(field.kind);
                    if(field.kind=="Int") output+=R"(,"minimum":-9007199254740991,"maximum":9007199254740991)";
                    if(field.kind=="Array") output+=R"(,"items":{})";
                    if(field.kind=="Map") output+=R"(,"additionalProperties":true)";
                    if(field.literal) output+=",\"default\":"+*field.literal;
                    output+='}';
                }
                if(output.size()>max_bytes) resource_error("openapi_bytes");
            }
            output+=R"(},"required":[)";
            first_field=true;
            for(const auto& field:layout.fields) if(!field.literal) {comma(output,first_field);output+=quote(field.name);}
            output+="]}";
        }
        output+=R"(}},"x-zzy-rules":{"numeric-tags":"Int rejects Float including 1.0. Float rejects Int. Bool is distinct. Generic JSON Schema cannot enforce these tags.","json-boundary":"Finite Float, safe Int, Unicode scalar strings and resource limits also apply in open Array and Map.","defaults":"ZZY fills missing fields. Null is distinct from missing. OpenAPI default is annotation only.","errors":"422 contract_input before business. 500 contract_response after business. Adapter failures bypass body contracts.","business":"ZZY owns business rules. Unlisted statuses have no shape validation."}})";
        if(output.size()>max_bytes) resource_error("openapi_bytes");
        return output;
    }
};
}
