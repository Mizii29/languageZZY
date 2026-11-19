#pragma once
#include "sketch_model.hpp"

namespace zzy {
struct SketchHost {
    using Id=sketch::Id;
    using XY=sketch::XY;
    using RGB=sketch::RGB;
    using Doc=sketch::Document;
    using State=sketch::State;
    using Geometry=sketch::Geometry;
    using Delta=sketch::Delta;
    ExecutionContext& c;
    NodeId site;

    [[noreturn]] void error(const char* code,const std::string& message) const {c.error(site,code,message);}
    [[noreturn]] void limited(const char* name,std::size_t limit,std::size_t actual) const {
        error("E211","resource limit exceeded: sketch."+std::string(name)+", limit="+std::to_string(limit)+", requested="+std::to_string(actual));
    }
    void capacity(const char* name,std::size_t n,std::size_t limit) const {c.point();if(n>limit) limited(name,limit,n);}
    Lease reserve(Charge charge) const {return Lease(c.heap.state,charge,site);}
    Value integer(Id i) const {return c.integer(BigInt(i),site);}
    Id bounded(const Value& v,Id lo,Id hi,const char* code="E208") const {
        const auto& n=c.object(v).integer;
        if(n<BigInt(lo) || n>BigInt(hi)) error(code,"sketch integer is outside its permitted range");
        return std::stoll(n.decimal());
    }
    std::string text(const Value& v) const {return encode_utf8(c.object(v).characters);}
    double number(const Value& v,double limit=sketch::coordinate,bool positive=false) const {
        const auto& n=c.object(v);
        const auto value=n.kind=="Int"?static_cast<double>(bounded(v,-static_cast<Id>(limit),static_cast<Id>(limit))):n.real;
        if(n.kind!="Int" && n.kind!="Float") error("E201","expected sketch Int or Float");
        if(!std::isfinite(value) || std::abs(value)>limit || (positive && value<=0)) error("E208","sketch number is outside its permitted range");
        return value;
    }
    XY point(double x,double y) const {
        if(!std::isfinite(x) || !std::isfinite(y) || std::abs(x)>sketch::coordinate || std::abs(y)>sketch::coordinate)
            error("E208","derived sketch coordinate is out of range");
        return {x,y};
    }
    RGB color(const Value& v) const {return c.heap.native<RGB>(v,site);}
    bool frozen(Handle h) const {return h.owner && c.heap.state->get(h).frozen;}
    bool layer_locked(const Doc& d,Id id) const {const auto& l=d.layers.at(id);return l.locked || frozen(l.handle);}
    void owned(const Value& v) const {if(v.ref().owner!=c.heap.state->owner) error("E203","foreign sketch value");}
    void idle(const Doc& d) const {if(d.group || d.draft) error("E214","an edit group or fill is open");}
    void link(const Value& a,const Value& b) const {
        auto lease=reserve({0,1,0});auto& n=c.object(a);n.edges.push_back(b.ref());n.charge=n.charge+lease.transfer();
    }
    Value snapshot(const std::string& name,std::vector<Value> fields) const {
        auto def=c.builtin(name,site);fields.insert(fields.begin(),def);
        auto value=c.make("Shape",{1,fields.size(),0},site,fields);
        auto& n=c.object(value);n.name=name;n.names=c.object(def).names;n.frozen=true;
        return value;
    }
    std::shared_ptr<Doc> canvas(Id width,Id height,std::string title) const {
        auto charge=reserve({0,3,128+4*title.size()});
        auto d=std::make_shared<Doc>();d->width=width;d->height=height;d->title=std::move(title);d->charge=std::move(charge);
        d->layers[0].name="default";return d;
    }
    Value canvas_value(const std::shared_ptr<Doc>& d) const {
        auto v=c.heap.native("sketch.Canvas",std::make_shared<sketch::CanvasRef>(sketch::CanvasRef{d}),{1,0,0},site);
        d->handle=v.ref();return v;
    }
    sketch::BlockRef block(Geometry g) const {
        std::size_t count=0;auto cost=sketch::cost(g,count);capacity("path_segments",count,sketch::segments_limit);
        return std::make_shared<const sketch::Block>(std::move(g),count,reserve(cost));
    }
    void add(Doc& d,Delta& change,Geometry geometry) const {
        capacity("objects",d.objects.size()+1,sketch::objects_limit);
        if(d.next_id==INT64_MAX) error("E211","sketch object ID exhausted");
        geometry.id=d.next_id;auto b=block(std::move(geometry));
        capacity("path_segments",d.segments+b->segments,sketch::segments_limit);
        sketch::attr(change,d,"canvas","segments",static_cast<Id>(d.segments+b->segments));
        change.added.emplace_back(d.objects.size(),std::move(b));
    }
    void apply(Doc& d,const Delta& delta,bool forward,std::vector<sketch::Field> fields) const {
        const auto& removed=forward?delta.removed:delta.added;
        const auto& added=forward?delta.added:delta.removed;
        for(auto it=removed.rbegin();it!=removed.rend();++it) d.objects.erase(d.objects.begin()+static_cast<std::ptrdiff_t>(it->first));
        for(const auto& [i,b]:added) d.objects.insert(d.objects.begin()+static_cast<std::ptrdiff_t>(i),b);
        for(std::size_t i=0;i<fields.size();++i) sketch::set(d,delta.attrs[i],std::move(fields[i]));
    }
    std::vector<sketch::Field> prepare_fields(const Delta& delta,bool forward) const {
        std::vector<sketch::Field> out;out.reserve(delta.attrs.size());
        for(const auto& a:delta.attrs) out.push_back(forward?a.after:a.before);
        return out;
    }
    Charge delta_cost(const Delta& delta) const {
        Charge cost{0,2+4*delta.attrs.size()+delta.removed.size()+delta.added.size(),
            160+64*delta.attrs.size()+16*(delta.removed.size()+delta.added.size())};
        for(const auto& a:delta.attrs) for(const auto* v:{&a.before,&a.after}) {
            if(const auto* state=std::get_if<State>(v)) cost.payload+=4*(state->font.size()+state->align.size());
            if(const auto* str=std::get_if<std::string>(v)) cost.payload+=4*str->size();
            if(const auto* ids=std::get_if<sketch::Ids>(v)) cost.slots+=ids->size();
        }
        return cost;
    }
    // Reserve every throwing operation before publishing geometry, pen state or history.
    void commit(Doc& d,Delta delta) const {
        if(delta.attrs.empty() && delta.removed.empty() && delta.added.empty()) return;
        auto charge=delta_cost(delta);
        delta.bytes=static_cast<std::size_t>(charge.payload);
        capacity("history_commands",d.history_size-d.redo_size+1,sketch::history_limit);
        capacity("history_bytes",d.history_cost-d.redo_cost+delta.bytes,sketch::history_bytes);
        delta.charge=reserve(charge);
        auto scratch=reserve(charge);auto fields=prepare_fields(delta,true);
        const auto length=d.objects.size()-delta.removed.size()+delta.added.size();
        if(length>d.objects.capacity()) d.objects.reserve(std::max(length,d.objects.capacity()*2));
        const auto grows=std::any_of(delta.added.begin(),delta.added.end(),[&](const auto& p){return p.second->value.id==d.next_id;});
        sketch::Entry single;auto& entry=d.group?*d.group:single;
        if(entry.deltas.size()==entry.deltas.capacity()) entry.deltas.reserve(entry.deltas.size()*2+1);
        if(!d.group && d.undo.size()==d.undo.capacity()) d.undo.reserve(d.undo.size()*2+1);
        c.point();
        apply(d,delta,true,std::move(fields));
        if(grows) ++d.next_id;
        d.history_size=d.history_size-d.redo_size+1;d.history_cost=d.history_cost-d.redo_cost+delta.bytes;
        d.redo_size=d.redo_cost=0;d.redo.clear();
        entry.deltas.push_back(std::move(delta));if(!d.group) d.undo.push_back(std::move(single));
    }
    Value history(Doc& d,const std::string& op) const {
        idle(d);
        if(op=="clear_history") {
            d.undo.clear();d.redo.clear();d.history_cost=d.history_size=d.redo_cost=d.redo_size=0;
            return c.null_;
        }
        const bool forward=op=="redo";
        auto& from=forward?d.redo:d.undo;auto& to=forward?d.undo:d.redo;
        if(from.empty()) return c.false_;
        const auto& entry=from.back();
        std::vector<std::vector<sketch::Field>> fields;
        auto scratch=reserve({0,entry.deltas.size(),0});
        std::size_t bytes=0,maximum=d.objects.size(),length=maximum;
        for(std::size_t i=0;i<entry.deltas.size();++i) {
            const auto& delta=entry.deltas[forward?i:entry.deltas.size()-1-i];
            c.point();scratch.grow(delta_cost(delta),site);fields.push_back(prepare_fields(delta,forward));bytes+=delta.bytes;
            for(const auto& a:delta.attrs) {
                Handle handle;
                if(a.target.compare(0,4,"pen:")==0) handle=d.pens.find(std::string_view(a.target).substr(4))->second.handle;
                if(a.target.compare(0,6,"layer:")==0) handle=d.layers.at(sketch::layer_id(a.target)).handle;
                if(frozen(handle)) error("E203","history affects a frozen sketch handle");
            }
            for(const auto* edits:{&delta.removed,&delta.added})
                for(const auto& [j,b]:*edits) {
                    (void)j;const auto id=b->value.layer;
                    if(sketch::active(d,id) && layer_locked(d,id)) error("E203","history affects a locked sketch layer");
                }
            length=forward?length-delta.removed.size()+delta.added.size():length-delta.added.size()+delta.removed.size();
            maximum=std::max(maximum,length);
        }
        if(to.size()==to.capacity()) to.reserve(to.size()*2+1);
        if(maximum>d.objects.capacity()) d.objects.reserve(maximum);
        c.point();
        for(std::size_t i=0;i<entry.deltas.size();++i)
            apply(d,entry.deltas[forward?i:entry.deltas.size()-1-i],forward,std::move(fields[i]));
        if(forward) {d.redo_cost-=bytes;d.redo_size-=entry.deltas.size();}
        else {d.redo_cost+=bytes;d.redo_size+=entry.deltas.size();}
        to.push_back(std::move(from.back()));from.pop_back();return c.true_;
    }
    void move(Doc& d,sketch::Pen& p,const std::string& name,State state,std::vector<XY> points={}) const {
        Geometry g;if(p.state.down && points.size()>1) g.strokes.push_back({std::move(points),p.state.color,p.state.width});
        if(d.draft) {
            auto& draft=*d.draft;
            if(!g.strokes.empty()) {
                auto b=block(std::move(g));
                capacity("path_segments",d.segments+draft.segments+b->segments,sketch::segments_limit);
                draft.charge.grow({0,1,0},site);draft.strokes.push_back(std::move(b));draft.segments+=draft.strokes.back()->segments;
            }
            p.state=std::move(state);return;
        }
        Delta delta;sketch::attr(delta,d,"pen:"+name,"state",std::move(state));
        if(!g.strokes.empty()) {g.layer=p.layer;add(d,delta,std::move(g));}
        commit(d,std::move(delta));
    }
    std::vector<XY> arc(State& state,double radius,double extent) const {
        const auto theta=sketch::radians(state.heading),angle=std::copysign(1.,radius)*extent;
        const auto start=state.position;
        const auto center=point(start[0]-std::sin(theta)*radius,start[1]+std::cos(theta)*radius);
        const auto step=std::min(sketch::pi/2,4*std::asin(std::min(1.,std::sqrt(.25/(2*std::abs(radius))))));
        const auto count_d=std::ceil(std::abs(sketch::radians(angle))/step);
        if(count_d>sketch::curves) limited("curve_segments",sketch::curves,static_cast<std::size_t>(count_d));
        const auto count=std::max<std::size_t>(1,static_cast<std::size_t>(count_d));
        std::vector<XY> points;points.reserve(count+1);points.push_back(start);
        for(std::size_t i=1;i<=count;++i) {
            c.point();const auto t=sketch::radians(angle*static_cast<double>(i)/static_cast<double>(count));
            const auto x=start[0]-center[0],y=start[1]-center[1],co=std::cos(t),si=std::sin(t);
            points.push_back(point(center[0]+x*co-y*si,center[1]+x*si+y*co));
        }
        if(std::fmod(extent,360)==0) points.back()=start;
        else state.heading=sketch::heading(state.heading+angle);
        state.position=points.back();return points;
    }
    std::vector<XY> bezier(XY a,XY b,XY d,XY e) const {
        struct Curve {XY a,b,d,e;unsigned depth;};
        std::vector<Curve> stack{{a,b,d,e,0}};
        std::vector<XY> points{a};
        const auto mid=[](XY p,XY q)->XY{return {(p[0]+q[0])/2,(p[1]+q[1])/2};};
        while(!stack.empty()) {
            c.point();const auto x=stack.back();stack.pop_back();
            if(std::max(sketch::distance(x.b,x.a,x.e),sketch::distance(x.d,x.a,x.e))<=.25) {
                capacity("curve_segments",points.size(),sketch::curves);points.push_back(x.e);continue;
            }
            capacity("curve_depth",x.depth+1,24);
            const auto ab=mid(x.a,x.b),bd=mid(x.b,x.d),de=mid(x.d,x.e),abd=mid(ab,bd),bde=mid(bd,de),m=mid(abd,bde);
            stack.push_back({m,bde,de,x.e,x.depth+1});stack.push_back({x.a,ab,abd,m,x.depth+1});
        }
        return points;
    }
    Value pen_call(Doc& d,sketch::Pen& p,const std::string& name,const std::string& op,const std::vector<Value>& args) const;
    Value render(const Doc& d,const Value& target={}) const;
    Value invoke(const std::string& op,const std::vector<Value>& args) const;
};
}

#include "sketch_geometry.hpp"
