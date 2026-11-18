#pragma once
#include <string_view>
namespace zzy {
// Execution subset of the frozen ABI. Empty type accepts any ZZY value.
// Optional host modules remain outside this table.
struct CoreHost {std::string_view name;std::size_t arity;std::string_view types[3];};
inline constexpr CoreHost core_hosts[]={
    {"len",1,{"Array|String|Map|Range"}},{"str",1,{"Int|Float|Bool|Null|String|Quantity"}},
    {"range",3,{"Int","Int","Int"}},{"wake",1,{"Lazy"}},
    {"io.print",1,{""}},{"io.input",1,{"String"}},
    {"io.read_text",1,{"String"}},{"io.write_text",2,{"String","String"}},
    {"io.write_atomic",2,{"String","String"}},{"io.replace_file",2,{"String","String"}},
    {"array.copy",1,{"Array"}},{"array.push",2,{"Array",""}},{"array.pop",1,{"Array"}},
    {"array.sum",1,{"Array"}},{"array.stats",1,{"Array"}},{"array.sorted",1,{"Array"}},
    {"array.map",2,{"Array","Function"}},{"array.filter",2,{"Array","Function"}},
    {"data.map",0,{""}},{"data.kind",1,{""}},{"data.has",2,{"Map","String"}},
    {"data.get",2,{"Map","String"}},{"data.set",3,{"Map","String",""}},{"data.keys",1,{"Map"}},
    {"data.parse",1,{"String"}},{"data.stringify",1,{""}},
#ifdef ZZY_NATIVE_SQLITE
    {"db.transaction",2,{"String","Function"}},{"db.query",2,{"String","Array"}},
#endif
    {"text.trim",1,{"String"}},{"text.contains",2,{"String","String"}},
    {"text.join",2,{"Array","String"}},{"text.split",2,{"String","String"}},
    {"text.replace",3,{"String","String","String"}},{"text.safe_int",1,{"String"}},
    {"math.abs",1,{"Int|Float"}},{"unit.make",2,{"Int|Float","String"}},
    {"unit.format",2,{"Quantity","String"}}
};
inline bool core_host_accepts(std::string_view expected,std::string_view kind) {
    if(expected.empty()) return true;
    while(true) {
        const auto at=expected.find('|');if(expected.substr(0,at)==kind) return true;
        if(at==std::string_view::npos) return false;expected.remove_prefix(at+1);
    }
}
}
