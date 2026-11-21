#include "zzy_native/execution.hpp"
#include "zzy_native/prepare.hpp"
#include "vm.hpp"
#include <chrono>
#include <iostream>
#include <sstream>

namespace {
using Clock = std::chrono::steady_clock;
auto ns(Clock::time_point a, Clock::time_point b) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(b - a).count();
}
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 4 && argc != 5) return 2;
    const std::wstring_view mode(argv[1]);
    if (mode != L"ast" && mode != L"vm" && mode != L"auto") return 2;
    if (argc == 5 && std::wstring_view(argv[4]) != L"--cancel") return 2;
    std::optional<zzy::Program> program;
    try {
        const auto policy = zzy::load_policy(argv[3]);
        std::atomic<bool> cancel{false};
        zzy::FrontendMeter meter(policy, cancel);
        const auto start = Clock::now();
        program.emplace(zzy::prepare(argv[2], meter));
        const auto prepared = Clock::now();
        cancel.store(argc == 5, std::memory_order_relaxed);
        std::int64_t lower_ns = 0;
        auto initialized = prepared, executed = prepared;
        std::string output, reason;
        bool vm = false;
        if (mode != L"ast") {
            try {
                if (policy.limits != zzy::ResourcePolicy{}.limits)
                    throw int_vm::Declined{"custom resource policy"};
                const auto lowering = Clock::now();
                const auto code = int_vm::Compiler(program->data()).lower();
                const auto lowered = Clock::now();
                lower_ns = ns(lowering, lowered);
                int_vm::Machine machine(code, cancel);
                initialized = Clock::now();
                output = machine.run();
                executed = Clock::now();
                vm = true;
            } catch (const int_vm::Declined& error) {
                reason = error.reason;
                if (mode == L"vm") {
                    std::cerr << "VM declined: " << reason << '\n';
                    return 3;
                }
            }
        }
        if (!vm) {
            std::ostringstream stream, errors;
            zzy::ExecutionContext context(*program, policy, cancel, stream, errors);
            initialized = Clock::now();
            context.execute();
            executed = Clock::now();
            output = stream.str();
        }
        program.reset();
        const auto cleaned = Clock::now();
        std::cout << "{\"backend\":" << zzy::quote(vm ? "vm" : "ast")
                  << ",\"reason\":" << zzy::quote(reason)
                  << ",\"prepare_ns\":" << ns(start, prepared)
                  << ",\"lower_ns\":" << lower_ns
                  << ",\"execute_ns\":" << ns(initialized, executed)
                  << ",\"cleanup_ns\":" << ns(executed, cleaned)
                  << ",\"stdout\":" << zzy::quote(output) << "}\n";
        return 0;
    } catch (const zzy::Cancelled&) {
        return 130;
    } catch (const zzy::FrontendError& error) {
        std::cerr << zzy::render_frontend(error, true);
        return 2;
    } catch (const zzy::RuntimeError& error) {
        if (program) std::cerr << zzy::runtime_diagnostic(program->data(), error, true);
        return 1;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
