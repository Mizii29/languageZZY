#pragma once
#include <cstdint>
#include <functional>
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
inline std::size_t utf8_width(char32_t cp) {
    if(cp>0x10ffff || (cp>=0xd800 && cp<=0xdfff)) throw std::invalid_argument("non-scalar codepoint");
    return cp<0x80?1:cp<0x800?2:cp<0x10000?3:4;
}
inline char32_t utf8_next(std::string_view bytes,std::size_t& i) {
    const auto first=static_cast<unsigned char>(bytes[i++]);
    char32_t cp=first,minimum=0;
    unsigned count=0;
    if(first<0x80) {}
    else if(first>=0xc2 && first<=0xdf) {cp=first&31;count=1;minimum=0x80;}
    else if(first>=0xe0 && first<=0xef) {cp=first&15;count=2;minimum=0x800;}
    else if(first>=0xf0 && first<=0xf4) {cp=first&7;count=3;minimum=0x10000;}
    else throw std::invalid_argument("invalid UTF-8 leading byte");
    for(unsigned j=0;j<count;++j) {
        if(i>=bytes.size()) throw std::invalid_argument("truncated UTF-8 sequence");
        const auto next=static_cast<unsigned char>(bytes[i++]);
        if((next&0xc0)!=0x80) throw std::invalid_argument("invalid UTF-8 continuation");
        cp=(cp<<6)|(next&63);
    }
    if(cp<minimum || cp>0x10ffff || (cp>=0xd800 && cp<=0xdfff)) throw std::invalid_argument("non-scalar UTF-8 sequence");
    return cp;
}
inline Decoded decode_utf8(std::string_view bytes,bool strip_bom=false,const std::function<void()>& safe_point={}) {
    Decoded out;
    std::size_t i=strip_bom && bytes.substr(0,3)=="\xef\xbb\xbf"?3:0;
    while(i<bytes.size()) {
        if(out.text.size()%1024==0 && safe_point) safe_point();
        out.byte_offsets.push_back(i);
        out.text+=utf8_next(bytes,i);
    }
    out.byte_offsets.push_back(bytes.size());
    return out;
}
inline void append_utf8(std::string& out,char32_t c) {
        (void)utf8_width(c);
        if(c<0x80) out+=static_cast<char>(c);
        else if(c<0x800) {out+=static_cast<char>(0xc0|(c>>6));out+=static_cast<char>(0x80|(c&63));}
        else if(c<0x10000) {out+=static_cast<char>(0xe0|(c>>12));out+=static_cast<char>(0x80|((c>>6)&63));out+=static_cast<char>(0x80|(c&63));}
        else {out+=static_cast<char>(0xf0|(c>>18));out+=static_cast<char>(0x80|((c>>12)&63));out+=static_cast<char>(0x80|((c>>6)&63));out+=static_cast<char>(0x80|(c&63));}
}
inline std::string encode_utf8(std::u32string_view text) {
    std::string out;
    for(char32_t c:text) append_utf8(out,c);
    return out;
}
}
