#include "zzy_native/integer_dispatch.hpp"
#include "zzy_native/prepare.hpp"
#include <chrono>
#include <iostream>
#include <sstream>

namespace {
using Clock=std::chrono::steady_clock;
std::int64_t ns(Clock::time_point a,Clock::time_point b) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(b-a).count();
}
}

int wmain(int argc,wchar_t** argv) {
    if(argc!=4 && argc!=5) return 2;
    const std::wstring_view mode(argv[1]);
    if(mode!=L"ast" && mode!=L"mixed" && mode!=L"auto") return 2;
    const bool cancel_in_vm=argc==5 && std::wstring_view(argv[4])==L"--cancel-vm";
    if(argc==5 && (!cancel_in_vm || mode==L"ast")) return 2;
    std::optional<zzy::Program> program;
    std::ostringstream output,errors;
    try {
        const auto policy=zzy::load_policy(argv[3]);
        std::atomic<bool> cancel{false};
        zzy::FrontendMeter meter(policy,cancel);
        const auto start=Clock::now();
        program.emplace(zzy::prepare(argv[2],meter));
        const auto prepared=Clock::now();
        zzy::IntegerDispatch dispatch;
        zzy::ExecutionContext context(*program,policy,cancel,output,errors,true);
        const auto lowering_start=Clock::now();
        if(mode!=L"ast") dispatch.attach(context,policy,cancel,mode==L"auto",
            cancel_in_vm?64:std::numeric_limits<std::size_t>::max());
        const auto lowered=Clock::now();
        context.execute();
        const auto executed=Clock::now();
        const auto name=dispatch.last_function==zzy::no_node?std::string{}:
            zzy::spelling(program->data().nodes[dispatch.last_function].token);
        std::cout<<"{\"backend\":\""<<(dispatch.vm_calls?"mixed":"ast")
                  <<"\",\"function\":"<<zzy::quote(name)<<",\"prepare_ns\":"<<ns(start,prepared)
                  <<",\"lower_ns\":"<<ns(lowering_start,lowered)
                  <<",\"execute_ns\":"<<ns(lowered,executed)
                  <<",\"compiled_functions\":"<<dispatch.compiled_functions()
                  <<",\"vm_calls\":"<<dispatch.vm_calls<<",\"ast_calls\":"<<dispatch.ast_calls
                  <<",\"vm_retries\":"<<dispatch.vm_retries
                  <<",\"stdout\":"<<zzy::quote(output.str())
                  <<",\"stderr\":"<<zzy::quote(errors.str())<<"}\n";
        return 0;
    } catch(const zzy::Cancelled&) {std::cout<<output.str();return 130;}
    catch(const zzy::FrontendError& error) {std::cerr<<zzy::render_frontend(error,true);return 2;}
    catch(const zzy::RuntimeError& error) {
        std::cout<<output.str();
        std::cerr<<zzy::runtime_diagnostic(program->data(),error,true);
        return 1;
    }
    catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
