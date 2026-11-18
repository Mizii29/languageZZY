#pragma once
#include <locale.h>

namespace zzy {
namespace json_detail {
struct Invalid : std::runtime_error {using std::runtime_error::runtime_error;};
inline bool digit(char32_t c) {return c>=U'0' && c<=U'9';}
inline bool space(char32_t c) {return c==U' ' || c==U'\t' || c==U'\r' || c==U'\n';}
struct NumericLocale {
    _locale_t value=_create_locale(LC_NUMERIC,"C");
    NumericLocale() {if(!value) throw std::bad_alloc();}
    ~NumericLocale() {_free_locale(value);}
    NumericLocale(const NumericLocale&)=delete;
    NumericLocale& operator=(const NumericLocale&)=delete;
};
}

inline void ExecutionContext::map_insert(const Value& map,std::string key,const Value& key_value,const Value& value,NodeId site) {
    auto& n=object(map);
    check("container_items",n.names.size()+1,site);
    Lease space(heap.state,{0,2,key.size()},site);
    if(n.names.size()==n.names.capacity()) n.names.reserve(n.names.size()*2+1);
    if(n.edges.size()+2>n.edges.capacity()) n.edges.reserve(n.edges.size()*2+2);
    n.names.push_back(std::move(key));
    n.edges.push_back(key_value.ref());
    n.edges.push_back(value.ref());
    const auto charge=space.transfer();
    n.charge=n.charge+charge;
    ++n.version;
}

struct ExecutionContext::JsonReader {
    struct Frame {
        Value container;
        char32_t end;
        bool first=true;
        std::set<std::u32string_view> keys;
        Lease workspace;
        Frame(Value v,char32_t end_,ExecutionContext& context,NodeId site):
            container(std::move(v)),end(end_),workspace(context.heap.state,{0,1,0},site) {}
    };
    ExecutionContext& c;
    NodeId site;
    std::u32string_view text;
    std::size_t index=0;
    std::vector<Frame> stack;

    JsonReader(ExecutionContext& context,NodeId at,std::u32string_view input):c(context),site(at),text(input) {}
    char32_t peek() const {return index<text.size()?text[index]:U'\0';}
    void tick() const {if((index&4095)==0) c.point();}
    void spaces() {while(json_detail::space(peek())) {tick();++index;}}
    bool take(char32_t ch) {spaces();if(peek()!=ch) return false;++index;return true;}
    char32_t hex() {
        char32_t value=0;
        for(int i=0;i<4;++i) {
            const auto cp=peek();
            if(cp>=U'0' && cp<=U'9') value=(value<<4)+(cp-U'0');
            else if(cp>=U'a' && cp<=U'f') value=(value<<4)+(cp-U'a'+10);
            else if(cp>=U'A' && cp<=U'F') value=(value<<4)+(cp-U'A'+10);
            else throw json_detail::Invalid("非法 Unicode 转义");
            ++index;
        }
        return value;
    }
    char32_t character() {
        tick();
        auto cp=text[index++];
        if(cp<32) throw json_detail::Invalid("JSON String 含控制字符");
        if(cp!=U'\\') return cp;
        if(index==text.size()) throw json_detail::Invalid("未结束的 JSON 转义");
        switch(text[index++]) {
            case U'"':return U'"'; case U'\\':return U'\\'; case U'/':return U'/';
            case U'b':return U'\b'; case U'f':return U'\f'; case U'n':return U'\n';
            case U'r':return U'\r'; case U't':return U'\t';
            case U'u':
                cp=hex();
                if(cp>=0xd800 && cp<=0xdbff) {
                    if(text.substr(index,2)!=U"\\u") throw json_detail::Invalid("孤立代理码点");
                    index+=2;
                    const auto low=hex();
                    if(low<0xdc00 || low>0xdfff) throw json_detail::Invalid("孤立代理码点");
                    return 0x10000+((cp-0xd800)<<10)+(low-0xdc00);
                }
                if(cp>=0xdc00 && cp<=0xdfff) throw json_detail::Invalid("孤立代理码点");
                return cp;
            default:throw json_detail::Invalid("非法 JSON 转义");
        }
    }
    Value string_value() {
        spaces();
        const auto begin=index;
        if(!take(U'"')) throw json_detail::Invalid("需要 JSON String");
        std::size_t count=0;
        while(index<text.size() && peek()!=U'"') {
            (void)character();
            c.check("text_codepoints",++count,site);
        }
        if(index==text.size()) throw json_detail::Invalid("未结束的 JSON String");
        const auto end=++index;
        // Preserve the raw token plus decoded output working budget.
        Lease raw(c.heap.state,{0,0,4*(end-begin)},site);
        Lease decoded(c.heap.state,{0,0,4*count},site);
        std::u32string value;
        value.reserve(count);
        index=begin+1;
        while(index<end-1) value+=character();
        index=end;
        decoded.release();
        return c.string(std::move(value),site);
    }
    Value number() {
        const auto start=index;
        const bool negative=peek()==U'-';
        if(negative) ++index;
        if(!json_detail::digit(peek())) throw json_detail::Invalid("非法 JSON 值");
        std::size_t digits=0;
        auto consume_digit=[&] {tick();++index;c.check("numeric_digits",++digits,site);};
        if(peek()==U'0') consume_digit();
        else while(json_detail::digit(peek())) consume_digit();
        const auto tail=[&](auto test) {
            auto i=index+1;
            if(test && i<text.size() && (text[i]==U'+' || text[i]==U'-')) ++i;
            return i<text.size() && json_detail::digit(text[i]);
        };
        bool floating=false;
        if(peek()==U'.' && tail(false)) {
            floating=true;++index;
            while(json_detail::digit(peek())) consume_digit();
        }
        if((peek()==U'e' || peek()==U'E') && tail(true)) {
            floating=true;++index;
            if(peek()==U'+' || peek()==U'-') ++index;
            while(json_detail::digit(peek())) consume_digit();
        }
        Lease raw(c.heap.state,{0,0,4*(index-start)},site);
        if(floating) {
            std::string token;
            token.reserve(index-start);
            for(auto i=start;i<index;++i) {if((i&4095)==0) c.point();token+=static_cast<char>(text[i]);}
            const json_detail::NumericLocale locale;
            char* end=nullptr;
            const auto n=_strtod_l(token.c_str(),&end,locale.value);
            if(end!=token.c_str()+token.size() || !std::isfinite(n)) throw json_detail::Invalid("JSON Float 必须有限");
            return c.real(n,site);
        }
        auto result=c.zero_;
        for(auto i=start+(negative?1:0);i<index;++i) {
            c.point();
            result=c.publish_int(c.arithmetic("MULTIPLY",c.object(result).integer,BigInt(10),site),site);
            result=c.publish_int(c.arithmetic("PLUS",c.object(result).integer,BigInt(text[i]-U'0'),site),site);
        }
        if(negative && !c.object(result).integer.zero()) {
            Lease scratch(c.heap.state,{0,0,c.int_bytes(c.object(result).integer)},site);
            auto value=-c.object(result).integer;
            scratch.release();
            result=c.integer(std::move(value),site);
        }
        return result;
    }
    Value value() {
        c.point();spaces();
        if(peek()==U'"') return string_value();
        if(peek()==U'[' || peek()==U'{') {
            c.check("value_depth",stack.size()+1,site);
            const bool array=peek()==U'[';
            ++index;
            auto container=c.make(array?"Array":"Map",{1,0,0},site);
            stack.emplace_back(container,array?U']':U'}',c,site);
            return container;
        }
        if(text.substr(index,4)==U"true") {index+=4;return c.true_;}
        if(text.substr(index,5)==U"false") {index+=5;return c.false_;}
        if(text.substr(index,4)==U"null") {index+=4;return c.null_;}
        return number();
    }
    Value read() {
        c.check("io_payload_bytes",c.utf8_size(text),site);
        auto root=value();
        while(!stack.empty()) {
            c.point();
            const auto at=stack.size()-1;
            const auto end=stack[at].end;
            if(take(end)) {stack.pop_back();continue;}
            auto& cursor=stack[at];
            if(!cursor.first && !take(U',')) throw json_detail::Invalid("需要逗号或容器结尾");
            cursor.first=false;
            const auto parent=cursor.container;
            const bool map=end==U'}';
            const auto& container=c.object(parent);
            c.check("container_items",(map?container.names.size():container.edges.size())+1,site);
            if(map) {
                auto key=string_value();
                const auto& chars=c.object(key).characters;
                if(cursor.keys.count(chars)) throw json_detail::Invalid("JSON 重复键");
                if(!take(U':')) throw json_detail::Invalid("需要冒号");
                cursor.workspace.grow({0,1,0},site);
                cursor.keys.insert(chars);
                auto child=value();
                Lease encoded(c.heap.state,{0,0,c.utf8_size(chars)},site);
                auto name=encode_utf8(chars);
                encoded.release();
                c.map_insert(parent,std::move(name),key,child,site);
            } else {
                auto child=value();
                c.append(parent,child,site);
            }
        }
        spaces();
        if(index!=text.size()) throw json_detail::Invalid("JSON 尾部有多余数据");
        return root;
    }
};

struct ExecutionContext::JsonWriter {
    struct Frame {Value value;std::size_t index=0;bool entered=false;Lease workspace;};
    ExecutionContext& c;
    NodeId site;
    std::u32string output;
    std::size_t bytes=0;
    Lease buffer;
    std::vector<Frame> stack;
    std::set<std::uint64_t> active;
    JsonWriter(ExecutionContext& context,NodeId at):c(context),site(at),buffer(context.heap.state,{},at) {}

    void reserve(std::size_t points,std::size_t size) {
        c.check("text_codepoints",output.size()+points,site);
        c.check("io_payload_bytes",bytes+size,site);
        buffer.grow({0,0,4*points},site);
        bytes+=size;
    }
    void punctuation(char32_t cp) {reserve(1,1);output+=cp;}
    void ascii(std::string_view text) {
        reserve(text.size(),text.size());
        for(std::size_t i=0;i<text.size();++i) {if((i&4095)==0) c.point();output+=static_cast<unsigned char>(text[i]);}
    }
    static char32_t simple_escape(char32_t cp) {
        switch(cp) {
            case U'"':case U'\\':return cp;
            case U'\b':return U'b'; case U'\f':return U'f'; case U'\n':return U'n'; case U'\r':return U'r'; case U'\t':return U't';
            default:return 0;
        }
    }
    void quoted(std::u32string_view text) {
        std::size_t points=2,size=2;
        for(std::size_t i=0;i<text.size();++i) {
            if((i&4095)==0) c.point();
            const auto cp=text[i];
            const std::size_t escape=simple_escape(cp)?2:cp<32?6:0;
            points+=escape?escape:1;
            size+=escape?escape:utf8_width(cp);
        }
        reserve(points,size);
        output+=U'"';
        for(std::size_t i=0;i<text.size();++i) {
            if((i&4095)==0) c.point();
            const auto cp=text[i];
            if(const auto escaped=simple_escape(cp)) {output+=U'\\';output+=escaped;}
            else if(cp<32) {output+=U"\\u00";output+=U"0123456789abcdef"[cp>>4];output+=U"0123456789abcdef"[cp&15];}
            else output+=cp;
        }
        output+=U'"';
    }
    void push(Value value) {stack.push_back({std::move(value),0,false,Lease(c.heap.state,{0,1,0},site)});}
    Value write(const Value& value) {
        push(value);
        while(!stack.empty()) {
            c.point();
            auto& cursor=stack.back();
            const auto& n=c.object(cursor.value);
            const bool array=n.kind=="Array",map=n.kind=="Map",shape=n.kind=="Shape";
            if(!array && !map && !shape) {
                if(n.kind=="String") quoted(n.characters);
                else if(n.kind=="Int" || n.kind=="Float" || n.kind=="Bool" || n.kind=="Null") ascii(c.scalar_text(cursor.value,site));
                else throw json_detail::Invalid(n.kind+" 不能序列化");
                stack.pop_back();
                continue;
            }
            if(!cursor.entered) {
                c.check("value_depth",stack.size(),site);
                if(!active.insert(cursor.value.ref().id).second) throw json_detail::Invalid("循环引用不能序列化");
                cursor.entered=true;
                punctuation(array?U'[':U'{');
            }
            const auto count=array?n.edges.size():n.names.size();
            if(cursor.index==count) {
                punctuation(array?U']':U'}');
                active.erase(cursor.value.ref().id);
                stack.pop_back();
                continue;
            }
            const auto i=cursor.index++;
            if(i) punctuation(U',');
            if(map) quoted(c.object(c.heap.pin(n.edges[2*i])).characters);
            else if(shape) {
                const auto& name=n.names[i];
                Lease key(c.heap.state,{0,0,4*c.codepoints(name)},site);
                std::u32string chars;
                for(std::size_t j=0;j<name.size();) chars+=utf8_next(name,j);
                quoted(chars);
            }
            if(!array) punctuation(U':');
            push(c.heap.pin(n.edges[array?i:map?2*i+1:i+1]));
        }
        buffer.release();
        return c.string(std::move(output),site);
    }
};

inline Value ExecutionContext::json_library(const std::string& name,const Value& value,NodeId site) {
    try {
        auto converted=name=="data.parse"?JsonReader(*this,site,object(value).characters).read():JsonWriter(*this,site).write(value);
        return result(true,converted,site);
    } catch(const json_detail::Invalid& failure) {
        return result(false,string(failure.what(),site),site);
    }
}
}
