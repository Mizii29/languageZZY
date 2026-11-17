#pragma once
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include "frontend_diagnostic.hpp"
#include <algorithm>
#include <climits>
namespace zzy {
inline std::wstring widen(const std::string& utf8) {
    if(utf8.empty()) return {};
    if(utf8.find('\0')!=std::string::npos || utf8.size()>INT_MAX) throw FrontendError("E401","invalid path or argument");
    const int size=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,utf8.data(),static_cast<int>(utf8.size()),nullptr,0);
    if(!size) throw FrontendError("E401","argument is not strict UTF-8");
    std::wstring out(static_cast<std::size_t>(size),L'\0');
    if(!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,utf8.data(),static_cast<int>(utf8.size()),out.data(),size)) throw FrontendError("E401","cannot decode argument");
    return out;
}
inline std::string narrow(const std::wstring& wide) {
    if(wide.empty()) return {};
    if(wide.size()>INT_MAX) throw FrontendError("E401","argument too large");
    const int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide.data(),static_cast<int>(wide.size()),nullptr,0,nullptr,nullptr);
    if(!size) throw FrontendError("E401","argument is not Unicode scalar text");
    std::string out(static_cast<std::size_t>(size),'\0');
    if(!WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,wide.data(),static_cast<int>(wide.size()),out.data(),size,nullptr,nullptr)) throw FrontendError("E401","cannot encode argument");
    return out;
}
inline std::wstring full_path(const std::wstring& path) {
    const auto size=GetFullPathNameW(path.c_str(),0,nullptr,nullptr);
    if(!size) throw FrontendError("E401","cannot resolve path");
    std::wstring result(size,L'\0');
    const auto length=GetFullPathNameW(path.c_str(),size,result.data(),nullptr);
    if(!length || length>=size) throw FrontendError("E401","cannot resolve path");
    result.resize(length);return result;
}
inline std::wstring extended_path(const std::wstring& path) {
    auto full=full_path(path);
    if(full.substr(0,4)==L"\\\\?\\") return full;
    if(full.substr(0,2)==L"\\\\") return L"\\\\?\\UNC\\"+full.substr(2);
    return L"\\\\?\\"+full;
}
class FileHandle {
    HANDLE value_=INVALID_HANDLE_VALUE;
public:
    explicit FileHandle(HANDLE value):value_(value) {}
    FileHandle(const FileHandle&)=delete;
    FileHandle& operator=(const FileHandle&)=delete;
    ~FileHandle() {if(value_!=INVALID_HANDLE_VALUE) CloseHandle(value_);}
    HANDLE get() const {return value_;}
    explicit operator bool() const {return value_!=INVALID_HANDLE_VALUE;}
};
inline std::wstring final_path(HANDLE handle) {
    const auto size=GetFinalPathNameByHandleW(handle,nullptr,0,FILE_NAME_NORMALIZED|VOLUME_NAME_DOS);
    if(!size) throw FrontendError("E401","cannot canonicalize source");
    std::wstring out(size,L'\0');
    const auto length=GetFinalPathNameByHandleW(handle,out.data(),size,FILE_NAME_NORMALIZED|VOLUME_NAME_DOS);
    if(!length || length>=size) throw FrontendError("E401","cannot canonicalize source");
    out.resize(length);
    if(out.substr(0,8)==L"\\\\?\\UNC\\") out=L"\\\\"+out.substr(8);
    else if(out.substr(0,4)==L"\\\\?\\") out=out.substr(4);
    return out;
}
inline bool same_path(const std::wstring& a,const std::wstring& b) {
    return CompareStringOrdinal(a.c_str(),static_cast<int>(a.size()),b.c_str(),static_cast<int>(b.size()),TRUE)==CSTR_EQUAL;
}
inline std::string display_path(const std::wstring& path) {
    auto absolute=full_path(path);
    const auto size=GetCurrentDirectoryW(0,nullptr);
    if(!size) return narrow(absolute);
    std::wstring cwd(size,L'\0');const auto length=GetCurrentDirectoryW(size,cwd.data());
    if(!length || length>=size) return narrow(absolute);
    cwd.resize(length);
    const auto parts=[](const std::wstring& value) {
        std::vector<std::wstring> result;
        std::size_t begin=0;
        for(std::size_t i=0;i<=value.size();++i) if(i==value.size() || value[i]==L'\\' || value[i]==L'/') {
            result.push_back(value.substr(begin,i-begin));begin=i+1;
        }
        return result;
    };
    const auto a=parts(absolute),b=parts(cwd);
    std::size_t common=0;
    while(common<a.size() && common<b.size() && same_path(a[common],b[common])) ++common;
    if(common && !(absolute.substr(0,2)==L"\\\\" && common<4)) {
        std::wstring relative;
        for(std::size_t i=common;i<b.size();++i) if(!b[i].empty()) relative+=L"../";
        for(std::size_t i=common;i<a.size();++i) {if(i>common) relative+=L'/';relative+=a[i];}
        absolute=relative.empty()?L".":relative;
    }
    std::replace(absolute.begin(),absolute.end(),L'\\',L'/');return narrow(absolute);
}
}
