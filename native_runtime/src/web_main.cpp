#include <httplib.h>
#include "zzy_native/prepare.hpp"
#include "zzy_native/web_contracts.hpp"
#include <chrono>
#include <condition_variable>
#include <iostream>

namespace {
using namespace zzy;
using namespace zzy::web;
using namespace std::chrono_literals;
using Clock=std::chrono::steady_clock;
constexpr std::size_t payload_limit=65536,metadata_limit=16384;
std::atomic<bool> stopping{false};
std::mutex log_mutex;

BOOL WINAPI console_stop(DWORD event) {
    if(event!=CTRL_C_EVENT && event!=CTRL_BREAK_EVENT) return FALSE;
    stopping.store(true);
    return TRUE;
}
void log_error(const std::string& message) {
    const std::lock_guard<std::mutex> guard(log_mutex);
    std::cerr<<message<<std::flush;
}
void reply(httplib::Response& response,int status,std::string body,const char* mime="application/json") {
    response.status=status;
    response.set_content(std::move(body),mime);
}
void fail(httplib::Response& response,int status,std::string_view code,const Violation* violation=nullptr) {
    std::string body="{\"error\":{\"code\":"+quote(code);
    if(violation) body+=",\"path\":"+quote(violation->path)+",\"reason\":"+quote(violation->reason);
    reply(response,status,body+"}}");
}
std::string read_small(const std::string& path,std::size_t bound) {
    FileHandle file(CreateFileW(extended_path(widen(path)).c_str(),GENERIC_READ,FILE_SHARE_READ,
        nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr));
    if(!file || GetFileType(file.get())!=FILE_TYPE_DISK) config_error("cannot open configuration or page");
    std::string result(bound+1,'\0');
    DWORD count=0;
    if(!ReadFile(file.get(),result.data(),static_cast<DWORD>(result.size()),&count,nullptr)) config_error("cannot read configuration or page");
    if(count>bound) config_error("configuration or page exceeds 65536 bytes");
    result.resize(count);
    try {(void)decode_utf8(result);}catch(const std::invalid_argument&) {config_error("configuration or page must be UTF-8");}
    return result;
}
int integer_option(const std::string& value,int minimum,int maximum) {
    int out=0;
    const auto parsed=std::from_chars(value.data(),value.data()+value.size(),out);
    if(parsed.ec!=std::errc{} || parsed.ptr!=value.data()+value.size() || out<minimum || out>maximum) config_error("invalid numeric option");
    return out;
}
struct WebOptions {
    std::string source,page,contracts;
    std::map<RouteKey,std::string> routes;
    int port=8000,workers=4;
    std::chrono::milliseconds timeout=5000ms;
    bool shared=false,describe=false;
};
WebOptions options(int argc,wchar_t** args) {
    WebOptions out;
    out.source=narrow(args[1]);
    std::set<std::string> seen;
    for(int i=2;i<argc;++i) {
        const auto key=narrow(args[i]);
        const auto next=[&]() {
            if(++i>=argc) config_error("missing value for "+key);
            return narrow(args[i]);
        };
        if(key!="--route" && !seen.insert(key).second) config_error("duplicate option: "+key);
        if(key=="--route") {
            auto method=next(),path=next(),function=next();
            if((method!="GET" && method!="POST") || path.substr(0,5)!="/api/" || path.size()<=5 ||
                path.find_first_of("?#{} \r\n\t")!=std::string::npos) config_error("invalid fixed route");
            if(!out.routes.emplace(RouteKey{std::move(method),std::move(path)},std::move(function)).second) config_error("duplicate route");
            if(out.routes.size()>256) resource_error("contract_routes");
        } else if(key=="--page") out.page=next();
        else if(key=="--contracts") out.contracts=next();
        else if(key=="--port") out.port=integer_option(next(),0,65535);
        else if(key=="--workers") out.workers=integer_option(next(),1,16);
        else if(key=="--timeout-ms") out.timeout=std::chrono::milliseconds(integer_option(next(),1,60000));
        else if(key=="--shared") out.shared=true;
        else if(key=="--openapi") out.describe=true;
        else config_error("unknown option: "+key);
    }
    if(out.routes.empty()) config_error("at least one route is required");
    if(out.describe && out.contracts.empty()) config_error("--openapi requires --contracts");
    return out;
}
Routes resolve_routes(const ProgramData& program,const WebOptions& config) {
    Routes out;
    for(const auto& [route,name]:config.routes) {
        NodeId handler=no_node;
        for(auto id:program.nodes.at(program.root).children) {
            const auto& node=program.nodes.at(id);
            if(node.kind=="function" && node.children.size()==2 && spelling(node.token)==name) {handler=id;break;}
        }
        if(handler==no_node) config_error("route requires a single-parameter top-level function: "+name);
        out.emplace(route,Route{handler,no_node,{}});
    }
    return out;
}

enum class CancelReason { none, timeout, disconnect, shutdown };
// The interpreter stays on the HTTP worker, which holds its slot through cleanup.
class Deadline {
    std::atomic<bool>& cancelled;
    const Clock::time_point end;
    std::function<bool()> disconnected;
    std::mutex mutex;
    std::condition_variable changed;
    bool finished=false;
    std::atomic<CancelReason> why{CancelReason::none};
    std::thread watcher;

    void cancel(CancelReason reason) {
        auto expected=CancelReason::none;
        why.compare_exchange_strong(expected,reason);
        cancelled.store(true);
    }
    void run() {
        std::unique_lock<std::mutex> lock(mutex);
        while(!finished) {
            if(stopping.load()) {cancel(CancelReason::shutdown);return;}
            if(Clock::now()>=end) {cancel(CancelReason::timeout);return;}
            if(disconnected && disconnected()) {cancel(CancelReason::disconnect);return;}
            changed.wait_until(lock,std::min(end,Clock::now()+10ms),[this]{return finished;});
        }
    }
public:
    Deadline(std::atomic<bool>& flag,std::chrono::milliseconds timeout,std::function<bool()> check={})
        :cancelled(flag),end(Clock::now()+timeout),disconnected(std::move(check)),watcher([this]{run();}) {}
    ~Deadline() {
        {const std::lock_guard<std::mutex> lock(mutex);finished=true;}
        changed.notify_one();
        watcher.join();
    }
    CancelReason reason() {
        if(stopping.load()) cancel(CancelReason::shutdown);
        else if(Clock::now()>=end) cancel(CancelReason::timeout);
        return why.load();
    }
};
std::string ascii_lower(std::string value) {
    for(auto& c:value) if(c>='A' && c<='Z') c=static_cast<char>(c-'A'+'a');
    return value;
}
std::string header_token(const httplib::Request& request,const std::string& key) {
    auto value=ascii_lower(request.get_header_value(key));
    const auto first=value.find_first_not_of(" \t");
    if(first==std::string::npos) return {};
    return value.substr(first,value.find_last_not_of(" \t")-first+1);
}
std::string latin1(std::string_view bytes) {
    std::string result;
    for(unsigned char byte:bytes) append_utf8(result,byte);
    return result;
}
std::string query_utf8(const std::string& input) {
    const auto bytes=httplib::decode_query_component(input);
    std::string result;
    for(std::size_t i=0;i<bytes.size();) {
        const auto start=i;
        try {append_utf8(result,utf8_next(bytes,i));}
        catch(const std::invalid_argument&) {
            const auto first=static_cast<unsigned char>(bytes[start]);
            i=start+1;
            const std::size_t width=first>=0xc2 && first<=0xdf?2:first>=0xe0 && first<=0xef?3:first>=0xf0 && first<=0xf4?4:1;
            while(i<bytes.size() && i-start<width) {
                const auto next=static_cast<unsigned char>(bytes[i]);
                if(next<0x80 || next>0xbf || (i==start+1 &&
                    ((first==0xe0 && next<0xa0) || (first==0xed && next>0x9f) ||
                     (first==0xf0 && next<0x90) || (first==0xf4 && next>0x8f)))) break;
                ++i;
            }
            append_utf8(result,0xfffd);
        }
    }
    return result;
}
std::string_view raw_query(const httplib::Request& request) {
    const auto position=request.target.find('?');
    return position==std::string::npos?std::string_view{}:std::string_view(request.target).substr(position+1);
}
Value request_value(ExecutionContext& c,const httplib::Request& request,const Value& body) {
    const auto result=WebRuntime::map(c);
    using Bridge=WebRuntime;
    Bridge::put(c,result,"method",Bridge::string(c,request.method));
    Bridge::put(c,result,"path",Bridge::string(c,request.path));
    const auto pair=[&](const std::string& key,const std::string& value) {
        return Bridge::array(c,{Bridge::string(c,key),Bridge::string(c,value)});
    };
    auto query=raw_query(request);
    std::vector<Value> pairs;
    Lease scratch(c.heap.state,{});
    while(!query.empty()) {
        const auto end=query.find('&');
        const auto item=query.substr(0,end);
        const auto split=item.find('=');
        if(!item.empty()) {
            scratch.grow({0,1,0},no_node);
            pairs.push_back(pair(query_utf8(std::string(item.substr(0,split))),
                split==std::string_view::npos?"":query_utf8(std::string(item.substr(split+1)))));
        }
        if(end==std::string_view::npos) break;
        query.remove_prefix(end+1);
    }
    Bridge::put(c,result,"query",Bridge::array(c,pairs));
    pairs.clear();
    for(const auto& [key,value]:request.headers) {
        scratch.grow({0,1,0},no_node);
        pairs.push_back(pair(latin1(ascii_lower(key)),latin1(value)));
    }
    Bridge::put(c,result,"headers",Bridge::array(c,pairs));
    Bridge::put(c,result,"body",body);
    return result;
}
int status_value(ExecutionContext& context,const Value& value) {
    if(!value) return 0;
    const auto& n=WebRuntime::node(context,value);
    if(n.kind!="Int" || n.integer<BigInt(200) || n.integer>BigInt(599)) return 0;
    const auto status=std::stoi(n.integer.decimal());
    return response_status(status)?status:0;
}
class Server final : public httplib::Server {
    struct Wire {
        httplib::Stream& stream;
        std::atomic<int>& slots;
        bool admitted=false,reading_body=false;
        ~Wire() {if(admitted) --slots;}
    };
    inline static thread_local Wire* wire=nullptr;
    const Program& program;
    const Routes& routes;
    const Contracts& contracts;
    const ExecutionContext* shared;
    const WebOptions& config;
    std::optional<std::string> page,openapi;
    std::atomic<int> slots{0};

    bool process_and_close_socket(socket_t socket) override {
        const auto close_socket=httplib::detail::scope_exit([&]{httplib::detail::drain_and_close_socket(socket);});
        const auto seconds=static_cast<time_t>(config.timeout.count()/1000);
        const auto micros=static_cast<time_t>((config.timeout.count()%1000)*1000);
        httplib::detail::SocketStream stream(socket,seconds,micros,seconds,micros);
        stream.set_read_interrupt([] {return stopping.load();});
        Wire active{stream,slots};
        wire=&active;
        const auto reset=httplib::detail::scope_exit([]{wire=nullptr;});
        bool closed=false;
        return serve_guarded([&] {
            return process_request(stream,"",0,"127.0.0.1",0,true,closed,
                [](httplib::Request& request) {request.ranges.clear();});
        });
    }
    bool admit() {
        if(stopping.load()) return false;
        auto count=slots.load();
        do {if(count>=config.workers) return false;} while(!slots.compare_exchange_weak(count,count+1));
        wire->admitted=true;
        return true;
    }
    httplib::Server::HandlerResponse before_read(const httplib::Request& req,httplib::Response& res) {
        using Result=httplib::Server::HandlerResponse;
        const auto reject=[&](int status,const char* code) {
            fail(res,status,code);
            return Result::Handled;
        };
        if(!admit()) return reject(503,"busy");
        std::size_t bytes=raw_query(req).size();
        for(const auto& [key,value]:req.headers) bytes+=key.size()+value.size();
        if(bytes>metadata_limit) return reject(431,"metadata_too_large");
        const auto encoding=header_token(req,"Content-Encoding");
        if((req.has_header("Content-Encoding") && encoding!="identity") ||
            req.get_header_value_count("Content-Encoding")>1) return reject(415,"unsupported_encoding");
        const auto length=req.get_header_value_u64("Content-Length",0);
        if(length>payload_limit) return reject(413,"body_too_large");
        const bool has_body=length || req.has_header("Transfer-Encoding");
        const std::string* static_body=nullptr;
        const char* mime="application/json";
        if(req.path=="/" && page) {static_body=&*page;mime="text/html; charset=utf-8";}
        if(req.path=="/openapi.json" && openapi) static_body=&*openapi;
        if(static_body) {
            if(req.method!="GET" && req.method!="HEAD") return reject(405,"method_not_allowed");
            if(has_body) return reject(400,"unexpected_body");
            reply(res,200,*static_body,mime);
            return Result::Handled;
        }
        if(!routes.count({req.method,req.path})) {
            if(routes.count({"GET",req.path}) || routes.count({"POST",req.path})) return reject(405,"method_not_allowed");
            return reject(404,"not_found");
        }
        if(req.method=="POST") {
            const auto type=header_token(req,"Content-Type");
            if(req.get_header_value_count("Content-Type")!=1 ||
                (type!="application/json" && type!="application/json; charset=utf-8")) return reject(415,"unsupported_media_type");
        }
        wire->reading_body=has_body;
        wire->stream.set_max_timeout(static_cast<time_t>(config.timeout.count()));
        return Result::Unhandled;
    }
    void handle(const httplib::Request& req,httplib::Response& res) {
        wire->reading_body=false;
        if(req.method=="GET" && !req.body.empty()) {fail(res,400,"unexpected_body");return;}
        const auto& route=routes.at({req.method,req.path});
        std::atomic<bool> cancel{false};
        Deadline deadline(cancel,config.timeout,req.is_connection_closed);
        bool valid_input=false;
        try {
            std::ostringstream output,errors;
            ExecutionContext ctx(program,WebRuntime::policy(),cancel,output,errors);
            WebRuntime::begin(ctx);
            auto body=req.method=="GET"?WebRuntime::null(ctx):WebRuntime::parse(ctx,req.body);
            if(route.request!=no_node) body=contracts.convert(ctx,route.request,body);
            auto request=request_value(ctx,req,body);
            valid_input=true;
            if(shared) WebRuntime::attach(ctx,*shared);
            else WebRuntime::initialize(ctx);
            auto response=WebRuntime::invoke(ctx,route.function,request);
            const auto& n=WebRuntime::node(ctx,response);
            if((n.kind!="Map" && n.kind!="Shape") || n.names.size()!=2) throw json_detail::Invalid("invalid Response envelope");
            const auto status=status_value(ctx,WebRuntime::get(ctx,response,"status"));
            auto result=WebRuntime::get(ctx,response,"body");
            if(!status || !result) throw json_detail::Invalid("invalid Response fields");
            const auto contract=route.responses.find(status);
            if(contract!=route.responses.end()) result=contracts.convert(ctx,contract->second,result);
            reply(res,status,WebRuntime::encode(ctx,result));
        } catch(const Violation& error) {
            fail(res,valid_input?500:422,valid_input?"contract_response":"contract_input",&error);
        } catch(const json_detail::Invalid&) {
            fail(res,valid_input?500:400,valid_input?"invalid_response":"invalid_json");
        } catch(const std::invalid_argument&) {
            fail(res,valid_input?500:400,valid_input?"internal_error":"invalid_json");
        } catch(const RuntimeError& error) {
            if(error.code=="E211") fail(res,valid_input?503:413,"resource_limit");
            else {log_error(runtime_diagnostic(program.data(),error,false));fail(res,500,"zzy_error");}
        } catch(const Cancelled&) {
            fail(res,504,"request_timeout");
        } catch(const std::exception&) {
            fail(res,500,"internal_error");
        }
        switch(deadline.reason()) {
            case CancelReason::timeout:fail(res,504,"request_timeout");break;
            case CancelReason::disconnect:fail(res,400,"disconnected");break;
            case CancelReason::shutdown:fail(res,503,"busy");break;
            default:break;
        }
    }
public:
    Server(const Program& p,const Routes& r,const Contracts& c,const ExecutionContext* snapshot,const WebOptions& options,
        std::optional<std::string> landing,std::optional<std::string> document)
        :program(p),routes(r),contracts(c),shared(snapshot),config(options),page(std::move(landing)),openapi(std::move(document)) {
        // A fixed transport reserve parses headers to answer HTTP 503.
        // Above the connection queue bound the HTTP library drops sockets.
        const auto transport=static_cast<std::size_t>(config.workers)+4;
        new_task_queue=[transport]{return new httplib::ThreadPool(transport,0,transport);};
        set_default_headers({{"Connection","close"}});
        set_payload_max_length(payload_limit);
        set_read_timeout(config.timeout);
        set_idle_interval(50ms);
        set_pre_routing_handler([this](const auto& req,auto& res){return before_read(req,res);});
        set_error_handler([](const httplib::Request&,httplib::Response& res) {
            if(!res.body.empty()) return;
            if(res.status==413) fail(res,413,"body_too_large");
            else if(res.status==414) fail(res,431,"metadata_too_large");
            else if(wire && wire->reading_body && wire->stream.get_error()==httplib::Error::Timeout) fail(res,408,"body_timeout");
            else if(wire && wire->reading_body && wire->stream.get_error()==httplib::Error::ConnectionClosed) fail(res,400,"disconnected");
            else fail(res,res.status,"invalid_request");
        });
        set_exception_handler([](const httplib::Request&,httplib::Response& res,std::exception_ptr) {fail(res,500,"internal_error");});
        Get(".*",[this](const auto& req,auto& res){handle(req,res);});
        Post(".*",[this](const auto& req,auto& res){handle(req,res);});
    }
};
int run(const WebOptions& config) {
    auto policy=WebRuntime::policy();
    FrontendMeter meter(policy,stopping);
    const auto program=prepare(widen(config.source),meter);
    auto routes=resolve_routes(program.data(),config);
    Contracts contracts(program.data(),stopping);
    std::optional<std::string> document;
    if(!config.contracts.empty()) {
        std::ostringstream output,errors;
        ExecutionContext conversion(program,policy,stopping,output,errors);
        WebRuntime::begin(conversion);
        const auto input=read_small(config.contracts,payload_limit);
        try {contracts.bind(conversion,WebRuntime::parse(conversion,input),routes);}
        catch(const json_detail::Invalid&) {config_error("contracts must be strict JSON");}
        document=contracts.openapi(routes);
    }
    if(config.describe) {std::cout<<*document<<'\n';return 0;}
    std::optional<std::string> page;
    if(!config.page.empty()) page=read_small(config.page,payload_limit);
    std::atomic<bool> init_cancel{false};
    std::ostringstream output,errors;
    std::unique_ptr<ExecutionContext> shared;
    if(config.shared) {
        Deadline deadline(init_cancel,config.timeout);
        shared=std::make_unique<ExecutionContext>(program,policy,init_cancel,output,errors);
        try {
            WebRuntime::begin(*shared);
            WebRuntime::initialize(*shared);
            WebRuntime::freeze(*shared);
            if(deadline.reason()!=CancelReason::none) throw Cancelled{};
        } catch(const RuntimeError& error) {
            log_error(runtime_diagnostic(program.data(),error,false));
            return 2;
        } catch(const Cancelled&) {
            if(stopping.load()) throw;
            config_error("shared initialization timed out");
        }
    }
    Server server(program,routes,contracts,shared.get(),config,std::move(page),std::move(document));
    int port=config.port;
    if(port==0) port=server.bind_to_any_port("127.0.0.1");
    else if(!server.bind_to_port("127.0.0.1",port)) port=-1;
    if(port<=0) config_error("cannot bind localhost listener");
    server.set_start_handler([port]{std::cout<<"ZZY native web listening on http://127.0.0.1:"<<port<<'\n'<<std::flush;});
    std::atomic<bool> ended{false};
    std::thread stopper([&] {
        while(!ended.load()) {
            if(stopping.load()) {server.stop();return;}
            std::this_thread::sleep_for(10ms);
        }
    });
    const auto join=httplib::detail::scope_exit([&]{ended.store(true);stopper.join();});
    return server.listen_after_bind() || stopping.load()?0:2;
}
}

int wmain(int argc,wchar_t** argv) {
    try {
        zzy::configure_streams();
        if(argc==1 || (argc==2 && std::wstring_view(argv[1])==L"--help")) {
            std::cout<<"ZZY native web (cpp-httplib "<<CPPHTTPLIB_VERSION<<")\n"
                "zzy-native-web MODULE --route GET|POST /api/PATH FUNCTION [--route ...]\n"
                "    [--port PORT] [--workers COUNT] [--timeout-ms MS] [--page FILE]\n"
                "    [--shared] [--contracts FILE] [--openapi]\n";
            return 0;
        }
        if(!SetConsoleCtrlHandler(console_stop,TRUE)) config_error("cannot register console cancellation");
        return run(options(argc,argv));
    } catch(const Cancelled&) {return 130;}
    catch(const FrontendError& error) {std::cerr<<render_frontend(error,false);return 2;}
    catch(const RuntimeError& error) {std::cerr<<render_frontend(FrontendError(error.code,error.what()),false);return 2;}
    catch(const std::exception&) {std::cerr<<"E401 native Web host failed\n";return 2;}
}
