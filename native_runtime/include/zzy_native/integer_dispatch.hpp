#pragma once
#include "execution.hpp"
#include "integer_vm.hpp"

namespace zzy {
// The dispatch table is prepared once and owned by a single execution request.
class IntegerDispatch {
    int_vm::Code code_{};
    int_vm::Entries entries_;
public:
    std::size_t vm_calls = 0, ast_calls = 0, vm_retries = 0;
    NodeId last_function = no_node;

    std::size_t compiled_functions() const { return code_.functions.size(); }

    void attach(ExecutionContext& context, const ResourcePolicy& policy, std::atomic<bool>& cancel,
                bool loops_only, std::size_t cancel_after = std::numeric_limits<std::size_t>::max()) {
        if (context.program.graph.size() != 1 || policy.limits != ResourcePolicy{}.limits)
            return;
        std::tie(code_, entries_) = int_vm::Compiler(context.program).lower_mixed(cancel);
        context.set_fast_integer_call(
            [this, &context, &cancel, loops_only, cancel_after]
            (NodeId id, const std::vector<Value>& args, NodeId call_site)
                -> std::optional<ExecutionContext::FastIntegerResult> {
                const auto found = entries_.find(id);
                ++ast_calls;
                if (found == entries_.end() || (loops_only && !code_.functions[found->second].has_loop))
                    return std::nullopt;
                std::array<std::int64_t, int_vm::max_locals> values;
                for (std::size_t i = 0; i < args.size(); ++i) {
                    const auto& node = context.heap.get(args[i]);
                    if (node.kind != "Int" || node.integer.bits() > 60) return std::nullopt;
                    const auto& arg = node.integer;
                    const auto& words = arg.words();
                    std::uint64_t magnitude = words.empty() ? 0 : words[0];
                    if (words.size() > 1) magnitude |= std::uint64_t(words[1]) << 32;
                    const auto value = static_cast<std::int64_t>(magnitude);
                    values[i] = arg.sign() < 0 ? -value : value;
                }
                auto& heap = context.heap.state;
                const auto payload_left = heap->policy.limits.at("runtime_payload_bytes") - heap->used.payload;
                const auto steps = static_cast<std::size_t>(std::min<std::uint64_t>(2000000, payload_left / 32));
                try {
                    int_vm::Machine machine(code_, cancel, heap, steps, cancel_after);
                    const auto result = machine.run_integer(found->second, values.data(), args.size(),
                                                            context.active_call_depth());
                    auto converted = ExecutionContext::FastIntegerResult{
                        BigInt(result.value), result.site == no_node ? call_site : result.site};
                    ++vm_calls;
                    --ast_calls;
                    last_function = id;
                    return converted;
                } catch (const int_vm::Declined&) {
                    ++vm_retries;
                    return std::nullopt;
                }
            });
    }
};
}
