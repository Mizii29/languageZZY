#pragma once
#include <array>
#include <map>
#include <thread>
#include <variant>

namespace zzy::sketch {
using Id=std::int64_t;
using RGB=std::array<int,3>;
using XY=std::array<double,2>;
using Ids=std::vector<Id>;
constexpr double coordinate=1000000,style=10000,pi=3.14159265358979323846;
constexpr std::size_t dimension=32768,curves=65536,segments_limit=1000000,objects_limit=100000,
    entities_limit=256,history_limit=100000,history_bytes=64*1024*1024;
struct State {
    XY position{};
    double heading=0,width=1;
    bool down=true,cursor=true;
    RGB color{},fill{};
    std::string font="sans-serif",align="left";
    bool operator==(const State& x) const {
        return position==x.position && heading==x.heading && width==x.width && down==x.down &&
            cursor==x.cursor && color==x.color && fill==x.fill && font==x.font && align==x.align;
    }
    bool operator!=(const State& x) const {return !(*this==x);}
};
struct Stroke {std::vector<XY> points;RGB color{};double width=1;};
struct Geometry {
    Id id=0,layer=0;
    std::string kind="path";
    std::vector<Stroke> strokes;
    std::vector<XY> boundary;
    RGB fill{};
    XY center{};
    double diameter=0,size=12,angle=0;
    std::string text,font="sans-serif",align="left";
    std::shared_ptr<const std::vector<Geometry>> children;
};
inline Charge cost(const Geometry& g,std::size_t& segments) {
    Charge charge{1,4+g.boundary.size(),128+16*g.boundary.size()+4*(g.text.size()+g.font.size())};
    if(g.kind=="dot" || g.kind=="text") ++segments;
    for(const auto& s:g.strokes) {
        segments+=s.points.size()-1;
        charge=charge+Charge{0,1+s.points.size(),48+16*s.points.size()};
    }
    if(g.kind=="group"&&g.children) for(const auto& child:*g.children) {
        std::size_t count=0;const auto nested=cost(child,count);segments+=count;
        charge.slots+=nested.slots;charge.payload+=nested.payload;
    }
    return charge;
}
inline std::vector<const Geometry*> leaves(const Geometry& geometry) {
    std::vector<const Geometry*> out;std::vector<const Geometry*> todo{&geometry};
    while(!todo.empty()) {const auto* current=todo.back();todo.pop_back();if(current->kind=="group"&&current->children) {
        for(auto it=current->children->rbegin();it!=current->children->rend();++it)todo.push_back(&*it);
    } else out.push_back(current);}
    return out;
}
struct Block {
    Geometry value;
    std::size_t segments;
    Lease charge;
    Block(Geometry data,std::size_t count,Lease owner):value(std::move(data)),segments(count),charge(std::move(owner)) {}
};
using BlockRef=std::shared_ptr<const Block>;
using Blocks=std::vector<BlockRef>;
using Entries=std::vector<std::pair<std::size_t,BlockRef>>;
struct Layer {
    std::string name;
    bool visible=true,locked=false;
    Handle handle;
    Lease charge;
};
struct Pen {
    State state;
    Id layer=0;
    Handle handle;
    Lease charge;
};
using Field=std::variant<Id,RGB,Ids,State,std::string,bool>;
struct Attr {std::string target,key;Field before,after;};
struct Delta {std::vector<Attr> attrs;Entries removed,added;std::size_t bytes=0;Lease charge;};
struct Entry {std::string label;std::vector<Delta> deltas;Lease charge;};
struct Draft {
    std::string pen;
    State before;
    Blocks strokes;
    std::size_t segments=0;
    Lease charge;
};
struct Registration {
    Handle root,callback;
    Id interval=0;
};
struct Document {
    std::thread::id thread=std::this_thread::get_id();
    Handle handle;
    Id width=0,height=0,next_id=1,next_layer=1;
    Id interval_ms=40,next_timer=1;
    std::string title;
    RGB background{255,255,255};
    std::map<Id,Layer> layers;
    Ids order{0};
    std::map<std::string,Pen,std::less<>> pens;
    Blocks objects;
    std::size_t segments=0,history_size=0,history_cost=0,redo_size=0,redo_cost=0;
    std::vector<Entry> undo,redo;
    std::optional<Entry> group;
    std::optional<Draft> draft;
    std::map<std::string,Registration> callbacks;
    std::map<Id,Registration> timers;
    Lease charge;
};
struct CanvasRef {std::shared_ptr<Document> doc;};
struct PenRef {std::shared_ptr<Document> doc;std::string name;};
struct LayerRef {std::shared_ptr<Document> doc;Id id;};
struct DrawingRef {Blocks objects;};

inline double radians(double a) {return a*pi/180;}
inline double heading(double a) {a=std::fmod(a,360);return a<0?a+360:a==0?0:a;}
inline double distance(XY p,XY a,XY b) {
    const double x=b[0]-a[0],y=b[1]-a[1],length=x*x+y*y;
    const double t=length?std::clamp(((p[0]-a[0])*x+(p[1]-a[1])*y)/length,0.,1.):0.;
    return std::hypot(p[0]-a[0]-t*x,p[1]-a[1]-t*y);
}
inline bool three_vertices(const std::vector<XY>& points) {
    if(points.size()<3) return false;
    const auto second=std::find_if(points.begin()+1,points.end(),[&](XY p) {return p!=points.front();});
    return second!=points.end() && std::any_of(second+1,points.end(),[&](XY p) {return p!=points.front() && p!=*second;});
}
inline std::string layer_key(Id id) {return "layer:"+std::to_string(id);}
inline Id layer_id(std::string_view target) {
    Id id=0;const auto conversion=std::from_chars(target.data()+6,target.data()+target.size(),id);
    if(conversion.ec!=std::errc{} || conversion.ptr!=target.data()+target.size()) throw std::logic_error("invalid history layer target");
    return id;
}
inline Field get(const Document& d,const Attr& a) {
    if(a.target=="canvas") {
        if(a.key=="segments") return static_cast<Id>(d.segments);
        if(a.key=="background") return d.background;
        return d.order;
    }
    if(a.target.compare(0,4,"pen:")==0) {
        const auto& p=d.pens.find(std::string_view(a.target).substr(4))->second;if(a.key=="state") return p.state;return p.layer;
    }
    const auto& l=d.layers.at(layer_id(a.target));
    if(a.key=="name") return l.name;
    return a.key=="visible"?l.visible:l.locked;
}
inline void set(Document& d,const Attr& a,Field value) {
    if(a.target=="canvas") {
        if(a.key=="segments") d.segments=static_cast<std::size_t>(std::get<Id>(value));
        else if(a.key=="background") d.background=std::get<RGB>(value);
        else d.order=std::get<Ids>(std::move(value));
    } else if(a.target.compare(0,4,"pen:")==0) {
        auto& p=d.pens.find(std::string_view(a.target).substr(4))->second;
        if(a.key=="state") {
            auto state=std::get<State>(std::move(value));state.cursor=p.state.cursor;p.state=std::move(state);
        } else p.layer=std::get<Id>(value);
    } else {
        auto& l=d.layers.at(layer_id(a.target));
        if(a.key=="name") l.name=std::get<std::string>(std::move(value));
        else (a.key=="visible"?l.visible:l.locked)=std::get<bool>(value);
    }
}
inline void attr(Delta& delta,const Document& d,std::string target,std::string key,Field after) {
    Attr a{std::move(target),std::move(key),{},std::move(after)};a.before=get(d,a);
    if(a.before!=a.after) delta.attrs.push_back(std::move(a));
}
inline bool active(const Document& d,Id layer) {return std::find(d.order.begin(),d.order.end(),layer)!=d.order.end();}
}
