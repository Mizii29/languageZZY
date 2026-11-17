from pathlib import Path
import sys, unicodedata, hashlib, json
ROOT=Path(__file__).resolve().parents[2]
def ranges(predicate):
    result=[]
    for cp in range(0x110000):
        if predicate(chr(cp)):
            if result and result[-1][1]==cp-1: result[-1][1]=cp
            else: result.append([cp,cp])
    return result
if __name__=='__main__':
    if sys.version_info[:3] != (3,12,14) or unicodedata.unidata_version!='15.0.0':
        raise SystemExit('Requires frozen CPython 3.12.14 / Unicode 15.0.0')
    tables={'identifier_start':ranges(str.isidentifier),'identifier_continue':ranges(lambda c:('a'+c).isidentifier()),'space':ranges(str.isspace)}
    data='#pragma once\n#include <cstdint>\n#include <cstddef>\nnamespace zzy::unicode {\nstruct Range {char32_t first,last;};\ninline constexpr const char* version="15.0.0";\n'
    for name,items in tables.items():
        data+='inline constexpr Range '+name+'[]={\n'+''.join('    {0x%x,0x%x},\n'%tuple(x) for x in items)+'};\n'
    data+='template<std::size_t N> inline bool contains(const Range (&ranges)[N],char32_t c) {\n    std::size_t lo=0,hi=N;\n    while(lo<hi) {const auto mid=lo+(hi-lo)/2; if(c<ranges[mid].first) hi=mid; else if(c>ranges[mid].last) lo=mid+1; else return true;}\n    return false;\n}\n}\n'
    (ROOT/'native_runtime/include/zzy_native/unicode_tables.hpp').write_text(data,encoding='utf-8',newline='\n')
    metadata={'python':sys.version,'unicode':unicodedata.unidata_version,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'tables_sha256':hashlib.sha256(data.encode()).hexdigest(),'range_counts':{k:len(v) for k,v in tables.items()},'purpose':'Offline implementation data, not a runtime dependency or golden oracle'}
    (ROOT/'native_runtime/tests/unicode-tables.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
