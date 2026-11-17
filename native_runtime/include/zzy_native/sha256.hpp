#pragma once
#include <array>
#include <cstdint>
#include <functional>
#include <string>
#include <string_view>
namespace zzy {
inline std::string sha256(std::string_view input,const std::function<void()>& safe_point={}) {
    constexpr std::uint32_t k[]={
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    std::array<std::uint32_t,8> h={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    const auto rotate=[](std::uint32_t n,unsigned r){return (n>>r)|(n<<(32-r));};
    const std::size_t blocks=(input.size()+9+63)/64;
    for(std::size_t block=0;block<blocks;++block) {
        if(block%16==0 && safe_point) safe_point();
        std::uint32_t w[64]={};
        for(std::size_t j=0;j<64;++j) {
            const auto index=block*64+j;
            unsigned char b=0;
            if(index<input.size()) b=static_cast<unsigned char>(input[index]);
            else if(index==input.size()) b=0x80;
            else if(index>=blocks*64-8) b=static_cast<unsigned char>((static_cast<std::uint64_t>(input.size())*8)>>((blocks*64-1-index)*8));
            w[j/4]|=static_cast<std::uint32_t>(b)<<((3-j%4)*8);
        }
        for(unsigned j=16;j<64;++j) {
            const auto a=w[j-15],b=w[j-2];
            w[j]=w[j-16]+(rotate(a,7)^rotate(a,18)^(a>>3))+w[j-7]+(rotate(b,17)^rotate(b,19)^(b>>10));
        }
        auto a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],v=h[7];
        for(unsigned j=0;j<64;++j) {
            const auto t1=v+(rotate(e,6)^rotate(e,11)^rotate(e,25))+((e&f)^(~e&g))+k[j]+w[j];
            const auto t2=(rotate(a,2)^rotate(a,13)^rotate(a,22))+((a&b)^(a&c)^(b&c));
            v=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
        }
        h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=v;
    }
    constexpr char hex[]="0123456789abcdef";
    std::string result;
    for(auto value:h) for(int shift=28;shift>=0;shift-=4) result+=hex[(value>>shift)&15];
    return result;
}
}
