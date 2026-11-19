#pragma once

namespace zzy {
// A session discards this view before any document edits or callbacks. History
// and geometry can therefore be borrowed without copying the command log.
class SketchReplay {
    const SketchHost& host;
    const SketchHost::Doc& source;
    std::size_t cursor, spacing;
    std::map<std::size_t,SketchHost::Doc> checkpoints;
    Charge cached{};
    SketchHost::Doc view;
    static std::size_t distance(std::size_t a,std::size_t b) {return a>b?a-b:b-a;}
    void checkpoint() {
        if(checkpoints.size()>=8||checkpoints.count(cursor))return;
        const auto estimate=view.charge.amount();
        if(estimate.payload+cached.payload>16*1024*1024||
           estimate.slots+cached.slots>200000||!host.fits(estimate))return;
        try {
            auto snapshot=host.projection(view);
            cached=cached+snapshot.charge.amount();
            checkpoints.emplace(cursor,std::move(snapshot));
        } catch(const RuntimeError& e) {
            if(e.code!="E211")throw;
        }
    }
public:
    SketchReplay(const SketchHost& h,const SketchHost::Doc& d)
        :host(h),source(d),cursor(d.undo.size()),spacing(std::max<std::size_t>(1,(cursor+6)/7)),view(h.projection(d)) {
        host.idle(d);
        checkpoint();
        seek(0);
    }
    std::size_t size() const {return source.undo.size();}
    std::size_t position() const {return cursor;}
    const SketchHost::Doc& scene() const {return view;}
    void seek(std::size_t target) {
        target=std::min(target,size());
        auto closest=checkpoints.end();
        auto best=distance(target,cursor);
        for(auto it=checkpoints.begin();it!=checkpoints.end();++it) {
            const auto cost=distance(target,it->first);
            if(cost<best) {best=cost;closest=it;}
        }
        if(closest!=checkpoints.end()) {
            view=host.projection(closest->second);
            cursor=closest->first;
        }
        while(cursor!=target) {
            const bool forward=cursor<target;
            host.project_step(view,source.undo[forward?cursor:cursor-1],forward);
            if(forward)++cursor;else --cursor;
            if(cursor%spacing==0)checkpoint();
        }
    }
};
}
