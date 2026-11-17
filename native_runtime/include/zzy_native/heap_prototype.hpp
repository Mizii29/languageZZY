#pragma once
#include "protocol.hpp"
#include <atomic>
#include <cassert>
#include <limits>
#include <memory>
#include <unordered_map>
#include <utility>
#include <vector>

// N0 ownership experiment, NOT an implementation of ZZY container semantics.
namespace zzy::prototype {
struct Amount {
    std::uint64_t objects=0,slots=0,payload=0;
    bool operator==(const Amount& rhs) const {return objects==rhs.objects && slots==rhs.slots && payload==rhs.payload;}
};
class Budget {
    Amount limits_,used_;
public:
    explicit Budget(Amount limits):limits_(limits) {}
    const Amount& used() const noexcept {return used_;}
    const char* exceeded(Amount add) const noexcept {
        if(add.objects>limits_.objects-used_.objects) return "runtime_objects";
        if(add.slots>limits_.slots-used_.slots) return "runtime_slots";
        if(add.payload>limits_.payload-used_.payload) return "runtime_payload_bytes";
        return nullptr;
    }
    void reserve(Amount add) {
        if(const auto* key=exceeded(add)) throw LimitExceeded(key);
        used_.objects+=add.objects;used_.slots+=add.slots;used_.payload+=add.payload;
    }
    void release(Amount remove) noexcept {
        assert(used_.objects>=remove.objects && used_.slots>=remove.slots && used_.payload>=remove.payload);
        used_.objects-=remove.objects;used_.slots-=remove.slots;used_.payload-=remove.payload;
    }
};
class Ticket {
    Budget* budget_;Amount amount_;
public:
    Ticket(Budget& budget,Amount amount):budget_(&budget),amount_(amount) {budget.reserve(amount);}
    Ticket(const Ticket&)=delete;
    Ticket& operator=(const Ticket&)=delete;
    ~Ticket() {if(budget_)budget_->release(amount_);}
    void commit() noexcept {budget_=nullptr;}
};
class Heap;
struct Handle {std::uint64_t owner=0,id=0;};
using Roots=std::unordered_map<std::uint64_t,Handle>;
class Root {
    friend class Heap;
    std::weak_ptr<Roots> roots_;std::uint64_t root_id_=0;Handle handle_;
    Root(const std::shared_ptr<Roots>& roots,std::uint64_t id,Handle handle):roots_(roots),root_id_(id),handle_(handle) {}
public:
    Root()=default;
    Root(const Root&)=delete;
    Root& operator=(const Root&)=delete;
    Root(Root&& other) noexcept {swap(other);}
    Root& operator=(Root&& other) noexcept {if(this!=&other){reset();swap(other);}return *this;}
    ~Root() {reset();}
    void swap(Root& other) noexcept {roots_.swap(other.roots_);std::swap(root_id_,other.root_id_);std::swap(handle_,other.handle_);}
    void reset() noexcept;
    Handle get() const noexcept {return handle_;}
};
enum class Kind {array,map,closure,cell,text};
struct Node {
    Kind kind;Amount charge;std::vector<Handle> edges;bool marked=false;
    Node(Kind k,Amount c):kind(k),charge(c) {}
};
class Heap {
    friend class Root;
    Budget budget_;
    std::unordered_map<std::uint64_t,std::unique_ptr<Node>> nodes_;
    std::shared_ptr<Roots> roots_=std::make_shared<Roots>();
    inline static std::atomic<std::uint64_t> next_owner_{1};
    const std::uint64_t owner_id_=next_owner_.fetch_add(1);
    std::uint64_t next_node_=1,next_root_=1;
    bool closed_=false;
    std::atomic<bool> cancelled_{false};
    bool fail_allocate_=false,fail_mutate_=false;
    void check() const {if(closed_)throw std::logic_error("closed heap");if(cancelled_.load())throw Cancelled{};}
    Node& node(Handle handle) {
        if(closed_ || handle.owner!=owner_id_)throw std::invalid_argument("foreign/closed handle");
        auto found=nodes_.find(handle.id);
        if(found==nodes_.end())throw std::invalid_argument("stale handle");
        return *found->second;
    }
    Ticket reserve(Amount amount) {
        check();
        if(budget_.exceeded(amount))collect();
        return Ticket(budget_,amount);
    }
    static std::uint64_t next(std::uint64_t& id) {
        if(id==std::numeric_limits<std::uint64_t>::max())throw LimitExceeded("runtime_objects");
        return id++;
    }
    void append(Handle from,const std::vector<Handle>& to) {
        check();
        // Pin every operand before any GC-capable operation.
        auto source=pin(from);
        std::vector<Root> operands;
        operands.reserve(to.size());
        for(auto target:to)operands.push_back(pin(target));
        auto charge=Amount{0,static_cast<std::uint64_t>(to.size()),0};
        auto ticket=reserve(charge);
        if(fail_mutate_){fail_mutate_=false;throw std::bad_alloc();}
        auto& object=node(from);
        object.edges.reserve(object.edges.size()+to.size());
        object.edges.insert(object.edges.end(),to.begin(),to.end());
        object.charge.slots+=charge.slots;
        ticket.commit();
    }
public:
    explicit Heap(Amount limits={200000,2000000,134217728}):budget_(limits) {}
    Heap(const Heap&)=delete;
    Heap& operator=(const Heap&)=delete;
    ~Heap() {close();}
    const Amount& used() const noexcept {return budget_.used();}
    std::size_t size() const noexcept {return nodes_.size();}
    Root pin(Handle handle) {
        check();node(handle);
        const auto id=next(next_root_);
        roots_->emplace(id,handle);
        return Root(roots_,id,handle);
    }
    Root allocate(Kind kind,std::uint64_t payload=0) {
        // Scalar payloads and internal Cells are GC nodes, but NOT logical
        // runtime_objects. Cell references are charged by their outgoing slot.
        const Amount charge{kind==Kind::text || kind==Kind::cell ? 0u:1u,0,payload};
        auto ticket=reserve(charge);
        if(fail_allocate_){fail_allocate_=false;throw std::bad_alloc();}
        auto object=std::make_unique<Node>(kind,charge);
        const auto id=next(next_node_);
        nodes_.emplace(id,std::move(object));
        // Commit before pin; on pin failure erase the object and refund once.
        ticket.commit();
        try{return pin({owner_id_,id});}
        catch(...){nodes_.erase(id);budget_.release(charge);throw;}
    }
    void edge(Handle from,Handle to) {append(from,{to});}
    void map_entry(Handle map,Handle key,Handle value) {
        check();
        if(node(map).kind!=Kind::map || node(key).kind!=Kind::text)throw std::invalid_argument("map/key kinds");
        append(map,{key,value});
    }
    std::size_t edge_count(Handle handle) {return node(handle).edges.size();}
    std::size_t collect() {
        if(closed_)return 0;
        // Allocate mark worklist BEFORE changing marks. No recursive graph walk.
        std::vector<Node*> todo;todo.reserve(nodes_.size());
        for(auto& entry:nodes_)entry.second->marked=false;
        const auto mark=[&](Handle handle) {
            auto& target=node(handle);
            if(!target.marked){target.marked=true;todo.push_back(&target);}
        };
        for(const auto& root:*roots_)mark(root.second);
        while(!todo.empty()) {
            auto* current=todo.back();todo.pop_back();
            for(auto target:current->edges)mark(target);
        }
        std::size_t removed=0;
        for(auto it=nodes_.begin();it!=nodes_.end();) {
            if(!it->second->marked){budget_.release(it->second->charge);it=nodes_.erase(it);++removed;}
            else ++it;
        }
        return removed;
    }
    void cancel() noexcept {cancelled_.store(true);}
    void close() noexcept {
        if(closed_)return;
        roots_->clear();
        for(auto& entry:nodes_)budget_.release(entry.second->charge);
        nodes_.clear();closed_=true;
    }
    void fail_next_allocation() noexcept {fail_allocate_=true;}
    void fail_next_mutation() noexcept {fail_mutate_=true;}
};
inline void Root::reset() noexcept {
    if(auto roots=roots_.lock())roots->erase(root_id_);
    roots_.reset();root_id_=0;handle_={};
}
}
