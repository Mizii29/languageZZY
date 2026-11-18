#pragma once
#include "runtime_heap.hpp"
#include "host_metadata.hpp"
#include "core_hosts.hpp"
#include <deque>
#include <iomanip>
#include <sstream>
#include <charconv>
namespace zzy {
class ExecutionContext {
public:
    using Done=std::function<void(Value)>;
    using Next=std::function<void()>;
    const Program snapshot;
    const ProgramData& program;
    RuntimeHeap heap;
private:
    struct Type {std::string name;Value nominal;};
    struct Binding {Value raw;Type type;Lease slot;};
    struct Frame {Value function;std::vector<Value> locals;std::vector<Type> types;Lease space;NodeId call=no_node;bool lazy=false;std::size_t boundary=0;};
    struct Task {Next action;};
    std::vector<Task> tasks;
    std::map<NodeId,Binding> globals;
    std::vector<std::shared_ptr<Frame>> calls;
    std::vector<std::pair<std::size_t,std::size_t>> query_items;
    std::shared_ptr<Frame> frame;
    std::map<std::string,Value> builtins;
    std::map<NodeId,Value> modules;
    Value null_,true_,false_,zero_,current;
    std::ostream& output;std::ostream& errors;
    std::istream* input;
    std::uint64_t stdout_used=0,stderr_used=0;
    std::string flow;Value returned;NodeId return_site=no_node;
    bool diagnostic_json;
    friend struct ExecutionProbe;
    const AstNode& ast(NodeId id) const {return program.nodes.at(id);}
    RuntimeNode& object(const Value& v) const {return heap.get(v);}
    [[noreturn]] void error(NodeId site,const std::string& code,const std::string& text) const {throw RuntimeError(code,text,site);}
    void check(const std::string& key,std::uint64_t n,NodeId site) const {heap.state->check(key,n,site);}
    void point() const {heap.state->point();}
    void push(Next action) {tasks.push_back({std::move(action)});}
    Value make(std::string kind,Charge charge,NodeId site,std::vector<Value> children={}) {
        RuntimeNode n;n.kind=std::move(kind);for(const auto& v:children) n.edges.push_back(v.ref());return heap.allocate(std::move(n),charge,site);
    }
    Value boolean(bool b) const {return b?true_:false_;}
    void typecheck(const Type& t,const Value& v,NodeId site,bool full=true) const {
        if(t.name.empty()) return;
        const auto& n=object(v);bool valid=n.kind==t.name;
        if(t.nominal) valid=(n.kind=="Shape" || n.kind=="Machine") && !n.edges.empty() && n.edges[0]==t.nominal.ref();
        if(!valid) {RuntimeError e("E201","expected "+t.name+", got "+n.kind,site);e.expression_span=full;throw e;}
    }
    void typecheck(const std::string& kind,const Value& v,NodeId site) const {typecheck(Type{kind,{}},v,site);}
    Value raw(const Reference& r,NodeId site) {
        if(!r.builtin.empty()) return builtin(r.builtin,site);
        if(r.kind=="global") {auto it=globals.find(r.symbol);if(it==globals.end()) error(site,"E302","name not initialized");return it->second.raw;}
        if(!frame) throw std::logic_error("missing execution frame");
        if(r.kind=="self") return frame->function;
        if(r.kind=="capture") return heap.pin(object(frame->function).edges.at(r.key));
        if(r.kind=="local") {auto v=frame->locals.at(r.key);if(!v) error(site,"E302","name not initialized");return v;}
        throw std::logic_error("unknown reference layout");
    }
    Value read(const Reference& r,NodeId site) {auto v=raw(r,site);return object(v).kind=="Cell"?heap.pin(object(v).edges.at(0)):v;}
    Type annotation(NodeId site) {
        const auto it=program.annotations.find(site);if(it==program.annotations.end()) return {};
        const auto& a=it->second;if(!a.builtin.empty()) return {a.builtin,{}};
        auto v=read(a.binding,site);for(const auto& f:a.fields) v=field(v,f,site);
        if(object(v).kind!="Definition" && object(v).kind!="MachineDefinition") error(site,"E201","annotation is not a definition");
        return {object(v).name,v};
    }
    void define(NodeId id,Value value,Type type={},Lease reserved={}) {
        const auto& info=program.symbols.at(id);
        if(info.cell) {
            std::vector<Value> edges{value};if(type.nominal) edges.push_back(type.nominal);
            auto cell=make("Cell",{0,edges.size(),0},id,edges);object(cell).type_names={type.name};object(cell).type_nominals={type.nominal?1U:no_node};value=std::move(cell);
        }
        if(info.owner==no_node) {
            if(!reserved) reserved=Lease(heap.state,{0,1,0},id);
            Binding b{std::move(value),std::move(type),std::move(reserved)};globals.insert_or_assign(id,std::move(b));
        }
        else {if(!frame) throw std::logic_error("missing local frame");frame->locals.at(info.slot)=std::move(value);frame->types.at(info.slot)=std::move(type);}
    }
    Value integer(BigInt n,NodeId site) {
        check("integer_bits",n.bits(),site);if(n.zero() && zero_) return zero_;
        RuntimeNode v;v.kind="Int";v.integer=std::move(n);const auto bytes=(v.integer.bits()+7)/8;
        return heap.allocate(std::move(v),{0,0,bytes},site);
    }
    Value literal_int(const std::vector<std::uint32_t>& words,NodeId site) {
        if(words.empty()) return zero_;
        const auto bits=(words.size()-1)*32+BigInt::word_bits(words.back());check("integer_bits",bits,site);
        Lease space(heap.state,{0,0,(bits+7)/8},site);BigInt value(words);space.release();return integer(std::move(value),site);
    }
    Value real(double n,NodeId site) {
        if(!std::isfinite(n)) error(site,"E208","Float must be finite");RuntimeNode v;v.kind="Float";v.real=n;return heap.allocate(std::move(v),{0,0,8},site);
    }
    Value string(std::u32string n,NodeId site) {
        check("text_codepoints",n.size(),site);const auto size=n.size();RuntimeNode v;v.kind="String";v.characters=std::move(n);return heap.allocate(std::move(v),{0,0,4*size},site);
    }
    std::size_t codepoints(std::string_view text) const {
        std::size_t size=0;for(std::size_t i=0;i<text.size();++i) {if((i&4095)==0) point();if((static_cast<unsigned char>(text[i])&0xc0)!=0x80) ++size;}return size;
    }
    Value string(const std::string& n,NodeId site) {
        const auto size=codepoints(n);check("text_codepoints",size,site);Lease space(heap.state,{0,0,4*size},site);
        auto decoded=decode_utf8(n,false,[this]{point();}).text;space.release();return string(std::move(decoded),site);
    }
    Value array(const std::vector<Value>& values,NodeId site) {check("container_items",values.size(),site);return make("Array",{1,values.size(),0},site,values);}
    void append(const Value& a,const Value& v,NodeId site) {
        auto& n=object(a);if(n.active) error(site,"E206","cannot resize an actively traversed Array");check("container_items",n.edges.size()+1,site);
        Lease space(heap.state,{0,1,0},site);n.edges.push_back(v.ref());n.charge.slots+=space.transfer().slots;++n.version;
    }
    Value result(bool success,const Value& v,NodeId site) {
        if(!success) typecheck("String",v,site);auto r=make("Result",{0,1,0},site,{v});object(r).flag=success;return r;
    }
    Value builtin(const std::string& name,NodeId site) {
        auto it=builtins.find(name);if(it!=builtins.end()) return it->second;
        if(name=="array.Stats") {
            auto v=make("Definition",{1,4,0},site);auto& n=object(v);n.name=name;
            n.names={"count","sum","min","max"};n.type_names={"Int","Int","",""};
            n.type_nominals={no_node,no_node,no_node,no_node};
            builtins.emplace(name,v);return v;
        }
        const bool ns=name=="io" || name=="array" || name=="data" || name=="text" || name=="math" || name=="unit" || name=="sketch" || name=="db";
        auto v=make(ns?"Namespace":"Function",{1,1,0},site);object(v).name=name;builtins.emplace(name,v);return v;
    }
    Value field(const Value& owner,const std::string& name,NodeId site,bool write=false) {
        auto& n=object(owner);
        if(n.kind=="Namespace") {
            if(write) error(site,"E203","namespace is read only");const auto qualified=n.name+"."+name;bool known=false;
            for(const auto& h:static_hosts) if(h.name==qualified) {known=true;break;}
            if(qualified=="array.Stats") return builtin(qualified,site);
            if(qualified=="sketch.Canvas" || qualified=="sketch.Pen" ||
               qualified=="sketch.Layer" || qualified=="sketch.Color" || qualified=="sketch.Drawing" ||
               qualified=="sketch.LayerInfo" || qualified=="sketch.Position")
                error(site,"E402","native host capability not implemented: "+qualified);
            if(!known) error(site,"E302","unknown namespace member: "+name);return builtin(qualified,site);
        }
        if(n.kind=="Machine") {if(name!="state") error(site,"E204","unknown Machine field");if(write) error(site,"E203","Machine state is read only");return heap.pin(n.edges.at(1));}
        if(n.kind!="Shape" && n.kind!="Module") error(site,"E201","field access needs a shape/module");
        if(write && n.kind=="Module") error(site,"E203","module is read only");
        const auto it=std::find(n.names.begin(),n.names.end(),name);if(it==n.names.end()) error(site,n.kind=="Module"?"E303":"E302","unknown field: "+name);
        return heap.pin(n.edges.at(static_cast<std::size_t>(it-n.names.begin())+(n.kind=="Shape"?1:0)));
    }
    std::size_t index_number(const Value& v,std::size_t count,NodeId site) const {
        typecheck(Type{"Int",{}},v,site,false);const auto& i=object(v).integer;
        if(i.sign()<0 || i>=BigInt(static_cast<std::int64_t>(count))) error(site,"E204","index out of bounds");
        return static_cast<std::size_t>(std::stoull(i.decimal()));
    }
    Value index(const Value& owner,const Value& key,NodeId site,bool write=false) {
        auto& n=object(owner);if(n.kind!="Array" && n.kind!="String") error(site,"E201","index needs Array/String");
        typecheck(Type{"Int",{}},key,site,false);if(write && n.kind=="String") error(site,"E203","String is immutable");
        const auto i=index_number(key,n.kind=="Array"?n.edges.size():n.characters.size(),site);
        return n.kind=="Array"?heap.pin(n.edges[i]):string(std::u32string(1,n.characters[i]),site);
    }
    Value make_function(NodeId id) {
        const auto& plan=program.functions.at(id);std::vector<Value> captures;
        for(const auto& c:plan.captures) captures.push_back(raw(c.source,id));
        std::vector<Type> types;
        if(ast(id).kind!="lazy") {for(std::size_t i=0;i+1<ast(id).children.size();++i) types.push_back(annotation(ast(id).children[i]));types.push_back(annotation(id));}
        std::vector<std::size_t> nominal;
        for(const auto& t:types) {nominal.push_back(t.nominal?captures.size():no_node);if(t.nominal) captures.push_back(t.nominal);}
        auto v=make(ast(id).kind=="lazy"?"Lazy":"Function",{1,captures.size()+(ast(id).kind=="lazy"?1:0),0},id,captures);
        for(const auto& t:types) object(v).type_names.push_back(t.name);object(v).type_nominals=std::move(nominal);
        auto& n=object(v);n.syntax=id;n.name=spelling(ast(id).token);return v;
    }
    Type stored_type(const Value& definition,std::size_t index) {
        const auto& n=object(definition);const auto nominal=n.type_nominals.at(index);
        return {n.type_names.at(index),nominal==no_node?Value{}:heap.pin(n.edges.at(nominal))};
    }
    static std::size_t int_bytes(const BigInt& n) {return (n.bits()+7)/8;}
    struct HeldInt {BigInt value;Lease space;};
    HeldInt arithmetic(const std::string& op,const BigInt& a,const BigInt& b,NodeId site) {
        const auto cancel=[this] {point();};std::size_t width=0;BigInt value;
        if(op=="PLUS" || op=="MINUS") {
            if((op=="PLUS" && a.sign()!=b.sign() && BigInt::magnitude_compare(a,b)==0) || (op=="MINUS" && a==b)) return {};
            Lease scratch(heap.state,{0,0,std::max(int_bytes(a),int_bytes(b))},site);
            width=a.sum_bits(b,op=="MINUS",cancel);
        } else if(op=="MULTIPLY") {
            if(a.zero() || b.zero()) return {};
            const auto upper=a.bits()+b.bits();check("integer_bits",upper-1,site);
            if(upper>heap.state->policy.limits.at("integer_bits") || !heap.state->fits({0,0,(upper+7)/8})) {
                Lease scratch(heap.state,{0,0,std::max(int_bytes(a),int_bytes(b))},site);width=a.product_bits(b,cancel);
            } else width=upper;
        } else {
            const auto max_bytes=std::max(int_bytes(a),int_bytes(b));
            if(b==BigInt(1) || b==BigInt(-1)) {
                Lease result(heap.state,{0,0,max_bytes},site);
                if(op=="REMAINDER") return {BigInt(),std::move(result)};
                return {b.sign()>0?a:-a,std::move(result)};
            }
            Lease scratch(heap.state,{0,0,2*max_bytes+int_bytes(b)},site);
            auto qr=a.divmod(b,cancel);value=op=="FLOOR_DIVIDE"?std::move(qr.first):std::move(qr.second);
            check("integer_bits",value.bits(),site);return {std::move(value),std::move(scratch)};
        }
        check("integer_bits",width,site);Lease result(heap.state,{0,0,(width+7)/8},site);
        if(op=="PLUS") value=a+b;else if(op=="MINUS") value=a-b;else value=a.multiply(b,cancel);
        check("integer_bits",value.bits(),site);return {std::move(value),std::move(result)};
    }
    Value publish_int(HeldInt data,NodeId site) {
        data.space.release();return integer(std::move(data.value),site);
    }
    int compare(const Value& a,const Value& b,NodeId site) {
        const auto& x=object(a);const auto& y=object(b);
        if(x.kind=="Int" && y.kind=="Int") return x.integer.compare(y.integer);
        if(x.kind=="Float" && y.kind=="Float") return x.real<y.real?-1:x.real>y.real?1:0;
        if(x.kind=="Int" && y.kind=="Float") return x.integer.compare(y.real);
        if(x.kind=="Float" && y.kind=="Int") return -y.integer.compare(x.real);
        if(x.kind=="String" && y.kind=="String") return x.characters<y.characters?-1:x.characters>y.characters?1:0;
        error(site,"E201","incompatible ordering operands");
    }
    Value binary(const std::string& op,Value a,Value b,NodeId site) {
        if(op=="EQUAL" || op=="NOT_EQUAL") {
            std::size_t depth=0;while(object(a).kind=="Result" && object(b).kind=="Result") {
                check("value_depth",++depth,site);if(object(a).flag!=object(b).flag) return boolean(op=="NOT_EQUAL");
                a=heap.pin(object(a).edges[0]);b=heap.pin(object(b).edges[0]);
            }
            const auto& x=object(a);const auto& y=object(b);bool equal=a.same(b);
            const bool numeric=(x.kind=="Int" || x.kind=="Float") && (y.kind=="Int" || y.kind=="Float");
            if(numeric) equal=compare(a,b,site)==0;
            else if(x.kind==y.kind) {
                if(x.kind=="String") equal=x.characters==y.characters;
                else if(x.kind=="Bool") equal=x.flag==y.flag;else if(x.kind=="Null") equal=true;
                else if(x.kind=="Range") {equal=true;for(std::size_t i=0;i<3;++i) equal=equal && object(heap.pin(x.edges[i])).integer==object(heap.pin(y.edges[i])).integer;}
                else if(x.kind=="Quantity") equal=x.length==y.length && x.time==y.time && x.rational.numerator==y.rational.numerator && x.rational.denominator==y.rational.denominator;
            }
            return boolean(op=="EQUAL"?equal:!equal);
        }
        if(object(a).kind=="Quantity" || object(b).kind=="Quantity") return quantity_binary(op,a,b,site);
        if(op=="INTERVAL") return range({a,b,integer(BigInt(1),site)},site);
        if(op=="LESS" || op=="LESS_EQUAL" || op=="GREATER" || op=="GREATER_EQUAL") {const int c=compare(a,b,site);return boolean(op=="LESS"?c<0:op=="LESS_EQUAL"?c<=0:op=="GREATER"?c>0:c>=0);}
        const auto& x=object(a);const auto& y=object(b);
        if(op=="PLUS" && x.kind=="String" && y.kind=="String") {const auto size=x.characters.size()+y.characters.size();check("text_codepoints",size,site);Lease space(heap.state,{0,0,4*size},site);auto text=x.characters+y.characters;space.release();return string(std::move(text),site);}
        if((x.kind!="Int" && x.kind!="Float") || (y.kind!="Int" && y.kind!="Float") || ((op=="FLOOR_DIVIDE" || op=="REMAINDER") && (x.kind!="Int" || y.kind!="Int"))) error(site,"E201","incompatible arithmetic operands");
        if((op=="DIVIDE" || op=="FLOOR_DIVIDE" || op=="REMAINDER") && (y.kind=="Int"?y.integer.zero():y.real==0)) error(site,"E205","zero divisor");
        if(x.kind=="Int" && y.kind=="Int" && op!="DIVIDE") return publish_int(arithmetic(op,x.integer,y.integer,site),site);
        const double left=x.kind=="Int"?x.integer.real():x.real,right=y.kind=="Int"?y.integer.real():y.real;
        if(!std::isfinite(left) || !std::isfinite(right)) error(site,"E208","Float promotion overflow");
        return real(op=="PLUS"?left+right:op=="MINUS"?left-right:op=="MULTIPLY"?left*right:left/right,site);
    }
    Value range(const std::vector<Value>& args,NodeId site) {
        for(std::size_t i=0;i<args.size();++i) typecheck(Type{"Int",{}},args[i],ast(site).kind=="call"?ast(site).children[i+1]:site,ast(site).kind=="call");
        if(object(args[2]).integer.zero()) error(site,"E208","zero Range step");
        return make("Range",{1,3,0},site,args);
    }
    Value quantity(Rational value,int length,int time,NodeId site) {
        check("integer_bits",value.numerator.bits(),site);check("integer_bits",value.denominator.bits(),site);
        check("quantity_exponent_abs",static_cast<std::uint64_t>(std::abs(length)),site);check("quantity_exponent_abs",static_cast<std::uint64_t>(std::abs(time)),site);
        const auto bytes=(value.numerator.bits()+7)/8+(value.denominator.bits()+7)/8+(BigInt(length).bits()+7)/8+(BigInt(time).bits()+7)/8;
        RuntimeNode n;n.kind="Quantity";n.rational=std::move(value);n.length=length;n.time=time;return heap.allocate(std::move(n),{0,0,bytes},site);
    }
    Rational rational(const Value& v,NodeId site) {
        const auto& n=object(v);if(n.kind=="Quantity") return n.rational;
        if(n.kind=="Int") return Rational::reduced(n.integer);
        if(n.kind=="Float") {auto r=BigInt::ratio(n.real);return Rational::reduced(std::move(r.first),std::move(r.second));}
        error(site,"E201","Quantity arithmetic requires numeric operands");
    }
    HeldInt product(const BigInt& a,const BigInt& b,NodeId site) {return arithmetic("MULTIPLY",a,b,site);}
    HeldInt divisor(const BigInt& a,const BigInt& b,NodeId site) {
        if(a.zero() || b.zero() || BigInt::magnitude_compare(a,b)==0) {
            const auto& n=a.zero()?b:a;Lease result(heap.state,{0,0,int_bytes(n)},site);
            return {n.abs(),std::move(result)};
        }
        if(a==BigInt(1) || b==BigInt(1) || a==BigInt(-1) || b==BigInt(-1))
            return {BigInt(1),Lease(heap.state,{0,0,1},site)};
        Lease working(heap.state,{0,0,5*std::max(int_bytes(a),int_bytes(b))+2},site);
        auto value=gcd(a,b,[this]{point();});const auto size=int_bytes(value);
        working.release();return {std::move(value),Lease(heap.state,{0,0,size},site)};
    }
    Rational normalize(HeldInt& n,HeldInt& d,NodeId site) {
        if(n.value.zero()) return Rational{};
        if(d.value.sign()<0) {
            n.value.negate();d.value.negate();
        }
        auto g=divisor(n.value,d.value,site);
        if(g.value==BigInt(1)) return Rational::reduced(std::move(n.value),std::move(d.value));
        auto reduced_n=arithmetic("FLOOR_DIVIDE",n.value,g.value,site);
        auto reduced_d=arithmetic("FLOOR_DIVIDE",d.value,g.value,site);
        n=std::move(reduced_n);d=std::move(reduced_d);
        return Rational::reduced(std::move(n.value),std::move(d.value));
    }
    Value quantity_binary(const std::string& op,const Value& a,const Value& b,NodeId site) {
        const auto& x=object(a);const auto& y=object(b);
        const auto working=[](const RuntimeNode& n) -> std::size_t {
            if(n.kind=="Quantity") return int_bytes(n.rational.numerator)+int_bytes(n.rational.denominator);
            if(n.kind=="Int") return int_bytes(n.integer)+1;
            if(n.kind=="Float") {int exp=0;std::frexp(n.real,&exp);return n.real==0?1:static_cast<std::size_t>(exp>53?exp+1:54+std::max(0,54-exp))/8+2;}
            return 0;
        };
        Lease workspace(heap.state,{0,0,working(x)+working(y)},site);
        const auto u=rational(a,site),v=rational(b,site);
        for(const auto* n:{&u.numerator,&u.denominator,&v.numerator,&v.denominator}) check("integer_bits",n->bits(),site);
        const auto al=x.kind=="Quantity"?x.length:0,at=x.kind=="Quantity"?x.time:0,bl=y.kind=="Quantity"?y.length:0,bt=y.kind=="Quantity"?y.time:0;
        if(op=="PLUS" || op=="MINUS" || op=="LESS" || op=="LESS_EQUAL" || op=="GREATER" || op=="GREATER_EQUAL") {
            if(x.kind!="Quantity" || y.kind!="Quantity") error(site,"E201","addition/order requires two Quantities");
            if(al!=bl || at!=bt) error(site,"E213","incompatible dimensions");
            const auto g=divisor(u.denominator,v.denominator,site);
            const auto du=arithmetic("FLOOR_DIVIDE",u.denominator,g.value,site);
            const auto dv=arithmetic("FLOOR_DIVIDE",v.denominator,g.value,site);
            auto left=product(u.numerator,dv.value,site),right=product(v.numerator,du.value,site);
            if(op!="PLUS" && op!="MINUS") {const auto c=left.value.compare(right.value);return boolean(op=="LESS"?c<0:op=="LESS_EQUAL"?c<=0:op=="GREATER"?c>0:c>=0);}
            auto num=arithmetic(op,left.value,right.value,site);auto den=product(u.denominator,dv.value,site);
            auto normalized=normalize(num,den,site);num.space.release();den.space.release();
            return quantity(std::move(normalized),al,at,site);
        }
        if(op!="MULTIPLY" && op!="DIVIDE") error(site,"E201","unsupported Quantity operator");
        const bool inverse=op=="DIVIDE";const auto& c=inverse?v.denominator:v.numerator;const auto& d=inverse?v.numerator:v.denominator;
        if(d.zero()) error(site,"E205","zero divisor");
        const auto length=al+(inverse?-bl:bl),time=at+(inverse?-bt:bt);
        check("quantity_exponent_abs",static_cast<std::uint64_t>(std::abs(length)),site);check("quantity_exponent_abs",static_cast<std::uint64_t>(std::abs(time)),site);
        const auto g=divisor(u.numerator,d,site),h=divisor(c,u.denominator,site);
        const auto un=arithmetic("FLOOR_DIVIDE",u.numerator,g.value,site),vn=arithmetic("FLOOR_DIVIDE",c,h.value,site);
        const auto ud=arithmetic("FLOOR_DIVIDE",u.denominator,h.value,site),vd=arithmetic("FLOOR_DIVIDE",d,g.value,site);
        auto num=product(un.value,vn.value,site),den=product(ud.value,vd.value,site);
        if(den.value.sign()<0) {num.value.negate();den.value.negate();}
        auto normalized=num.value.zero()?Rational{}:Rational::reduced(std::move(num.value),std::move(den.value));
        num.space.release();den.space.release();return quantity(std::move(normalized),length,time,site);
    }
    static std::string float_text(double value) {
        char buffer[128];const auto r=std::to_chars(buffer,buffer+sizeof(buffer),value,std::chars_format::scientific);
        if(r.ec!=std::errc()) throw std::logic_error("Float formatting failed");std::string scientific(buffer,r.ptr);const auto at=scientific.find('e');
        const int exponent=std::stoi(scientific.substr(at+1));if(exponent<-4 || exponent>=16) return scientific;
        auto digits=scientific.substr(0,at);std::string sign;if(!digits.empty() && digits[0]=='-') {sign="-";digits.erase(0,1);}
        const auto dot=digits.find('.');if(dot!=std::string::npos) digits.erase(dot,1);const int point=exponent+1;
        if(point<=0) return sign+"0."+std::string(static_cast<std::size_t>(-point),'0')+digits;
        if(static_cast<std::size_t>(point)>=digits.size()) return sign+digits+std::string(static_cast<std::size_t>(point)-digits.size(),'0')+".0";
        digits.insert(static_cast<std::size_t>(point),".");return sign+digits;
    }
    std::string integer_text(const BigInt& value,NodeId site) {
        Lease scratch(heap.state,{0,0,int_bytes(value)},site);
        const auto text=value.decimal([this]{point();});check("numeric_digits",text.size()-(value.sign()<0?1:0),site);return text;
    }
    std::string scalar_text(const Value& value,NodeId site) {
        const auto& n=object(value);
        if(n.kind=="Int") return integer_text(n.integer,site);
        if(n.kind=="String") return encode_utf8(n.characters);
        if(n.kind=="Bool") return n.flag?"true":"false";if(n.kind=="Null") return "null";
        if(n.kind=="Float") return float_text(n.real);
        if(n.kind=="Quantity") {
            auto text=integer_text(n.rational.numerator,site);if(n.rational.denominator!=BigInt(1)) text+="/"+integer_text(n.rational.denominator,site);text+="::";
            if(!n.length && !n.time) return text+"one";
            for(const auto dim:{std::pair<const char*,int>{"m",n.length},{"s",n.time}}) if(dim.second) {if(text.back()!=':') text+='*';text+=dim.first;if(dim.second!=1) text+='^'+std::to_string(dim.second);}return text;
        }
        if(n.kind=="Function") return "<function "+n.name+">";if(n.kind=="Namespace") return "<module "+n.name+">";
        if(n.kind=="Definition") return "<shape "+n.name+">";if(n.kind=="Module") return "<module>";
        if(n.kind=="Lazy") return "<lazy "+n.state+">";
        if(n.kind=="Native") return "<"+n.name+">";
        if(n.kind=="MachineDefinition") return "<machine "+n.name+">";
        if(n.kind=="Machine") return "<machine "+object(heap.pin(n.edges[0])).name+": "+scalar_text(heap.pin(n.edges[1]),site)+">";
        throw std::logic_error("no scalar display");
    }
    struct Display {std::string text;std::vector<Lease> pieces;std::size_t count=0;};
    Display display(const Value& value,NodeId site) {
        struct Cursor {Value value;std::size_t index=0;bool started=false;};
        Display result;std::vector<Cursor> todo{{value}};std::set<std::uint64_t> active;
        const auto append_text=[this,site,&result](std::string_view text) {
            const auto size=codepoints(text);check("text_codepoints",result.count+size,site);
            result.pieces.emplace_back(heap.state,Charge{0,0,4*size},site);result.count+=size;result.text+=text;
        };
        while(!todo.empty()) {
            point();auto& cursor=todo.back();const auto& n=object(cursor.value);
            const bool composite=n.kind=="Array" || n.kind=="Shape" || n.kind=="Map" || n.kind=="Result" || n.kind=="Range";
            const auto identity=cursor.value.ref().id;
            if(!composite || (!cursor.started && active.count(identity))) {
                append_text(composite?"<cycle>":scalar_text(cursor.value,site));todo.pop_back();continue;
            }
            const auto start=n.kind=="Shape"?1U:0U;
            if(!cursor.started) {
                check("value_depth",todo.size(),site);active.insert(identity);cursor.started=true;cursor.index=start;
                append_text(n.kind=="Array"?"[":n.kind=="Result"?(n.flag?"(^_^)(":"(T_T)("):n.kind=="Range"?"range(":n.kind=="Map"?"{":object(heap.pin(n.edges[0])).name+"::{");
            }
            if(cursor.index==n.edges.size()) {append_text(n.kind=="Array"?"]":n.kind=="Map" || n.kind=="Shape"?"}":")");active.erase(identity);todo.pop_back();continue;}
            const auto i=cursor.index;cursor.index+=n.kind=="Map"?2:1;
            if(i>start) append_text(", ");if(n.kind=="Map" || n.kind=="Shape") {append_text(n.names[n.kind=="Map"?i/2:i-start]);append_text(": ");}
            todo.push_back({heap.pin(n.edges[i+(n.kind=="Map"?1:0)])});
        }
        return result;
    }
    void write(std::ostream& stream,const std::string& text,bool err,NodeId site) {
        (void)site;
        auto& count=err?stderr_used:stdout_used;check(err?"stderr_bytes":"stdout_bytes",count+text.size(),no_node);count+=text.size();stream<<text;stream.flush();
    }
    Value input_line(const Value& prompt,NodeId site) {
        write(output,encode_utf8(object(prompt).characters),false,site);if(!input) return null_;
        std::u32string line;std::vector<Lease> pieces;std::size_t bytes=0;bool pending_cr=false;
        const auto append_char=[&](char32_t c) {check("text_codepoints",line.size()+1,site);pieces.emplace_back(heap.state,Charge{0,0,4},site);line+=c;};
        for(;;) {
            point();const int first=input->get();
            if(first==std::char_traits<char>::eof()) {
                if(input->bad()) error(site,"E401","cannot read UTF-8 stdin");
                if(pending_cr) append_char(U'\r');if(line.empty()) return null_;break;
            }
            const auto c=static_cast<unsigned char>(first);
            const std::size_t width=c<0x80?1:c>=0xc2 && c<=0xdf?2:c>=0xe0 && c<=0xef?3:c>=0xf0 && c<=0xf4?4:0;
            if(!width) error(site,"E401","invalid UTF-8 stdin");
            std::string encoded(1,static_cast<char>(first));
            for(std::size_t j=1;j<width;++j) {point();const auto byte=input->get();if(byte==std::char_traits<char>::eof()) error(site,"E401","incomplete UTF-8 stdin");encoded+=static_cast<char>(byte);}
            char32_t cp=0;try {cp=decode_utf8(encoded).text.at(0);}catch(const std::invalid_argument&) {error(site,"E401","invalid UTF-8 stdin");}
            bytes+=width;check("io_payload_bytes",bytes,site);if(cp==U'\n') break;
            if(pending_cr) append_char(U'\r');pending_cr=cp==U'\r';if(!pending_cr) append_char(cp);
        }
        Lease join(heap.state,{0,0,4*line.size()},site);join.release();return string(std::move(line),site);
    }
    void eval(NodeId id,Done done);
    void statement(NodeId id,Next done);
    void block(NodeId id,Next done);
    void call(Value fn,std::vector<Value> args,NodeId site,Done done,std::vector<NodeId> argument_sites={});
    void array_library(const std::string& name,const std::vector<Value>& args,NodeId site,Done done);
    Value text_library(const std::string& name,const std::vector<Value>& args,NodeId site);
    Value file_library(const std::string& name,const std::vector<Value>& args,NodeId site);
    Value json_library(const std::string& name,const Value& value,NodeId site);
    struct JsonReader;
    struct JsonWriter;
    void map_insert(const Value& map,std::string key,const Value& key_value,const Value& value,NodeId site);
    std::size_t utf8_size(std::u32string_view text) const;
    void construct(NodeId id,Value base,Done done);
    void query(NodeId id,Value source,Done done);
    void wake(Value value,NodeId site,Done done);
    void begin_query_item(std::size_t i) {query_items.emplace_back(i,calls.size());}
    void end_query_item() {query_items.pop_back();}
    void initialize() {
        null_=make("Null",{},no_node);true_=make("Bool",{},no_node);object(true_).flag=true;false_=make("Bool",{},no_node);zero_=integer(BigInt(),no_node);
        builtin("io",no_node);builtin("io.print",no_node);
    }
    void drain() {
        while(!tasks.empty()) {point();auto task=std::move(tasks.back());tasks.pop_back();task.action();if(heap.state->nodes.size()>heap.state->roots.size()+4096) heap.collect();}
    }
    void unwind(RuntimeError* error) noexcept {
        auto item=query_items.rbegin();
        for(auto depth=calls.size();;--depth) {
            while(item!=query_items.rend() && item->second==depth) {
                if(error) try {error->notes.push_back("查询输入下标 "+std::to_string(item->first));}catch(...) {}
                ++item;
            }
            if(!depth) break;
            auto& active=*calls[depth-1];
            if(active.lazy) {
                auto& lazy=object(active.function);lazy.failure.reset();lazy.state="NEW";
                if(error && error->code!="E211") try {lazy.failure=std::make_shared<RuntimeError>(*error);lazy.state="FAILED";}catch(...) {}
            }
            if(error) try {
                const auto& n=ast(active.call);const auto p=n.token.source->position(n.token.start);
                error->notes.push_back((active.lazy?"wake：":"调用 "+object(active.function).name+"：")+display_path(n.token.source->path)+":"+std::to_string(p.line)+":"+std::to_string(p.column));
            } catch(...) {}
        }
        query_items.clear();
        tasks.clear();calls.clear();frame.reset();flow.clear();returned={};return_site=no_node;current={};
    }
    struct Arguments {std::vector<Value> values;Lease space;Arguments(std::shared_ptr<HeapState> h,std::size_t n,NodeId site):space(h,{0,n,0},site) {values.reserve(n);}};
    void arguments(std::vector<NodeId> ids,std::shared_ptr<Arguments> values,std::size_t i,Next done) {
        if(i==ids.size()) {push(std::move(done));return;}
        const auto id=ids[i];
        eval(id,[this,ids=std::move(ids),values,i,done=std::move(done)](Value v) mutable {values->values.push_back(std::move(v));push([this,ids=std::move(ids),values,i,done=std::move(done)]() mutable {arguments(std::move(ids),values,i+1,std::move(done));});});
    }
public:
    ExecutionContext(const Program& p,const ResourcePolicy& policy,std::atomic<bool>& cancel,std::ostream& out,std::ostream& err,bool json=false,std::istream* in=nullptr)
        :snapshot(p),program(snapshot.data()),heap(policy,cancel),output(out),errors(err),input(in),diagnostic_json(json) {}
    void execute() {
        try {
            initialize();block(program.root,[]{});drain();
            cleanup();
        } catch(RuntimeError& e) {
            unwind(&e);
            cleanup();throw;
        } catch(...) {unwind(nullptr);cleanup();throw;}
    }
    void failure(std::string record) {
        const auto limit=heap.state->policy.limits.at("stderr_bytes");
        if(record.size()>limit-stderr_used)
            record=render_frontend(FrontendError("E211","resource limit exceeded: stderr_bytes, limit="+
                std::to_string(limit)+", requested="+std::to_string(stderr_used+record.size())),diagnostic_json);
        errors<<record;errors.flush();
    }
    void cleanup() noexcept {tasks.clear();calls.clear();frame.reset();globals.clear();builtins.clear();modules.clear();current={};returned={};null_={};true_={};false_={};zero_={};heap.state->close();}
};
inline void ExecutionContext::eval(NodeId id,Done done) {
    push([this,id,done=std::move(done)]() mutable {
        point();if(!flow.empty()) {done(null_);return;}const auto& n=ast(id);const auto& k=n.kind;
        if(k=="integer") done(literal_int(program.numbers.at(id).words,id));
        else if(k=="float") done(real(program.numbers.at(id).real,id));
        else if(k=="string") done(string(n.text,id));
        else if(k=="null") done(null_);else if(k=="bool") done(boolean(n.flag));
        else if(k=="name") done(read(program.references.at(id),id));
        else if(k=="current") {if(!current) throw std::logic_error("current item not installed");done(current);}
        else if(k=="group") eval(n.children[0],std::move(done));
        else if(k=="lambda" || k=="lazy") done(make_function(id));
        else if(k=="quantity") {const auto& q=program.quantities.at(id);done(quantity(Rational::reduced(BigInt(q.numerator),BigInt(q.denominator)),q.length,q.time,id));}
        else if(k=="construct" || k=="with") eval(n.children[0],[this,id,done](Value base) {construct(id,base,done);});
        else if(k=="query") eval(n.children[0],[this,id,done](Value source) {query(id,source,done);});
        else if(k=="result") eval(n.children[0],[this,id,done](Value v) {done(result(ast(id).text=="SUCCESS",v,ast(id).children[0]));});
        else if(k=="propagate") eval(n.children[0],[this,id,done](Value v) {typecheck("Result",v,ast(id).children[0]);if(!object(v).flag) {flow="return";returned=v;return_site=id;tasks.resize(frame->boundary);}else done(heap.pin(object(v).edges[0]));});
        else if(k=="pipe") eval(n.children[0],[this,id,done](Value source) {
            const auto call_id=ast(id).children[1];const auto previous=current;current=source;eval(call_id,[this,previous,done](Value v) {current=previous;done(v);});
        });
        else if(k=="send") eval(n.children[0],[this,id,done](Value machine) {eval(ast(id).children[1],[this,id,machine,done](Value event) {
            typecheck("Machine",machine,ast(id).children[0]);typecheck("String",event,ast(id).children[1]);auto& n=object(machine);const auto definition=heap.pin(n.edges[0]);const auto state=heap.pin(n.edges[1]);
            const auto& transitions=program.machines.at(object(definition).syntax).edges;const auto current_state=encode_utf8(object(state).characters),event_text=encode_utf8(object(event).characters);
            const auto it=transitions.find({current_state,event_text});if(it==transitions.end()) done(result(false,string("invalid transition: "+current_state+" -- "+event_text,id),id));
            else {const auto next=string(it->second,id);const auto r=result(true,next,id);n.edges[1]=next.ref();done(r);}
        });});
        else if(k=="field") eval(n.children[0],[this,id,done=std::move(done)](Value v) {done(field(v,ast(id).text,id));});
        else if(k=="index") eval(n.children[0],[this,id,done=std::move(done)](Value owner) {eval(ast(id).children[1],[this,id,owner,done](Value key) {done(index(owner,key,id));});});
        else if(k=="array") {
            check("container_items",n.children.size(),id);auto a=array({},id);
            auto step=std::make_shared<std::function<void(std::size_t)>>();std::weak_ptr<std::function<void(std::size_t)>> weak=step;
            *step=[this,id,a,done,weak](std::size_t i) {if(i==ast(id).children.size()) {done(a);return;}auto keep=weak.lock();eval(ast(id).children[i],[this,a,i,id,keep](Value v) {append(a,v,id);push([keep,i] {(*keep)(i+1);});});};
            (*step)(0);
        }
        else if(k=="unary") eval(n.children[0],[this,id,done](Value v) {
            const auto& op=ast(id).token.kind;const auto& x=object(v);
            if(op=="NOT") {typecheck(Type{"Bool",{}},v,id,false);done(boolean(!x.flag));}
            else if(x.kind=="Quantity") {
                Lease copy(heap.state,{0,0,int_bytes(x.rational.numerator)+int_bytes(x.rational.denominator)},id);
                auto r=x.rational;if(op!="PLUS") r.numerator.negate();
                copy.release();done(quantity(std::move(r),x.length,x.time,id));
            }
            else if(x.kind!="Int" && x.kind!="Float") error(id,"E201","unary sign needs a number");
            else if(op=="PLUS") done(v);else done(x.kind=="Int"?integer(-x.integer,id):real(-x.real,id));
        });
        else if(k=="add" || k=="binary") eval(n.children[0],[this,id,done](Value left) {
            const auto op=ast(id).token.kind;
            if(op=="AND" || op=="OR") {typecheck("Bool",left,ast(id).children[0]);if((op=="AND" && !object(left).flag) || (op=="OR" && object(left).flag)) {done(left);return;}}
            eval(ast(id).children[1],[this,id,left,done,op](Value right) {if(!flow.empty()) {done(null_);return;}if(op=="AND" || op=="OR") {typecheck("Bool",right,ast(id).children[1]);done(right);}else done(binary(op,left,right,id));});
        });
        else if(k=="call") eval(n.children[0],[this,id,done](Value fn) {
            auto args=std::make_shared<Arguments>(heap.state,ast(id).children.size()-1,id);std::vector<NodeId> ids(ast(id).children.begin()+1,ast(id).children.end());
            arguments(std::move(ids),args,0,[this,fn,args,id,done] {if(!flow.empty()) {done(null_);return;}call(fn,args->values,id,[args,done](Value v) {done(v);});});
        });
        else error(id,"E402","native execution not yet implemented: "+k);
    });
}
inline void ExecutionContext::block(NodeId id,Next done) {
    struct Scope {std::vector<NodeId> bindings;};auto scope=std::make_shared<Scope>();
    // File scopes persist for module exports/defaults; block locals are removed
    // on every control-flow exit, including early return and loop signals.
    const bool local=ast(id).kind=="block";
    if(local && !frame) for(auto child:ast(id).children) if(program.symbols.count(child)) scope->bindings.push_back(child);
    auto active_frame=frame;
    auto step=std::make_shared<std::function<void(std::size_t)>>();std::weak_ptr<std::function<void(std::size_t)>> weak=step;
    *step=[this,id,done,scope,local,active_frame,weak](std::size_t i) {
        if(i==ast(id).children.size() || !flow.empty()) {
            if(local) {
                if(active_frame) {const auto& blocks=program.functions.at(object(active_frame->function).syntax).blocks;auto it=blocks.find(id);if(it!=blocks.end()) for(auto slot:it->second) {active_frame->locals[slot]={};active_frame->types[slot]={};}}
                else for(auto symbol:scope->bindings) globals.erase(symbol);
            }
            push(done);return;
        }
        auto keep=weak.lock();statement(ast(id).children[i],[this,keep,i] {push([keep,i] {(*keep)(i+1);});});
    };push([step] {(*step)(0);});
}
inline void ExecutionContext::statement(NodeId id,Next done) {
    push([this,id,done=std::move(done)] {
        point();if(!flow.empty()) {push(done);return;}const auto& n=ast(id);const auto& k=n.kind;
        if(k=="spec") push(done);
        else if(k=="block" || k=="program") block(id,done);
        else if(k=="binding") {
            auto space=std::make_shared<Lease>();if(!frame) *space=Lease(heap.state,{0,1,0},id);
            auto type=annotation(id);eval(n.children[0],[this,id,type,done,space](Value v) {typecheck(type,v,ast(id).children[0]);define(id,v,type,std::move(*space));push(done);});
        }
        else if(k=="assert") eval(n.children[0],[this,id,done](Value v) {typecheck("Bool",v,ast(id).children[0]);if(!object(v).flag) error(id,"E210","assertion failed");push(done);});
        else if(k=="function") {Lease space;if(!frame) space=Lease(heap.state,{0,1,0},id);define(id,make_function(id),{},std::move(space));push(done);}
        else if(k=="machine") {auto v=make("MachineDefinition",{1,0,0},id);object(v).syntax=id;object(v).name=spelling(n.token);define(id,v);push(done);}
        else if(k=="shape") {
            auto v=make("Definition",{1,0,0},id);auto& definition=object(v);definition.syntax=id;definition.name=spelling(n.token);define(id,v);
            std::vector<Type> types;std::vector<Value> edges;
            for(auto field:n.children) types.push_back(annotation(field));
            Lease space(heap.state,{0,static_cast<std::uint64_t>(std::count_if(types.begin(),types.end(),[](const Type& t){return bool(t.nominal);})),0},id);
            for(std::size_t i=0;i<types.size();++i) {definition.names.push_back(spelling(ast(n.children[i]).token));definition.type_names.push_back(types[i].name);definition.type_nominals.push_back(types[i].nominal?edges.size():no_node);if(types[i].nominal) edges.push_back(types[i].nominal);}
            for(const auto& edge:edges) definition.edges.push_back(edge.ref());definition.charge.slots+=space.transfer().slots;push(done);
        }
        else if(k=="use") {
            const auto root=program.imports.at(id);const auto it=modules.find(root);
            if(it!=modules.end()) {define(id,it->second);push(done);}
            else {
                std::vector<NodeId> exports;for(auto child:ast(root).children) if(ast(child).kind=="function" || ast(child).kind=="shape" || ast(child).kind=="machine") exports.push_back(child);
                auto module=make("Module",{1,exports.size(),0},id);modules.emplace(root,module);
                block(root,[this,id,module,exports,done] {auto& n=object(module);for(auto child:exports) {n.names.push_back(spelling(ast(child).token));const auto& v=globals.at(child).raw;n.edges.push_back(object(v).kind=="Cell"?object(v).edges[0]:v.ref());}define(id,module);push(done);});
            }
        }
        else if(k=="match") eval(n.children[0],[this,id,done](Value target) {
            auto next=std::make_shared<std::function<void(std::size_t)>>();std::weak_ptr<std::function<void(std::size_t)>> weak=next;
            *next=[this,id,done,target,weak](std::size_t i) {
                if(i==ast(id).children.size()) error(id,"E207","no match arm selected");
                const auto& arm=ast(ast(id).children[i]);const auto p=arm.children[0],body=arm.children[1];const auto& pattern=ast(p);
                if(pattern.kind=="wildcard") {block(body,done);return;}
                auto keep=weak.lock();
                if(pattern.kind=="payload_pattern") {auto& n=object(target);if(n.kind=="Result" && n.flag==(pattern.text=="SUCCESS")) {define(p,heap.pin(n.edges[0]));block(body,[this,p,done] {if(!frame) globals.erase(p);push(done);});}else push([keep,i] {(*keep)(i+1);});}
                else eval(pattern.children[0],[this,target,p,body,done,keep,i](Value v) {if(object(binary("EQUAL",target,v,p)).flag) block(body,done);else push([keep,i] {(*keep)(i+1);});});
            };(*next)(1);
        });
        else if(k=="trace") eval(n.children[0],[this,id,done](Value value) {
            const auto child=ast(id).children[0];const auto& n=ast(child);auto formatted=display(value,id);auto rendered=render_frontend(FrontendError("",formatted.text,display_path(n.token.source->path),n.token.source->span(n.start,n.end)),diagnostic_json,"trace");write(errors,rendered,true,id);push(done);
        });
        else if(k=="return") {
            const auto finish=[this,id,done](Value v) {flow="return";returned=v;return_site=ast(id).children.empty()?id:ast(id).children[0];push(done);};
            if(n.children.empty()) finish(null_);else eval(n.children[0],finish);
        }
        else if(k=="break" || k=="continue") {flow=k;push(done);}
        else if(k=="assignment") {
            const auto target=n.children[0],rhs=n.children[1];const auto& t=ast(target);
            if(t.kind=="name") {
                const auto ref=program.references.at(target);const auto info=program.symbols.find(ref.symbol);
                if(info==program.symbols.end() || !info->second.mutable_binding) error(target,"E203","binding is immutable");
                auto cell=raw(ref,target);Type type;
                if(ref.kind=="global") type=globals.at(ref.symbol).type;
                else if(ref.kind=="local") type=frame->types.at(ref.key);
                // Captured mutable annotations are held by the Cell itself.
                if(object(cell).kind=="Cell" && !object(cell).type_names.empty()) type=stored_type(cell,0);
                const auto active_frame=frame;
                eval(rhs,[this,ref,cell,type,rhs,done,active_frame](Value value) {
                    typecheck(type,value,rhs);
                    if(object(cell).kind=="Cell") object(cell).edges[0]=value.ref();
                    else if(ref.kind=="global") globals.at(ref.symbol).raw=value;
                    else active_frame->locals.at(ref.key)=value;
                    push(done);
                });
            } else if(t.kind=="index") eval(t.children[0],[this,target,rhs,done](Value owner) {
                eval(ast(target).children[1],[this,target,rhs,owner,done](Value key) {
                    index(owner,key,target,true);eval(rhs,[this,target,owner,key,done](Value value) {const auto i=index_number(key,object(owner).edges.size(),target);object(owner).edges[i]=value.ref();++object(owner).version;push(done);});
                });
            });
            else eval(t.children[0],[this,target,rhs,done](Value owner) {
                const auto name=ast(target).text;field(owner,name,target,true);auto& instance=object(owner);const auto i=static_cast<std::size_t>(std::find(instance.names.begin(),instance.names.end(),name)-instance.names.begin());
                const auto type=stored_type(heap.pin(instance.edges[0]),i);eval(rhs,[this,owner,i,type,rhs,done](Value value) {typecheck(type,value,rhs);object(owner).edges[i+1]=value.ref();push(done);});
            });
        }
        else if(k=="if") {
            auto step=std::make_shared<std::function<void(std::size_t)>>();std::weak_ptr<std::function<void(std::size_t)>> weak=step;
            *step=[this,id,done,weak](std::size_t i) {
                if(i>=ast(id).children.size()) {push(done);return;}
                const auto child=ast(id).children[i];if(ast(child).kind=="block") {block(child,done);return;}
                auto keep=weak.lock();eval(child,[this,id,i,child,done,keep](Value v) {typecheck("Bool",v,child);if(object(v).flag) block(ast(id).children[i+1],done);else push([keep,i] {(*keep)(i+2);});});
            };(*step)(0);
        }
        else if(k=="while") {
            auto loop=std::make_shared<Next>();std::weak_ptr<Next> weak=loop;
            *loop=[this,id,done,weak] {
                auto keep=weak.lock();eval(ast(id).children[0],[this,id,done,keep](Value v) {
                    typecheck("Bool",v,ast(id).children[0]);if(!object(v).flag) {push(done);return;}
                    block(ast(id).children[1],[this,keep,done] {if(flow=="break") {flow.clear();push(done);}else if(flow=="return") push(done);else {flow.clear();push([keep] {(*keep)();});}});
                });
            };push([loop] {(*loop)();});
        }
        else if(k=="for") eval(n.children[0],[this,id,done](Value source) {
            const auto kind=object(source).kind;if(kind!="Array" && kind!="Range" && kind!="String") error(id,"E201","for requires Array/Range/String");
            struct Iteration {Value source;std::size_t offset=0;HeldInt position;std::shared_ptr<HeapState> heap;bool active=false;~Iteration() {if(active && !heap->closed) --heap->get(source.ref()).active;}};
            auto state=std::make_shared<Iteration>();state->source=source;state->heap=heap.state;
            if(kind=="Array") {++object(source).active;state->active=true;}
            if(kind=="Range") {
                const auto& start=object(heap.pin(object(source).edges[0])).integer;
                state->position.space=Lease(heap.state,{0,0,int_bytes(start)},id);state->position.value=start;
            }
            auto loop=std::make_shared<Next>();std::weak_ptr<Next> weak=loop;
            *loop=[this,id,done,state,kind,weak] {
                point();const auto& src=object(state->source);Value value;bool finished=false;
                if(kind=="Array") {finished=state->offset==src.edges.size();if(!finished) value=heap.pin(src.edges[state->offset++]);}
                else if(kind=="String") {finished=state->offset==src.characters.size();if(!finished) value=string(std::u32string(1,src.characters[state->offset++]),id);}
                else {
                    const auto& stop=object(heap.pin(src.edges[1])).integer;const auto& step=object(heap.pin(src.edges[2])).integer;
                    auto& cursor=state->position;finished=step.sign()>0?cursor.value>=stop:cursor.value<=stop;
                    if(!finished) {
                        value=integer(cursor.value,id);
                        // The cursor can cross the endpoint; only emitted values are language Ints.
                        const auto bits=cursor.value.sum_bits(step,false,[this]{point();});
                        Lease next(heap.state,{0,0,(bits+7)/8},id);auto position=cursor.value+step;
                        cursor={std::move(position),std::move(next)};
                    }
                }
                if(finished) {if(!frame) globals.erase(id);push(done);return;}
                define(id,value);auto keep=weak.lock();block(ast(id).children[1],[this,id,keep,done] {if(!frame) globals.erase(id);if(flow=="break") {flow.clear();push(done);}else if(flow=="return") push(done);else {flow.clear();push([keep] {(*keep)();});}});
            };push([loop] {(*loop)();});
        });
        else if(k=="expression") eval(n.children[0],[this,done](Value) {push(done);});
        else error(id,"E402","native statement not yet implemented: "+k);
    });
}
inline void ExecutionContext::call(Value fn,std::vector<Value> args,NodeId site,Done done,std::vector<NodeId> argument_sites) {
    const auto argument_site=[&](std::size_t i) {return argument_sites.empty()?ast(site).children.at(i+1):argument_sites.at(i);};
    const auto& f=object(fn);
    if(f.kind=="MachineDefinition") {
        if(args.size()!=1) error(site,"E202","Machine constructor expects one argument");const auto arg=ast(site).children[1];typecheck("String",args[0],arg);
        if(!program.machines.at(f.syntax).states.count(encode_utf8(object(args[0]).characters))) error(arg,"E212","unknown initial state");
        done(make("Machine",{1,2,0},site,{fn,args[0]}));return;
    }
    if(f.kind!="Function") error(site,"E202","value is not callable");
    if(f.syntax!=no_node) {
        const auto id=f.syntax;const auto& node=ast(id);const auto count=node.children.size()-1;
        if(args.size()!=count) error(site,"E202","wrong argument count: "+f.name);
        check("call_depth",calls.size()+1,site);
        auto next=std::make_shared<Frame>();next->function=fn;next->call=site;calls.push_back(next);
        for(std::size_t i=0;i<count;++i) typecheck(stored_type(fn,i),args[i],argument_site(i));
        const auto& plan=program.functions.at(id);next->space=Lease(heap.state,{0,plan.locals.size()+1,0},site);
        next->locals.resize(plan.locals.size());next->types.resize(plan.locals.size());auto previous=frame;frame=next;
        for(std::size_t i=0;i<count;++i) define(node.children[i],args[i],stored_type(fn,i));
        const auto previous_item=current;
        const auto finish=[this,fn,id,previous,next,done,previous_item](Value v) {
            const auto site=flow=="return"?return_site:ast(id).kind=="lambda"?ast(id).children.back():id;
            if(flow=="return") v=returned;
            typecheck(stored_type(fn,ast(id).children.size()-1),v,site,flow=="return" || ast(id).kind=="lambda");
            flow.clear();returned={};return_site=no_node;current=previous_item;next->locals.clear();next->types.clear();next->space.release();frame=previous;calls.pop_back();push([done,v] {done(v);});
        };
        if(node.kind=="lambda") eval(node.children.back(),finish);
        else {push([this,finish] {finish(null_);});next->boundary=tasks.size();block(node.children.back(),[] {});}return;
    }
    const auto& name=f.name;
    const CoreHost* signature=nullptr;for(const auto& host:core_hosts) if(host.name==name) {signature=&host;break;}
    if(!signature) error(site,"E402","native host capability not implemented: "+name);
    if(args.size()!=signature->arity) error(site,"E202","wrong argument count: "+name);
    for(std::size_t i=0;i<args.size();++i) if(!core_host_accepts(signature->types[i],object(args[i]).kind)) {
        RuntimeError e("E201","invalid argument for "+name,name=="len" || name=="str"?site:argument_site(i));
        e.expression_span=name!="len" && name!="str";throw e;
    }
    if(name=="array.sum" || name=="array.stats" || name=="array.sorted" || name=="array.map" || name=="array.filter") {
        array_library(name,args,site,std::move(done));return;
    }
    if(name.compare(0,5,"text.")==0) {
        done(text_library(name,args,site));return;
    }
    if(name=="io.input") {typecheck("String",args[0],ast(site).children[1]);done(input_line(args[0],site));return;}
    if(name=="data.parse" || name=="data.stringify") {done(json_library(name,args[0],site));return;}
    if(name=="io.read_text" || name=="io.write_text" || name=="io.write_atomic" || name=="io.replace_file") {
        done(file_library(name,args,site));return;
    }
    if(name=="wake") {typecheck("Lazy",args[0],ast(site).children[1]);wake(args[0],site,done);return;}
    if(name=="unit.make" || name=="unit.format") {
        typecheck("String",args[1],ast(site).children[2]);const auto unit=encode_utf8(object(args[1]).characters);
        const std::map<std::string,std::tuple<int,int,int,int>> units={{"one",{1,1,0,0}},{"m",{1,1,1,0}},{"mm",{1,1000,1,0}},{"cm",{1,100,1,0}},{"km",{1000,1,1,0}},{"s",{1,1,0,1}},{"ms",{1,1000,0,1}},{"min",{60,1,0,1}},{"h",{3600,1,0,1}}};
        const auto& n=object(args[0]);if(name=="unit.make" && n.kind!="Int" && n.kind!="Float") error(ast(site).children[1],"E201","unit.make requires Int/Float");
        if(name=="unit.format") typecheck("Quantity",args[0],ast(site).children[1]);
        const auto it=units.find(unit);if(it==units.end()) {RuntimeError e("E306","unknown unit",ast(site).children[2]);e.expression_span=true;throw e;}const auto [num,den,l,t]=it->second;
        const auto multiplier=quantity(Rational::reduced(BigInt(num),BigInt(den)),l,t,site);
        if(name=="unit.make") done(quantity_binary("MULTIPLY",args[0],multiplier,site));
        else {if(n.length!=l || n.time!=t) error(site,"E213","incompatible dimensions");const auto q=quantity_binary("DIVIDE",args[0],multiplier,site);const auto text=scalar_text(q,site);done(string(text.substr(0,text.find("::"))+"::"+unit,site));}return;
    }
    if(name=="array.push" || name=="array.pop" || name=="array.copy") {
        typecheck("Array",args[0],ast(site).children[1]);auto& n=object(args[0]);
        if(name=="array.push") {append(args[0],args[1],site);done(null_);}
        else if(name=="array.copy") {auto copy=array({},site);for(auto h:n.edges) {point();append(copy,heap.pin(h),site);}done(copy);}
        else {if(n.active) error(site,"E206","cannot resize an actively traversed Array");if(n.edges.empty()) error(site,"E204","empty Array");auto v=heap.pin(n.edges.back());n.edges.pop_back();--n.charge.slots;heap.state->refund({0,1,0});++n.version;done(v);}return;
    }
    if(name=="data.map") {done(make("Map",{1,0,0},site));return;}
    if(name=="data.kind") {auto kind=object(args[0]).kind;const std::map<std::string,std::string> names={{"Int","int"},{"Float","float"},{"String","string"},{"Bool","bool"},{"Null","null"},{"Array","array"},{"Map","map"}};done(string(names.count(kind)?names.at(kind):"other",site));return;}
    if(name=="data.set" || name=="data.get" || name=="data.has" || name=="data.keys") {
        typecheck("Map",args[0],ast(site).children[1]);auto& n=object(args[0]);
        if(name=="data.keys") {auto keys=array({},site);for(std::size_t i=0;i<n.names.size();++i) {point();append(keys,heap.pin(n.edges[2*i]),site);}done(keys);return;}
        typecheck("String",args[1],ast(site).children[2]);
        Lease encoded_key(heap.state,{0,0,utf8_size(object(args[1]).characters)},site);
        auto key=encode_utf8(object(args[1]).characters);const auto it=std::find(n.names.begin(),n.names.end(),key);const auto index=static_cast<std::size_t>(it-n.names.begin());
        if(name=="data.has") done(boolean(it!=n.names.end()));
        else if(name=="data.get") {if(it==n.names.end()) error(site,"E204","missing Map key");done(heap.pin(n.edges[2*index+1]));}
        else {
            if(it!=n.names.end()) {n.edges[2*index+1]=args[2].ref();++n.version;}
            else {encoded_key.release();map_insert(args[0],std::move(key),args[1],args[2],site);}
            done(null_);
        }
        return;
    }
    if(name=="math.abs") {auto& n=object(args[0]);if(n.kind=="Int") {Lease copy(heap.state,{0,0,int_bytes(n.integer)},site);auto value=n.integer.abs();copy.release();done(integer(std::move(value),site));}else if(n.kind=="Float") done(real(std::abs(n.real),site));else error(ast(site).children[1],"E201","abs requires Int/Float");return;}
    if(name=="io.print") {
        const auto& node=object(args[0]);Display formatted;
        if(node.kind=="Array" || node.kind=="Map" || node.kind=="Shape" || node.kind=="Range" || node.kind=="Result" || node.kind=="Quantity") formatted=display(args[0],site);
        else {formatted.text=scalar_text(args[0],site);formatted.count=codepoints(formatted.text);}
        check("text_codepoints",formatted.count,site);
        Lease formatting(heap.state,{0,0,4*(formatted.count+1+(node.kind=="Int"?formatted.count:0))},site);
        write(output,formatted.text+"\n",false,site);done(null_);
    } else if(name=="range") done(range(args,site));
    else if(name=="str") {
        const auto& kind=object(args[0]).kind;
        if(kind!="Int" && kind!="Float" && kind!="String" && kind!="Bool" && kind!="Null" && kind!="Quantity") error(site,"E201","str requires a scalar");
        done(kind=="String"?args[0]:string(scalar_text(args[0],site),site));
    } else {
        const auto& n=object(args[0]);BigInt size;
        if(n.kind=="String") size=BigInt(static_cast<std::int64_t>(n.characters.size()));
        else if(n.kind=="Array" || n.kind=="Map") size=BigInt(static_cast<std::int64_t>(n.kind=="Map"?n.names.size():n.edges.size()));
        else if(n.kind=="Range") {
            const auto& start=object(heap.pin(n.edges[0])).integer;const auto& stop=object(heap.pin(n.edges[1])).integer;const auto& step=object(heap.pin(n.edges[2])).integer;
            size=(stop-start+step-BigInt(step.sign()>0?1:-1))/step;if(size.sign()<0) size=BigInt();
        } else error(site,"E201","len requires String/Array/Map/Range");
        done(integer(std::move(size),site));
    }
}
inline std::string runtime_diagnostic(const ProgramData& program,const RuntimeError& error,bool json) {
    std::optional<std::string> file;std::optional<Span> span;
    if(error.site!=no_node) {const auto& n=program.nodes.at(error.site);file=display_path(n.token.source->path);span=error.expression_span?n.token.source->span(n.start,n.end):token_span(n.token);}
    auto record=render_frontend(FrontendError(error.code,error.what(),file,span),json);
    if(json) {
        const auto at=record.rfind("[]");std::string notes="[";
        for(const auto& note:error.notes) {auto item=quote(note);if(record.size()+notes.size()+item.size()>4000) break;if(notes.size()>1) notes+=',';notes+=item;}
        notes+=']';if(at!=std::string::npos && record.size()+notes.size()-2<=4096) record.replace(at,2,notes);
    } else for(const auto& note:error.notes) if(record.size()+note.size()+8<=4096) record+="  note: "+one_line(note)+"\n";
    return record;
}
inline void ExecutionContext::wake(Value value,NodeId site,Done done) {
    auto& lazy=object(value);
    if(lazy.state=="READY") {done(heap.pin(lazy.edges.back()));return;}
    if(lazy.state=="FAILED") {
        auto e=*lazy.failure;const auto& n=ast(site);const auto p=n.token.source->position(n.token.start);
        e.notes.push_back("wake："+display_path(n.token.source->path)+":"+std::to_string(p.line)+":"+std::to_string(p.column));throw e;
    }
    if(lazy.state=="RUNNING") error(site,"E209","cyclic Lazy wake");
    check("call_depth",calls.size()+1,site);
    const auto& plan=program.functions.at(lazy.syntax);
    auto next=std::make_shared<Frame>();next->function=value;next->lazy=true;next->call=site;next->space=Lease(heap.state,{0,plan.locals.size()+1,0},site);
    next->locals.resize(plan.locals.size());next->types.resize(plan.locals.size());lazy.edges.reserve(lazy.edges.size()+1);
    auto previous=frame;calls.push_back(next);frame=next;lazy.state="RUNNING";
    eval(ast(lazy.syntax).children[0],[this,next,previous,value,done](Value result) {
        auto& lazy=object(value);lazy.edges.push_back(result.ref());lazy.state="READY";next->space.release();frame=previous;calls.pop_back();push([done,result] {done(result);});
    });
}
inline void ExecutionContext::construct(NodeId id,Value base,Done done) {
    const auto& n=ast(id);const bool copy=n.kind=="with";const auto& b=object(base);
    if(copy?b.kind!="Shape":b.kind!="Definition") error(id,"E201",copy?"with requires a shape instance":"construction requires a shape definition");
    const auto definition=copy?heap.pin(b.edges[0]):base;const auto& def=object(definition);
    const auto count=def.names.size();
    std::vector<std::pair<std::size_t,NodeId>> updates;std::vector<bool> supplied(count);
    for(std::size_t i=1;i<n.children.size();++i) {
        const auto& init=ast(n.children[i]);const auto match=std::find(def.names.begin(),def.names.end(),init.text);
        if(match==def.names.end()) error(n.children[i],"E203","unknown initializer field: "+init.text);
        const auto index=static_cast<std::size_t>(match-def.names.begin());
        if(supplied[index]) error(n.children[i],"E203","duplicate initializer field: "+init.text);
        supplied[index]=true;updates.emplace_back(index,init.children[0]);
    }
    if(!copy) for(std::size_t i=0;i<count;++i) if(!supplied[i]) {
        if(def.syntax==no_node) error(id,"E203","missing required field: "+def.names[i]);
        const auto field=ast(def.syntax).children[i];if(ast(field).children.empty()) error(id,"E203","missing required field: "+def.names[i]);updates.emplace_back(i,ast(field).children[0]);
    }
    std::vector<Value> edges{definition};for(std::size_t i=0;i<count;++i) edges.push_back(copy?heap.pin(b.edges[i+1]):null_);
    auto instance=make("Shape",{1,edges.size(),0},id,edges);object(instance).names=def.names;
    auto step=std::make_shared<std::function<void(std::size_t)>>();std::weak_ptr<std::function<void(std::size_t)>> weak=step;
    *step=[this,instance,definition,done,updates=std::move(updates),weak](std::size_t i) {
        if(i==updates.size()) {done(instance);return;}
        const auto [index,expr]=updates[i];auto keep=weak.lock();
        eval(expr,[this,instance,definition,index,expr,keep,i](Value v) {typecheck(stored_type(definition,index),v,expr);object(instance).edges[index+1]=v.ref();push([keep,i] {(*keep)(i+1);});});
    };(*step)(0);
}
inline void ExecutionContext::query(NodeId id,Value source,Done done) {
    const auto& n=ast(id);typecheck("Array",source,n.children[0]);const auto count=object(source).edges.size();
    struct Query {
        std::vector<Value> snapshot;std::vector<std::size_t> selected;std::vector<std::pair<std::size_t,Value>> keys;
        Lease snapshot_space,selected_space,key_space;std::size_t take=0;Value previous,result;
        NodeId keep=no_node,order=no_node,take_expr=no_node,yield=no_node;bool descending=false;
        std::string category;int length=0,time=0;
    };
    auto q=std::make_shared<Query>();q->previous=current;q->take=count;
    q->snapshot_space=Lease(heap.state,{0,count,0},id);for(auto edge:object(source).edges) q->snapshot.push_back(heap.pin(edge));
    for(std::size_t i=1;i<n.children.size();++i) {const auto& clause=ast(n.children[i]);const auto expr=clause.children[0];
        if(clause.kind=="keep") q->keep=expr;else if(clause.kind=="order") {q->order=expr;q->descending=clause.text=="DESC";}else if(clause.kind=="take") q->take_expr=expr;else if(clause.kind=="yield") q->yield=expr;
    }
    enum class Phase {Keep,Keys,Yield};using Step=std::function<void(Phase,std::size_t)>;
    auto step=std::make_shared<Step>();std::weak_ptr<Step> weak=step;
    *step=[this,q,id,done,weak](Phase phase,std::size_t i) {
        auto keep=weak.lock();
        const auto proceed=[this,keep](Phase next,std::size_t at) {push([keep,next,at] {(*keep)(next,at);});};
        if(phase==Phase::Keep) {
            if(i==q->snapshot.size()) {
                if(q->order!=no_node) {q->key_space=Lease(heap.state,{0,3*q->selected.size(),0},id);proceed(Phase::Keys,0);}
                else {q->result=array({},id);proceed(Phase::Yield,0);}return;
            }
            current=q->snapshot[i];
            if(q->keep==no_node) {q->selected.push_back(i);proceed(Phase::Keep,i+1);}
            else {begin_query_item(i);eval(q->keep,[this,q,i,proceed](Value value) {end_query_item();typecheck("Bool",value,q->keep);if(object(value).flag) q->selected.push_back(i);proceed(Phase::Keep,i+1);});}
        } else if(phase==Phase::Keys) {
            if(i==q->selected.size()) {
                std::stable_sort(q->keys.begin(),q->keys.end(),[this,q](const auto& a,const auto& b) {point();if(q->category=="Quantity") return object(quantity_binary(q->descending?"GREATER":"LESS",a.second,b.second,q->order)).flag;const int c=compare(a.second,b.second,q->order);return q->descending?c>0:c<0;});
                for(std::size_t k=0;k<q->keys.size();++k) q->selected[k]=q->keys[k].first;
                q->keys.clear();q->key_space.release();q->result=array({},id);proceed(Phase::Yield,0);return;
            }
            const auto index=q->selected[i];current=q->snapshot[index];begin_query_item(index);
            eval(q->order,[this,q,index,i,proceed](Value value) {
                end_query_item();const auto& n=object(value);const auto category=n.kind=="Int" || n.kind=="Float"?"number":n.kind;
                if((category!="number" && category!="String" && category!="Quantity") || (!q->category.empty() && q->category!=category)) error(q->order,"E201","incompatible query order keys");
                if(category=="Quantity" && !q->category.empty() && (q->length!=n.length || q->time!=n.time)) error(q->order,"E213","incompatible query key dimensions");
                q->category=category;q->length=n.length;q->time=n.time;q->keys.emplace_back(index,value);proceed(Phase::Keys,i+1);
            });
        } else {
            if(i==q->selected.size() || i==q->take) {current=q->previous;done(q->result);return;}
            const auto index=q->selected[i];current=q->snapshot[index];begin_query_item(index);
            eval(q->yield,[this,q,i,proceed](Value value) {end_query_item();append(q->result,value,q->yield);proceed(Phase::Yield,i+1);});
        }
    };
    const auto start=[this,q,step,count,id] {q->selected_space=Lease(heap.state,{0,count,0},id);push([step] {(*step)(Phase::Keep,0);});};
    if(q->take_expr==no_node) start();
    else eval(q->take_expr,[this,q,count,start](Value value) {
        typecheck("Int",value,q->take_expr);const auto& amount=object(value).integer;
        if(amount.sign()<0) error(q->take_expr,"E208","take cannot be negative");
        if(amount<BigInt(static_cast<std::int64_t>(count))) q->take=static_cast<std::size_t>(std::stoull(amount.decimal()));start();
    });
}
}
#include "core_library.hpp"
#include "file_library.hpp"
#include "json_library.hpp"
