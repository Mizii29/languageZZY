#pragma once
#include "frontend_resources.hpp"
#include <algorithm>
#include "windows_files.hpp"
#include <memory>
namespace zzy {
struct Source final {
    const std::wstring path;
    const std::string raw;
    const Decoded decoded;
    const std::vector<std::size_t> line_starts;
    static std::vector<std::size_t> lines(const std::u32string& text,const std::function<void()>& safe_point={}) {
        std::vector<std::size_t> result{0};
        for(std::size_t i=0;i<text.size();++i) {
            if(i%1024==0 && safe_point) safe_point();
            if(text[i]==U'\n') result.push_back(i+1);
        }
        return result;
    }
    Source(std::wstring p,std::string bytes,const std::function<void()>& safe_point={})
        :path(std::move(p)),raw(std::move(bytes)),decoded(decode_utf8(raw,true,safe_point)),line_starts(lines(decoded.text,safe_point)) {}
    Position position(std::size_t offset) const {
        if(offset>decoded.text.size()) throw std::out_of_range("source offset");
        const auto upper=std::upper_bound(line_starts.begin(),line_starts.end(),offset);
        const auto line=static_cast<std::size_t>(upper-line_starts.begin());
        return {line,offset-line_starts[line-1]+1};
    }
    Span span(std::size_t start,std::size_t end) const {
        if(end<start) throw std::out_of_range("reversed span");
        return {position(start),position(end)};
    }
    std::size_t codepoint_offset(std::size_t raw_offset) const {
        const auto& offsets=decoded.byte_offsets;
        const auto it=std::lower_bound(offsets.begin(),offsets.end(),raw_offset);
        if(it==offsets.end() || *it!=raw_offset) throw std::out_of_range("not a codepoint boundary (or stripped BOM)");
        return static_cast<std::size_t>(it-offsets.begin());
    }
    std::string info(const ResourcePolicy& policy,const std::function<void()>& safe_point={}) const {
        return "{\"file\":"+quote(display_path(path))+",\"bytes\":"+std::to_string(raw.size())+
            ",\"codepoints\":"+std::to_string(decoded.text.size())+",\"lines\":"+std::to_string(line_starts.size())+
            ",\"sha256\":"+quote(sha256(raw,safe_point))+",\"syntax_checked\":false,\"resource_fingerprint\":"+quote(policy.fingerprint())+"}\n";
    }
};
struct SourceSnapshot {
    std::map<std::wstring,std::string> files;
    std::map<std::wstring,std::wstring> aliases;
};
class SourceLoader {
    FrontendMeter& meter;
    const SourceSnapshot* snapshot;
    std::map<std::wstring,std::wstring>* observed;
    std::map<std::wstring,std::shared_ptr<const Source>> cache;
    std::uint64_t reserved_bytes=0,reserved_modules=0;
public:
    explicit SourceLoader(FrontendMeter& m,const SourceSnapshot* frozen=nullptr,
                          std::map<std::wstring,std::wstring>* paths=nullptr)
        :meter(m),snapshot(frozen),observed(paths) {}
    SourceLoader(const SourceLoader&)=delete;
    SourceLoader& operator=(const SourceLoader&)=delete;
    ~SourceLoader() {close();}
    void close() noexcept {
        cache.clear();meter.source_total-=reserved_bytes;meter.module_count-=reserved_modules;
        reserved_bytes=reserved_modules=0;
    }
    std::shared_ptr<const Source> load(const std::wstring& path,std::uint64_t depth=1) {
        const auto file=display_path(path);
        meter.check("import_depth",depth,file);
        if(snapshot) {
            const auto alias=snapshot->aliases.find(full_path(path));
            if(alias==snapshot->aliases.end())throw FrontendError("E401","missing source alias in spec snapshot",file);
            const auto& canonical=alias->second;
            const auto cached=cache.find(canonical);
            if(cached!=cache.end())return cached->second;
            const auto& bytes=snapshot->files.at(canonical);
            meter.check("module_count",meter.module_count+1,file);
            meter.check("source_file_bytes",bytes.size(),file);
            meter.check("source_total_bytes",meter.source_total+bytes.size(),file);
            auto source=std::make_shared<const Source>(canonical,bytes,[&]{meter.safe_point();});
            cache.emplace(canonical,source);
            reserved_bytes+=bytes.size();++reserved_modules;
            meter.source_total+=bytes.size();++meter.module_count;
            return source;
        }
        // Canonicalize through a handle (junctions and 8.3 aliases included).
        FileHandle stream(CreateFileW(extended_path(path).c_str(),GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
                                     nullptr,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,nullptr));
        if(!stream) throw FrontendError("E401","cannot open source",file);
        const auto canonical=final_path(stream.get());
        for(const auto& item:cache) if(same_path(item.first,canonical)) {
            if(observed)observed->insert_or_assign(full_path(path),item.first);
            return item.second;
        }
        if(observed)observed->insert_or_assign(full_path(path),canonical);
        meter.check("module_count",meter.module_count+1,file);
        BY_HANDLE_FILE_INFORMATION attributes{};
        if(!GetFileInformationByHandle(stream.get(),&attributes) || (attributes.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY))
            throw FrontendError("E401","source is not a regular file",file);
        std::string bytes;
        char buffer[65536];
        while(true) {
            meter.safe_point();
            const auto available=std::min(meter.policy().limits.at("source_file_bytes")-bytes.size(),
                meter.policy().limits.at("source_total_bytes")-meter.source_total-bytes.size());
            const auto count=std::min<std::uint64_t>(sizeof(buffer),available+1);
            DWORD size=0;
            if(!ReadFile(stream.get(),buffer,static_cast<DWORD>(count),&size,nullptr)) throw FrontendError("E401","cannot read source",file);
            meter.check("source_file_bytes",bytes.size()+size,file);
            meter.check("source_total_bytes",meter.source_total+bytes.size()+size,file);
            bytes.append(buffer,size);
            if(size==0) break;
        }
        std::shared_ptr<const Source> source;
        try {source=std::make_shared<const Source>(canonical,std::move(bytes),[&]{meter.safe_point();});}
        catch(const std::invalid_argument&) {throw FrontendError("E401","source is not strict UTF-8",file);}
        meter.safe_point();
        cache.emplace(canonical,source);
        reserved_bytes+=source->raw.size();++reserved_modules;
        meter.source_total+=source->raw.size();++meter.module_count;
        return source;
    }
};
inline ResourcePolicy load_policy(const std::wstring& path) {
    const auto file=display_path(path);
    FileHandle stream(CreateFileW(extended_path(path).c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr));
    if(!stream) throw FrontendError("E401","cannot open resource configuration",file);
    std::string bytes(65537,'\0');DWORD size=0;
    if(!ReadFile(stream.get(),bytes.data(),static_cast<DWORD>(bytes.size()),&size,nullptr)) throw FrontendError("E401","cannot read resource configuration",file);
    bytes.resize(size);
    try {return PolicyParser(bytes).parse();}
    catch(const FrontendError& error) {throw FrontendError(error.code,error.what(),file);}
}
}
