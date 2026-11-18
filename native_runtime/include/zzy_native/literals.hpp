#pragma once
#include "program.hpp"
#include <cmath>
#include <cstring>
#include <locale.h>
#include <numeric>
namespace zzy {
// Unsigned arbitrary precision only for static literal preparation. Runtime
// arithmetic/BigInt ABI belongs to N3. Little endian base 2^32, zero = [].
class LiteralNat {
    void normalize() {while(!words.empty() && words.back()==0) words.pop_back();}
public:
    std::vector<std::uint32_t> words;
    explicit LiteralNat(std::uint64_t value=0) {
        if(value) {words.push_back(static_cast<std::uint32_t>(value));if(value>>32) words.push_back(static_cast<std::uint32_t>(value>>32));}
    }
    explicit LiteralNat(std::vector<std::uint32_t> value):words(std::move(value)) {}
    bool zero() const {return words.empty();}
    void multiply(std::uint32_t value) {
        std::uint64_t carry=0;
        for(auto& w:words) {const auto product=static_cast<std::uint64_t>(w)*value+carry;w=static_cast<std::uint32_t>(product);carry=product>>32;}
        if(carry) words.push_back(static_cast<std::uint32_t>(carry));
        normalize();
    }
    void add(std::uint32_t value) {
        std::uint64_t carry=value;
        for(auto& w:words) {carry+=w;w=static_cast<std::uint32_t>(carry);carry>>=32;if(!carry) return;}
        if(carry) words.push_back(static_cast<std::uint32_t>(carry));
    }
    std::uint32_t remainder(std::uint32_t value) const {
        std::uint64_t carry=0;for(auto it=words.rbegin();it!=words.rend();++it) carry=((carry<<32)|*it)%value;
        return static_cast<std::uint32_t>(carry);
    }
    std::uint32_t divide(std::uint32_t value) {
        std::uint64_t carry=0;
        for(auto it=words.rbegin();it!=words.rend();++it) {const auto x=(carry<<32)|*it;*it=static_cast<std::uint32_t>(x/value);carry=x%value;}
        normalize();return static_cast<std::uint32_t>(carry);
    }
    std::size_t bits() const {
        if(zero()) return 0;
        std::size_t n=(words.size()-1)*32;auto w=words.back();while(w) {++n;w>>=1;}return n;
    }
    static LiteralNat decimal(const std::string& text,FrontendMeter& meter) {
        LiteralNat n;std::size_t i=0;
        for(const auto c:text) if(c!='.') {if(i++%128==0) meter.safe_point();n.multiply(10);n.add(static_cast<std::uint32_t>(c-'0'));}
        return n;
    }
    std::string decimal() const {
        if(zero()) return "0";
        auto n=*this;std::vector<std::uint32_t> chunks;
        while(!n.zero()) chunks.push_back(n.divide(1000000000));
        std::string out=std::to_string(chunks.back());
        for(std::size_t i=chunks.size()-1;i>0;--i) {auto s=std::to_string(chunks[i-1]);out+=std::string(9-s.size(),'0')+s;}
        return out;
    }
};
inline void literal_bits(const LiteralNat& n,const Token& t,FrontendMeter& meter) {
    meter.check("integer_bits",n.bits(),display_path(t.source->path),token_span(t));
}
inline NumericLiteral numeric_literal(const AstNode& node,FrontendMeter& meter) {
    if(node.kind=="integer") {
        auto n=LiteralNat::decimal(spelling(node.token),meter);literal_bits(n,node.token,meter);return {false,std::move(n.words),0};
    }
    const auto locale=_create_locale(LC_NUMERIC,"C");if(!locale) throw std::bad_alloc();
    const auto text=spelling(node.token);char* end=nullptr;const auto value=_strtod_l(text.c_str(),&end,locale);_free_locale(locale);
    if(end!=text.c_str()+text.size() || !std::isfinite(value)) fail_at(node.token,"E208","Float literal must be finite");
    return {true,{},value};
}
inline QuantityLiteral quantity_literal(const AstNode& node,FrontendMeter& meter) {
    struct Unit {std::uint32_t n,d;int length,time;};
    const std::map<std::string,Unit> units={{"ms",{1,1000,0,1}},{"s",{1,1,0,1}},{"min",{60,1,0,1}},{"h",{3600,1,0,1}},
        {"mm",{1,1000,1,0}},{"cm",{1,100,1,0}},{"m",{1,1,1,0}},{"km",{1000,1,1,0}},{"one",{1,1,0,0}}};
    const auto found=units.find(spelling(*node.auxiliary));if(found==units.end()) fail_at(*node.auxiliary,"E306","unknown unit");
    const auto unit=found->second;const auto text=spelling(node.token);
    auto numerator=LiteralNat::decimal(text,meter);literal_bits(numerator,node.token,meter);
    const auto dot=text.find('.');const auto places=dot==std::string::npos?0:text.size()-dot-1;
    meter.check("integer_bits",static_cast<std::uint64_t>(static_cast<double>(places)*std::log2(10.0))+1,
                display_path(node.token.source->path),token_span(node.token));
    LiteralNat denominator(1);
    for(std::size_t i=0;i<places;++i) {if(i%128==0) meter.safe_point();denominator.multiply(10);}
    const auto a=std::gcd(numerator.remainder(unit.d),unit.d),b=std::gcd(denominator.remainder(unit.n),unit.n);
    numerator.divide(a);denominator.divide(b);numerator.multiply(unit.n/b);denominator.multiply(unit.d/a);
    literal_bits(numerator,node.token,meter);literal_bits(denominator,node.token,meter);
    if(numerator.zero()) denominator=LiteralNat(1);
    else for(const auto factor:{2u,5u}) while(numerator.remainder(factor)==0 && denominator.remainder(factor)==0) {
        meter.safe_point();numerator.divide(factor);denominator.divide(factor);
    }
    meter.check("quantity_exponent_abs",static_cast<std::uint64_t>(std::max(unit.length,unit.time)),display_path(node.token.source->path),token_span(node.token));
    return {std::move(numerator.words),std::move(denominator.words),unit.length,unit.time};
}
// Exact numeric pattern equality, including Int vs integral Float. Do not round
// arbitrary integers through double (e.g. 9007199254740993 != 9007199254740992.0).
inline std::string numeric_pattern(const NumericLiteral& n,bool negative) {
    if(!n.floating) {const LiteralNat integer(n.words);return std::string(negative && !integer.zero()?"-":"+")+integer.decimal();}
    const auto value=n.real;
    if(std::trunc(value)==value) {
        if(value==0) return "+0";
        std::uint64_t bits=0;std::memcpy(&bits,&value,sizeof(bits));
        const auto exponent=static_cast<int>((bits>>52)&2047)-1023;
        const auto mantissa=(bits&UINT64_C(0xfffffffffffff))|UINT64_C(0x10000000000000);
        LiteralNat integer(exponent<52?mantissa>>(52-exponent):mantissa);
        for(int i=52;i<exponent;++i) integer.multiply(2);
        return std::string(negative?"-":"+")+integer.decimal();
    }
    const double signed_value=negative?-value:value;std::uint64_t bits=0;std::memcpy(&bits,&signed_value,sizeof(bits));
    return "float:"+std::to_string(bits);
}
}
