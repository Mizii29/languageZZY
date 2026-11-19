#pragma once

namespace zzy {
inline SketchHost::Id SketchHost::interval(const Value& duration) const {
    const auto& q=c.object(duration);
    if(q.length!=0||q.time!=1)error("E201","sketch interval requires a time Quantity");
    if(q.rational.numerator.sign()<=0)error("E208","sketch interval must be positive");
    auto scaled=c.arithmetic("MULTIPLY",q.rational.numerator,BigInt(1000),site);
    auto scratch=reserve({0,0,2*c.int_bytes(scaled.value)+c.int_bytes(q.rational.denominator)});
    auto division=scaled.value.divmod(q.rational.denominator,[&]{c.point();});
    const auto rounded=division.second.zero()?division.first:division.first+BigInt(1);
    if(rounded>BigInt(86400000))error("E208","sketch interval exceeds 24 hours");
    c.check("integer_bits",rounded.bits(),site);
    return std::stoll(rounded.decimal());
}

inline void SketchHost::unlink_event(Doc& d,Handle registration) const {
    auto& canvas=c.heap.state->get(d.handle);
    const auto edge=std::find(canvas.edges.begin(),canvas.edges.end(),registration);
    if(edge!=canvas.edges.end()) {
        canvas.edges.erase(edge);
        --canvas.charge.slots;
        c.heap.state->refund({0,1,0});
    }
}

inline void SketchHost::clear_events(Doc& d) const {
    for(const auto& x:d.callbacks)unlink_event(d,x.second.root);
    for(const auto& x:d.timers)unlink_event(d,x.second.root);
    d.callbacks.clear();
    d.timers.clear();
}

inline Value SketchHost::events(const std::string& op,const std::vector<Value>& args,Doc& d) const {
    if(op=="frame_interval") {d.interval_ms=interval(args[1]);return c.null_;}
    if(op=="cancel_timer") {
        const auto& id=c.object(args[1]).integer;
        if(id.sign()<=0||!(id<BigInt(d.next_timer)))return c.false_;
        const auto entry=d.timers.find(std::stoll(id.decimal()));
        if(entry==d.timers.end())return c.false_;
        unlink_event(d,entry->second.root);
        d.timers.erase(entry);
        return c.true_;
    }
    const auto& callback=args.back();
    owned(callback);
    const bool timer=op=="every";
    const auto& node=c.object(callback);
    const std::size_t arity=timer?0:op=="on_key"?1:3;
    if(node.syntax==no_node||c.ast(node.syntax).children.size()!=arity+1)
        error("E202","invalid fixed arity for sketch callback");
    const auto ms=timer?interval(args[1]):0;
    if(timer) {
        capacity("timers",d.timers.size()+1,sketch::entities_limit);
        if(d.next_timer==INT64_MAX)error("E211","sketch timer ID exhausted");
    }
    auto result=timer?integer(d.next_timer):c.null_;
    auto root=c.make("SketchRegistration",{1,1,32},site,{callback});
    const sketch::Registration value{root.ref(),callback.ref(),ms};
    link(args[0],root);
    try {
        if(timer) {d.timers.emplace(d.next_timer,value);++d.next_timer;}
        else {
            const auto name=op.substr(3);
            const auto existing=d.callbacks.find(name);
            if(existing==d.callbacks.end())d.callbacks.emplace(name,value);
            else {
                unlink_event(d,existing->second.root);
                existing->second=value;
            }
        }
    } catch(...) {
        unlink_event(d,root.ref());
        throw;
    }
    return result;
}
}
