#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace zzy {
// Signed magnitude, base 2^32. No host-width narrowing of ZZY integers.
class BigInt {
    int sign_=0;
    std::vector<std::uint32_t> words_;
    void normalize() {while(!words_.empty() && !words_.back()) words_.pop_back();if(words_.empty()) sign_=0;}
    static BigInt magnitude_add(const BigInt& a,const BigInt& b) {
        BigInt r;r.sign_=1;std::uint64_t carry=0;
        for(std::size_t i=0;i<std::max(a.words_.size(),b.words_.size());++i) {
            carry+=(i<a.words_.size()?a.words_[i]:0);carry+=(i<b.words_.size()?b.words_[i]:0);
            r.words_.push_back(static_cast<std::uint32_t>(carry));carry>>=32;
        }
        if(carry) r.words_.push_back(static_cast<std::uint32_t>(carry));r.normalize();return r;
    }
    static BigInt magnitude_sub(const BigInt& a,const BigInt& b) {
        BigInt r;r.sign_=1;std::uint64_t borrow=0;
        for(std::size_t i=0;i<a.words_.size();++i) {
            const std::uint64_t sub=(i<b.words_.size()?b.words_[i]:0)+borrow;
            const std::uint64_t v=a.words_[i];r.words_.push_back(static_cast<std::uint32_t>(v-sub));borrow=v<sub;
        }
        r.normalize();return r;
    }
public:
    BigInt()=default;
    explicit BigInt(std::int64_t n) {
        if(!n) return;sign_=n<0?-1:1;
        const std::uint64_t v=n<0?std::uint64_t(0)-static_cast<std::uint64_t>(n):static_cast<std::uint64_t>(n);
        words_.push_back(static_cast<std::uint32_t>(v));if(v>>32) words_.push_back(static_cast<std::uint32_t>(v>>32));
    }
    explicit BigInt(std::vector<std::uint32_t> words,int sign=1):sign_(sign),words_(std::move(words)) {normalize();}
    static BigInt decimal(const std::string& text) {
        BigInt r;std::size_t i=0;int sign=1;
        if(!text.empty() && (text[0]=='-' || text[0]=='+')) {sign=text[0]=='-'?-1:1;++i;}
        if(i==text.size()) throw std::invalid_argument("empty integer");
        for(;i<text.size();++i) {if(text[i]<'0' || text[i]>'9') throw std::invalid_argument("integer digit");r=r*BigInt(10)+BigInt(text[i]-'0');}
        if(!r.zero()) r.sign_=sign;return r;
    }
    int sign() const {return sign_;}
    static std::size_t word_bits(std::uint32_t v) {std::size_t n=0;while(v) {++n;v>>=1;}return n;}
    std::uint32_t word(std::size_t i) const {return i<words_.size()?words_[i]:0;}
    bool zero() const {return !sign_;}
    const std::vector<std::uint32_t>& words() const {return words_;}
    std::size_t bits() const {
        if(zero()) return 0;auto high=words_.back();std::size_t n=(words_.size()-1)*32;
        while(high) {++n;high>>=1;}return n;
    }
    BigInt abs() const {auto r=*this;if(!r.zero()) r.sign_=1;return r;}
    void negate() noexcept {sign_=-sign_;}
    BigInt operator-() const {auto r=*this;r.negate();return r;}
    static int magnitude_compare(const BigInt& a,const BigInt& b) {
        if(a.words_.size()!=b.words_.size()) return a.words_.size()<b.words_.size()?-1:1;
        for(std::size_t i=a.words_.size();i>0;--i) if(a.words_[i-1]!=b.words_[i-1]) return a.words_[i-1]<b.words_[i-1]?-1:1;
        return 0;
    }
    int compare(const BigInt& b) const {if(sign_!=b.sign_) return sign_<b.sign_?-1:1;return sign_*magnitude_compare(*this,b);}
    bool operator==(const BigInt& b) const {return compare(b)==0;}
    bool operator!=(const BigInt& b) const {return compare(b)!=0;}
    bool operator<(const BigInt& b) const {return compare(b)<0;}
    bool operator>(const BigInt& b) const {return compare(b)>0;}
    bool operator<=(const BigInt& b) const {return compare(b)<=0;}
    bool operator>=(const BigInt& b) const {return compare(b)>=0;}
    BigInt operator+(const BigInt& b) const {
        if(zero()) return b;if(b.zero()) return *this;
        if(sign_==b.sign_) {auto r=magnitude_add(*this,b);r.sign_=sign_;return r;}
        const int c=magnitude_compare(*this,b);if(!c) return BigInt();
        auto r=c>0?magnitude_sub(*this,b):magnitude_sub(b,*this);r.sign_=c>0?sign_:b.sign_;return r;
    }
    BigInt operator-(const BigInt& b) const {return *this+-b;}
    std::size_t sum_bits(const BigInt& b,bool subtract,const std::function<void()>& point) const {
        if(zero()) return b.bits();if(b.zero()) return bits();
        const bool adding=sign_==(subtract?-b.sign_:b.sign_);
        const bool swapped=!adding && magnitude_compare(*this,b)<0;
        const auto& x=swapped?b:*this;const auto& y=swapped?*this:b;
        std::uint64_t carry=0;std::size_t bits=0;
        const auto count=std::max(x.words_.size(),y.words_.size());
        for(std::size_t i=0;i<count;++i) {
            point();const std::uint64_t a=x.word(i),v=y.word(i);
            const auto out=adding?a+v+carry:a-v-carry;
            carry=adding?out>>32:static_cast<std::uint64_t>(a<v+carry);
            const auto n=word_bits(static_cast<std::uint32_t>(out));if(n) bits=i*32+n;
        }
        return adding && carry?count*32+1:bits;
    }
    std::size_t product_bits(const BigInt& b,const std::function<void()>& point) const {
        if(zero() || b.zero()) return 0;
        std::uint64_t carry=0;std::size_t width=0;
        for(std::size_t place=0;place<words_.size()+b.words_.size();++place) {
            point();std::uint64_t lower=carry&UINT64_C(0xffffffff),upper=carry>>32;
            const auto start=place>=b.words_.size()?place-b.words_.size()+1:0;
            const auto end=std::min(place+1,words_.size());
            for(std::size_t i=start;i<end;++i) {
                if((i&255)==0) point();
                const auto p=std::uint64_t(words_[i])*b.words_[place-i];lower+=p&UINT64_C(0xffffffff);
                upper+=(p>>32)+(lower>>32);lower&=UINT64_C(0xffffffff);
            }
            carry=upper;const auto n=word_bits(static_cast<std::uint32_t>(lower));if(n) width=place*32+n;
        }
        return width;
    }
    BigInt multiply(const BigInt& b,const std::function<void()>& point={}) const {
        if(zero() || b.zero()) return BigInt();
        BigInt r;r.sign_=sign_*b.sign_;r.words_.resize(words_.size()+b.words_.size());
        for(std::size_t i=0;i<words_.size();++i) {
            if(point) point();std::uint64_t carry=0;
            for(std::size_t j=0;j<b.words_.size();++j) {
                const std::uint64_t v=std::uint64_t(words_[i])*b.words_[j]+r.words_[i+j]+carry;
                r.words_[i+j]=static_cast<std::uint32_t>(v);carry=v>>32;
            }
            r.words_[i+b.words_.size()]=static_cast<std::uint32_t>(carry);
        }
        r.normalize();return r;
    }
    BigInt operator*(const BigInt& b) const {return multiply(b);}
    BigInt shift(std::size_t bits) const {
        if(zero()) return *this;BigInt r;r.sign_=sign_;r.words_.assign(bits/32,0);
        std::uint64_t carry=0;
        for(auto v:words_) {carry|=std::uint64_t(v)<<(bits%32);r.words_.push_back(static_cast<std::uint32_t>(carry));carry>>=32;}
        if(carry) r.words_.push_back(static_cast<std::uint32_t>(carry));return r;
    }
    // Binary long division is deliberately simple; cancellation at each bit.
    std::pair<BigInt,BigInt> divmod(const BigInt& b,const std::function<void()>& point={}) const {
        if(b.zero()) throw std::domain_error("zero divisor");
        BigInt q,r;const auto divisor=b.abs();q.sign_=1;q.words_.resize(words_.size());
        for(std::size_t k=bits();k>0;--k) {
            if(point) point();r=r.shift(1);
            if((words_[(k-1)/32]>>((k-1)%32))&1) r=r+BigInt(1);
            if(magnitude_compare(r,divisor)>=0) {r=magnitude_sub(r,divisor);q.words_[(k-1)/32]|=std::uint32_t(1)<<((k-1)%32);}
        }
        q.normalize();if(!q.zero()) q.sign_=sign_*b.sign_;
        if(!r.zero()) r.sign_=sign_;
        if(!r.zero() && sign_!=b.sign_) {q=q-BigInt(1);r=r+b;}
        return {std::move(q),std::move(r)};
    }
    BigInt operator/(const BigInt& b) const {return divmod(b).first;}
    BigInt operator%(const BigInt& b) const {return divmod(b).second;}
    std::string decimal(const std::function<void()>& point={}) const {
        if(zero()) return "0";auto v=words_;std::vector<std::uint32_t> chunks;
        while(!v.empty()) {
            if(point) point();
            std::uint64_t carry=0;
            for(std::size_t i=v.size();i>0;--i) {carry=(carry<<32)|v[i-1];v[i-1]=static_cast<std::uint32_t>(carry/1000000000);carry%=1000000000;}
            chunks.push_back(static_cast<std::uint32_t>(carry));while(!v.empty() && !v.back()) v.pop_back();
        }
        std::string out=sign_<0?"-":"";out+=std::to_string(chunks.back());
        for(std::size_t i=chunks.size()-1;i>0;--i) {auto s=std::to_string(chunks[i-1]);out+=std::string(9-s.size(),'0')+s;}return out;
    }
    bool bit(std::size_t i) const {return ((word(i/32)>>(i%32))&1U)!=0;}
    double real() const {
        const auto width=bits();if(width>1024) return sign_<0?-HUGE_VAL:HUGE_VAL;
        const auto discarded=width>53?width-53:0;std::uint64_t mantissa=0;
        for(auto i=width;i>discarded;--i) mantissa=(mantissa<<1)|std::uint64_t(bit(i-1));
        if(discarded && bit(discarded-1)) {
            bool round=(mantissa&1)!=0;for(std::size_t i=0;!round && i+1<discarded;++i) round=bit(i);
            if(round) ++mantissa;
        }
        const auto value=std::ldexp(static_cast<double>(mantissa),static_cast<int>(discarded));return sign_<0?-value:value;
    }
    static std::pair<BigInt,BigInt> ratio(double x) {
        if(!std::isfinite(x)) throw std::domain_error("non-finite float");
        std::uint64_t raw=0;std::memcpy(&raw,&x,sizeof(raw));const auto exponent=(raw>>52)&2047;
        const auto fraction=raw&UINT64_C(0xfffffffffffff);
        auto mantissa=fraction+(exponent?(UINT64_C(1)<<52):0);
        if(!mantissa) return {BigInt(),BigInt(1)};
        int shift=exponent?static_cast<int>(exponent)-1075:-1074;
        while(shift<0 && (mantissa&1)==0) {mantissa>>=1;++shift;}
        BigInt n(static_cast<std::int64_t>(mantissa));
        BigInt d(1);if(shift>=0) n=n.shift(static_cast<std::size_t>(shift));else d=d.shift(static_cast<std::size_t>(-shift));
        if(raw>>63) n=-n;return {std::move(n),std::move(d)};
    }
    int compare(double x) const {
        if(!std::isfinite(x)) throw std::domain_error("non-finite float");
        const int s=x<0?-1:x>0?1:0;if(sign_!=s) return sign_<s?-1:1;if(!s) return 0;
        int exponent=0;const auto fraction=std::frexp(std::abs(x),&exponent);
        if(exponent<1) return s;
        const auto w=bits();if(w!=static_cast<std::size_t>(exponent)) return w<static_cast<std::size_t>(exponent)?-s:s;
        const auto mantissa=static_cast<std::uint64_t>(std::ldexp(fraction,53));
        for(auto i=w;i>0;--i) {
            const auto offset=static_cast<int>(i-1)-exponent+53;
            const bool theirs=offset>=0 && ((mantissa>>offset)&1U)!=0;
            if(bit(i-1)!=theirs) return theirs?-s:s;
        }
        const int fractional=53-exponent;
        return fractional>0 && (mantissa&((UINT64_C(1)<<fractional)-1))?-s:0;
    }
};
inline BigInt gcd(BigInt a,BigInt b,const std::function<void()>& point={}) {
    a=a.abs();b=b.abs();while(!b.zero()) {auto r=a.divmod(b,point).second;a=std::move(b);b=std::move(r);}return a;
}
struct Rational {
    BigInt numerator,denominator{1};
    Rational()=default;
    static Rational reduced(BigInt n,BigInt d=BigInt(1)) {
        Rational value;value.numerator=std::move(n);value.denominator=std::move(d);return value;
    }
};
}
