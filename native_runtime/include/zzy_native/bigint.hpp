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
    bool zero() const {return !sign_;}
    const std::vector<std::uint32_t>& words() const {return words_;}
    std::size_t bits() const {
        if(zero()) return 0;auto high=words_.back();std::size_t n=(words_.size()-1)*32;
        while(high) {++n;high>>=1;}return n;
    }
    BigInt abs() const {auto r=*this;if(!r.zero()) r.sign_=1;return r;}
    BigInt operator-() const {auto r=*this;r.sign_=-r.sign_;return r;}
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
    std::string decimal() const {
        if(zero()) return "0";auto v=words_;std::vector<std::uint32_t> chunks;
        while(!v.empty()) {
            std::uint64_t carry=0;
            for(std::size_t i=v.size();i>0;--i) {carry=(carry<<32)|v[i-1];v[i-1]=static_cast<std::uint32_t>(carry/1000000000);carry%=1000000000;}
            chunks.push_back(static_cast<std::uint32_t>(carry));while(!v.empty() && !v.back()) v.pop_back();
        }
        std::string out=sign_<0?"-":"";out+=std::to_string(chunks.back());
        for(std::size_t i=chunks.size()-1;i>0;--i) {auto s=std::to_string(chunks[i-1]);out+=std::string(9-s.size(),'0')+s;}return out;
    }
    double real() const {double r=0;for(std::size_t i=words_.size();i>0;--i) r=std::ldexp(r,32)+words_[i-1];return sign_<0?-r:r;}
    static std::pair<BigInt,BigInt> ratio(double x) {
        if(!std::isfinite(x)) throw std::domain_error("non-finite float");
        std::uint64_t raw=0;std::memcpy(&raw,&x,sizeof(raw));const auto exponent=(raw>>52)&2047;
        const auto fraction=raw&UINT64_C(0xfffffffffffff);
        BigInt n(std::vector<std::uint32_t>{static_cast<std::uint32_t>(fraction),static_cast<std::uint32_t>(fraction>>32)});
        if(exponent) n=n+BigInt(1).shift(52);
        const int shift=exponent?static_cast<int>(exponent)-1075:-1074;
        BigInt d(1);if(shift>=0) n=n.shift(static_cast<std::size_t>(shift));else d=d.shift(static_cast<std::size_t>(-shift));
        if(raw>>63) n=-n;return {std::move(n),std::move(d)};
    }
    int compare(double x) const {const auto r=ratio(x);return (*this*r.second).compare(r.first);}
};
inline BigInt gcd(BigInt a,BigInt b,const std::function<void()>& point={}) {
    a=a.abs();b=b.abs();while(!b.zero()) {auto r=a.divmod(b,point).second;a=std::move(b);b=std::move(r);}return a;
}
struct Rational {
    BigInt numerator,denominator{1};
    Rational()=default;
    Rational(BigInt n,BigInt d=BigInt(1)):numerator(std::move(n)),denominator(std::move(d)) {
        if(denominator.zero()) throw std::domain_error("zero denominator");
        if(denominator.sign()<0) {numerator=-numerator;denominator=-denominator;}
        auto g=gcd(numerator,denominator);numerator=numerator/g;denominator=denominator/g;
    }
};
}
