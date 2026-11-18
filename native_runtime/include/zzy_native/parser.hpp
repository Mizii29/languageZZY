#pragma once
#include "ast.hpp"
namespace zzy {
class Parser {
    const std::vector<Token>& tokens;
    FrontendMeter& meter;
    AstBuilder& ast;
    std::size_t index=0,nesting=0;
    const Token& current() const {return tokens.at(index);}
    bool is(const std::string& k) const {return current().kind==k;}
    Token advance() {auto token=current();if(token.kind!="EOF") ++index;meter.safe_point();return token;}
    bool accept(const std::string& k) {if(!is(k)) return false;advance();return true;}
    [[noreturn]] void error(const Token& t,const std::string& message) const {fail_at(t,"E103",message);}
    Token expect(const std::string& k,const std::string& description) {
        if(!is(k)) error(current(),"expected "+description+"; got "+(is("EOF")?"EOF":spelling(current())));
        return advance();
    }
    struct Nest {
        Parser& p;
        Nest(Parser& parser,const Token& t):p(parser) {
            frontend_stack_point();p.meter.check("syntax_depth",p.nesting+1,display_path(t.source->path),token_span(t));++p.nesting;
        }
        ~Nest() {--p.nesting;}
    };
    NodeId make(const std::string& kind,const Token& t,std::vector<NodeId> children={},const std::string& text="",
                Annotation a={},bool flag=false,std::optional<Token> auxiliary={},std::vector<std::string> labels={},
                std::optional<std::size_t> end={}) {
        return ast.add(kind,t,std::move(children),text,std::move(a),flag,std::move(auxiliary),std::move(labels),end);
    }
    Annotation annotation() {
        if(current().kind.rfind("TYPE_",0)==0) return {{advance()},true};
        if(!is("IDENT")) error(current(),"expected type annotation");
        Annotation a{{advance()},false};
        while(accept("DOT")) a.names.push_back(expect("IDENT","type name"));
        return a;
    }
    NodeId nested(const Token& opening) {Nest guard(*this,opening);return expression();}
    std::vector<NodeId> arguments(const Token& opening,const std::string& ending) {
        std::vector<NodeId> args;
        if(!is(ending)) do {args.push_back(nested(opening));} while(accept("COMMA") && !is(ending));
        return args;
    }
    std::pair<std::vector<NodeId>,Token> initializers() {
        const auto opening=expect("LEFT_BRACE","{");std::vector<NodeId> fields;
        if(!is("RIGHT_BRACE")) {
            do {
                const auto name=expect("IDENT","field name");expect("COLON",":");
                fields.push_back(make("initializer",name,{nested(opening)},spelling(name)));
            } while(accept("COMMA") && !is("RIGHT_BRACE"));
        }
        return {std::move(fields),expect("RIGHT_BRACE","}")};
    }
    NodeId function(bool named) {
        const auto keyword=expect("FUNCTION","(addnew)");const auto name=named?expect("IDENT","function name"):keyword;
        expect("LEFT_PAREN","(");std::vector<NodeId> children;
        if(!is("RIGHT_PAREN")) do {
            const auto parameter=expect("IDENT","parameter name");const auto a=accept("COLON")?annotation():Annotation{};
            children.push_back(make("parameter",parameter,{},"",a));
        } while(accept("COMMA") && !is("RIGHT_PAREN"));
        expect("RIGHT_PAREN",")");const auto a=named && accept("ARROW")?annotation():Annotation{};
        if(named) children.push_back(block());
        else {expect("FAT_ARROW","=>");children.push_back(nested(keyword));}
        return make(named?"function":"lambda",name,std::move(children),"",a);
    }
    NodeId pattern() {
        const auto token=current();
        if(accept("WILDCARD")) return make("wildcard",token);
        if(is("SUCCESS") || is("FAILURE")) {
            const auto tag=advance();expect("LEFT_PAREN","(");const auto name=expect("IDENT","payload binding");
            expect("RIGHT_PAREN",")");return make("payload_pattern",name,{},tag.kind);
        }
        std::optional<Token> sign;
        if(is("PLUS") || is("MINUS")) sign=advance();
        const std::set<std::string> scalars={"INTEGER","FLOAT","STRING","RAW","TRUE","FALSE","NULL"};
        if((sign && !is("INTEGER") && !is("FLOAT")) || (!sign && !scalars.count(current().kind)))
            error(current(),"expected scalar or Result pattern");
        auto value=primary();
        if(ast.nodes[value].kind=="quantity") error(ast.nodes[value].token,"Quantity constant pattern is unsupported");
        if(sign) value=make("unary",*sign,{value});
        return make("constant_pattern",token,{value});
    }
    NodeId query(NodeId source,const Token& token) {
        expect("LEFT_BRACE","query {");std::vector<NodeId> children{source};
        for(const auto& kind:{"KEEP","ORDER","TAKE","YIELD"}) {
            if(!is(kind)) {if(std::string(kind)=="YIELD") error(current(),"query requires one final yield");continue;}
            const auto keyword=advance();expect("COLON",":");const auto value=nested(keyword);
            const auto direction=std::string(kind)=="ORDER" && (is("ASC") || is("DESC"))?advance().kind:"ASC";
            expect("SEMICOLON",";");std::string lower=kind;for(auto& c:lower) c=static_cast<char>(c-'A'+'a');
            children.push_back(make(lower,keyword,{value},direction));
        }
        const auto closing=expect("RIGHT_BRACE","query }");
        return make("query",token,std::move(children),"",{},false,{}, {},closing.end);
    }
    static int precedence(const std::string& kind) {
        static const std::map<std::string,int> values={{"OR",20},{"AND",30},{"EQUAL",40},{"NOT_EQUAL",40},
            {"LESS",45},{"LESS_EQUAL",45},{"GREATER",45},{"GREATER_EQUAL",45},{"INTERVAL",50},{"PLUS",60},
            {"MINUS",60},{"MULTIPLY",70},{"DIVIDE",70},{"FLOOR_DIVIDE",70},{"REMAINDER",70}};
        const auto it=values.find(kind);return it==values.end()?-1:it->second;
    }
    static bool comparison(const std::string& kind) {return precedence(kind)==40 || precedence(kind)==45;}
    NodeId expression(int minimum=0) {
        frontend_stack_point();NodeId left;
        if(is("PLUS") || is("MINUS") || is("NOT")) {
            const auto token=advance();Nest guard(*this,token);
            left=make("unary",token,{expression(token.kind=="NOT"?35:80)});
        } else left=postfix();
        while(true) {
            if(is("QUERY") && minimum<=15) {const auto t=advance();left=query(left,t);continue;}
            if(is("PIPE") && minimum<=0) {
                const auto t=advance();const auto fn=postfix(false);const auto opening=expect("LEFT_PAREN","pipeline (");
                auto args=arguments(opening,"RIGHT_PAREN");args.insert(args.begin(),fn);const auto closing=expect("RIGHT_PAREN",")");
                const auto call=make("call",opening,std::move(args),"",{},false,{}, {},closing.end);
                left=make("pipe",t,{left,call});continue;
            }
            if(is("SEND") && minimum<=5) {
                const auto t=advance();if(ast.nodes[left].kind=="send") error(t,"only one ungrouped send is allowed");
                const auto right=expression(6);left=make("send",t,{left,right});continue;
            }
            if(is("WITH") && minimum<=10) {
                const auto t=advance();auto fields=initializers();fields.first.insert(fields.first.begin(),left);
                left=make("with",t,std::move(fields.first),"",{},false,{}, {},fields.second.end);continue;
            }
            const auto p=precedence(current().kind);if(p<minimum) break;
            const auto op=advance();const auto right=expression(p+1);
            if(comparison(op.kind)) for(auto id:{left,right})
                if(ast.nodes[id].kind=="binary" && comparison(ast.nodes[id].token.kind)) error(op,"comparison chaining requires grouping");
            if(op.kind=="INTERVAL" && ast.nodes[left].kind=="binary" && ast.nodes[left].token.kind=="INTERVAL")
                error(op,"intervals cannot be chained");
            left=make(op.kind=="PLUS"?"add":"binary",op,{left,right});
        }
        return left;
    }
    NodeId postfix(bool calls=true) {
        auto value=primary();
        while(is("DOT") || is("LEFT_PAREN") || is("LEFT_BRACKET") || is("DOUBLE_COLON") || is("QUESTION")) {
            if(!calls && (is("LEFT_PAREN") || is("QUESTION"))) break;
            if(is("QUESTION")) {const auto t=advance();value=make("propagate",t,{value});continue;}
            if(accept("DOT")) {const auto name=expect("IDENT","field name");value=make("field",name,{value},spelling(name));}
            else if(accept("DOUBLE_COLON")) {
                auto base=value;while(ast.nodes[base].kind=="field") base=ast.nodes[base].children[0];
                if(ast.nodes[base].kind!="name") error(ast.nodes[value].token,"constructor requires qualified name");
                // Node storage may reallocate while reading fields: keep a token copy.
                const auto token=ast.nodes[value].token;auto fields=initializers();fields.first.insert(fields.first.begin(),value);
                value=make("construct",token,std::move(fields.first),"",{},false,{}, {},fields.second.end);
            } else if(is("LEFT_BRACKET")) {
                const auto opening=advance();const auto subscript=nested(opening);const auto close=expect("RIGHT_BRACKET","]");
                value=make("index",opening,{value,subscript},"",{},false,{}, {},close.end);
            } else {
                const auto opening=advance();auto args=arguments(opening,"RIGHT_PAREN");args.insert(args.begin(),value);
                const auto close=expect("RIGHT_PAREN",")");value=make("call",opening,std::move(args),"",{},false,{}, {},close.end);
            }
        }
        return value;
    }
    NodeId primary() {
        if(is("FUNCTION")) return function(false);
        const auto token=advance();
        if(token.kind=="AT") return make("current",token);
        if(token.kind=="SUCCESS" || token.kind=="FAILURE" || token.kind=="LAZY") {
            const auto opening=expect("LEFT_PAREN","(");const auto value=nested(opening);const auto close=expect("RIGHT_PAREN",")");
            return make(token.kind=="LAZY"?"lazy":"result",token,{value},token.kind,{},false,{}, {},close.end);
        }
        if((token.kind=="INTEGER" || token.kind=="FLOAT") && accept("DOUBLE_COLON")) {
            const auto unit=expect("IDENT","unit name");return make("quantity",token,{},"",{},false,unit,{},unit.end);
        }
        const std::map<std::string,std::string> kinds={{"INTEGER","integer"},{"FLOAT","float"},{"STRING","string"},
            {"IDENT","name"},{"TRUE","bool"},{"FALSE","bool"},{"NULL","null"}};
        const auto it=kinds.find(token.kind);
        if(it!=kinds.end()) return make(it->second,token,{},token.kind=="STRING"?token.value.value():spelling(token),{},token.kind=="TRUE");
        if(token.kind=="RAW") {
            const auto string=expect("STRING","raw string");return make("string",token,{},string.value.value(),{},false,{}, {},string.end);
        }
        if(token.kind=="LEFT_PAREN") {
            const auto value=nested(token);const auto close=expect("RIGHT_PAREN",")");return make("group",token,{value},"",{},false,{}, {},close.end);
        }
        if(token.kind=="LEFT_BRACKET") {
            auto items=arguments(token,"RIGHT_BRACKET");const auto close=expect("RIGHT_BRACKET","]");return make("array",token,std::move(items),"",{},false,{}, {},close.end);
        }
        error(token,"expected expression");
    }
    NodeId block() {
        const auto opening=expect("LEFT_BRACE","{");Nest guard(*this,opening);std::vector<NodeId> children;
        while(!is("RIGHT_BRACE") && !is("EOF")) children.push_back(statement());
        const auto close=expect("RIGHT_BRACE","}");return make("block",opening,std::move(children),"",{},false,{}, {},close.end);
    }
    NodeId statement() {
        frontend_stack_point();
        if(accept("USE")) {
            const auto path=expect("STRING","module path string");expect("AS","(as)");const auto alias=expect("IDENT","module alias");expect("SEMICOLON",";");
            return make("use",alias,{},"",{},false,path);
        }
        if(is("ASSERT") || is("TRACE")) {const auto t=advance();const auto v=expression();expect("SEMICOLON",";");return make(t.kind=="ASSERT"?"assert":"trace",t,{v});}
        if(is("SPEC")) {const auto t=advance();const auto name=expect("STRING","spec name");return make("spec",t,{block()},name.value.value());}
        if(accept("MACHINE")) {
            const auto name=expect("IDENT","machine name");expect("LEFT_BRACE","{");std::vector<NodeId> edges;
            while(!is("RIGHT_BRACE") && !is("EOF")) {
                const auto start=expect("IDENT","source state");expect("STATE_EDGE","--");const auto event=expect("STRING","event");
                expect("STATE_ARROW","-->");const auto end=expect("IDENT","destination state");expect("SEMICOLON",";");
                edges.push_back(make("edge",event,{},"",{},false,{}, {spelling(start),event.value.value(),spelling(end)}));
            }
            const auto close=expect("RIGHT_BRACE","}");return make("machine",name,std::move(edges),"",{},false,{}, {},close.end);
        }
        if(is("MATCH")) {
            const auto t=advance();std::vector<NodeId> children{expression()};expect("LEFT_BRACE","{");
            while(!is("RIGHT_BRACE") && !is("EOF")) {
                const auto p=pattern();const auto pt=ast.nodes[p].token;expect("FAT_ARROW","=>");const auto b=block();children.push_back(make("arm",pt,{p,b}));
            }
            const auto close=expect("RIGHT_BRACE","}");if(children.size()==1) error(close,"match requires at least one arm");
            return make("match",t,std::move(children),"",{},false,{}, {},close.end);
        }
        if(is("FUNCTION") && tokens.at(index+1).kind=="IDENT") return function(true);
        if(is("RETURN")) {
            const auto t=advance();std::vector<NodeId> children;if(!is("SEMICOLON")) children.push_back(expression());expect("SEMICOLON",";");return make("return",t,std::move(children));
        }
        if(is("LEFT_BRACE")) return block();
        if(is("IMMUTABLE_DECL") || is("MUTABLE_DECL")) {
            const auto declaration=advance();const auto name=expect("IDENT","binding name");const auto a=accept("COLON")?annotation():Annotation{};
            expect("INIT",":=");const auto value=expression();expect("SEMICOLON",";");return make("binding",name,{value},"",a,declaration.kind=="MUTABLE_DECL");
        }
        if(accept("SHAPE")) {
            const auto name=expect("IDENT","shape name");expect("LEFT_BRACE","{");std::vector<NodeId> fields;
            while(!is("RIGHT_BRACE") && !is("EOF")) {
                const auto field=expect("IDENT","field name");const auto a=accept("COLON")?annotation():Annotation{};
                std::vector<NodeId> defaults;if(accept("INIT")) defaults.push_back(expression());expect("SEMICOLON",";");
                fields.push_back(make("definition_field",field,std::move(defaults),"",a));
            }
            const auto close=expect("RIGHT_BRACE","}");return make("shape",name,std::move(fields),"",{},false,{}, {},close.end);
        }
        if(is("IF")) {
            const auto t=advance();std::vector<NodeId> children;children.push_back(expression());children.push_back(block());
            while(accept("ELIF")) {children.push_back(expression());children.push_back(block());}
            if(accept("ELSE")) children.push_back(block());
            return make("if",t,std::move(children));
        }
        if(is("WHILE")) {const auto t=advance();const auto condition=expression();const auto body=block();return make("while",t,{condition,body});}
        if(accept("FOR")) {const auto name=expect("IDENT","loop binding");expect("IN","(in)");const auto value=expression();const auto body=block();return make("for",name,{value,body});}
        if(is("BREAK") || is("CONTINUE")) {const auto t=advance();expect("SEMICOLON",";");return make(t.kind=="BREAK"?"break":"continue",t);}
        const auto value=expression();const auto token=ast.nodes[value].token;
        if(accept("ASSIGN")) {
            auto base=value;while(ast.nodes[base].kind=="field" || ast.nodes[base].kind=="index") base=ast.nodes[base].children[0];
            if(ast.nodes[base].kind!="name") error(token,"assignment target must be a name, field or index");
            const auto right=expression();expect("SEMICOLON",";");return make("assignment",token,{value,right});
        }
        expect("SEMICOLON",";");return make("expression",token,{value});
    }
public:
    Parser(const std::vector<Token>& ts,FrontendMeter& m,AstBuilder& a):tokens(ts),meter(m),ast(a) {}
    NodeId parse() {
        const auto first=current();std::vector<NodeId> statements;
        while(!is("EOF")) statements.push_back(statement());
        return make("program",first,std::move(statements));
    }
};
}
