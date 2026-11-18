#pragma once
namespace zzy {
inline void ExecutionContext::array_library(const std::string& name,const std::vector<Value>& args,NodeId site,Done done) {
    const auto source=args[0];auto& input_array=object(source);
    if(name=="array.map" || name=="array.filter") {
        struct Iteration {
            Value source,result,callback;std::shared_ptr<HeapState> heap;
            ~Iteration() {if(heap && !heap->closed) --heap->get(source.ref()).active;}
        };
        auto state=std::make_shared<Iteration>();state->source=source;state->callback=args[1];
        state->result=array({},site);state->heap=heap.state;++input_array.active;
        auto step=std::make_shared<std::function<void(std::size_t)>>();std::weak_ptr<std::function<void(std::size_t)>> weak=step;
        *step=[this,state,name,site,done,weak](std::size_t index) {
            point();if(index==object(state->source).edges.size()) {done(state->result);return;}
            const auto item=heap.pin(object(state->source).edges[index]);
            auto slot=std::make_shared<Lease>(heap.state,Charge{0,1,0},site);auto keep=weak.lock();
            call(state->callback,{item},site,[this,state,name,site,item,index,slot,keep](Value mapped) {
                if(name=="array.filter") {typecheck("Bool",mapped,ast(site).children[2]);if(object(mapped).flag) append(state->result,item,site);}
                else append(state->result,mapped,site);
                slot->release();push([keep,index] {(*keep)(index+1);});
            },{ast(site).children[1]});
        };
        push([step] {(*step)(0);});return;
    }
    if(name=="array.sorted") {
        const auto kind=input_array.edges.empty()?"":object(heap.pin(input_array.edges[0])).kind;
        if(!kind.empty() && kind!="Int" && kind!="String") error(site,"E201","sorted requires homogeneous Int/String");
        for(auto handle:input_array.edges) {point();if(object(heap.pin(handle)).kind!=kind) error(site,"E201","sorted requires homogeneous Int/String");}
        Lease scratch(heap.state,{0,3*input_array.edges.size(),0},site);
        std::vector<Value> ordered;ordered.reserve(input_array.edges.size());for(auto handle:input_array.edges) {point();ordered.push_back(heap.pin(handle));}
        std::stable_sort(ordered.begin(),ordered.end(),[this,site](const Value& a,const Value& b) {point();return compare(a,b,site)<0;});
        auto result=array({},site);for(const auto& value:ordered) {point();append(result,value,site);}
        done(result);return;
    }
    auto total=integer(BigInt(),site);Value minimum=null_,maximum=null_;
    for(auto handle:input_array.edges) {
        point();const auto item=heap.pin(handle);typecheck("Int",item,ast(site).children[1]);
        total=publish_int(arithmetic("PLUS",object(total).integer,object(item).integer,site),site);
        if(minimum.same(null_) || compare(item,minimum,site)<0) minimum=item;
        if(maximum.same(null_) || compare(item,maximum,site)>0) maximum=item;
    }
    if(name=="array.sum") {done(total);return;}
    const auto count=integer(BigInt(static_cast<std::int64_t>(input_array.edges.size())),site);
    const auto definition=builtin("array.Stats",site);
    auto result=make("Shape",{1,5,0},site,{definition,count,total,minimum,maximum});
    object(result).names=object(definition).names;done(result);
}

inline Value ExecutionContext::text_library(const std::string& name,const std::vector<Value>& args,NodeId site) {
    const auto find=[this](const std::u32string& text,const std::u32string& needle,std::size_t from) {
        std::size_t ticks=0;if(needle.size()>text.size()) return std::u32string::npos;
        for(std::size_t i=from;i<=text.size()-needle.size();++i) {
            std::size_t j=0;for(;j<needle.size();++j) {if((ticks++&4095)==0) point();if(text[i+j]!=needle[j]) break;}
            if(j==needle.size()) return i;
        }
        return std::u32string::npos;
    };
    if(name=="text.contains") return boolean(find(object(args[0]).characters,object(args[1]).characters,0)!=std::u32string::npos);
    if(name=="text.trim") {
        const auto& text=object(args[0]).characters;
        const auto space=[](char32_t c) {return (c>=9 && c<=13) || (c>=28 && c<=32) || c==133 || c==160 || c==5760 || (c>=8192 && c<=8202) || c==8232 || c==8233 || c==8239 || c==8287 || c==12288;};
        std::size_t start=0,end=text.size();while(start<end && space(text[start])) {point();++start;}while(end>start && space(text[end-1])) {point();--end;}
        Lease space_used(heap.state,{0,0,4*(end-start)},site);auto converted=text.substr(start,end-start);space_used.release();
        return string(std::move(converted),site);
    }
    if(name=="text.safe_int") {
        const auto& text=object(args[0]).characters;std::size_t start=0,end=text.size();
        const auto space=[](char32_t c) {return c==U' ' || c==U'\t' || c==U'\r' || c==U'\n';};
        while(start<end && space(text[start])) {point();++start;}while(end>start && space(text[end-1])) {point();--end;}
        Lease sliced(heap.state,{0,0,4*(end-start)},site);
        std::size_t digits=0;for(std::size_t i=start;i<end;++i) {point();if(text[i]>=U'0' && text[i]<=U'9') ++digits;}
        check("numeric_digits",digits,site);const bool negative=start<end && text[start]==U'-';
        std::size_t first=start;if(first<end && (text[first]==U'+' || text[first]==U'-')) ++first;
        bool valid=first<end;for(auto i=first;i<end;++i) {point();valid=valid && text[i]>=U'0' && text[i]<=U'9';}
        if(!valid) return result(false,string("invalid integer",site),site);
        auto value=integer(BigInt(),site);
        for(auto i=first;i<end;++i) {
            point();value=publish_int(arithmetic("MULTIPLY",object(value).integer,BigInt(10),site),site);
            value=publish_int(arithmetic("PLUS",object(value).integer,BigInt(text[i]-U'0'),site),site);
        }
        if(negative) {Lease copy(heap.state,{0,0,int_bytes(object(value).integer)},site);auto n=-object(value).integer;copy.release();value=integer(std::move(n),site);}
        return result(true,value,site);
    }
    if(name=="text.join") {
        const auto& values=object(args[0]);const auto& separator=object(args[1]).characters;std::size_t size=0;
        for(auto handle:values.edges) {point();typecheck("String",heap.pin(handle),ast(site).children[1]);}
        for(auto handle:values.edges) {point();size+=object(heap.pin(handle)).characters.size();}
        if(!values.edges.empty()) size+=(values.edges.size()-1)*separator.size();
        check("text_codepoints",size,site);Lease refs(heap.state,{0,values.edges.size(),0},site),text_space(heap.state,{0,0,4*size},site);
        std::u32string text;text.reserve(size);
        for(std::size_t i=0;i<values.edges.size();++i) {point();if(i) text+=separator;text+=object(heap.pin(values.edges[i])).characters;}
        text_space.release();return string(std::move(text),site);
    }
    const bool replace=name=="text.replace";const auto& text=object(args[replace?2:0]).characters;
    const auto& separator=object(args[replace?0:1]).characters;
    if(separator.empty()) error(site,"E208",replace?"empty replacement target":"empty separator");
    std::size_t count=0;
    for(std::size_t start=0;;) {
        point();const auto at=find(text,separator,start);if(at==std::u32string::npos) break;
        ++count;start=at+separator.size();
    }
    if(replace) {
        const auto& replacement=object(args[1]).characters;const auto size=text.size()-count*separator.size()+count*replacement.size();
        check("text_codepoints",size,site);Lease space(heap.state,{0,0,4*size},site);std::u32string converted;converted.reserve(size);
        std::size_t start=0;for(;;) {
            point();const auto at=find(text,separator,start);
            if(at==std::u32string::npos) {converted.append(text,start,std::u32string::npos);break;}
            converted.append(text,start,at-start);converted+=replacement;start=at+separator.size();
        }
        space.release();return string(std::move(converted),site);
    }
    check("container_items",count+1,site);auto converted=array({},site);
    std::size_t start=0;for(;;) {
        point();const auto at=find(text,separator,start);const auto stop=at==std::u32string::npos?text.size():at;
        Lease piece(heap.state,{0,0,4*(stop-start)},site);auto part=text.substr(start,stop-start);piece.release();
        append(converted,string(std::move(part),site),site);
        if(at==std::u32string::npos) return converted;start=at+separator.size();
    }
}
}
