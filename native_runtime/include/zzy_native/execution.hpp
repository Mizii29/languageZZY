#pragma once
#include "runtime_heap.hpp"
#include "host_metadata.hpp"
#include <deque>
#include <iomanip>
#include <sstream>
namespace zzy {
class ExecutionContext {
public:
    using Done=std::function<void(Value)>;
    using Next=std::function<void()>;
    const ProgramData& program;
    RuntimeHeap heap;
private:
    struct Type {std::string name;Value nominal;};
    struct Binding {Value raw;Type type;Lease slot;};
    struct Frame {Value function;std::vector<Value> locals;std::vector<Type> types;Lease space;NodeId call=no_node;bool lazy=false;};
    struct Task {Next action;};
    std::vector<Task> tasks;
    std::map<NodeId,Binding> globals;
    std::vector<std::shared_ptr<Frame>> calls;
    std::shared_ptr<Frame> frame;
    std::map<std::string,Value> builtins;
    std::map<NodeId,Value> modules;
    Value null_,true_,false_,zero_,current;
    std::ostream& output;std::ostream& errors;
    std::uint64_t stdout_used=0,stderr_used=0;
    std::string flow;Value returned;NodeId return_site=no_node;
    bool diagnostic_json;
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
    void typecheck(const Type& t,const Value& v,NodeId site) const {
        if(t.name.empty()) return;
        const auto& n=object(v);bool valid=n.kind==t.name;
        if(t.nominal) valid=(n.kind=="Shape" || n.kind=="Machine") && !n.edges.empty() && n.edges[0]==t.nominal.ref();
        if(!valid) {RuntimeError e("E201","expected "+t.name+", got "+n.kind,site);e.expression_span=true;throw e;}
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
    void define(NodeId id,Value value,Type type={}) {
        const auto& info=program.symbols.at(id);
        if(info.cell) {
            std::vector<Value> edges{value};if(type.nominal) edges.push_back(type.nominal);
            auto cell=make("Cell",{0,edges.size(),0},id,edges);object(cell).type_names={type.name};object(cell).type_nominals={type.nominal?1U:no_node};value=std::move(cell);
        }
        if(info.owner==no_node) {Binding b{std::move(value),std::move(type),Lease(heap.state,{0,1,0},id)};globals.insert_or_assign(id,std::move(b));}
        else {if(!frame) throw std::logic_error("missing local frame");frame->locals.at(info.slot)=std::move(value);frame->types.at(info.slot)=std::move(type);}
    }
    Value integer(BigInt n,NodeId site) {
        check("integer_bits",n.bits(),site);if(n.zero() && zero_) return zero_;
        RuntimeNode v;v.kind="Int";v.integer=std::move(n);const auto bytes=(v.integer.bits()+7)/8;
        return heap.allocate(std::move(v),{0,0,bytes},site);
    }
    Value real(double n,NodeId site) {
        if(!std::isfinite(n)) error(site,"E208","Float must be finite");RuntimeNode v;v.kind="Float";v.real=n;return heap.allocate(std::move(v),{0,0,8},site);
    }
    Value string(std::u32string n,NodeId site) {
        check("text_codepoints",n.size(),site);const auto size=n.size();RuntimeNode v;v.kind="String";v.characters=std::move(n);return heap.allocate(std::move(v),{0,0,4*size},site);
    }
    Value string(const std::string& n,NodeId site) {return string(decode_utf8(n).text,site);}
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
        const bool ns=name=="io" || name=="array" || name=="data" || name=="text" || name=="math" || name=="unit" || name=="sketch" || name=="db";
        auto v=make(ns?"Namespace":"Function",{1,1,0},site);object(v).name=name;builtins.emplace(name,v);return v;
    }
    Value field(const Value& owner,const std::string& name,NodeId site,bool write=false) {
        auto& n=object(owner);
        if(n.kind=="Namespace") {
            if(write) error(site,"E203","namespace is read only");const auto qualified=n.name+"."+name;bool known=false;
            for(const auto& h:static_hosts) if(h.name==qualified) {known=true;break;}
            if(!known) error(site,"E302","unknown namespace member: "+name);return builtin(qualified,site);
        }
        if(n.kind=="Machine") {if(name!="state") error(site,"E204","unknown Machine field");if(write) error(site,"E203","Machine state is read only");return heap.pin(n.edges.at(1));}
        if(n.kind!="Shape" && n.kind!="Module") error(site,"E201","field access needs a shape/module");
        if(write && n.kind=="Module") error(site,"E203","module is read only");
        const auto it=std::find(n.names.begin(),n.names.end(),name);if(it==n.names.end()) error(site,"E204","unknown field: "+name);
        return heap.pin(n.edges.at(static_cast<std::size_t>(it-n.names.begin())+(n.kind=="Shape"?1:0)));
    }
    std::size_t index_number(const Value& v,std::size_t count,NodeId site) const {
        typecheck("Int",v,site);const auto& i=object(v).integer;
        if(i.sign()<0 || i>=BigInt(static_cast<std::int64_t>(count))) error(site,"E204","index out of bounds");
        return static_cast<std::size_t>(std::stoull(i.decimal()));
    }
    Value index(const Value& owner,const Value& key,NodeId site,bool write=false) {
        auto& n=object(owner);if(n.kind!="Array" && n.kind!="String") error(site,"E201","index needs Array/String");
        if(write && n.kind=="String") error(site,"E203","String is immutable");
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
    BigInt arithmetic(const std::string& op,const BigInt& a,const BigInt& b,NodeId site) {
        // Inputs stay rooted; bound scratch before host limb allocation. Result
        // ownership is transferred only after its exact bit size is checked.
        Lease scratch(heap.state,{0,0,(std::max(a.bits(),b.bits())+7)/8},site);
        BigInt r;
        if(op=="PLUS") r=a+b;else if(op=="MINUS") r=a-b;
        else if(op=="MULTIPLY") r=a.multiply(b,[&]{point();});
        else {const auto qr=a.divmod(b,[&]{point();});r=op=="FLOOR_DIVIDE"?qr.first:qr.second;}
        check("integer_bits",r.bits(),site);return r;
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
            }
            return boolean(op=="EQUAL"?equal:!equal);
        }
        if(op=="INTERVAL") return range({a,b,integer(BigInt(1),site)},site);
        if(op=="LESS" || op=="LESS_EQUAL" || op=="GREATER" || op=="GREATER_EQUAL") {const int c=compare(a,b,site);return boolean(op=="LESS"?c<0:op=="LESS_EQUAL"?c<=0:op=="GREATER"?c>0:c>=0);}
        const auto& x=object(a);const auto& y=object(b);
        if(op=="PLUS" && x.kind=="String" && y.kind=="String") {check("text_codepoints",x.characters.size()+y.characters.size(),site);return string(x.characters+y.characters,site);}
        if((x.kind!="Int" && x.kind!="Float") || (y.kind!="Int" && y.kind!="Float") || ((op=="FLOOR_DIVIDE" || op=="REMAINDER") && (x.kind!="Int" || y.kind!="Int"))) error(site,"E201","incompatible arithmetic operands");
        if((op=="DIVIDE" || op=="FLOOR_DIVIDE" || op=="REMAINDER") && (y.kind=="Int"?y.integer.zero():y.real==0)) error(site,"E205","zero divisor");
        if(x.kind=="Int" && y.kind=="Int" && op!="DIVIDE") return integer(arithmetic(op,x.integer,y.integer,site),site);
        const double left=x.kind=="Int"?x.integer.real():x.real,right=y.kind=="Int"?y.integer.real():y.real;
        if(!std::isfinite(left) || !std::isfinite(right)) error(site,"E208","Float promotion overflow");
        return real(op=="PLUS"?left+right:op=="MINUS"?left-right:op=="MULTIPLY"?left*right:left/right,site);
    }
    Value range(const std::vector<Value>& args,NodeId site) {
        for(const auto& v:args) typecheck("Int",v,site);if(object(args[2]).integer.zero()) error(site,"E208","zero Range step");
        return make("Range",{1,3,0},site,args);
    }
    std::string display(const Value& value,NodeId site,std::size_t depth=0,std::set<std::uint64_t>* active=nullptr) {
        point();std::set<std::uint64_t> own;if(!active) active=&own;const auto& n=object(value);
        if(active->count(value.ref().id)) return "<cycle>";
        if(n.kind=="Int") {const auto s=n.integer.decimal();check("numeric_digits",s.size()-(n.integer.sign()<0?1:0),site);return s;}
        if(n.kind=="String") return encode_utf8(n.characters);
        if(n.kind=="Bool") return n.flag?"true":"false";if(n.kind=="Null") return "null";
        if(n.kind=="Float") {std::ostringstream s;s<<std::setprecision(17)<<n.real;auto t=s.str();if(t.find_first_of(".eE")==std::string::npos) t+=".0";return t;}
        if(n.kind=="Function") return "<function "+n.name+">";if(n.kind=="Namespace") return "<module "+n.name+">";
        if(n.kind=="Definition") return "<shape "+n.name+">";if(n.kind=="Module") return "<module>";
        if(n.kind=="Lazy") return "<lazy "+n.state+">";
        if(n.kind=="MachineDefinition") return "<machine "+n.name+">";
        if(n.kind=="Machine") return "<machine "+object(heap.pin(n.edges[0])).name+": "+display(heap.pin(n.edges[1]),site)+">";
        check("value_depth",depth+1,site);active->insert(value.ref().id);
        std::string s=n.kind=="Array"?"[":n.kind=="Result"?(n.flag?"(^_^)(":"(T_T)("):n.kind=="Range"?"range(":n.kind=="Map"?"{":object(heap.pin(n.edges[0])).name+"::{";
        const auto start=n.kind=="Shape"?1U:0U;
        for(std::size_t i=start;i<n.edges.size();++i) {if(i>start) s+=", ";if(n.kind=="Shape" || n.kind=="Map") s+=n.names[i-start]+": ";s+=display(heap.pin(n.edges[i]),site,depth+1,active);check("text_codepoints",decode_utf8(s).text.size(),site);}
        s+=n.kind=="Array"?"]":n.kind=="Map" || n.kind=="Shape"?"}":")";active->erase(value.ref().id);return s;
    }
    void write(std::ostream& stream,const std::string& text,bool err,NodeId site) {
        auto& count=err?stderr_used:stdout_used;check(err?"stderr_bytes":"stdout_bytes",count+text.size(),site);count+=text.size();stream<<text;stream.flush();
    }
    void eval(NodeId id,Done done);
    void statement(NodeId id,Next done);
    void block(NodeId id,Next done);
    void call(Value fn,std::vector<Value> args,NodeId site,Done done);
    void construct(NodeId id,Value base,Done done);
    void query(NodeId id,Value source,Done done);
    struct Arguments {std::vector<Value> values;Lease space;Arguments(std::shared_ptr<HeapState> h,std::size_t n,NodeId site):space(h,{0,n,0},site) {values.reserve(n);}};
    void arguments(std::vector<NodeId> ids,std::shared_ptr<Arguments> values,std::size_t i,Next done) {
        if(i==ids.size()) {push(std::move(done));return;}
        const auto id=ids[i];
        eval(id,[this,ids=std::move(ids),values,i,done=std::move(done)](Value v) mutable {values->values.push_back(std::move(v));push([this,ids=std::move(ids),values,i,done=std::move(done)]() mutable {arguments(std::move(ids),values,i+1,std::move(done));});});
    }
public:
    ExecutionContext(const Program& p,const ResourcePolicy& policy,std::atomic<bool>& cancel,std::ostream& out,std::ostream& err,bool json=false)
        :program(p.data()),heap(policy,cancel),output(out),errors(err),diagnostic_json(json) {}
    void execute() {
        try {
            null_=make("Null",{},no_node);true_=make("Bool",{},no_node);object(true_).flag=true;false_=make("Bool",{},no_node);zero_=integer(BigInt(),no_node);
            builtin("io",no_node);builtin("io.print",no_node);
            block(program.root,[]{});
            while(!tasks.empty()) {point();auto task=std::move(tasks.back());tasks.pop_back();task.action();if(heap.state->nodes.size()>heap.state->roots.size()+4096) heap.collect();}
            cleanup();
        } catch(RuntimeError& e) {
            for(auto it=calls.rbegin();it!=calls.rend();++it) {const auto& n=ast((*it)->call);e.notes.push_back(((*it)->lazy?"wake: ":"call: ")+display_path(n.token.source->path)+":"+std::to_string(n.token.source->position(n.token.start).line));}
            cleanup();throw;
        } catch(...) {cleanup();throw;}
    }
    void cleanup() noexcept {tasks.clear();calls.clear();frame.reset();globals.clear();builtins.clear();modules.clear();current={};returned={};null_={};true_={};false_={};zero_={};heap.state->close();}
};
inline void ExecutionContext::eval(NodeId id,Done done) {
    push([this,id,done=std::move(done)]() mutable {
        point();if(!flow.empty()) {done(null_);return;}const auto& n=ast(id);const auto& k=n.kind;
        if(k=="integer") done(integer(BigInt(program.numbers.at(id).words),id));
        else if(k=="float") done(real(program.numbers.at(id).real,id));
        else if(k=="string") done(string(n.text,id));
        else if(k=="null") done(null_);else if(k=="bool") done(boolean(n.flag));
        else if(k=="name") done(read(program.references.at(id),id));
        else if(k=="current") {if(!current) throw std::logic_error("current item not installed");done(current);}
        else if(k=="group") eval(n.children[0],std::move(done));
        else if(k=="lambda") done(make_function(id));
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
            if(op=="NOT") {typecheck("Bool",v,id);done(boolean(!x.flag));}
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
        else if(k=="binding") {auto type=annotation(id);eval(n.children[0],[this,id,type,done](Value v) {if(flow.empty()) {typecheck(type,v,ast(id).children[0]);define(id,v,type);}push(done);});}
        else if(k=="assert") eval(n.children[0],[this,id,done](Value v) {typecheck("Bool",v,ast(id).children[0]);if(!object(v).flag) error(id,"E210","assertion failed");push(done);});
        else if(k=="function") {define(id,make_function(id));push(done);}
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
            else error(target,"E402","field assignment awaits shape batch");
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
            const auto kind=object(source).kind;if(kind!="Array" && kind!="Range" && kind!="String") error(ast(id).children[0],"E201","for requires Array/Range/String");
            struct Iteration {Value source;std::size_t offset=0;BigInt position;std::shared_ptr<HeapState> heap;bool active=false;~Iteration() {if(active && !heap->closed) --heap->get(source.ref()).active;}};
            auto state=std::make_shared<Iteration>();state->source=source;state->heap=heap.state;
            if(kind=="Array") {++object(source).active;state->active=true;}
            if(kind=="Range") state->position=object(heap.pin(object(source).edges[0])).integer;
            auto loop=std::make_shared<Next>();std::weak_ptr<Next> weak=loop;
            *loop=[this,id,done,state,kind,weak] {
                point();const auto& src=object(state->source);Value value;bool finished=false;
                if(kind=="Array") {finished=state->offset==src.edges.size();if(!finished) value=heap.pin(src.edges[state->offset++]);}
                else if(kind=="String") {finished=state->offset==src.characters.size();if(!finished) value=string(std::u32string(1,src.characters[state->offset++]),id);}
                else {const auto& stop=object(heap.pin(src.edges[1])).integer;const auto& step=object(heap.pin(src.edges[2])).integer;finished=step.sign()>0?state->position>=stop:state->position<=stop;if(!finished) {value=integer(state->position,id);state->position=state->position+step;}}
                if(finished) {if(!frame) globals.erase(id);push(done);return;}
                define(id,value);auto keep=weak.lock();block(ast(id).children[1],[this,id,keep,done] {if(flow=="break") {flow.clear();if(!frame) globals.erase(id);push(done);}else if(flow=="return") {if(!frame) globals.erase(id);push(done);}else {flow.clear();push([keep] {(*keep)();});}});
            };push([loop] {(*loop)();});
        });
        else if(k=="expression") eval(n.children[0],[this,done](Value) {push(done);});
        else error(id,"E402","native statement not yet implemented: "+k);
    });
}
inline void ExecutionContext::call(Value fn,std::vector<Value> args,NodeId site,Done done) {
    const auto& f=object(fn);if(f.kind!="Function") error(site,"E202","value is not callable");
    if(f.syntax!=no_node) {
        const auto id=f.syntax;const auto& node=ast(id);const auto count=node.children.size()-1;
        if(args.size()!=count) error(site,"E202","wrong argument count: "+f.name);
        check("call_depth",calls.size()+1,site);
        auto next=std::make_shared<Frame>();next->function=fn;next->call=site;calls.push_back(next);
        for(std::size_t i=0;i<count;++i) typecheck(stored_type(fn,i),args[i],ast(site).children[i+1]);
        const auto& plan=program.functions.at(id);next->space=Lease(heap.state,{0,plan.locals.size()+1,0},site);
        next->locals.resize(plan.locals.size());next->types.resize(plan.locals.size());auto previous=frame;frame=next;
        for(std::size_t i=0;i<count;++i) define(node.children[i],args[i],stored_type(fn,i));
        const auto finish=[this,fn,id,previous,next,done](Value v) {
            const auto site=flow=="return"?return_site:ast(id).kind=="lambda"?ast(id).children.back():id;
            if(flow=="return") v=returned;
            typecheck(stored_type(fn,ast(id).children.size()-1),v,site);
            flow.clear();returned={};return_site=no_node;next->locals.clear();next->types.clear();next->space.release();frame=previous;calls.pop_back();push([done,v] {done(v);});
        };
        if(node.kind=="lambda") eval(node.children.back(),finish);else block(node.children.back(),[this,finish] {finish(null_);});return;
    }
    const auto& name=f.name;
    const std::map<std::string,std::size_t> arities={{"io.print",1},{"len",1},{"str",1},{"range",3},
        {"array.push",2},{"array.pop",1},{"array.copy",1},{"data.map",0},{"data.set",3},{"data.get",2},{"data.has",2},{"data.keys",1},{"data.kind",1},
        {"math.abs",1},{"text.contains",2},{"text.trim",1}};
    const auto signature=arities.find(name);if(signature==arities.end()) error(site,"E402","native host capability not implemented: "+name);
    if(args.size()!=signature->second) error(site,"E202","wrong argument count: "+name);
    if(name=="array.push" || name=="array.pop" || name=="array.copy") {
        typecheck("Array",args[0],ast(site).children[1]);auto& n=object(args[0]);
        if(name=="array.push") {append(args[0],args[1],site);done(null_);}
        else if(name=="array.copy") {std::vector<Value> copy;for(auto h:n.edges) copy.push_back(heap.pin(h));done(array(copy,site));}
        else {if(n.active) error(site,"E206","cannot resize an actively traversed Array");if(n.edges.empty()) error(site,"E204","empty Array");auto v=heap.pin(n.edges.back());n.edges.pop_back();--n.charge.slots;heap.state->refund({0,1,0});++n.version;done(v);}return;
    }
    if(name=="data.map") {done(make("Map",{1,0,0},site));return;}
    if(name=="data.kind") {auto kind=object(args[0]).kind;const std::map<std::string,std::string> names={{"Int","int"},{"Float","float"},{"String","string"},{"Bool","bool"},{"Null","null"},{"Array","array"},{"Map","map"}};done(string(names.count(kind)?names.at(kind):"other",site));return;}
    if(name=="data.set" || name=="data.get" || name=="data.has" || name=="data.keys") {
        typecheck("Map",args[0],ast(site).children[1]);auto& n=object(args[0]);
        if(name=="data.keys") {std::vector<Value> keys;for(std::size_t i=0;i<n.names.size();++i) keys.push_back(heap.pin(n.edges[2*i]));done(array(keys,site));return;}
        typecheck("String",args[1],ast(site).children[2]);const auto key=encode_utf8(object(args[1]).characters);const auto it=std::find(n.names.begin(),n.names.end(),key);const auto index=static_cast<std::size_t>(it-n.names.begin());
        if(name=="data.has") done(boolean(it!=n.names.end()));
        else if(name=="data.get") {if(it==n.names.end()) error(site,"E204","missing Map key");done(heap.pin(n.edges[2*index+1]));}
        else {if(it!=n.names.end()) n.edges[2*index+1]=args[2].ref();else {
            check("container_items",n.names.size()+1,site);Lease space(heap.state,{0,2,0},site);
            // Reserve all host vector capacity before changing either vector.
            n.names.reserve(n.names.size()+1);n.edges.reserve(n.edges.size()+2);n.names.push_back(key);n.edges.push_back(args[1].ref());n.edges.push_back(args[2].ref());n.charge.slots+=space.transfer().slots;
        }done(null_);}return;
    }
    if(name=="math.abs") {auto& n=object(args[0]);if(n.kind=="Int") done(integer(n.integer.abs(),site));else if(n.kind=="Float") done(real(std::abs(n.real),site));else error(ast(site).children[1],"E201","abs requires Int/Float");return;}
    if(name=="text.contains" || name=="text.trim") {
        typecheck("String",args[0],ast(site).children[1]);const auto& t=object(args[0]).characters;
        if(name=="text.contains") {typecheck("String",args[1],ast(site).children[2]);done(boolean(t.find(object(args[1]).characters)!=std::u32string::npos));}
        else {const auto space=[](char32_t c) {return (c>=9 && c<=13) || (c>=28 && c<=32) || c==133 || c==160 || c==5760 || (c>=8192 && c<=8202) || c==8232 || c==8233 || c==8239 || c==8287 || c==12288;};std::size_t a=0,b=t.size();while(a<b && space(t[a])) ++a;while(b>a && space(t[b-1])) --b;done(string(t.substr(a,b-a),site));}return;
    }
    if(name=="io.print") {
        auto text=display(args[0],site);const auto count=decode_utf8(text).text.size();check("text_codepoints",count,site);
        Lease formatting(heap.state,{0,0,4*(count+1)},site);write(output,text+"\n",false,site);done(null_);
    } else if(name=="range") done(range(args,site));
    else if(name=="str") {
        const auto& kind=object(args[0]).kind;
        if(kind!="Int" && kind!="Float" && kind!="String" && kind!="Bool" && kind!="Null") error(site,"E201","str requires a scalar");
        done(kind=="String"?args[0]:string(display(args[0],site),site));
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
}
