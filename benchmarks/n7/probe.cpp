#include "zzy_native/execution.hpp"
#include "zzy_native/prepare.hpp"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>

namespace zzy {
using Clock=std::chrono::steady_clock;
static auto ns(Clock::time_point a,Clock::time_point b) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(b-a).count();
}
struct ExecutionProbe {
    static void measure(const std::wstring& path,const ResourcePolicy& policy) {
        std::atomic<bool> cancel{false};
        std::ostringstream out,err;
        FrontendMeter meter(policy,cancel);
        const auto start=Clock::now();
        SourceSnapshot bytes;
        {
            const auto canonical=std::filesystem::canonical(path).wstring();
            std::ifstream input(std::filesystem::path(canonical),std::ios::binary);
            if(!input) throw std::runtime_error("cannot read benchmark source");
            auto raw=std::string(std::istreambuf_iterator<char>(input),{});
            meter.check("source_file_bytes",raw.size());
            bytes.files.emplace(canonical,std::move(raw));
            bytes.aliases.emplace(full_path(path),canonical);
        }
        const auto read=Clock::now();
        std::optional<Program> program=Preparation(meter,&bytes).load(path);
        const auto prepared=Clock::now();
        auto context=std::make_unique<ExecutionContext>(*program,policy,cancel,out,err);
        context->initialize();
        const auto initialized=Clock::now();
        context->block(context->program.root,[]{});
        context->drain();
        const auto executed=Clock::now();
        const auto peak=context->heap.state->peak;
        context->cleanup();
        if(!(context->heap.state->used==Charge{})) throw std::logic_error("heap quota leak");
        context.reset();program.reset();bytes.files.clear();bytes.aliases.clear();
        const auto cleaned=Clock::now();
        std::cout<<"{\"read_ns\":"<<ns(start,read)<<",\"prepare_ns\":"<<ns(read,prepared)
            <<",\"init_ns\":"<<ns(prepared,initialized)<<",\"execute_ns\":"<<ns(initialized,executed)
            <<",\"cleanup_ns\":"<<ns(executed,cleaned)<<",\"stdout\":"<<quote(out.str())
            <<",\"stderr\":"<<quote(err.str())<<",\"logical_peak\":{\"runtime_objects\":"<<peak.objects
            <<",\"runtime_slots\":"<<peak.slots<<",\"runtime_payload_bytes\":"<<peak.payload<<"}}\n";
#ifdef ZZY_N7_PROFILE
        n7_profile::report(std::cerr);
#endif
    }
};
}

int wmain(int argc,wchar_t** argv) {
    if(argc!=3) return 2;
    try {
        zzy::ExecutionProbe::measure(argv[1],zzy::load_policy(argv[2]));
        return 0;
    } catch(const std::exception& error) {
        std::cerr<<error.what()<<'\n';
        return 1;
    }
}
