#pragma once
#include <array>
#include <chrono>
#include <cstdint>
#include <ostream>

namespace n7_profile {
enum Kind {dispatch,get,pin,check,reserve,collect,allocate,count};
struct Tally {std::uint64_t calls=0;std::int64_t exclusive=0;};
inline thread_local std::array<Tally,count> totals{};
struct Scope;
inline thread_local Scope* active=nullptr;
struct Scope {
    using Clock=std::chrono::steady_clock;
    Kind kind;
    Scope* parent=active;
    Clock::time_point begin=Clock::now();
    std::int64_t nested=0;
    explicit Scope(Kind k):kind(k) {active=this;}
    ~Scope() {
        const auto elapsed=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-begin).count();
        active=parent;
        if(parent) parent->nested+=elapsed;
        ++totals[kind].calls;
        totals[kind].exclusive+=elapsed-nested;
    }
};
inline void report(std::ostream& out) {
    constexpr std::array<const char*,count> names={"dispatch","get","pin","check","reserve","collect","allocate"};
    out<<'{';
    for(std::size_t i=0;i<names.size();++i) {
        if(i) out<<',';
        out<<'"'<<names[i]<<"\":{\"calls\":"<<totals[i].calls<<",\"exclusive_ns\":"<<totals[i].exclusive<<'}';
    }
    out<<"}\n";
}
}
