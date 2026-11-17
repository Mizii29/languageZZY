#include "zzy_native/source.hpp"
#include "zzy_native/policy.hpp"
#include "zzy_native/unicode_tables.hpp"
#include <functional>
#include <iostream>
namespace {
void require(bool condition,const char* message) {if(!condition) throw std::runtime_error(message);}
template<class F> void expect_error(const char* code,F function,const char* key="") {
    try {function();}catch(const zzy::FrontendError& error) {
        require(error.code==code,"wrong error code");require(std::string(error.what()).find(key)!=std::string::npos,"wrong resource key");return;
    }
    throw std::runtime_error("expected diagnostic");
}
void hash() {
    require(zzy::sha256("")=="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","empty hash");
    require(zzy::sha256("abc")=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","abc hash");
    require(zzy::sha256(std::string(1000000,'a'))=="cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0","long hash");
    zzy::ResourcePolicy policy;
    require(policy.canonical_json()==zzy::default_policy,"canonical default policy");
    require(policy.fingerprint()==zzy::default_policy_sha,"policy hash");
}
void utf8() {
    const std::u32string points={0,0x7f,0x80,0x7ff,0x800,0xffff,0x10000,0x10ffff};
    require(zzy::decode_utf8(zzy::encode_utf8(points)).text==points,"UTF-8 scalar boundary roundtrip");
    for(const std::string invalid:{"\x80","\xc0\x80","\xc1\xbf","\xc2","\xc2x","\xe0\x80\x80","\xed\xa0\x80","\xf0\x80\x80\x80","\xf4\x90\x80\x80","\xf5\x80\x80\x80","\xe2\x82"}) {
        bool rejected=false;try {(void)zzy::decode_utf8(invalid);}catch(const std::invalid_argument&) {rejected=true;}
        require(rejected,"malformed UTF-8 accepted");
    }
    require(zzy::decode_utf8("\xef\xbb\xbf\xef\xbb\xbf",true).text==U"\ufeff","only one leading BOM removed");
    require(zzy::unicode::contains(zzy::unicode::identifier_start,U'\U00010400'),"supplementary identifier");
    require(!zzy::unicode::contains(zzy::unicode::identifier_start,U'\U0001f600'),"emoji not identifier");
    require(zzy::unicode::contains(zzy::unicode::identifier_continue,U'\u0301'),"combining continuation");
    require(zzy::unicode::contains(zzy::unicode::space,U'\x1c'),"Python whitespace contract");
}
void positions() {
    zzy::Source s(L"sample", "\xef\xbb\xbf"+zzy::encode_utf8(U"\u4e2d\U0001f600\tX\r\n\u5c3e\n"));
    require(s.decoded.text.size()==8 && s.line_starts.size()==3,"BOM CRLF codepoints");
    require(s.position(3).line==1 && s.position(3).column==4,"tab is one column");
    require(s.position(6).line==2 && s.position(6).column==1,"CRLF line transition");
    require(s.position(8).line==3 && s.position(8).column==1,"EOF position");
    const std::vector<std::size_t> offsets={3,6,10,11,12,13,14,17,18};
    require(s.decoded.byte_offsets==offsets,"raw byte mapping");
    for(std::size_t i=0;i<offsets.size();++i) require(s.codepoint_offset(offsets[i])==i,"inverse mapping");
    for(const auto i:{0,4,7,19}) {bool rejected=false;try {(void)s.codepoint_offset(i);}catch(const std::out_of_range&) {rejected=true;}require(rejected,"nonboundary accepted");}
    zzy::Source empty(L"empty","");require(empty.position(0).line==1 && empty.position(0).column==1,"empty EOF");
    zzy::Source cr(L"cr","a\rb");require(cr.position(2).line==1 && cr.position(2).column==3,"bare CR not newline");
}
void write(const std::wstring& path,const std::string& text) {
    zzy::FileHandle out(CreateFileW(zzy::extended_path(path).c_str(),GENERIC_WRITE,0,nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr));
    DWORD written=0;
    if(!out || !WriteFile(out.get(),text.data(),static_cast<DWORD>(text.size()),&written,nullptr) || written!=text.size()) throw std::runtime_error("fixture write");
}
void loader() {
    wchar_t temporary[MAX_PATH+1]={};require(GetTempPathW(MAX_PATH,temporary)!=0,"temporary path");
    const auto root=std::wstring(temporary)+L"ZZY N1 \u4e2d\u6587 "+std::to_wstring(GetCurrentProcessId());
    require(CreateDirectoryW(root.c_str(),nullptr)!=0,"fixture directory");
    struct Cleanup {std::wstring root;~Cleanup(){for(auto name:{L"/a.zzy",L"/b.zzy",L"/c.zzy"}) DeleteFileW((root+name).c_str());RemoveDirectoryW(root.c_str());}} cleanup{root};
    const auto a=root+L"/a.zzy",b=root+L"/b.zzy",c=root+L"/c.zzy";
    write(a,"ab");write(b,"cd");write(c,"\xff");
    zzy::ResourcePolicy policy;policy.limits.at("source_file_bytes")=3;policy.limits.at("source_total_bytes")=3;
    std::atomic<bool> cancel{false};zzy::FrontendMeter meter(policy,cancel);
    {
        zzy::SourceLoader sources(meter);
        const auto old=sources.load(a);write(a,"changed");
        require(sources.load(root+L"/./a.zzy")==old,"immutable canonical snapshot");
        require(old->raw=="ab" && meter.source_total==2 && meter.module_count==1,"snapshot charges");
        expect_error("E211",[&]{sources.load(b);},"source_total_bytes");
        expect_error("E401",[&]{sources.load(root+L"/absent");});
        expect_error("E401",[&]{sources.load(root);});
        expect_error("E401",[&]{sources.load(c);});
        require(meter.source_total==2 && meter.module_count==1,"rollback on all source failures");
        policy.limits.at("import_depth")=1;expect_error("E211",[&]{sources.load(a,2);},"import_depth");
        policy.limits.at("module_count")=1;expect_error("E211",[&]{sources.load(b);},"module_count");
        sources.close();sources.close();require(meter.source_total==0 && meter.module_count==0,"close idempotent");
    }
    policy.limits.at("module_count")=2;policy.limits.at("source_total_bytes")=9;
    for(unsigned size=2;size<=4;++size) {
        write(a,std::string(size,'x'));zzy::SourceLoader sources(meter);
        if(size<=3) require(sources.load(a)->raw.size()==size,"source boundary below/equal");
        else expect_error("E211",[&]{sources.load(a);},"source_file_bytes");
    }
    cancel=true;bool cancelled=false;try {zzy::SourceLoader sources(meter);sources.load(b);}catch(const zzy::Cancelled&) {cancelled=true;}
    require(cancelled && meter.source_total==0 && meter.module_count==0,"cancel before allocation");
    // Removing loaded files proves read handles were closed by the loader.
    require(DeleteFileW(b.c_str())!=0,"source handle released");
}
void policy() {
    auto p=zzy::PolicyParser(R"({"limits":{"numeric_digits":7,"source_file_bytes":9223372036854775807},"policy_version":1})").parse();
    require(p.limits.at("numeric_digits")==7 && p.limits.at("source_file_bytes")==INT64_MAX,"policy bounds");
    require(zzy::PolicyParser(R"({"policy_version":1,"limits":{"numeric_\u0064igits":3}})").parse().limits.at("numeric_digits")==3,"JSON escaped key");
    for(const std::string invalid:{"{}","[]",R"({"policy_version":true,"limits":{}})",R"({"policy_version":1,"limits":{"numeric_digits":0}})",
            R"({"policy_version":1,"limits":{"numeric_digits":1.0}})",R"({"policy_version":1,"limits":{"numeric_digits":-1}})",
            R"({"policy_version":1,"limits":{"numeric_digits":9223372036854775808}})",R"({"policy_version":1,"limits":{"numeric_digits":01}})",
            R"({"policy_version":1,"limits":{"numeric_digits":2,"numeric_\u0064igits":3}})",R"({"policy_version":1,"limits":{},"policy_version":1})",
            R"({"policy_version":1,"limits":{},"extra":1})",R"({"policy_version":1,"limits":{"unknown":1}})",R"({"policy_version":1,"limits":{},})",
            R"({"policy_version":1,"limits":{"numeric_digits":null}})",R"({"policy_version":1,"limits":{"numeric_digits":NaN}})",R"({"policy_version":1,"limits":{"\ud800":1}})"})
        expect_error("E401",[&]{zzy::PolicyParser(invalid).parse();});
    expect_error("E401",[&]{zzy::PolicyParser(std::string(65537,' ')).parse();});
    expect_error("E401",[&]{zzy::PolicyParser("\xef\xbb\xbf{\"policy_version\":1,\"limits\":{}}").parse();});
}
void diagnostics() {
    const zzy::FrontendError error("E101",std::string(6000,'\n'),std::string(5000,'x'),zzy::Span{{2,3},{2,4}});
    for(const bool json:{false,true}) {
        const auto rendered=zzy::render_frontend(error,json);
        require(rendered.size()<=4096 && rendered.back()=='\n',"bounded final diagnostic");
        (void)zzy::decode_utf8(rendered);
        if(json) require(rendered.substr(0,19)=="{\"schema_version\":1","schema preserved");
    }
}
}
int main(int argc,char** argv) {
    zzy::configure_streams();
    const std::pair<const char*,std::function<void()>> cases[]={{"sha256",hash},{"utf8",utf8},{"positions",positions},{"source-loader",loader},{"policy",policy},{"diagnostics",diagnostics}};
    unsigned count=0;
    try {
        if(argc>2) throw std::runtime_error("one case selector only");
        for(const auto& test:cases) if(argc==1 || argv[1]==std::string(test.first)) {test.second();++count;std::cout<<test.first<<": passed\n";}
        require(count>0,"no frontend cases selected");std::cout<<"frontend: "<<count<<" cases passed\n";return 0;
    } catch(const std::exception& e) {std::cerr<<"frontend test failed: "<<e.what()<<'\n';return 1;}
}
