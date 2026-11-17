#pragma once
#include "frontend_diagnostic.hpp"
#include "sha256.hpp"
#include <atomic>
#include <map>
#include <set>
namespace zzy {
struct ResourcePolicy {
    std::map<std::string,std::uint64_t> limits={
        {"source_file_bytes",2097152},{"source_total_bytes",16777216},{"module_count",128},{"import_depth",32},
        {"tokens_per_file",250000},{"ast_nodes_total",500000},{"syntax_depth",64},{"numeric_digits",4096},
        {"integer_bits",65536},{"quantity_exponent_abs",64},{"call_depth",64},{"value_depth",64},
        {"container_items",1000000},{"text_codepoints",4194304},{"io_payload_bytes",16777216},
        {"runtime_objects",200000},{"runtime_slots",2000000},{"runtime_payload_bytes",134217728},
        {"stdout_bytes",1048576},{"stderr_bytes",1048576},{"program_cache_entries",32},{"program_cache_bytes",67108864}};
    std::string canonical_json() const {
        std::string out="{\"effective_decimal_digits\":"+std::to_string(limits.at("numeric_digits"))+",\"host_decimal_digits\":0,\"limits\":{";
        bool first=true;
        for(const auto& item:limits) {if(!first) out+=',';first=false;out+=quote(item.first)+":"+std::to_string(item.second);}
        return out+"},\"policy_version\":1,\"profile\":\"default-v1\"}";
    }
    std::string fingerprint() const {return sha256(canonical_json());}
};
// Deliberately narrow, non-recursive parser for the frozen limits-file format.
// This is host configuration, not a ZZY parser or a general JSON value API.
class PolicyParser {
    std::u32string text;
    std::size_t index=0;
    [[noreturn]] void fail() const {throw FrontendError("E401","invalid resource configuration");}
    void ws() {while(index<text.size() && (text[index]==U' ' || text[index]==U'\t' || text[index]==U'\r' || text[index]==U'\n')) ++index;}
    bool take(char32_t c) {ws();if(index<text.size() && text[index]==c) {++index;return true;}return false;}
    void expect(char32_t c) {if(!take(c)) fail();}
    char32_t hex4() {
        char32_t value=0;
        for(int j=0;j<4;++j) {
            if(index==text.size()) fail();
            const auto c=text[index++];
            const int digit=c>=U'0' && c<=U'9'?static_cast<int>(c-U'0'):
                c>=U'a' && c<=U'f'?static_cast<int>(c-U'a')+10:c>=U'A' && c<=U'F'?static_cast<int>(c-U'A')+10:-1;
            if(digit<0) fail();
            value=(value<<4)|static_cast<unsigned>(digit);
        }
        return value;
    }
    std::string string() {
        expect(U'"');std::u32string out;
        while(index<text.size()) {
            auto c=text[index++];
            if(c==U'"') return encode_utf8(out);
            if(c<32) fail();
            if(c==U'\\') {
                if(index==text.size()) fail();
                c=text[index++];
                switch(c) {
                case U'"':case U'\\':case U'/':break;
                case U'b':c=U'\b';break;case U'f':c=U'\f';break;case U'n':c=U'\n';break;case U'r':c=U'\r';break;case U't':c=U'\t';break;
                case U'u':
                    c=hex4();
                    if(c>=0xd800 && c<=0xdbff) {
                        if(index+2>text.size() || text[index++]!=U'\\' || text[index++]!=U'u') fail();
                        const auto low=hex4();if(low<0xdc00 || low>0xdfff) fail();
                        c=0x10000+((c-0xd800)<<10)+(low-0xdc00);
                    } else if(c>=0xdc00 && c<=0xdfff) fail();
                    break;
                default:fail();
                }
            }
            out+=c;
        }
        fail();
    }
    std::uint64_t integer() {
        ws();const auto start=index;
        std::uint64_t value=0;
        while(index<text.size() && text[index]>=U'0' && text[index]<=U'9') {
            const auto digit=static_cast<unsigned>(text[index++]-U'0');
            if(value>(UINT64_C(9223372036854775807)-digit)/10) fail();
            value=value*10+digit;
        }
        if(index==start || (index-start>1 && text[start]==U'0')) fail();
        return value;
    }
public:
    explicit PolicyParser(std::string_view bytes) {
        if(bytes.size()>65536) fail();
        try {text=decode_utf8(bytes).text;}catch(const std::invalid_argument&) {fail();}
    }
    ResourcePolicy parse() {
        ResourcePolicy policy;
        expect(U'{');std::set<std::string> fields;
        if(!take(U'}')) {
            do {
                const auto name=string();if(!fields.insert(name).second) fail();expect(U':');
                if(name=="policy_version") {if(integer()!=1) fail();}
                else if(name=="limits") {
                    expect(U'{');std::set<std::string> keys;
                    if(!take(U'}')) {
                        do {
                            const auto key=string();if(!keys.insert(key).second || !policy.limits.count(key)) fail();
                            expect(U':');const auto value=integer();if(!value) fail();policy.limits.at(key)=value;
                        } while(take(U','));
                        expect(U'}');
                    }
                } else fail();
            } while(take(U','));
            expect(U'}');
        }
        ws();if(index!=text.size() || fields!=std::set<std::string>{"policy_version","limits"}) fail();
        return policy;
    }
};
class FrontendMeter {
    const ResourcePolicy& policy_;
    std::atomic<bool>& cancelled_;
public:
    std::uint64_t source_total=0,module_count=0,stdout_used=0;
    FrontendMeter(const ResourcePolicy& policy,std::atomic<bool>& cancelled):policy_(policy),cancelled_(cancelled) {}
    const ResourcePolicy& policy() const {return policy_;}
    void safe_point() const {if(cancelled_.load(std::memory_order_relaxed)) throw Cancelled{};}
    void check(const std::string& key,std::uint64_t requested,std::optional<std::string> file={},std::optional<Span> span={}) const {
        safe_point();const auto limit=policy_.limits.at(key);
        if(requested>limit) throw FrontendError("E211","resource limit exceeded: "+key+", limit="+std::to_string(limit)+", requested="+std::to_string(requested),std::move(file),span);
    }
    void write(std::ostream& stream,const std::string& record) {
        check("stdout_bytes",stdout_used+record.size());
        stdout_used+=record.size();stream<<record;stream.flush();
    }
};
}
