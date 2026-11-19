#pragma once
#include "sketch_model.hpp"
#include "prepare.hpp"

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
    bool fits(Charge charge) const {return c.heap.state->fits(charge);}
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
    Value array(const std::vector<Value>& values) const {return c.array(values,site);}
    Value map(const std::vector<std::pair<std::string,Value>>& values) const {
        auto result=c.make("Map",{1,0,0},site);
        for(const auto& [key,value]:values) {auto text_value=c.string(key,site);c.map_insert(result,key,text_value,value,site);}
        return result;
    }
    Value map_value(const Value& value,const std::string& key) const {
        const auto& n=c.object(value);auto it=std::find(n.names.begin(),n.names.end(),key);
        if(n.kind!="Map" || it==n.names.end()) error("E401","invalid sketch document field");
        return c.heap.pin(n.edges.at(2*static_cast<std::size_t>(it-n.names.begin())+1));
    }
    Value make_color(RGB color) const {
        const auto packed=(color[0]<<16)|(color[1]<<8)|color[2];
        auto result=c.heap.native("sketch.Color",std::make_shared<RGB>(color),{1,0,3},site);
        c.object(result).integer=BigInt(packed);c.object(result).frozen=true;return result;
    }
    std::vector<XY> translate_points(const std::vector<XY>& points,double x,double y,double scale=1,double angle=0) const {
        const auto theta=sketch::radians(angle),co=std::cos(theta)*scale,si=std::sin(theta)*scale;
        std::vector<XY> out;out.reserve(points.size());
        for(auto p:points) {c.point();out.push_back(point(x+co*p[0]-si*p[1],y+si*p[0]+co*p[1]));}
        return out;
    }
    Value point_array(XY p) const {return array({c.real(p[0],site),c.real(p[1],site)});}
    Value color_array(RGB value) const {return array({integer(value[0]),integer(value[1]),integer(value[2])});}
    Value encode_geometry(const Geometry& g) const {
        if(g.kind=="path" || g.kind=="fill") {
            std::vector<Value> strokes;
            for(const auto& stroke:g.strokes) {
                std::vector<Value> points;for(auto p:stroke.points)points.push_back(point_array(p));
                strokes.push_back(map({{"points",array(points)},{"color",color_array(stroke.color)},{"width",c.real(stroke.width,site)}}));
            }
            std::vector<std::pair<std::string,Value>> fields{{"type",c.string(g.kind,site)},{"strokes",array(strokes)}};
            if(g.kind=="fill") {std::vector<Value> boundary;for(auto p:g.boundary)boundary.push_back(point_array(p));fields.emplace_back("boundary",array(boundary));fields.emplace_back("fill",color_array(g.fill));}
            return map(fields);
        }
        if(g.kind=="dot") return map({{"type",c.string("dot",site)},{"center",point_array(g.center)},{"diameter",c.real(g.diameter,site)},{"fill",color_array(g.fill)}});
        if(g.kind=="text") return map({{"type",c.string("text",site)},{"center",point_array(g.center)},{"text",c.string(g.text,site)},
            {"font",c.string(g.font,site)},{"align",c.string(g.align,site)},{"size",c.real(g.size,site)},{"angle",c.real(g.angle,site)},{"fill",color_array(g.fill)}});
        if(g.kind=="group" && g.children) {std::vector<Value> children;for(const auto& item:*g.children)children.push_back(encode_geometry(item));return map({{"type",c.string("group",site)},{"children",array(children)}});}
        error("E401","unsupported sketch geometry");
    }
    Value encode_drawing(const sketch::Blocks& blocks) const {
        std::vector<Value> objects;for(const auto& block:blocks)objects.push_back(encode_geometry(block->value));
        return map({{"schema_version",integer(1)},{"kind",c.string("zzy-drawing",site)},{"objects",array(objects)}});
    }
    double json_number(const Value& v,double limit=sketch::coordinate,bool positive=false) const {
        const auto& n=c.object(v);
        if(n.kind!="Int" && n.kind!="Float")error("E401","invalid sketch number");
        const double result=n.kind=="Int"?static_cast<double>(bounded(v,-static_cast<Id>(limit),static_cast<Id>(limit),"E401")):n.real;
        if(!std::isfinite(result)||std::abs(result)>limit||(positive&&result<=0))error("E401","sketch number outside bounds");return result;
    }
    Id json_integer(const Value& v,Id lo,Id hi) const {
        if(c.object(v).kind!="Int")error("E401","invalid sketch integer");return bounded(v,lo,hi,"E401");
    }
    std::string json_text(const Value& v) const {if(c.object(v).kind!="String")error("E401","invalid sketch string");return text(v);}
    bool json_bool(const Value& v) const {if(c.object(v).kind!="Bool")error("E401","invalid sketch Boolean");return c.object(v).flag;}
    XY decode_point(const Value& value) const {
        if(c.object(value).kind!="Array"||c.object(value).edges.size()!=2)error("E401","invalid sketch point");
        return point(json_number(c.heap.pin(c.object(value).edges[0])),json_number(c.heap.pin(c.object(value).edges[1])));
    }
    RGB decode_color(const Value& value) const {
        if(c.object(value).kind!="Array"||c.object(value).edges.size()!=3)error("E401","invalid sketch color");RGB out{};
        for(std::size_t i=0;i<3;++i)out[i]=static_cast<int>(json_integer(c.heap.pin(c.object(value).edges[i]),0,255));return out;
    }
    Geometry decode_geometry(const Value& value,Id identity=0,Id layer=0,bool child=false) const {
        if(c.object(value).kind!="Map")error("E401","invalid sketch geometry");auto kind=json_text(map_value(value,"type"));Geometry g;g.id=identity;g.layer=layer;g.kind=kind;
        if(kind=="path"||kind=="fill") {
            if(kind=="fill")fields(value,{"type","strokes","boundary","fill"});
            else fields(value,{"type","strokes"});
            const auto strokes=map_value(value,"strokes");if(c.object(strokes).kind!="Array"||c.object(strokes).edges.empty())error("E401","invalid sketch strokes");
            std::size_t segments=0;
            for(auto h:c.object(strokes).edges) {auto stroke=c.heap.pin(h);auto pts=map_value(stroke,"points"),clr=map_value(stroke,"color");
                fields(stroke,{"points","color","width"});
                if(c.object(pts).kind!="Array"||c.object(pts).edges.size()<2)error("E401","invalid sketch stroke points");
                segments+=items(pts).size()-1;capacity("path_segments",segments,sketch::segments_limit);
                sketch::Stroke out;for(auto p:items(pts)){c.point();out.points.push_back(decode_point(pin(p)));}
                out.color=decode_color(clr);out.width=json_number(map_value(stroke,"width"),sketch::style,true);g.strokes.push_back(std::move(out));}
            if(kind=="fill") {auto boundary=map_value(value,"boundary");if(c.object(boundary).kind!="Array")error("E401","invalid fill boundary");for(auto p:c.object(boundary).edges)g.boundary.push_back(decode_point(c.heap.pin(p)));
                g.fill=decode_color(map_value(value,"fill"));if(!sketch::three_vertices(g.boundary)||g.boundary.size()!=segments+1)error("E401","invalid fill boundary");
                std::size_t at=0;
                for(const auto& stroke:g.strokes) {
                    const std::size_t start=at?1:0;
                    if(start&&stroke.points.front()!=g.boundary[at-1])error("E401","disconnected fill strokes");
                    for(std::size_t i=start;i<stroke.points.size();++i) {
                        c.point();if(stroke.points[i]!=g.boundary[at++])error("E401","inconsistent fill boundary");
                    }
                }
            }
            return g;
        }
        if(kind=="dot") {fields(value,{"type","center","diameter","fill"});
            g.center=decode_point(map_value(value,"center"));g.diameter=json_number(map_value(value,"diameter"),sketch::style,true);g.fill=decode_color(map_value(value,"fill"));
            for(auto axis:g.center)if(std::abs(axis)+g.diameter/2>sketch::coordinate)error("E401","invalid dot bounds");
            return g;}
        if(kind=="text") {fields(value,{"type","center","text","font","align","size","angle","fill"});g.center=decode_point(map_value(value,"center"));g.text=json_text(map_value(value,"text"));g.font=json_text(map_value(value,"font"));g.align=json_text(map_value(value,"align"));
            if(g.align!="left"&&g.align!="center"&&g.align!="right")error("E401","invalid text alignment");g.size=json_number(map_value(value,"size"),sketch::style,true);g.angle=json_number(map_value(value,"angle"),1000000);g.fill=decode_color(map_value(value,"fill"));return g;}
        if(kind=="group"&&!child) {fields(value,{"type","children"});auto children=map_value(value,"children");
            capacity("objects",items(children).size(),sketch::objects_limit);
            std::vector<Geometry> decoded;
            for(auto h:items(children)){c.point();decoded.push_back(decode_geometry(pin(h),0,layer,true));}
            g.children=std::make_shared<const std::vector<Geometry>>(std::move(decoded));return g;}
        error("E401","unknown sketch geometry");
    }
    Value decode_json(const Value& result) const {
        if(c.object(result).kind!="Result")error("E401","invalid JSON decoder result");if(!c.object(result).flag)error("E401","invalid sketch JSON");return c.heap.pin(c.object(result).edges[0]);
    }
    void fields(const Value& v,std::initializer_list<std::string_view> keys) const {
        const auto& n=c.object(v);
        if(n.kind!="Map"||n.names.size()!=keys.size()||
           !std::all_of(keys.begin(),keys.end(),[&](std::string_view k){return std::find(n.names.begin(),n.names.end(),k)!=n.names.end();}))
            error("E401","unexpected schema fields");
    }
    const std::vector<Handle>& items(const Value& v) const {
        const auto& n=c.object(v);
        if(n.kind!="Array")error("E401","expected an Array in sketch data");
        return n.edges;
    }
    Value string(const std::string& s) const {return c.string(s,site);}
    Value boolean(bool b) const {return c.boolean(b);}
    Value real(double n) const {return c.real(n,site);}
    Value pin(Handle h) const {return c.heap.pin(h);}
    Value success(const Value& v) const {return c.result(true,v,site);}
    Value failure(const std::string& s) const {return c.result(false,string(s),site);}
    Geometry transform(const Geometry& g,double x,double y,double scale,double angle) const {
        c.point();
        Geometry out=g;
        if(g.children) {
            std::vector<Geometry> children;
            children.reserve(g.children->size());
            for(const auto& child:*g.children)children.push_back(transform(child,x,y,scale,angle));
            out.children=std::make_shared<const std::vector<Geometry>>(std::move(children));
            return out;
        }
        const auto style_value=[&](double value) {
            if(!std::isfinite(value)||value<=0||value>sketch::style)error("E208","sketch style outside permitted range");
            return value;
        };
        for(auto& stroke:out.strokes) {
            stroke.points=translate_points(stroke.points,x,y,scale,angle);
            stroke.width=style_value(stroke.width*scale);
        }
        out.boundary=translate_points(out.boundary,x,y,scale,angle);
        if(g.kind=="dot"||g.kind=="text")out.center=translate_points({g.center},x,y,scale,angle).front();
        if(g.kind=="dot") {
            out.diameter=style_value(g.diameter*scale);
            point(out.center[0]-out.diameter/2,out.center[1]-out.diameter/2);
            point(out.center[0]+out.diameter/2,out.center[1]+out.diameter/2);
        }
        if(g.kind=="text") {out.size=style_value(g.size*scale);out.angle=sketch::heading(g.angle+angle);}
        return out;
    }
    Value drawing_value(sketch::Blocks blocks) const {
        auto count=blocks.size();
        auto v=c.heap.native("sketch.Drawing",std::make_shared<sketch::DrawingRef>(sketch::DrawingRef{std::move(blocks)}),{1,count+1,0},site);
        c.object(v).frozen=true;
        return v;
    }
    Value project(const std::string& op,const std::vector<Value>& a,const Doc* doc=nullptr) const;
    Value project_data(const Doc& d) const;
    std::shared_ptr<Doc> read_project(const Value& data) const;
    Value state_record(const State& p) const;
    State read_state(const Value& data) const;
    Doc projection(const Doc& d) const;
    void project_step(Doc& d,const sketch::Entry& entry,bool forward,bool validate=false) const;
    void validate_projection(const Doc& d) const;
    Value pattern(const std::string& op,const std::vector<Value>& a) const;
    Value events(const std::string& op,const std::vector<Value>& args,Doc& d) const;
    void clear_events(Doc& d) const;
    void unlink_event(Doc& d,Handle registration) const;
    Id interval(const Value& duration) const;
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
#include "sketch_persistence.hpp"
#include "sketch_events.hpp"
#include "sketch_replay.hpp"
