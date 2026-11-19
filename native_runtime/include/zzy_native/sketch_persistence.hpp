#pragma once

namespace zzy {
inline Value SketchHost::pattern(const std::string& op,const std::vector<Value>& a) const {
    try {
        if(op=="drawing_from_json") {
            auto scratch=reserve({0,0,4*c.object(a[0]).characters.size()});
            auto data=decode_json(c.json_library("data.parse",a[0],site));
            fields(data,{"schema_version","kind","objects"});
            json_integer(map_value(data,"schema_version"),1,1);
            if(json_text(map_value(data,"kind"))!="zzy-drawing")error("E401","unsupported drawing schema");
            auto objects=map_value(data,"objects");
            capacity("objects",items(objects).size(),sketch::objects_limit);
            sketch::Blocks blocks;
            std::size_t segments=0;
            for(auto handle:items(objects)) {
                auto geometry=block(decode_geometry(pin(handle)));
                segments+=geometry->segments;
                capacity("path_segments",segments,sketch::segments_limit);
                blocks.push_back(std::move(geometry));
            }
            return success(drawing_value(std::move(blocks)));
        }
        owned(a[0]);
        const auto& drawing=c.heap.native<sketch::DrawingRef>(a[0],site);
        if(op=="save_function"&&drawing.objects.empty())return failure("sketch format/export: empty drawing");
        auto result=c.json_library("data.stringify",encode_drawing(drawing.objects),site);
        if(op=="drawing_text")return result;
        const auto name=text(a[2]);
        const auto encoded=text(decode_json(result));
        FrontendMeter meter(c.heap.state->policy,c.heap.state->cancelled);
        const auto name_source=std::make_shared<const Source>(L"<sketch-name>",name);
        const auto tokens=Lexer(name_source,meter).scan();
        if(tokens.size()!=2||tokens[0].kind!="IDENT"||spelling(tokens[0])!=name)
            return failure("sketch format/export: invalid function name");
        auto scratch=reserve({0,0,32*encoded.size()+2048});
        std::string escaped="\"";
        for(std::size_t i=0;i<encoded.size();) {
            c.point();
            if(encoded.compare(i,5,"[OoO]")==0) {escaped+="[OoO][OoO]";i+=5;continue;}
            switch(encoded[i]) {
            case '"':escaped+="[OoO]q";break;
            case '\n':escaped+="[OoO]n";break;
            case '\r':escaped+="[OoO]r";break;
            case '\t':escaped+="[OoO]t";break;
            default:escaped+=encoded[i];break;
            }
            ++i;
        }
        escaped+='"';
        const std::string payload=name=="__sketch_data"?"__sketch_payload":"__sketch_data";
        const auto generated="(zno) "+payload+":=(zzz)(sketch.drawing_from_json("+escaped+"));\n"
            "(addnew) "+name+"(canvas,x,y,scale,angle) -> (Result) {\n"
            "    (zno) d:=wake("+payload+")?;\n"
            "    (return) (^_^)(sketch.stamp(canvas,d,x,y,scale,angle));\n}\n";
        c.check("source_file_bytes",generated.size(),site);
        const auto source=std::make_shared<const Source>(L"<sketch-export.zzy>",generated);
        FrontendMeter generated_meter(c.heap.state->policy,c.heap.state->cancelled);
        AstBuilder ast(generated_meter);
        const auto generated_tokens=Lexer(source,generated_meter).scan();
        const auto root=Parser(generated_tokens,generated_meter,ast).parse();
        ProgramData data;
        Resolver(ast.nodes,data,generated_meter).resolve(root);
        scratch.release();
        return c.file_library("io.write_atomic",{a[1],string(generated)},site);
    } catch(const FrontendError& e) {
        if(e.code=="E211")error("E211",e.what());
        return failure(std::string("sketch format/export: ")+e.what());
    } catch(const RuntimeError& e) {
        if(e.code!="E401")throw;
        return failure(std::string("sketch format/export: ")+e.what());
    }
}

inline Value SketchHost::state_record(const State& p) const {
    return map({{"position",point_array(p.position)},{"heading",real(p.heading)},{"down",boolean(p.down)},
        {"color",color_array(p.color)},{"fill",color_array(p.fill)},{"width",real(p.width)},
        {"cursor",boolean(p.cursor)},{"font",string(p.font)},{"align",string(p.align)}});
}

inline SketchHost::State SketchHost::read_state(const Value& data) const {
    fields(data,{"position","heading","down","color","fill","width","cursor","font","align"});
    State p;
    p.position=decode_point(map_value(data,"position"));
    p.heading=json_number(map_value(data,"heading"),360);
    p.down=json_bool(map_value(data,"down"));
    p.color=decode_color(map_value(data,"color"));
    p.fill=decode_color(map_value(data,"fill"));
    p.width=json_number(map_value(data,"width"),sketch::style,true);
    p.cursor=json_bool(map_value(data,"cursor"));
    p.font=json_text(map_value(data,"font"));
    p.align=json_text(map_value(data,"align"));
    if(p.heading<0||p.heading>=360||(p.align!="left"&&p.align!="center"&&p.align!="right"))
        error("E401","invalid pen direction or alignment");
    return p;
}

inline Value SketchHost::project_data(const Doc& d) const {
    auto scratch=reserve({0,0,128});
    std::map<const sketch::Block*,std::size_t> indices;
    std::set<Id> layer_ids(d.order.begin(),d.order.end());
    std::vector<Value> geometry;
    const auto reference=[&](const sketch::BlockRef& b) {
        c.point();
        auto at=indices.find(b.get());
        if(at==indices.end()) {
            scratch.grow({0,3,64},site);
            at=indices.emplace(b.get(),geometry.size()).first;
            layer_ids.insert(b->value.layer);
            geometry.push_back(map({{"id",integer(b->value.id)},{"layer",integer(b->value.layer)},
                {"data",encode_geometry(b->value)}}));
        }
        return integer(static_cast<Id>(at->second));
    };
    const auto layer_order=[&](const sketch::Ids& order) {
        std::vector<Value> values;
        for(auto id:order) {layer_ids.insert(id);values.push_back(integer(id));}
        return array(values);
    };
    const auto record=[&](const sketch::Attr& attr,const sketch::Field& field)->Value {
        if(const auto* id=std::get_if<Id>(&field)) {
            if(attr.key=="layer")layer_ids.insert(*id);
            return integer(*id);
        }
        if(const auto* clr=std::get_if<RGB>(&field))return color_array(*clr);
        if(const auto* order=std::get_if<sketch::Ids>(&field))return layer_order(*order);
        if(const auto* state=std::get_if<State>(&field))return state_record(*state);
        if(const auto* label=std::get_if<std::string>(&field))return string(*label);
        return boolean(std::get<bool>(field));
    };
    const auto pairs=[&](const sketch::Entries& entries) {
        std::vector<Value> result;
        for(const auto& [index,b]:entries)result.push_back(array({integer(static_cast<Id>(index)),reference(b)}));
        return array(result);
    };
    const auto history=[&](const std::vector<sketch::Entry>& entries) {
        std::vector<Value> values;
        for(const auto& entry:entries) {
            std::vector<Value> deltas;
            for(const auto& delta:entry.deltas) {
                std::vector<Value> attrs;
                for(const auto& attr:delta.attrs) {
                    c.point();
                    if(attr.target.compare(0,6,"layer:")==0)layer_ids.insert(sketch::layer_id(attr.target));
                    attrs.push_back(map({{"target",string(attr.target)},{"key",string(attr.key)},
                        {"before",record(attr,attr.before)},{"after",record(attr,attr.after)}}));
                }
                deltas.push_back(map({{"attrs",array(attrs)},{"removed",pairs(delta.removed)},{"added",pairs(delta.added)}}));
            }
            values.push_back(map({{"label",string(entry.label)},{"deltas",array(deltas)}}));
        }
        return array(values);
    };
    std::vector<Value> objects,pens,layers;
    for(const auto& b:d.objects)objects.push_back(reference(b));
    const auto undo=history(d.undo),redo=history(d.redo);
    for(const auto& [name,p]:d.pens) {
        layer_ids.insert(p.layer);
        pens.push_back(map({{"name",string(name)},{"layer",integer(p.layer)},{"state",state_record(p.state)}}));
    }
    for(auto id:layer_ids) {
        const auto& layer=d.layers.at(id);
        layers.push_back(map({{"id",integer(id)},{"name",string(layer.name)},
            {"visible",boolean(layer.visible)},{"locked",boolean(layer.locked)}}));
    }
    return map({{"schema_version",integer(1)},{"kind",string("zzy-project")},{"width",integer(d.width)},
        {"height",integer(d.height)},{"title",string(d.title)},{"background",color_array(d.background)},
        {"next_id",integer(d.next_id)},{"next_layer",integer(d.next_layer)},{"interval_ms",integer(d.interval_ms)},
        {"layers",array(layers)},{"layer_order",layer_order(d.order)},{"pens",array(pens)},{"geometry",array(geometry)},
        {"objects",array(objects)},{"history",undo},{"redo",redo}});
}

inline SketchHost::Doc SketchHost::projection(const Doc& d) const {
    auto charge=reserve({0,3+d.objects.size()+4*(d.layers.size()+d.pens.size()),128+8*d.title.size()});
    Doc copy;
    copy.width=d.width;copy.height=d.height;copy.title=d.title;copy.background=d.background;
    copy.order=d.order;copy.segments=d.segments;copy.objects=d.objects;
    for(const auto& [id,l]:d.layers) {
        charge.grow({0,0,64+4*l.name.size()},site);
        auto& next=copy.layers[id];next.name=l.name;next.visible=l.visible;next.locked=l.locked;
    }
    for(const auto& [name,p]:d.pens) {
        charge.grow({0,0,128+4*(name.size()+p.state.font.size())},site);
        auto& next=copy.pens[name];next.state=p.state;next.layer=p.layer;
    }
    copy.charge=std::move(charge);
    return copy;
}

inline void SketchHost::project_step(Doc& view,const sketch::Entry& entry,bool forward,bool validate) const {
    for(std::size_t i=0;i<entry.deltas.size();++i) {
        c.point();
        const auto& delta=entry.deltas[forward?i:entry.deltas.size()-1-i];
        auto scratch=reserve(delta_cost(delta));
        const auto& removed=forward?delta.removed:delta.added;
        const auto& added=forward?delta.added:delta.removed;
        auto next=prepare_fields(delta,forward);
        if(validate) for(const auto& attr:delta.attrs) {
            auto expected=forward?attr.before:attr.after;
            auto actual=sketch::get(view,attr);
            if(auto* state=std::get_if<State>(&expected))state->cursor=std::get<State>(actual).cursor;
            if(actual!=expected)error("E401","history before/after mismatch");
        }
        for(auto it=removed.rbegin();it!=removed.rend();++it) {
            if(it->first>=view.objects.size()||view.objects[it->first]!=it->second)
                error("E401","history removal mismatch");
            view.objects.erase(view.objects.begin()+static_cast<std::ptrdiff_t>(it->first));
        }
        for(const auto& [index,b]:added) {
            if(index>view.objects.size())error("E401","history addition mismatch");
            if(view.objects.size()==view.objects.capacity()) {
                const auto growth=std::min(sketch::objects_limit+1,view.objects.size()*2+1);
                view.charge.grow({0,growth-view.objects.size(),0},site);
                view.objects.reserve(growth);
            }
            view.objects.insert(view.objects.begin()+static_cast<std::ptrdiff_t>(index),b);
            capacity("objects",view.objects.size(),sketch::objects_limit);
        }
        for(std::size_t index=0;index<next.size();++index)sketch::set(view,delta.attrs[index],std::move(next[index]));
        if(validate)validate_projection(view);
    }
}

inline void SketchHost::validate_projection(const Doc& view) const {
    auto scratch=reserve({0,view.objects.size()+view.order.size(),64+48*view.objects.size()+48*view.order.size()});
    std::set<Id> identities;
    std::set<std::string_view> names;
    std::size_t segments=0;
    capacity("objects",view.objects.size(),sketch::objects_limit);
    for(auto id:view.order)if(!names.insert(view.layers.at(id).name).second)error("E401","duplicate active layer name");
    for(const auto& [name,p]:view.pens) {
        (void)name;
        if(!sketch::active(view,p.layer))error("E401","pen on inactive layer");
    }
    for(const auto& b:view.objects) {
        c.point();
        if(!sketch::active(view,b->value.layer)||!identities.insert(b->value.id).second)
            error("E401","invalid active geometry reference");
        segments+=b->segments;
    }
    capacity("path_segments",segments,sketch::segments_limit);
    if(segments!=view.segments)error("E401","history segment count mismatch");
}

inline std::shared_ptr<SketchHost::Doc> SketchHost::read_project(const Value& data) const {
    fields(data,{"schema_version","kind","width","height","title","background","next_id","next_layer",
        "interval_ms","layers","layer_order","pens","geometry","objects","history","redo"});
    const auto get=[&](const char* key){return map_value(data,key);};
    json_integer(get("schema_version"),1,1);
    if(json_text(get("kind"))!="zzy-project")error("E401","unsupported project schema");
    auto d=canvas(json_integer(get("width"),1,sketch::dimension),json_integer(get("height"),1,sketch::dimension),json_text(get("title")));
    d->background=decode_color(get("background"));
    d->next_id=json_integer(get("next_id"),1,INT64_MAX);
    d->next_layer=json_integer(get("next_layer"),1,INT64_MAX);
    d->interval_ms=json_integer(get("interval_ms"),1,86400000);
    d->layers.clear();
    const auto layers=get("layers"),pens=get("pens");
    capacity("layers",items(layers).size(),sketch::entities_limit);
    capacity("pens",items(pens).size(),sketch::entities_limit);
    for(auto h:items(layers)) {
        c.point();
        const auto item=pin(h);
        fields(item,{"id","name","visible","locked"});
        const auto id=json_integer(map_value(item,"id"),0,d->next_layer-1);
        auto name=json_text(map_value(item,"name"));
        if(name.empty()||d->layers.count(id))error("E401","invalid or duplicate layer");
        auto& l=d->layers[id];
        l.charge=reserve({0,1,64+4*name.size()});l.name=std::move(name);
        l.visible=json_bool(map_value(item,"visible"));l.locked=json_bool(map_value(item,"locked"));
    }
    const auto layer_id=[&](const Value& v) {
        const auto id=json_integer(v,0,d->next_layer-1);
        if(!d->layers.count(id))error("E401","unknown layer reference");
        return id;
    };
    const auto order=[&](const Value& v) {
        sketch::Ids ids;
        for(auto h:items(v)) {
            auto id=layer_id(pin(h));
            if(std::find(ids.begin(),ids.end(),id)!=ids.end())error("E401","duplicate layer reference");
            ids.push_back(id);
        }
        if(std::find(ids.begin(),ids.end(),0)==ids.end())error("E401","default layer absent");
        return ids;
    };
    d->order=order(get("layer_order"));
    for(auto h:items(pens)) {
        const auto item=pin(h);
        fields(item,{"name","layer","state"});
        auto name=json_text(map_value(item,"name"));
        if(name.empty()||d->pens.count(name))error("E401","invalid or duplicate pen name");
        auto& p=d->pens[name];
        p.layer=layer_id(map_value(item,"layer"));p.state=read_state(map_value(item,"state"));
        p.charge=reserve({0,2,128+8*name.size()+4*p.state.font.size()});
    }
    const auto geometry=get("geometry");
    auto storage=reserve({0,items(geometry).size(),0});
    sketch::Blocks pool;
    for(auto h:items(geometry)) {
        c.point();
        const auto item=pin(h);
        fields(item,{"id","layer","data"});
        pool.push_back(block(decode_geometry(map_value(item,"data"),
            json_integer(map_value(item,"id"),1,d->next_id-1),layer_id(map_value(item,"layer")))));
    }
    const auto reference=[&](const Value& v) {
        return pool[static_cast<std::size_t>(json_integer(v,0,static_cast<Id>(pool.size())-1))];
    };
    const auto objects=get("objects");
    capacity("objects",items(objects).size(),sketch::objects_limit);
    for(auto h:items(objects)) {auto b=reference(pin(h));d->segments+=b->segments;d->objects.push_back(std::move(b));}
    const auto pairs=[&](const Value& input) {
        sketch::Entries result;
        for(auto h:items(input)) {
            const auto pair=pin(h);
            if(items(pair).size()!=2)error("E401","invalid geometry delta");
            const auto index=static_cast<std::size_t>(json_integer(pin(items(pair)[0]),0,sketch::objects_limit));
            if(!result.empty()&&index<=result.back().first)error("E401","unordered delta indices");
            result.emplace_back(index,reference(pin(items(pair)[1])));
        }
        return result;
    };
    const auto history=[&](const Value& input,std::vector<sketch::Entry>& entries) {
        for(auto h:items(input)) {
            const auto entry=pin(h);
            fields(entry,{"label","deltas"});
            sketch::Entry result;
            result.label=json_text(map_value(entry,"label"));
            result.charge=reserve({0,1,4*result.label.size()});
            const auto deltas=map_value(entry,"deltas");
            if(items(deltas).empty())error("E401","empty history entry");
            for(auto delta_handle:items(deltas)) {
                c.point();
                const auto delta=pin(delta_handle);
                fields(delta,{"attrs","removed","added"});
                Delta change;
                const auto attrs=map_value(delta,"attrs");
                std::set<std::pair<std::string,std::string>> seen;
                for(auto attr_handle:items(attrs)) {
                    const auto attr=pin(attr_handle);
                    fields(attr,{"target","key","before","after"});
                    const auto target=json_text(map_value(attr,"target")),key=json_text(map_value(attr,"key"));
                    if(!seen.emplace(target,key).second)error("E401","duplicate history field");
                    const auto convert=[&](const Value& v)->sketch::Field {
                        if(target=="canvas") {
                            if(key=="segments")return json_integer(v,0,sketch::segments_limit);
                            if(key=="background")return decode_color(v);
                            if(key=="layers")return order(v);
                        } else if(target.compare(0,4,"pen:")==0&&d->pens.count(target.substr(4))) {
                            if(key=="layer")return layer_id(v);
                            if(key=="state")return read_state(v);
                        } else if(target.compare(0,6,"layer:")==0) {
                            Id id=0;
                            const auto end=target.data()+target.size();
                            const auto parsed=std::from_chars(target.data()+6,end,id);
                            if(parsed.ec!=std::errc{}||parsed.ptr!=end)error("E401","invalid history layer target");
                            if(d->layers.count(id)&&sketch::layer_key(id)==target) {
                                if(key=="visible"||key=="locked")return json_bool(v);
                                if(key=="name") {auto name=json_text(v);if(!name.empty())return name;}
                            }
                        }
                        error("E401","invalid history field or target");
                    };
                    change.attrs.push_back({target,key,convert(map_value(attr,"before")),convert(map_value(attr,"after"))});
                }
                change.removed=pairs(map_value(delta,"removed"));
                change.added=pairs(map_value(delta,"added"));
                if(change.attrs.empty()&&change.removed.empty()&&change.added.empty())error("E401","empty history delta");
                const auto charge=delta_cost(change);
                change.bytes=static_cast<std::size_t>(charge.payload)+(result.deltas.empty()?4*result.label.size():0);
                d->history_cost+=change.bytes;
                capacity("history_commands",++d->history_size,sketch::history_limit);
                capacity("history_bytes",d->history_cost,sketch::history_bytes);
                change.charge=reserve(charge);
                result.deltas.push_back(std::move(change));
            }
            entries.push_back(std::move(result));
        }
    };
    history(get("history"),d->undo);
    const auto undo_count=d->history_size,undo_cost=d->history_cost;
    history(get("redo"),d->redo);
    d->redo_size=d->history_size-undo_count;d->redo_cost=d->history_cost-undo_cost;
    auto view=projection(*d);
    validate_projection(view);
    for(auto it=d->undo.rbegin();it!=d->undo.rend();++it)project_step(view,*it,false,true);
    for(const auto& entry:d->undo)project_step(view,entry,true,true);
    for(auto it=d->redo.rbegin();it!=d->redo.rend();++it)project_step(view,*it,true,true);
    for(const auto& entry:d->redo)project_step(view,entry,false,true);
    if(view.objects!=d->objects||view.segments!=d->segments)error("E401","history did not restore document");
    return d;
}

inline Value SketchHost::project(const std::string& op,const std::vector<Value>& a,const Doc* current) const {
    if(op=="save_project") {
        idle(*current);
        auto result=c.json_library("data.stringify",project_data(*current),site);
        if(!c.object(result).flag)return result;
        return c.file_library("io.write_atomic",{a[1],decode_json(result)},site);
    }
    const auto content=c.file_library("io.read_text",a,site);
    if(!c.object(content).flag)return content;
    try {
        auto bytes=decode_json(content);
        auto scratch=reserve({0,0,4*c.object(bytes).characters.size()});
        auto d=read_project(decode_json(c.json_library("data.parse",bytes,site)));
        auto canvas_handle=canvas_value(d);
        // Publish the connected handle graph only after the complete document has validated.
        for(auto& [id,layer]:d->layers)if(id) {
            const auto value=c.heap.native("sketch.Layer",std::make_shared<sketch::LayerRef>(sketch::LayerRef{d,id}),{1,0,0},site);
            layer.handle=value.ref();link(value,canvas_handle);link(canvas_handle,value);
        }
        for(auto& [name,pen]:d->pens) {
            const auto value=c.heap.native("sketch.Pen",std::make_shared<sketch::PenRef>(sketch::PenRef{d,name}),{1,0,0},site);
            pen.handle=value.ref();link(value,canvas_handle);link(canvas_handle,value);
        }
        return success(canvas_handle);
    } catch(const RuntimeError& e) {
        if(e.code!="E401")throw;
        return failure(std::string("sketch project: ")+e.what());
    }
}
}
