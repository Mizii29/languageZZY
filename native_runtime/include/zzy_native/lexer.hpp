#pragma once
#include "tokens.hpp"
#include "unicode_tables.hpp"
namespace zzy {
class Lexer {
    std::shared_ptr<const Source> source;
    FrontendMeter& meter;
    const std::u32string& text;
    const std::string file;
    std::size_t index=0,count=0;
    std::optional<std::size_t> raw_start;
    bool end() const {return index==text.size();}
    char32_t peek(std::size_t ahead=0) const {return ahead<text.size()-index?text[index+ahead]:0;}
    static bool digit(char32_t c) {return c>=U'0' && c<=U'9';}
    static bool continuation(char32_t c) {return unicode::contains(unicode::identifier_continue,c);}
    bool starts(std::u32string_view spelling) const {return text.compare(index,spelling.size(),spelling)==0;}
    void advance(std::size_t amount=1) {
        const auto previous=index;index+=amount;
        if(previous/1024!=index/1024) meter.safe_point();
    }
    [[noreturn]] void error(const std::string& code,const std::string& message,std::size_t start,std::size_t finish) const {
        throw FrontendError(code,message,file,source->span(start,finish));
    }
    void check(const std::string& key,std::uint64_t requested,std::size_t start,std::size_t finish) const {
        meter.check(key,requested,file,source->span(start,finish));
    }
    void comment(std::size_t start,bool multiline) {
        if(!multiline) {while(!end() && peek()!=U'\r' && peek()!=U'\n') advance();return;}
        while(!end()) {
            if(starts(U"zzyend")) {
                const auto before=index?text[index-1]:0;
                if(!continuation(before) && !continuation(peek(6))) {advance(6);return;}
                advance(6);
            } else advance();
        }
        error("E101","unterminated multiline comment; expected whole word zzyend",start,start+11);
    }
    void trivia() {
        while(!end()) {
            meter.safe_point();
            if(unicode::contains(unicode::space,peek())) {advance();continue;}
            if(!continuation(index?text[index-1]:0)) {
                if(starts(U"zzysayalot:")) {const auto start=index;advance(11);comment(start,true);continue;}
                if(starts(U"zzysay:")) {const auto start=index;advance(7);comment(start,false);continue;}
            }
            return;
        }
    }
    Token number(std::size_t start) {
        std::uint64_t digits=0;std::string kind="INTEGER";
        while(digit(peek())) {advance();check("numeric_digits",++digits,start,index);}
        if(peek()==U'.' && digit(peek(1))) {
            kind="FLOAT";advance();
            while(digit(peek())) {advance();check("numeric_digits",++digits,start,index);}
        }
        return {kind,source,start,index};
    }
    Token string(std::size_t start,bool raw) {
        advance();std::u32string value;
        while(!end()) {
            const auto c=peek();
            if(c==U'"') {advance();return {"STRING",source,start,index,encode_utf8(value),raw};}
            if(c==U'\r' || c==U'\n') error("E101","physical newline in string",start,start+1);
            std::u32string piece;
            if(!raw && starts(U"[OoO]")) {
                const auto escape=index;advance(5);
                if(starts(U"[OoO]")) {piece=U"[OoO]";advance(5);}
                else {
                    switch(peek()) {
                    case U'n':piece=U"\n";break;case U't':piece=U"\t";break;case U'r':piece=U"\r";break;
                    case U'q':piece=U"\"";break;case U'b':piece=U"\\";break;
                    default:error("E102","unknown or incomplete [OoO] escape",escape,index+(!end() && peek()!=U'"'?1:0));
                    }
                    advance();
                }
            } else {piece+=c;advance();}
            check("text_codepoints",value.size()+piece.size(),start,index);
            value+=piece;
        }
        error("E101","unterminated string",start,start+1);
    }
    Token next(std::size_t start) {
        if(peek()==U'"') {auto token=string(start,raw_start.has_value());raw_start.reset();return token;}
        if(digit(peek())) return number(start);
        if(unicode::contains(unicode::identifier_start,peek())) {
            advance();while(continuation(peek())) advance();
            const auto name=std::u32string_view(text).substr(start,index-start);
            if(name==U"zzyend") error("E101","zzyend only terminates multiline comments",start,index);
            const char* kind="IDENT";
            if(name==U"_") kind="WILDCARD";
            else for(const auto reserved:reserved_names) if(name==reserved) {kind="RESERVED_NAME";break;}
            return {kind,source,start,index};
        }
        for(const auto& fixed:fixed_tokens) if(starts(fixed.first)) {
            advance(fixed.first.size());if(std::string_view(fixed.second)=="RAW") raw_start=start;
            return {fixed.second,source,start,index};
        }
        error("E101","illegal character",start,start+1);
    }
public:
    Lexer(std::shared_ptr<const Source> s,FrontendMeter& m):source(std::move(s)),meter(m),text(source->decoded.text),file(display_path(source->path)) {}
    std::vector<Token> scan() {
        std::vector<Token> tokens;
        while(true) {
            meter.safe_point();trivia();const auto start=index;
            if(raw_start && (end() || peek()!=U'"')) error("E101","(raw) must precede a double-quoted string",*raw_start,*raw_start+5);
            if(end()) {tokens.emplace_back("EOF",source,start,start);return tokens;}
            check("tokens_per_file",count+1,start,start+1);
            tokens.push_back(next(start));++count;
        }
    }
};
}
