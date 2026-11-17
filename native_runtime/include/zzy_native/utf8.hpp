#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
namespace zzy {
struct Decoded {
    std::u32string text;
    // Includes EOF; BOM is excluded from text but included in raw offsets.
    std::vector<std::size_t> byte_offsets;
};
inline Decoded decode_utf8(std::string_view bytes,bool strip_bom=false) {
    Decoded out;
    std::size_t i=strip_bom && bytes.substr(0,3)=="\xef\xbb\xbf"?3:0;
    while(i<bytes.size()) {
        out.byte_offsets.push_back(i);
        const auto first=static_cast<unsigned char>(bytes[i++]);
        char32_t c=first;
        unsigned count=0;
        char32_t minimum=0;
        if(first<0x80) {}
        else if(first>=0xc2 && first<=0xdf) {c=first&31;count=1;minimum=0x80;}
        else if(first>=0xe0 && first<=0xef) {c=first&15;count=2;minimum=0x800;}
        else if(first>=0xf0 && first<=0xf4) {c=first&7;count=3;minimum=0x10000;}
        else throw std::invalid_argument("invalid UTF-8 leading byte");
        for(unsigned j=0;j<count;++j) {
            if(i>=bytes.size()) throw std::invalid_argument("truncated UTF-8 sequence");
            const auto next=static_cast<unsigned char>(bytes[i++]);
            if((next&0xc0)!=0x80) throw std::invalid_argument("invalid UTF-8 continuation");
            c=(c<<6)|(next&63);
        }
        if(c<minimum || c>0x10ffff || (c>=0xd800 && c<=0xdfff)) throw std::invalid_argument("non-scalar UTF-8 sequence");
        out.text+=c;
    }
    out.byte_offsets.push_back(bytes.size());
    return out;
}
inline std::string encode_utf8(std::u32string_view text) {
    std::string out;
    for(char32_t c:text) {
        if(c>0x10ffff || (c>=0xd800 && c<=0xdfff)) throw std::invalid_argument("non-scalar codepoint");
        if(c<0x80) out+=static_cast<char>(c);
        else if(c<0x800) {out+=static_cast<char>(0xc0|(c>>6));out+=static_cast<char>(0x80|(c&63));}
        else if(c<0x10000) {out+=static_cast<char>(0xe0|(c>>12));out+=static_cast<char>(0x80|((c>>6)&63));out+=static_cast<char>(0x80|(c&63));}
        else {out+=static_cast<char>(0xf0|(c>>18));out+=static_cast<char>(0x80|((c>>12)&63));out+=static_cast<char>(0x80|((c>>6)&63));out+=static_cast<char>(0x80|(c&63));}
    }
    return out;
}
}
