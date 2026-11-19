#pragma once
#include "bigint.hpp"
#include "program.hpp"
#include <memory>
#include <unordered_map>
#include <unordered_set>
namespace zzy {
struct RuntimeError : std::runtime_error {
    std::string code;NodeId site;bool expression_span=false;std::vector<std::string> notes;
    RuntimeError(std::string c,std::string message,NodeId n=no_node):std::runtime_error(std::move(message)),code(std::move(c)),site(n) {}
};
struct Charge {
    std::uint64_t objects=0,slots=0,payload=0;
    Charge operator+(const Charge& x) const {return {objects+x.objects,slots+x.slots,payload+x.payload};}
    bool operator==(const Charge& x) const {return objects==x.objects && slots==x.slots && payload==x.payload;}
};
struct Handle {std::uint64_t owner=0,id=0;bool operator==(const Handle& x) const {return owner==x.owner && id==x.id;}};
struct HeapState;
struct RootToken {
    std::weak_ptr<HeapState> heap;Handle handle;
    RootToken(std::weak_ptr<HeapState> h,Handle v):heap(std::move(h)),handle(v) {}
    ~RootToken();
};
class Value {
    std::shared_ptr<RootToken> root_;
public:
    Value()=default;
    explicit Value(std::shared_ptr<RootToken> r):root_(std::move(r)) {}
    Handle ref() const {return root_?root_->handle:Handle{};}
    explicit operator bool() const {return bool(root_);}
    bool same(const Value& x) const {return ref()==x.ref();}
};
// Every heap edge is a non-owning Handle. RootToken ownership never occurs in a
// node, so Array/Map/Cell/closure/Lazy cycles are collectable during a request.
struct RuntimeNode {
    std::string kind,name,text;
    BigInt integer;double real=0;bool flag=false;
    std::u32string characters;
    Rational rational;int length=0,time=0;
    std::vector<Handle> edges;
    std::vector<std::string> names;
    std::vector<std::string> type_names;
    std::vector<std::size_t> type_nominals;
    NodeId syntax=no_node;
    std::size_t active=0,version=0;
    std::string state="NEW";
    bool frozen=false;
    std::shared_ptr<RuntimeError> failure;
    // Opaque host ownership only; no language field lookup enters this payload.
    std::shared_ptr<void> native_payload;
    const void* native_type=nullptr;
    Charge charge;
};
struct HeapState : std::enable_shared_from_this<HeapState> {
    ResourcePolicy policy;std::atomic<bool>& cancelled;Charge used{},peak{};
    std::uint64_t owner,next=1;bool closed=false,fail_allocation=false;
    std::unordered_map<std::uint64_t,std::unique_ptr<RuntimeNode>> nodes;
    std::unordered_map<std::uint64_t,std::size_t> roots;
    // A published graph has no mutable nodes or root counters touched by readers.
    // Its service owner outlives all attached requests. Quotas stay with that owner.
    std::shared_ptr<HeapState> shared;
    static std::uint64_t new_owner() {static std::atomic<std::uint64_t> next_owner{1};return next_owner.fetch_add(1);}
    HeapState(ResourcePolicy p,std::atomic<bool>& c):policy(std::move(p)),cancelled(c),owner(new_owner()) {}
    void point() const {if(cancelled.load(std::memory_order_relaxed)) throw Cancelled{};if(closed) throw std::logic_error("closed execution heap");}
    void check(const std::string& key,std::uint64_t value,NodeId site=no_node) const {
        point();const auto limit=policy.limits.at(key);
        if(value>limit) throw RuntimeError("E211","resource limit exceeded: "+key+", limit="+std::to_string(limit)+", requested="+std::to_string(value),site);
    }
    RuntimeNode& get(Handle h) const {
        if(!closed && shared && h.owner==shared->owner) return shared->get(h);
        if(closed || h.owner!=owner || !nodes.count(h.id)) throw std::logic_error("foreign or released runtime value");
        return *nodes.at(h.id);
    }
    Value pin(Handle h) {
        get(h);auto token=std::make_shared<RootToken>(weak_from_this(),h);if(h.owner==owner) ++roots[h.id];return Value(std::move(token));
    }
    void refund(Charge x) {used.objects-=x.objects;used.slots-=x.slots;used.payload-=x.payload;}
    bool fits(Charge x) const {
        return x.objects<=policy.limits.at("runtime_objects")-used.objects &&
            x.slots<=policy.limits.at("runtime_slots")-used.slots && x.payload<=policy.limits.at("runtime_payload_bytes")-used.payload;
    }
    void collect() {
        point();std::unordered_set<std::uint64_t> seen;std::vector<std::uint64_t> work;
        for(const auto& r:roots) if(r.second) work.push_back(r.first);
        while(!work.empty()) {
            point();const auto id=work.back();work.pop_back();if(!seen.insert(id).second) continue;
            const auto it=nodes.find(id);if(it==nodes.end()) throw std::logic_error("dangling root");
            for(auto h:it->second->edges) {if(h.owner==owner) work.push_back(h.id);else if(!shared || h.owner!=shared->owner) throw std::logic_error("foreign heap edge");}
        }
        for(auto it=nodes.begin();it!=nodes.end();) {
            if(!seen.count(it->first)) {refund(it->second->charge);it=nodes.erase(it);}else ++it;
        }
    }
    void reserve(Charge x,NodeId site=no_node) {
        point();if(!fits(x)) collect();
        check("runtime_objects",used.objects+x.objects,site);check("runtime_slots",used.slots+x.slots,site);check("runtime_payload_bytes",used.payload+x.payload,site);
        used=used+x;peak.objects=std::max(peak.objects,used.objects);peak.slots=std::max(peak.slots,used.slots);peak.payload=std::max(peak.payload,used.payload);
    }
    void close() noexcept {nodes.clear();roots.clear();shared.reset();used={};closed=true;}
};
inline RootToken::~RootToken() {if(auto h=heap.lock()) if(!h->closed && handle.owner==h->owner) {const auto it=h->roots.find(handle.id);if(it!=h->roots.end() && --it->second==0) h->roots.erase(it);}}
class Lease {
    std::shared_ptr<HeapState> heap_;Charge charge_;
public:
    Lease()=default;
    Lease(std::shared_ptr<HeapState> heap,Charge charge,NodeId site=no_node):heap_(std::move(heap)),charge_(charge) {heap_->reserve(charge_,site);}
    Lease(const Lease&)=delete;Lease& operator=(const Lease&)=delete;
    Lease(Lease&& x) noexcept:heap_(std::move(x.heap_)),charge_(x.charge_) {x.charge_={};}
    Lease& operator=(Lease&& x) noexcept {if(this!=&x) {release();heap_=std::move(x.heap_);charge_=x.charge_;x.charge_={};}return *this;}
    ~Lease() {release();}
    explicit operator bool() const {return bool(heap_);}
    void grow(Charge charge,NodeId site) {heap_->reserve(charge,site);charge_=charge_+charge;}
    void release() {if(heap_ && !heap_->closed) heap_->refund(charge_);heap_.reset();charge_={};}
    Charge transfer() {auto x=charge_;heap_.reset();charge_={};return x;}
};
class RuntimeHeap {
public:
    std::shared_ptr<HeapState> state;
    RuntimeHeap(const ResourcePolicy& policy,std::atomic<bool>& cancel):state(std::make_shared<HeapState>(policy,cancel)) {}
    RuntimeHeap(const RuntimeHeap&)=delete;
    RuntimeHeap& operator=(const RuntimeHeap&)=delete;
    ~RuntimeHeap() {state->close();}
    Value allocate(RuntimeNode node,Charge charge,NodeId site=no_node) {
        // Edges must remain rooted by the caller throughout reserve/collection.
        for(auto h:node.edges) state->get(h);
        Lease ticket(state,charge,site);
        if(state->fail_allocation) {state->fail_allocation=false;throw std::bad_alloc();}
        auto data=std::make_unique<RuntimeNode>(std::move(node));data->charge=charge;
        const auto id=state->next++;state->nodes.emplace(id,std::move(data));
        ticket.transfer();
        try {return state->pin({state->owner,id});}
        catch(...) {state->refund(state->nodes.at(id)->charge);state->nodes.erase(id);throw;}
    }
    Value pin(Handle h) {return state->pin(h);}
    RuntimeNode& get(const Value& v) const {return state->get(v.ref());}
    template<class T> static const void* type_identity() {static const char id=0;return &id;}
    template<class T> Value native(std::string name,std::shared_ptr<T> value,Charge charge,NodeId site=no_node) {
        if(!value || charge.objects!=1) throw std::logic_error("invalid opaque host allocation");
        RuntimeNode n;n.kind="Native";n.name=std::move(name);n.native_type=type_identity<T>();n.native_payload=std::move(value);
        return allocate(std::move(n),charge,site);
    }
    template<class T> T& native(const Value& value,NodeId site=no_node) const {
        auto& n=get(value);if(n.kind!="Native" || n.native_type!=type_identity<T>()) throw RuntimeError("E201","opaque host type mismatch",site);
        return *static_cast<T*>(n.native_payload.get());
    }
    void collect() {state->collect();}
    void close() {state->close();}
};
}
