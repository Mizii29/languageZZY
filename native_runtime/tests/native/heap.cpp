#include "zzy_native/heap_prototype.hpp"
#include <iostream>
#include <string>

using namespace zzy::prototype;
#define REQUIRE(c) do {if(!(c))throw std::runtime_error(std::string("assertion: ")+ #c +" line "+std::to_string(__LINE__));}while(false)
namespace {
void array_cycle() {
    Heap h;auto a=h.allocate(Kind::array);h.edge(a.get(),a.get());
    REQUIRE(h.used()==(Amount{1,1,0}));a.reset();
    REQUIRE(h.collect()==1);REQUIRE(h.used()==Amount{});
}
void map_cycle() {
    Heap h;auto m=h.allocate(Kind::map);auto key=h.allocate(Kind::text,4);
    h.map_entry(m.get(),key.get(),m.get());REQUIRE(h.used()==(Amount{2,2,4}));
    key.reset();m.reset();REQUIRE(h.collect()==2);REQUIRE(h.used()==Amount{});
}
void closure_cycle() {
    Heap h;auto a=h.allocate(Kind::array);auto f=h.allocate(Kind::closure);auto c=h.allocate(Kind::cell);
    h.edge(a.get(),f.get());h.edge(f.get(),c.get());h.edge(c.get(),a.get());
    REQUIRE(h.used()==(Amount{3,3,0}));a.reset();f.reset();c.reset();
    REQUIRE(h.collect()==3);REQUIRE(h.used()==Amount{});
}
void reachable_and_alias() {
    Heap h;auto a=h.allocate(Kind::array);auto m=h.allocate(Kind::map);auto k=h.allocate(Kind::text,4);
    h.edge(a.get(),m.get());h.map_entry(m.get(),k.get(),m.get());
    auto alias=h.pin(a.get());a.reset();m.reset();k.reset();
    REQUIRE(h.collect()==0);REQUIRE(h.used()==(Amount{3,3,4}));
    alias.reset();REQUIRE(h.collect()==3);REQUIRE(h.used()==Amount{});
}
void quota_gc_retry() {
    Heap h({1,1,4});auto a=h.allocate(Kind::array);h.edge(a.get(),a.get());auto stale=a.get();a.reset();
    auto b=h.allocate(Kind::text,4);REQUIRE(h.used()==(Amount{1,0,4}));REQUIRE(b.get().id!=stale.id);
    try{auto invalid=h.pin(stale);throw std::runtime_error("stale accepted");}catch(const std::invalid_argument&){}
}
void atomic_limits() {
    Heap h({3,1,4});auto m=h.allocate(Kind::map);auto k=h.allocate(Kind::text,4);auto a=h.allocate(Kind::array);
    try{h.map_entry(m.get(),k.get(),a.get());throw std::runtime_error("slots allowed");}
    catch(const zzy::LimitExceeded& e){REQUIRE(e.key=="runtime_slots");}
    REQUIRE(h.edge_count(m.get())==0);REQUIRE(h.used()==(Amount{3,0,4}));
    try{auto extra=h.allocate(Kind::text,100);throw std::runtime_error("objects allowed");}
    catch(const zzy::LimitExceeded& e){REQUIRE(e.key=="runtime_objects");}
    REQUIRE(h.used()==(Amount{3,0,4}));
    Budget budget({10,10,10});budget.reserve({1,2,3});
    try{budget.reserve({1,2,std::numeric_limits<std::uint64_t>::max()});throw std::runtime_error("overflow allowed");}
    catch(const zzy::LimitExceeded& e){REQUIRE(e.key=="runtime_payload_bytes");}
    REQUIRE(budget.used()==(Amount{1,2,3}));budget.release({1,2,3});REQUIRE(budget.used()==Amount{});
}
void allocation_rollback() {
    Heap h;auto a=h.allocate(Kind::array);h.fail_next_allocation();
    try{auto extra=h.allocate(Kind::text,4);throw std::runtime_error("fault ignored");}catch(const std::bad_alloc&){}
    REQUIRE(h.used()==(Amount{1,0,0}));h.fail_next_mutation();
    try{h.edge(a.get(),a.get());throw std::runtime_error("fault ignored");}catch(const std::bad_alloc&){}
    REQUIRE(h.edge_count(a.get())==0);REQUIRE(h.used()==(Amount{1,0,0}));
}
void ownership() {
    Heap h1,h2;auto a=h1.allocate(Kind::array);auto b=h2.allocate(Kind::array);
    try{h1.edge(a.get(),b.get());throw std::runtime_error("foreign accepted");}catch(const std::invalid_argument&){}
    REQUIRE(h1.used()==(Amount{1,0,0}));REQUIRE(h2.used()==(Amount{1,0,0}));
    h1.close();h1.close();REQUIRE(h1.used()==Amount{});REQUIRE(h2.size()==1);
    try{auto invalid=h1.pin(a.get());throw std::runtime_error("closed accepted");}catch(const std::logic_error&){}
    Root escaped;Handle previous;
    {Heap context;escaped=context.allocate(Kind::array);previous=escaped.get();}
    escaped.reset(); // Safe even after its request heap has been destroyed.
    Heap replacement;
    try{auto invalid=replacement.pin(previous);throw std::runtime_error("old owner accepted");}catch(const std::invalid_argument&){}
}
void cancellation() {
    Heap h;auto a=h.allocate(Kind::array);h.edge(a.get(),a.get());h.cancel();
    try{auto extra=h.allocate(Kind::array);throw std::runtime_error("cancel ignored");}catch(const zzy::Cancelled&){}
    try{h.edge(a.get(),a.get());throw std::runtime_error("cancel mutation ignored");}catch(const zzy::Cancelled&){}
    REQUIRE(h.used()==(Amount{1,1,0}));h.close();h.close();REQUIRE(h.used()==Amount{});
    Heap next;auto valid=next.allocate(Kind::array);REQUIRE(next.size()==1);
}
void unwind_roots() {
    Heap h;
    try{auto a=h.allocate(Kind::array);h.edge(a.get(),a.get());throw std::runtime_error("business error");}
    catch(const std::runtime_error&){}
    REQUIRE(h.collect()==1);REQUIRE(h.used()==Amount{});
}
void iterative_graph() {
    Heap h({6000,6000,1});auto first=h.allocate(Kind::array);auto last=h.pin(first.get());
    for(int i=1;i<5000;++i){auto next=h.allocate(Kind::array);h.edge(last.get(),next.get());last=std::move(next);}
    h.edge(last.get(),first.get());last.reset();REQUIRE(h.collect()==0);first.reset();
    REQUIRE(h.collect()==5000);REQUIRE(h.used()==Amount{});
}
void repeated_collection() {
    Heap h({3,3,1});
    for(int i=0;i<1000;++i) {
        {auto a=h.allocate(Kind::array);auto f=h.allocate(Kind::closure);auto c=h.allocate(Kind::cell);
         h.edge(a.get(),f.get());h.edge(f.get(),c.get());h.edge(c.get(),a.get());}
        REQUIRE(h.collect()==3);REQUIRE(h.used()==Amount{});
    }
}
struct Case {const char* name;void (*test)();};
const Case cases[]={{"array-cycle",array_cycle},{"map-cycle",map_cycle},{"closure-cycle",closure_cycle},
    {"reachable-alias",reachable_and_alias},{"quota-gc-retry",quota_gc_retry},{"atomic-limits",atomic_limits},
    {"allocation-rollback",allocation_rollback},{"ownership",ownership},{"cancellation",cancellation},
    {"unwind-roots",unwind_roots},{"iterative-graph",iterative_graph},{"repeated-collection",repeated_collection}};
}
int main(int argc,char** argv) {
    int count=0;
    try {
        for(const auto& test:cases)if(argc==1 || test.name==std::string(argv[1])) {
            test.test();++count;std::cout<<test.name<<": passed\n";
        }
        if(count==0)throw std::runtime_error("no cases collected");
        std::cout<<"heap: "<<count<<" cases passed\n";return 0;
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
      catch(...){std::cerr<<"unexpected abort\n";return 1;}
}
