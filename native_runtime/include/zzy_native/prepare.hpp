#pragma once
#include "parser.hpp"
#include "resolver.hpp"
namespace zzy {
class Preparation {
    FrontendMeter& meter;
    SourceLoader loader;
    AstBuilder ast;
    ProgramData result;
    struct Visit {std::wstring path;NodeId root;bool active;};
    std::vector<Visit> visits;
    NodeId visit(const std::shared_ptr<const Source>& source,std::uint64_t depth,const std::optional<Token>& site={}) {
        frontend_stack_point();meter.safe_point();
        for(const auto& existing:visits) if(same_path(existing.path,source->path)) {
            if(existing.active) fail_at(*site,"E303","cyclic module import");
            return existing.root;
        }
        const auto index=visits.size();visits.push_back({source->path,no_node,true});
        const auto tokens=Lexer(source,meter).scan();const auto root=Parser(tokens,meter,ast).parse();
        visits[index].root=root;
        // Resolve this whole file before recursively preparing imports, as in
        // the formal frontend contract. This fixes first-error precedence.
        Resolver(ast.nodes,result,meter).resolve(root);
        ModulePlan module{root,source,{}};
        for(auto child:ast.nodes[root].children) {
            const auto& n=ast.nodes[child];
            if(n.kind=="function" || n.kind=="shape" || n.kind=="machine") module.exports.emplace(spelling(n.token),child);
        }
        // Recursive parsing can reallocate nodes: never keep AST references.
        const auto children=ast.nodes[root].children;
        for(auto child:children) if(ast.nodes[child].kind=="use") {
            const auto path_token=*ast.nodes[child].auxiliary;const auto path=*path_token.value;
            const auto dot=path.find_last_of('.');const auto slash=path.find_last_of("/\\");
            if(dot==std::string::npos || (slash!=std::string::npos && dot<slash) || path.substr(dot)!=".zzy")
                fail_at(path_token,"E303","module extension must be .zzy");
            const auto dependency_path=widen(path);
            const bool absolute=(dependency_path.size()>1 && dependency_path[1]==L':') ||
                (!dependency_path.empty() && (dependency_path[0]==L'\\' || dependency_path[0]==L'/'));
            const auto parent=source->path.substr(0,source->path.find_last_of(L"/\\")+1);
            std::shared_ptr<const Source> dependency;
            try {dependency=loader.load(absolute?dependency_path:parent+dependency_path,depth+1);}
            catch(const FrontendError& error) {fail_at(path_token,"E303",std::string("cannot read imported module: ")+error.what());}
            const auto dependency_root=visit(dependency,depth+1,path_token);result.imports.emplace(child,dependency_root);
        }
        visits[index].active=false;result.graph.push_back(std::move(module));return root;
    }
public:
    explicit Preparation(FrontendMeter& m):meter(m),loader(m),ast(m) {}
    Program load(const std::wstring& path) {
        result.root=visit(loader.load(path),1);result.nodes=std::move(ast.nodes);
        return Program(std::move(result));
    }
};
inline Program prepare(const std::wstring& path,FrontendMeter& meter) {return Preparation(meter).load(path);}
}
