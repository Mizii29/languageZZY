#pragma once

namespace zzy {
inline Value SketchHost::render(const Doc& d,const Value& target) const {
    std::string svg;
    auto storage=reserve({});std::size_t points=0;
    const auto number=[](double n) {return n==0?std::string("0"):ExecutionContext::float_text(n);};
    const auto rgb=[](RGB x){constexpr char hex[]="0123456789abcdef";std::string s="#";for(int v:x){s+=hex[v/16];s+=hex[v%16];}return s;};
    const auto append=[&](std::string_view part) {
        c.point();const auto count=c.codepoints(part);c.check("text_codepoints",points+count,site);
        c.check("io_payload_bytes",svg.size()+part.size(),site);storage.grow({0,0,part.size()},site);
        svg.append(part);points+=count;
    };
    const auto escape=[&](std::string_view x) {
        for(std::size_t i=0;i<x.size();) {
            const auto start=i;const auto ch=utf8_next(x,i);
            switch(ch){case U'&':append("&amp;");break;case U'<':append("&lt;");break;case U'>':append("&gt;");break;case U'"':append("&quot;");break;
                case U'\'':append("&apos;");break;case U'\r':append("&#13;");break;
                default:if((ch<0x20 && ch!=U'\n' && ch!=U'\t') || ch==0xfffe || ch==0xffff)throw std::invalid_argument("character forbidden by XML 1.0");append(x.substr(start,i-start));}
        }
    };
    const auto dimensions=" width=\""+std::to_string(d.width)+"\" height=\""+std::to_string(d.height)+"\"";
    append("<svg xmlns=\"http://www.w3.org/2000/svg\""+dimensions+" viewBox=\"0 0 "+std::to_string(d.width)+" "+std::to_string(d.height)+"\">\n<title>");
    escape(d.title);append("</title>\n<defs><clipPath id=\"canvas-clip\"><rect"+dimensions+"/></clipPath></defs>\n");
    append("<rect"+dimensions+" fill=\""+rgb(d.background)+"\"/>\n<g clip-path=\"url(#canvas-clip)\"><g transform=\"translate("+number(static_cast<double>(d.width)/2)+" "+number(static_cast<double>(d.height)/2)+")\">\n");
    const auto path=[&](const std::vector<XY>& xy) {
        append("<path d=\"");bool first=true;for(auto p:xy){append((first?"M":" L")+number(p[0])+" "+number(-p[1]));first=false;}
    };
    for(const auto layer:d.order) {
        const auto& l=d.layers.at(layer);if(!l.visible)continue;
        for(const auto& b:d.objects) {
            c.point();const auto& g=b->value;if(g.layer!=layer)continue;
            append("<g id=\"object-"+std::to_string(g.id)+"\">");
            const auto draw=[&](const Geometry& leaf) {
                if(!leaf.boundary.empty()){path(leaf.boundary);append(" Z\" fill=\""+rgb(leaf.fill)+"\" fill-rule=\"evenodd\" stroke=\"none\"/>");}
                if(leaf.kind=="dot")append("<circle cx=\""+number(leaf.center[0])+"\" cy=\""+number(-leaf.center[1])+"\" r=\""+number(leaf.diameter/2)+"\" fill=\""+rgb(leaf.fill)+"\"/>");
                if(leaf.kind=="text") {
                    const auto x=number(leaf.center[0]),y=number(-leaf.center[1]);
                    append("<text x=\""+x+"\" y=\""+y+"\" fill=\""+rgb(leaf.fill)+"\" font-size=\""+number(leaf.size)+"\" text-anchor=\""+(leaf.align=="left"?"start":leaf.align=="center"?"middle":"end")+"\" dominant-baseline=\"central\" font-family=\"");
                    escape(leaf.font);append("\" transform=\"rotate("+number(-leaf.angle)+" "+x+" "+y+")\">");escape(leaf.text);append("</text>");
                }
                for(const auto& s:leaf.strokes) {path(s.points);append("\" fill=\"none\" stroke=\""+rgb(s.color)+"\" stroke-width=\""+number(s.width)+"\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>");}
            };
            draw(g);append("</g>\n");
        }
    }
    append("</g></g>\n</svg>\n");
    auto result=c.string(svg,site);
    if(!target)return c.result(true,result,site);
    return c.file_library("io.write_atomic",{target,result},site);
}

inline Value SketchHost::pen_call(Doc& d,sketch::Pen& p,const std::string& name,const std::string& op,const std::vector<Value>& a) const {
    if(op=="position")return snapshot("sketch.Position",{c.real(p.state.position[0],site),c.real(p.state.position[1],site)});
    if(op=="heading")return c.real(p.state.heading,site);
    State state=p.state;Delta delta;const auto target="pen:"+name;
    if(op=="color"||op=="fill_color") {auto rgbv=color(a[1]);if(op=="color")state.color=rgbv;else state.fill=rgbv;}
    else if(op=="width")state.width=number(a[1],sketch::style,true);
    else if(op=="pen_up"||op=="pen_down")state.down=op=="pen_down";
    else if(op=="show_cursor"||op=="hide_cursor"){p.state.cursor=op=="show_cursor";return c.null_;}
    else if(op=="font")state.font=text(a[1]);
    else if(op=="text_align"){state.align=text(a[1]);if(state.align!="left"&&state.align!="center"&&state.align!="right")error("E208","invalid text alignment");}
    else if(op=="left"||op=="right"||op=="set_heading"){const auto angle=number(a[1],1000000);state.heading=sketch::heading(op=="left"?state.heading+angle:op=="right"?state.heading-angle:angle);}
    else if(op=="begin_fill"){if(!state.down||d.draft)error("E214","fill requires a down pen and no active fill");sketch::Draft draft;draft.pen=name;draft.before=state;draft.charge=reserve({1,3,128+4*name.size()});d.draft=std::move(draft);return c.null_;}
    else if(op=="cancel_fill"){if(!d.draft||d.draft->pen!=name)error("E214","no paired begin_fill");p.state=std::move(d.draft->before);d.draft.reset();return c.null_;}
    else if(op=="end_fill"){
        if(!d.draft||d.draft->pen!=name)error("E214","no paired begin_fill");
        std::size_t points=0;for(const auto& b:d.draft->strokes)points+=b->value.strokes[0].points.size();
        auto scratch=reserve({0,2*points+d.draft->strokes.size(),32*points+sizeof(sketch::Stroke)*d.draft->strokes.size()});
        std::vector<XY> boundary;
        for(const auto& b:d.draft->strokes)for(std::size_t i=boundary.empty()?0:1;i<b->value.strokes[0].points.size();++i){c.point();boundary.push_back(b->value.strokes[0].points[i]);}
        if(!sketch::three_vertices(boundary))error("E214","fill needs three distinct vertices");
        Geometry g;g.kind="fill";g.layer=p.layer;g.boundary=std::move(boundary);g.fill=d.draft->before.fill;
        for(const auto& b:d.draft->strokes)g.strokes.push_back(b->value.strokes[0]);
        Delta change;if(d.draft->before!=state)change.attrs.push_back({"pen:"+name,"state",d.draft->before,state});
        add(d,change,std::move(g));commit(d,std::move(change));d.draft.reset();return c.null_;
    }
    else if(op=="forward"||op=="backward"||op=="move_to"||op=="jump_to"||op=="home"||op=="circle"||op=="polyline"||op=="bezier_to") {
        const auto scratch_count=op=="circle"||op=="bezier_to"?sketch::curves+1:op=="polyline"?c.object(a[1]).edges.size()+1:2;
        if(op=="polyline")capacity("batch_points",scratch_count-1,10000);
        auto scratch=reserve({0,scratch_count,16*scratch_count+2048});
        std::vector<XY> points;
        if(op=="forward"||op=="backward"){const auto v=number(a[1])*(op=="backward"?-1:1),t=sketch::radians(state.heading);state.position=point(state.position[0]+v*std::cos(t),state.position[1]+v*std::sin(t));points={p.state.position,state.position};}
        else if(op=="move_to"||op=="jump_to"){state.position=point(number(a[1]),number(a[2]));if(op=="move_to")points={p.state.position,state.position};}
        else if(op=="home"){state.position={};state.heading=0;points={p.state.position,state.position};}
        else if(op=="circle"){const auto radius=number(a[1]),extent=number(a[2],1000000);if(radius==0)error("E208","arc radius cannot be zero");if(extent==0)return c.null_;points=arc(state,radius,extent);}
        else if(op=="polyline"){
            const auto& input=c.object(a[1]);capacity("batch_points",input.edges.size(),10000);if(input.edges.empty())return c.null_;points.reserve(input.edges.size()+1);points.push_back(state.position);
            for(auto edge:input.edges){c.point();const auto& pair=c.heap.state->get(edge);if(pair.kind!="Array"||pair.edges.size()!=2)error("E201","polyline point must be a two-number Array");auto x=c.heap.pin(pair.edges[0]),y=c.heap.pin(pair.edges[1]);const auto px=number(x),py=number(y);points.push_back(point(px,py));}
            state.position=points.back();
        } else {
            const auto x=number(a[1]),y=number(a[2]),z=number(a[3]),w=number(a[4]),u=number(a[5]),v=number(a[6]);const auto end=point(u,v);
            points=bezier(state.position,point(x,y),point(z,w),end);state.position=end;
        }
        if(op=="jump_to")points.clear();
        move(d,p,name,state,std::move(points));return c.null_;
    }
    else if(op=="dot"||op=="text"){
        Geometry g;g.kind=op;g.layer=p.layer;g.center=state.position;g.fill=state.color;
        if(op=="dot"){g.diameter=number(a[1],sketch::style,true);point(g.center[0]-g.diameter/2,g.center[1]-g.diameter/2);point(g.center[0]+g.diameter/2,g.center[1]+g.diameter/2);}
        else {g.text=text(a[1]);g.font=state.font;g.align=state.align;g.size=number(a[2],sketch::style,true);}
        add(d,delta,std::move(g));commit(d,std::move(delta));return c.null_;
    }
    else throw std::logic_error("unhandled registered sketch pen operator");
    if(op=="font" && state.font!=p.state.font) {
        auto charge=reserve({0,0,4*state.font.size()});
        move(d,p,name,std::move(state));p.charge.absorb(std::move(charge));
    } else move(d,p,name,std::move(state));
    return c.null_;
}

inline Value SketchHost::invoke(const std::string& qualified,const std::vector<Value>& args) const {
    const auto op=qualified.substr(7);
    if(op=="canvas"){
        const auto width=bounded(args[0],1,sketch::dimension),height=bounded(args[1],1,sketch::dimension);
        auto d=canvas(width,height,text(args[2]));auto v=canvas_value(d);
        d->layers[0].charge=reserve({0,1,28});
        return v;
    }
    if(op=="rgb"){
        RGB x{static_cast<int>(bounded(args[0],0,255)),static_cast<int>(bounded(args[1],0,255)),static_cast<int>(bounded(args[2],0,255))};
        auto v=c.heap.native("sketch.Color",std::make_shared<RGB>(x),{1,0,3},site);
        c.object(v).integer=BigInt((x[0]<<16)|(x[1]<<8)|x[2]);c.object(v).frozen=true;return v;
    }
    const auto receiver=args[0];owned(receiver);
    const auto& kind=ExecutionContext::tag(c.object(receiver));
    const sketch::PenRef* pen=nullptr;
    const sketch::LayerRef* layer=nullptr;
    std::shared_ptr<Doc> d;
    if(kind=="sketch.Canvas")d=c.heap.native<sketch::CanvasRef>(receiver,site).doc;
    else if(kind=="sketch.Pen"){pen=&c.heap.native<sketch::PenRef>(receiver,site);d=pen->doc;}
    else {layer=&c.heap.native<sketch::LayerRef>(receiver,site);d=layer->doc;}
    if(d->thread!=std::this_thread::get_id())error("E203","sketch document is thread owned");
    const bool write=op!="position"&&op!="heading"&&op!="svg_text"&&op!="save_svg"&&op!="layer_info"&&op!="show"&&op!="save_png";
    if(write&&(frozen(receiver.ref())||frozen(d->handle)))error("E203","sketch handle or document is frozen");
    if(layer&&!sketch::active(*d,layer->id))error("E203","layer is inactive");
    const auto read_position=op=="position"||op=="heading";
    if(d->draft&&!read_position) {
        const bool allowed=op=="forward"||op=="backward"||op=="left"||op=="right"||op=="set_heading"||op=="move_to"||op=="home"||op=="circle"||op=="polyline"||op=="bezier_to"||op=="color"||op=="width"||op=="end_fill"||op=="cancel_fill";
        if(!pen||d->draft->pen!=pen->name||!allowed)error("E214","operation is unavailable during active fill");
    }
    if(pen){
        auto& p=d->pens.at(pen->name);
        if(!sketch::active(*d,p.layer))error("E203","pen layer is inactive");
        if(op=="set_layer"){
            owned(args[1]);const auto& next=c.heap.native<sketch::LayerRef>(args[1],site);
            if(next.doc!=d||!sketch::active(*d,next.id))error("E203","layer is not active in this pen's canvas");
            Delta delta;sketch::attr(delta,*d,"pen:"+pen->name,"layer",next.id);commit(*d,std::move(delta));return c.null_;
        }
        if(write&&layer_locked(*d,p.layer))error("E203","pen layer is locked");
        return pen_call(*d,p,pen->name,op,args);
    }
    if(layer){
        Delta delta;const auto key=sketch::layer_key(layer->id);
        Lease name_charge;
        if(op=="move_layer"){
            auto order=d->order;const auto at=bounded(args[1],0,static_cast<Id>(order.size())-1,"E204");
            order.erase(std::find(order.begin(),order.end(),layer->id));order.insert(order.begin()+at,layer->id);
            sketch::attr(delta,*d,"canvas","layers",std::move(order));
        } else if(op=="rename_layer"){
            auto name=text(args[1]);if(name.empty())error("E208","layer name cannot be empty");
            for(auto id:d->order)if(id!=layer->id&&d->layers.at(id).name==name)error("E208","duplicate layer name");
            if(d->layers.at(layer->id).name!=name)name_charge=reserve({0,0,4*name.size()});
            sketch::attr(delta,*d,key,"name",std::move(name));
        } else sketch::attr(delta,*d,key,op=="lock_layer"?"locked":"visible",c.object(args[1]).flag);
        commit(*d,std::move(delta));
        if(name_charge)d->layers.at(layer->id).charge.absorb(std::move(name_charge));
        return c.null_;
    }
    if(op=="save_png"){idle(*d);return c.result(false,c.string("PNG backend unavailable",site),site);}
    if(op=="show")return c.result(false,c.string("GUI unavailable: run requires --gui",site),site);
    if(op=="svg_text"||op=="save_svg") {
        idle(*d);
        try{return render(*d,op=="save_svg"?args[1]:Value{});}
        catch(const std::invalid_argument& e){return c.result(false,c.string(e.what(),site),site);}
    }
    if(op=="undo"||op=="redo"||op=="clear_history")return history(*d,op);
    if(op=="begin_group"){idle(*d);sketch::Entry group;group.label=text(args[1]);group.charge=reserve({0,1,4*group.label.size()});d->group=std::move(group);return c.null_;}
    if(op=="end_group"){if(!d->group)error("E214","group is not paired");if(!d->group->deltas.empty())d->undo.push_back(std::move(*d->group));d->group.reset();return c.null_;}
    if(op=="background"||op=="clear"){
        Delta delta;
        if(op=="background")sketch::attr(delta,*d,"canvas","background",color(args[1]));
        else {
            for(auto id:d->order)if(layer_locked(*d,id))error("E203","layer is locked");
            for(std::size_t i=0;i<d->objects.size();++i){c.point();delta.removed.emplace_back(i,d->objects[i]);}
            sketch::attr(delta,*d,"canvas","segments",Id{0});
        }
        commit(*d,std::move(delta));return c.null_;
    }
    if(op=="layer_info"){std::vector<Value> values;std::size_t z=0;for(auto id:d->order){const auto& l=d->layers.at(id);std::size_t count=0;for(const auto& b:d->objects){c.point();count+=b->value.layer==id;}
        values.push_back(snapshot("sketch.LayerInfo",{c.string(l.name,site),c.boolean(l.visible),c.boolean(l.locked),integer(static_cast<Id>(count)),integer(static_cast<Id>(z++))}));}
        return c.array(values,site);
    }
    if(op=="add_layer"){
        const auto name=text(args[1]);if(name.empty())error("E208","layer name cannot be empty");for(auto id:d->order)if(d->layers.at(id).name==name)error("E208","duplicate layer name");
        capacity("layers",d->order.size()+1,sketch::entities_limit);const auto id=d->next_layer;auto handle=c.heap.native("sketch.Layer",std::make_shared<sketch::LayerRef>(sketch::LayerRef{d,id}),{1,0,0},site);
        sketch::Layer l;l.name=name;l.handle=handle.ref();l.charge=reserve({0,1,4*name.size()});d->layers.emplace(id,std::move(l));
        try {
            link(handle,receiver);
            link(receiver,handle);
            auto change=Delta{};auto order=d->order;order.push_back(id);sketch::attr(change,*d,"canvas","layers",std::move(order));commit(*d,std::move(change));
        } catch(...) {
            auto& n=c.object(receiver);
            if(!n.edges.empty()&&n.edges.back()==handle.ref()){n.edges.pop_back();--n.charge.slots;c.heap.state->refund({0,1,0});}
            d->layers.erase(id);throw;
        }
        ++d->next_layer;return handle;
    }
    if(op=="pen"){
        const auto name=text(args[1]);if(name.empty()||d->pens.count(name))error("E208","pen name must be non-empty and unique");
        capacity("pens",d->pens.size()+1,sketch::entities_limit);
        auto h=c.heap.native("sketch.Pen",std::make_shared<sketch::PenRef>(sketch::PenRef{d,name}),{1,0,0},site);
        sketch::Pen p;p.handle=h.ref();p.charge=reserve({0,2,8*name.size()+128});link(h,receiver);
        d->pens.emplace(name,std::move(p));try{link(receiver,h);}catch(...){d->pens.erase(name);throw;}
        return h;
    }
    error("E402","native sketch operation is not implemented: "+op);
}
inline Value ExecutionContext::sketch_library(const std::string& name,const std::vector<Value>& args,NodeId site) {
    return SketchHost{*this,site}.invoke(name,args);
}
}
