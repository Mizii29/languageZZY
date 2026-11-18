#pragma once
#include "windows_files.hpp"
#include <array>

namespace zzy {
namespace file_detail {
struct Failure : std::runtime_error {using std::runtime_error::runtime_error;};
[[noreturn]] inline void failed(const char* operation,DWORD code=GetLastError()) {
    throw Failure(std::string(operation)+" (Win32 "+std::to_string(code)+")");
}
inline void replace(const std::wstring& source,const std::wstring& target) {
    const auto attributes=GetFileAttributesW(source.c_str());
    if(attributes==INVALID_FILE_ATTRIBUTES) failed("cannot inspect replacement source");
    if(attributes&FILE_ATTRIBUTE_DIRECTORY) failed("replacement source is a directory",ERROR_DIRECTORY);
    if(!MoveFileExW(source.c_str(),target.c_str(),MOVEFILE_REPLACE_EXISTING)) failed("cannot replace target");
}
struct Temp {
    std::wstring path;
    bool owned=false;
    ~Temp() {if(owned) DeleteFileW(path.c_str());}
};
enum class Step {open,write,close,commit};
struct SystemWriter {
    bool write(HANDLE stream,const char* data,DWORD size,DWORD& written) const {
        return WriteFile(stream,data,size,&written,nullptr)!=0;
    }
    bool close(FileHandle& stream) const {return stream.close();}
};
template<class Checkpoint,class Writer=SystemWriter>
void write(const std::wstring& target,std::string_view bytes,bool atomic,Checkpoint checkpoint,Writer writer={}) {
    Temp temporary;
    HANDLE handle=INVALID_HANDLE_VALUE;
    checkpoint(Step::open);
    if(atomic) {
        static std::atomic<std::uint64_t> sequence{0};
        const auto parent=target.substr(0,target.find_last_of(L"\\/")+1);
        for(unsigned attempt=0;attempt<128;++attempt) {
            checkpoint(Step::open);
            temporary.path=parent+L".zzy-"+std::to_wstring(GetCurrentProcessId())+L"-"+
                std::to_wstring(GetTickCount64())+L"-"+std::to_wstring(sequence++)+L".tmp";
            // Even a caller who happens to choose a temporary-looking name
            // must not see their destination created before the commit point.
            if(same_path(temporary.path,target)) continue;
            handle=CreateFileW(temporary.path.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(handle!=INVALID_HANDLE_VALUE) {temporary.owned=true;break;}
            const auto code=GetLastError();
            if(code!=ERROR_FILE_EXISTS && code!=ERROR_ALREADY_EXISTS) failed("cannot create temporary file",code);
        }
    } else {
        handle=CreateFileW(target.c_str(),GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                           nullptr,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
    }
    if(handle==INVALID_HANDLE_VALUE) failed("cannot open output",atomic?ERROR_FILE_EXISTS:GetLastError());
    FileHandle stream(handle);
    for(std::size_t offset=0;offset<bytes.size();) {
        checkpoint(Step::write);
        const auto size=static_cast<DWORD>(std::min<std::size_t>(65536,bytes.size()-offset));
        DWORD written=0;
        if(!writer.write(stream.get(),bytes.data()+offset,size,written)) failed("cannot write output");
        if(!written) failed("incomplete write",ERROR_WRITE_FAULT);
        offset+=written;
    }
    checkpoint(Step::close);
    if(!writer.close(stream)) failed("cannot close output");
    if(atomic) {
        checkpoint(Step::commit);
        replace(temporary.path,target);
        temporary.owned=false;
    }
}
}

inline std::size_t ExecutionContext::utf8_size(std::u32string_view text) const {
    std::size_t size=0;
    for(std::size_t i=0;i<text.size();++i) {
        if((i&4095)==0) point();
        size+=utf8_width(text[i]);
    }
    return size;
}

inline Value ExecutionContext::file_library(const std::string& name,const std::vector<Value>& args,NodeId site) {
    using file_detail::Failure;
    const auto file_error=[&](const char* detail) {return result(false,string(std::string("I/O failed: ")+detail,site),site);};
    try {
        Lease paths(heap.state,{},site);
        const auto path=[&](const Value& value) {
            const auto& text=object(value).characters;
            Lease bytes(heap.state,{0,0,utf8_size(text)},site);
            if(text.empty()) throw Failure("empty path");
            auto resolved=extended_path(widen(encode_utf8(text)));
            paths.grow({0,0,sizeof(wchar_t)*resolved.size()},site);
            return resolved;
        };
        const auto target=path(args[0]);
        point();
        if(name=="io.read_text") {
            FileHandle stream(CreateFileW(target.c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                                          nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr));
            if(!stream) file_detail::failed("cannot open input");
            if(GetFileType(stream.get())!=FILE_TYPE_DISK) throw Failure("input is not a disk file");
            Lease bytes(heap.state,{},site);
            std::string raw;
            std::array<char,65536> chunk;
            std::size_t points=0;
            const auto limit=heap.state->policy.limits.at("io_payload_bytes");
            for(;;) {
                point();
                const auto wanted=static_cast<DWORD>(std::min<std::uint64_t>(chunk.size(),limit-raw.size()+1));
                DWORD read=0;
                if(!ReadFile(stream.get(),chunk.data(),wanted,&read,nullptr)) file_detail::failed("cannot read input");
                if(!read) break;
                check("io_payload_bytes",raw.size()+read,site);
                points+=codepoints({chunk.data(),read});
                check("text_codepoints",points,site);
                bytes.grow({0,0,read},site);
                raw.append(chunk.data(),read);
            }
            if(!stream.close()) file_detail::failed("cannot close input");
            Lease characters(heap.state,{0,0,4*points},site);
            std::u32string text;
            text.reserve(points);
            for(std::size_t i=0;i<raw.size();) {
                if((text.size()&4095)==0) point();
                text+=utf8_next(raw,i);
            }
            characters.release();
            return result(true,string(std::move(text),site),site);
        }
        if(name=="io.replace_file") {
            const auto destination=path(args[1]);
            auto success=result(true,null_,site);
            point();
            file_detail::replace(target,destination);
            return success;
        }
        const auto& text=object(args[1]).characters;
        const auto size=utf8_size(text);
        check("io_payload_bytes",size,site);
        Lease bytes(heap.state,{0,0,size},site);
        std::string raw;
        raw.reserve(size);
        for(std::size_t i=0;i<text.size();++i) {
            if((i&4095)==0) point();
            append_utf8(raw,text[i]);
        }
        auto success=result(true,null_,site);
        file_detail::write(target,raw,name=="io.write_atomic",[this](file_detail::Step) {point();});
        return success;
    } catch(const Failure& failure) {return file_error(failure.what());}
      catch(const FrontendError& failure) {return file_error(failure.what());}
      catch(const std::invalid_argument& failure) {return file_error(failure.what());}
}
}
