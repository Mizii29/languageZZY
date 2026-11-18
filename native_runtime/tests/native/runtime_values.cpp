#include "zzy_native/runtime_heap.hpp"
#include <iostream>
#include <sstream>
namespace {
void require(bool b,const char* message) {if(!b) throw std::runtime_error(message);}
using zzy::BigInt;
void integers() {
    require(BigInt::decimal("18446744073709551616").words()==std::vector<std::uint32_t>{0,0,1},"2^64 limbs");
    const auto a=BigInt::decimal("123456789012345678901234567890");
    const auto b=BigInt::decimal("98765432109876543210");
    require((a+b).decimal()=="123456789111111111011111111100","fixed big sum");
    require((a*b).decimal()=="12193263113702179522496570642237463801111263526900","fixed big product");
    require((a/b).decimal()=="1249999988" && (a%b).decimal()=="60185185207253086410","fixed big divmod");
    for(std::int64_t x=-300;x<=300;++x) for(std::int64_t y=-17;y<=17;++y) if(y) {
        auto q=x/y,r=x%y;if(r && ((r<0)!=(y<0))) {--q;r+=y;}
        const auto qr=BigInt(x).divmod(BigInt(y));
        require(qr.first==BigInt(q) && qr.second==BigInt(r),"signed floor quotient/remainder");
        require(qr.first*BigInt(y)+qr.second==BigInt(x),"division identity");
    }
    require(BigInt::decimal("-9223372036854775808")==BigInt(INT64_MIN),"signed minimum");
    require(BigInt().bits()==0 && BigInt(256).bits()==9,"exact bit lengths");
}
void floating() {
    const auto a=BigInt::decimal("9007199254740993");
    require(a.compare(9007199254740992.0)>0,"no lossy Int comparison");
    require((-a).compare(-9007199254740992.0)<0,"negative exact comparison");
    require(BigInt(1).compare(1.0)==0 && BigInt(1).compare(1.5)<0,"finite comparison");
    require(BigInt().compare(-0.0)==0,"negative zero");
    require(BigInt().compare(std::numeric_limits<double>::denorm_min())<0,"subnormal ratio");
    const auto r=BigInt::ratio(0.5);require(r.first/r.second==BigInt(),"Float binary ratio");
    const zzy::Rational f(r.first,r.second);require(f.numerator==BigInt(1) && f.denominator==BigInt(2),"ratio normalization");
}
zzy::Value node(zzy::RuntimeHeap& heap,const std::string& kind,zzy::Charge charge,std::vector<zzy::Handle> edges={}) {
    zzy::RuntimeNode n;n.kind=kind;n.edges=std::move(edges);return heap.allocate(std::move(n),charge);
}
void cycles() {
    zzy::ResourcePolicy p;std::atomic<bool> cancel{false};zzy::RuntimeHeap h(p,cancel);
    auto a=node(h,"Array",{1,1,0});auto map=node(h,"Map",{1,2,4},{a.ref(),a.ref()});
    auto cell=node(h,"Cell",{0,1,0},{map.ref()});auto closure=node(h,"Function",{1,1,0},{cell.ref()});
    h.get(a).edges={closure.ref()};h.collect();require(h.state->used==zzy::Charge{3,5,4},"reachable mixed cycle");
    map={};cell={};closure={};h.collect();require(h.state->nodes.size()==4,"alias root retains whole graph");
    a={};h.collect();require(h.state->used==zzy::Charge{} && h.state->nodes.empty(),"cycle refunded within request");
    for(int i=0;i<1000;++i) {auto x=node(h,"Array",{1,1,0});h.get(x).edges={x.ref()};}
    h.collect();require(h.state->used==zzy::Charge{},"repeated cycles no accumulated charge");
}
void budgets() {
    for(auto key:{std::string("runtime_objects"),std::string("runtime_slots"),std::string("runtime_payload_bytes")}) {
        for(std::uint64_t requested=2;requested<=4;++requested) {
            zzy::ResourcePolicy p;p.limits[key]=3;std::atomic<bool> cancel{false};zzy::RuntimeHeap h(p,cancel);
            zzy::Charge charge{0,0,0};if(key=="runtime_objects") charge.objects=requested;else if(key=="runtime_slots") charge.slots=requested;else charge.payload=requested;
            try {auto v=node(h,"probe",charge);require(requested<=3,"L+1 accepted");require(h.state->used==charge,"L-1/L charged");}
            catch(const zzy::RuntimeError& e) {require(requested==4 && e.code=="E211" && std::string(e.what()).find(key)!=std::string::npos,"boundary diagnostic");}
            h.collect();require(h.state->used==zzy::Charge{},"boundary refund");
        }
    }
    zzy::ResourcePolicy p;p.limits["runtime_objects"]=2;p.limits["runtime_slots"]=2;p.limits["runtime_payload_bytes"]=2;
    std::atomic<bool> cancel{false};zzy::RuntimeHeap h(p,cancel);auto a=node(h,"Array",{1,1,1});
    try {auto b=node(h,"Map",{1,2,1});throw std::runtime_error("atomic reserve accepted");}catch(const zzy::RuntimeError&) {}
    require(h.state->used==zzy::Charge{1,1,1},"multi-key reservation is atomic");
    h.state->fail_allocation=true;try {auto b=node(h,"Array",{1,1,1});throw std::runtime_error("injection ignored");}catch(const std::bad_alloc&) {}
    require(h.state->used==zzy::Charge{1,1,1},"allocation rollback");a={};auto b=node(h,"Array",{2,2,2});
    require(h.state->used==zzy::Charge{2,2,2},"collect before quota failure");
}
void ownership() {
    zzy::ResourcePolicy p;std::atomic<bool> cancel{false};zzy::RuntimeHeap a(p,cancel),b(p,cancel);
    auto x=node(a,"Int",{0,0,1});try {b.pin(x.ref());throw std::runtime_error("foreign accepted");}catch(const std::logic_error&) {}
    cancel=true;try {a.collect();throw std::runtime_error("cancel ignored");}catch(const zzy::Cancelled&) {}
    cancel=false;a.collect();require(a.state->used.payload==1,"cancel left roots intact");a.close();
    require(a.state->used==zzy::Charge{},"close refunds despite outstanding root");
    try {a.get(x);throw std::runtime_error("released accepted");}catch(const std::logic_error&) {}
    x={};a.close();
}
}
int main(int argc,char** argv) {
    const std::map<std::string,void(*)()> cases={{"integers",integers},{"floating",floating},{"cycles",cycles},{"budgets",budgets},{"ownership",ownership}};
    try {if(argc!=2 || !cases.count(argv[1])) throw std::runtime_error("nonempty named selection required");cases.at(argv[1])();std::cout<<argv[1]<<": PASS\n";return 0;}
    catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
