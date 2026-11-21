#pragma once
#include "zzy_native/program.hpp"
#include "zzy_native/runtime_heap.hpp"
#include <array>

namespace int_vm {
struct Declined {
    const char* reason;
};

// Two tag bits separate inline integers, array handles and booleans.
using Word = std::int64_t;
constexpr Word bound = (Word{1} << 60) - 1;
constexpr std::size_t max_locals = 32, max_stack = 64;
constexpr std::size_t max_code = 200000;
enum class Op {
    constant, load, store, add, sub, mul, mod, less, equal, negate,
    increment, jump, jump_false, call, empty_array, append, length, array, next, ret, unsupported
};
struct Instruction {
    Op op;
    Word operand;
};
struct Function {
    std::vector<Instruction> code;
    std::vector<std::size_t> parameters;
    std::size_t locals = 0;
    std::size_t depth = 1;
    zzy::Charge frame_peak{};
    bool has_loop = false;

    zzy::Charge frame_charge() const {
        return {locals + max_stack, locals + 1 + parameters.size() + max_stack,
                (locals + max_stack) * 8};
    }
};
using Entries = std::map<zzy::NodeId, std::size_t>;
struct Code {
    std::vector<Function> functions;
    std::size_t entry;
};
struct IntegerResult {std::int64_t value;zzy::NodeId site;};

class Compiler {
    using NodeId = zzy::NodeId;
    const zzy::ProgramData& program;
    std::map<NodeId, Word> constants_;
    Entries functions_;
    std::vector<Function> code_;
    std::size_t instruction_count_ = 0;
    std::size_t iterating_ = 0;
    std::size_t current_function_=0;
    bool mixed_ = false;

    const auto& node(NodeId id) const { return program.nodes.at(id); }
    const auto& ref(NodeId id) const { return program.references.at(id); }
    auto& code() { return code_.at(current_function_).code; }
    std::size_t emit(Op op, Word operand = 0) {
        if(instruction_count_>=max_code) throw Declined{"experimental code capacity"};
        code().push_back({op, operand});
        ++instruction_count_;
        return code().size() - 1;
    }
    void patch(std::size_t at) { code().at(at).operand = static_cast<Word>(code().size()); }
    bool builtin(NodeId id, std::string_view name) const {
        return node(id).kind == "name" && ref(id).builtin == name;
    }
    bool member(NodeId id, std::string_view owner, std::string_view name) const {
        const auto& callee = node(id);
        return callee.kind == "field" && callee.text == name && builtin(callee.children[0], owner);
    }
    Word integer(NodeId id) const {
        const auto& words = program.numbers.at(id).words;
        if (words.size() > 2) throw Declined{"large literal"};
        std::uint64_t value = words.empty() ? 0 : words.front();
        if (words.size() == 2) value |= std::uint64_t(words.back()) << 32;
        if (value > static_cast<std::uint64_t>(bound)) throw Declined{"large literal"};
        return static_cast<Word>(value) * 4;
    }
    Word slot(NodeId symbol) const {
        const auto& binding = program.symbols.at(symbol);
        if (binding.cell || binding.owner == zzy::no_node || binding.slot >= max_locals)
            throw Declined{"shared binding"};
        return static_cast<Word>(binding.slot);
    }
    std::size_t callable(NodeId id, std::size_t argc) const {
        if (node(id).kind != "name") throw Declined{"indirect call"};
        const auto found = functions_.find(ref(id).symbol);
        if (found == functions_.end()) throw Declined{"unsupported or recursive call"};
        if (code_.at(found->second).parameters.size() != argc) throw Declined{"call arity"};
        return found->second;
    }
    void expression(NodeId id, unsigned depth = 0) {
        if (depth >= 128) throw Declined{"experimental expression depth"};
        const auto& n = node(id);
        const auto& c = n.children;
        if (n.kind == "integer") emit(Op::constant, integer(id));
        else if (n.kind == "bool") emit(Op::constant, n.flag ? 6 : 2);
        else if (n.kind == "group") expression(c[0], depth + 1);
        else if (n.kind == "name") {
            const auto& reference = ref(id);
            if (reference.kind == "local") emit(Op::load, slot(reference.symbol));
            else if (const auto found = constants_.find(reference.symbol); found != constants_.end())
                emit(Op::constant, found->second);
            else throw Declined{"unsupported binding"};
        } else if (n.kind == "binary" || n.kind == "add") {
            const auto& k = n.token.kind;
            const Op op = k == "PLUS" ? Op::add : k == "MINUS" ? Op::sub :
                k == "MULTIPLY" ? Op::mul : k == "REMAINDER" ? Op::mod :
                k == "LESS" ? Op::less : k == "EQUAL" ? Op::equal : Op::unsupported;
            if (op == Op::unsupported) throw Declined{"unsupported operator"};
            expression(c[0], depth + 1); expression(c[1], depth + 1); emit(op);
        } else if (n.kind == "unary" && n.token.kind == "MINUS") {
            expression(c[0], depth + 1); emit(Op::negate);
        } else if (n.kind == "call") {
            if (c.size() == 2 && builtin(c[0], "len")) {
                if(mixed_) throw Declined{"array operation"};
                expression(c[1], depth + 1); emit(Op::length);
            } else {
                const auto target = callable(c[0], c.size() - 1);
                for (std::size_t i = 1; i < c.size(); ++i) expression(c[i], depth + 1);
                emit(Op::call, static_cast<Word>(target));
            }
        } else if (n.kind == "array") {
            if(mixed_) throw Declined{"array value"};
            for (auto child : c) expression(child, depth + 1);
            emit(c.empty() ? Op::empty_array : Op::array, static_cast<Word>(c.size()));
        } else throw Declined{"unsupported expression"};
    }
    void block(NodeId id) {
        for (auto child : node(id).children) statement(child);
    }
    bool increment(NodeId symbol, NodeId rhs, Word target) {
        const auto& n = node(rhs);
        if (!mixed_ || (n.kind != "add" && n.kind != "binary") || n.token.kind != "PLUS")
            return false;
        const auto lhs = n.children[0], step = n.children[1];
        if (node(lhs).kind != "name" || ref(lhs).symbol != symbol || node(step).kind != "integer")
            return false;
        const auto tagged = integer(step);
        if (tagged > std::numeric_limits<Word>::max() / static_cast<Word>(max_locals))
            return false;
        emit(Op::increment, tagged * static_cast<Word>(max_locals) + target);
        return true;
    }
    void statement(NodeId id) {
        const auto& n = node(id);
        const auto& c = n.children;
        if (n.kind == "binding" && n.annotation.empty()) {
            expression(c[0]); emit(Op::store, slot(id));
        } else if (n.kind == "assignment" && node(c[0]).kind == "name" &&
                   ref(c[0]).kind == "local" && program.symbols.at(ref(c[0]).symbol).mutable_binding) {
            const auto symbol = ref(c[0]).symbol;
            const auto target = slot(symbol);
            if (!increment(symbol, c[1], target)) {
                expression(c[1]); emit(Op::store, target);
            }
        } else if (n.kind == "while") {
            const auto start = code().size();
            expression(c[0]);
            const auto exit = emit(Op::jump_false);
            block(c[1]);
            emit(Op::jump, static_cast<Word>(start)); patch(exit);
        } else if (n.kind == "for") {
            if(mixed_) throw Declined{"array iteration"};
            expression(c[0]); emit(Op::constant, 0);
            const auto start = code().size();
            emit(Op::next, slot(id));
            const auto exit = emit(Op::jump_false);
            ++iterating_;
            block(c[1]);
            --iterating_;
            emit(Op::jump, static_cast<Word>(start)); patch(exit);
        } else if (n.kind == "if") {
            std::vector<std::size_t> exits;
            for (std::size_t i = 0; i + 1 < c.size(); i += 2) {
                expression(c[i]);
                const auto next = emit(Op::jump_false);
                block(c[i+1]); exits.push_back(emit(Op::jump)); patch(next);
            }
            if (c.size() % 2) block(c.back());
            for (auto exit : exits) patch(exit);
        } else if (n.kind == "return" && c.size() == 1) {
            expression(c[0]);
            emit(Op::ret,static_cast<Word>(c[0]));
        } else if (n.kind == "block") block(id);
        else if (n.kind == "expression") {
            const auto& call = node(c[0]);
            if (mixed_ || iterating_ || call.kind != "call" || call.children.size() != 3 ||
                !member(call.children[0], "array", "push")) throw Declined{"unsupported statement"};
            expression(call.children[1]); expression(call.children[2]); emit(Op::append);
        } else throw Declined{"unsupported statement"};
    }
    void function(NodeId id, std::size_t index) {
        const auto& n = node(id);
        const auto& plan = program.functions.at(id);
        if (!n.annotation.empty() || plan.locals.size() > max_locals)
            throw Declined{"function signature or frame"};
        Function compiled{{}, {}, plan.locals.size()};
        for (auto it = n.children.begin(); it != n.children.end() - 1; ++it) {
            if (!node(*it).annotation.empty()) throw Declined{"parameter annotation"};
            compiled.parameters.push_back(static_cast<std::size_t>(slot(*it)));
        }
        code_.at(index)=std::move(compiled);
        current_function_=index;
        block(n.children.back());
        emit(Op::unsupported);
        if (mixed_) {
            auto& fn = code_[index];
            zzy::Charge nested{};
            for (std::size_t pc = 0; pc < fn.code.size(); ++pc) {
                const auto& ins = fn.code[pc];
                if (ins.op == Op::jump && static_cast<std::size_t>(ins.operand) < pc)
                    fn.has_loop = true;
                if (ins.op != Op::call) continue;
                const auto& callee = code_.at(static_cast<std::size_t>(ins.operand));
                fn.has_loop = fn.has_loop || callee.has_loop;
                fn.depth = std::max(fn.depth, callee.depth + 1);
                nested.objects = std::max(nested.objects, callee.frame_peak.objects);
                nested.slots = std::max(nested.slots, callee.frame_peak.slots);
                nested.payload = std::max(nested.payload, callee.frame_peak.payload);
            }
            fn.frame_peak = fn.frame_charge() + nested;
        }
    }
public:
    explicit Compiler(const zzy::ProgramData& p) : program(p) {}
    std::pair<Code, Entries> lower_mixed(const std::atomic<bool>& cancelled) {
        mixed_ = true;
        for (auto id : node(program.root).children) {
            if (cancelled.load(std::memory_order_relaxed)) throw zzy::Cancelled{};
            const auto& n = node(id);
            if (n.kind == "binding" && !n.flag && n.annotation.empty() &&
                node(n.children[0]).kind == "integer") {
                try { constants_.emplace(id, integer(n.children[0])); }
                catch (const Declined&) { /* Keep this binding on the AST path. */ }
            }
            if (n.kind != "function") continue;
            // Resolver allows direct top-level dependencies on earlier declarations.
            // A self call, nested target, or declined dependency has no entry here.
            const auto index = code_.size();
            code_.emplace_back();
            const auto previous_count = instruction_count_;
            try {
                function(id, index);
                if (code_.back().depth > 64) throw Declined{"call graph depth"};
                functions_.emplace(id, index);
            } catch (const Declined&) {
                code_.pop_back();
                instruction_count_ = previous_count;
            }
        }
        return {Code{std::move(code_), 0}, std::move(functions_)};
    }
    Code lower() {
        const auto& body = node(program.root).children;
        if (program.graph.size() != 1 || body.empty()) throw Declined{"module or empty program"};
        for (auto it = body.begin(); it != body.end() - 1; ++it) {
            const auto& n = node(*it);
            if (n.kind == "binding" && !n.flag && n.annotation.empty() &&
                node(n.children[0]).kind == "integer")
                constants_.emplace(*it, integer(n.children[0]));
            else if (n.kind == "function") {
                functions_.emplace(*it,code_.size());
                code_.push_back({});
            }
            else throw Declined{"unsupported top level"};
        }
        for(auto it=body.begin();it!=body.end()-1;++it)
            if(node(*it).kind=="function") function(*it, functions_.at(*it));
        const auto& tail = node(body.back());
        if (tail.kind != "expression") throw Declined{"expected final print"};
        const auto& print = node(tail.children[0]);
        if (print.kind != "call" || print.children.size() != 2 ||
            !member(print.children[0], "io", "print")) throw Declined{"expected final print"};
        const auto& call = node(print.children[1]);
        if (call.kind != "call" || call.children.size() != 1) throw Declined{"expected entry call"};
        const auto entry = callable(call.children[0], 0);
        return {std::move(code_), entry};
    }
};

class Machine {
    const Code& code_;
    const std::atomic<bool>& cancelled_;
    std::shared_ptr<zzy::HeapState> heap_;
    std::size_t step_limit_;
    std::size_t cancel_after_;
    bool prepaid_ = false;
    std::vector<std::vector<Word>> arrays_;
    std::size_t elements_ = 0, steps_ = 0;
    zzy::NodeId return_site_=zzy::no_node;

    static Word integer(Word value) {
        if (value % 4) throw Declined{"expected integer"};
        return value / 4;
    }
    std::vector<Word>& array(Word value) {
        if ((value & 3) != 1) throw Declined{"expected integer array"};
        return arrays_.at(static_cast<std::size_t>(value / 4));
    }
    Word empty_array() {
        if (arrays_.size() == 64) throw Declined{"experimental array count"};
        const auto index = static_cast<Word>(arrays_.size());
        arrays_.emplace_back();
        return index * 4 + 1;
    }
    void claim(std::size_t count) {
        if (count > 100000 - elements_) throw Declined{"experimental array capacity"};
        elements_ += count;
    }
    static Word equal(Word a, Word b) {
        if ((a & 3) == 1 || (b & 3) == 1) throw Declined{"array identity comparison"};
        return a == b ? 6 : 2;
    }
    static void require_integers(Word a, Word b) {
        if ((a | b) & 3) throw Declined{"expected integer"};
    }
    static Word less(Word a, Word b) {
        require_integers(a, b);
        return a < b ? 6 : 2;
    }
    template<Op op>
    static Word add_sub(Word a, Word b) {
        require_integers(a, b);
        // Two valid tagged integers fit in signed 64 bits even before the bound check.
        const auto result = op == Op::add ? a + b : a - b;
        if (result < -bound * 4 || result > bound * 4) throw Declined{"integer range"};
        return result;
    }
    template<Op op>
    static Word numeric(Word a, Word b) {
        const auto x = integer(a), y = integer(b);
        Word result = 0;
        if constexpr (op == Op::mul) {
            // The admitted product fits signed 64 bits before the tag is applied.
            constexpr Word limit = 2147483647;
            if (x < -limit || x > limit || y < -limit || y > limit)
                throw Declined{"multiplication range"};
            result = x * y;
        } else if constexpr (op == Op::mod) {
            if (!y) throw Declined{"zero divisor"};
            result = x % y;
            if (result && (result < 0) != (y < 0)) result += y;
        }
        if (result < -bound || result > bound) throw Declined{"integer range"};
        return result * 4;
    }
    void tick() {
        if (cancelled_.load(std::memory_order_relaxed) || steps_ == cancel_after_)
            throw zzy::Cancelled{};
        if (steps_ == step_limit_) throw Declined{"experimental step capacity"};
        ++steps_;
    }
    Word invoke(std::size_t id, const Word* args, std::size_t depth) {
        if (!prepaid_ && depth > 64) throw Declined{"experimental call depth"};
        const auto& fn = code_.functions[id];
        zzy::Lease frame_budget;
        if (!prepaid_) {
            const auto budget = fn.frame_charge();
            if (!heap_->fits(budget)) throw Declined{"quota headroom"};
            frame_budget = zzy::Lease(heap_, budget);
        }
        std::array<Word, max_locals> locals;
        std::fill_n(locals.begin(), fn.locals, Word{3});
        for (std::size_t i = 0; i < fn.parameters.size(); ++i) {
            integer(args[i]);
            locals[fn.parameters[i]] = args[i];
        }
        std::array<Word, max_stack> values;
        std::size_t top = 0, ip = 0;
        const auto push = [&](Word v) {
            if (top == values.size()) throw Declined{"experimental operand stack"};
            values[top++] = v;
        };
        const auto binary = [&](auto operation) {
            const auto rhs = values[--top];
            values[top-1] = operation(values[top-1], rhs);
        };
        while (true) {
            tick();
            const auto ins = fn.code[ip++];
            const auto index = static_cast<std::size_t>(ins.operand);
            switch (ins.op) {
                case Op::constant: push(ins.operand); break;
                case Op::load:
                    if (locals[index] == 3) throw Declined{"uninitialized local"};
                    push(locals[index]); break;
                case Op::store: locals[index] = values[--top]; break;
                case Op::negate: values[top-1] = -integer(values[top-1]) * 4; break;
                case Op::add: binary(add_sub<Op::add>); break;
                case Op::sub: binary(add_sub<Op::sub>); break;
                case Op::mul: binary(numeric<Op::mul>); break;
                case Op::mod: binary(numeric<Op::mod>); break;
                case Op::less: binary(less); break;
                case Op::equal: binary(equal); break;
                case Op::increment: {
                    auto& local = locals[index % max_locals];
                    if (local == 3) throw Declined{"uninitialized local"};
                    tick();
                    tick();
                    const auto result = add_sub<Op::add>(local, ins.operand / static_cast<Word>(max_locals));
                    tick();
                    local = result;
                    break;
                }
                case Op::jump: ip = index; break;
                case Op::jump_false: {
                    const auto condition = values[--top];
                    if (condition == 2) ip = index;
                    else if (condition != 6) throw Declined{"expected boolean"};
                    break;
                }
                case Op::call: {
                    top -= code_.functions[index].parameters.size();
                    const auto result = invoke(index, values.data() + top, depth + 1);
                    push(result); break;
                }
                case Op::empty_array: push(empty_array()); break;
                case Op::append: {
                    const auto value = values[--top];
                    integer(value); claim(1);
                    array(values[--top]).push_back(value);
                    break;
                }
                case Op::length:
                    values[top-1] = static_cast<Word>(array(values[top-1]).size()) * 4;
                    break;
                case Op::array: {
                    claim(index);
                    const auto handle = empty_array();
                    auto& out = array(handle);
                    top -= index;
                    for (std::size_t i = 0; i < index; ++i) integer(values[top+i]);
                    out.assign(values.data() + top, values.data() + top + index);
                    push(handle); break;
                }
                case Op::next: {
                    auto& input = array(values[top-2]);
                    const auto pos = static_cast<std::size_t>(values[top-1] / 4);
                    if (pos == input.size()) { top -= 2; push(2); }
                    else { locals[index] = input[pos]; values[top-1] += 4; push(6); }
                    break;
                }
                case Op::ret:
                    return_site_=static_cast<zzy::NodeId>(ins.operand);
                    return values[top-1];
                default: throw Declined{"missing explicit return"};
            }
        }
    }
public:
    Machine(const Code& code,std::atomic<bool>& cancelled,
            std::shared_ptr<zzy::HeapState> heap={},
            std::size_t step_limit=2000000,
            std::size_t cancel_after=std::numeric_limits<std::size_t>::max())
        : code_(code),cancelled_(cancelled),
          heap_(heap?std::move(heap):std::make_shared<zzy::HeapState>(zzy::ResourcePolicy{},cancelled)),
          step_limit_(step_limit),cancel_after_(cancel_after) {}
    IntegerResult run_integer(std::size_t entry, const std::int64_t* args,
                              std::size_t count, std::size_t initial_depth) {
        std::array<Word,max_locals> encoded;
        const auto& fn = code_.functions.at(entry);
        if (count != fn.parameters.size()) throw Declined{"argument count"};
        if (initial_depth > 64 || fn.depth > 65 - initial_depth)
            throw Declined{"call graph depth"};
        for(std::size_t i=0;i<count;++i) {
            if(args[i] < -bound || args[i] > bound) throw Declined{"argument range"};
            encoded[i]=args[i]*4;
        }
        if(step_limit_>std::numeric_limits<std::size_t>::max()/8)
            throw Declined{"experimental payload budget"};
        // One VM instruction can create at most one supported scalar Int. Reserve
        // the entire step allowance up front so fallback never masks a quota error.
        const auto execution_charge = zzy::Charge{0, 0, step_limit_ * 8} + fn.frame_peak;
        if(!heap_->fits(execution_charge)) throw Declined{"quota headroom"};
        zzy::Lease execution_budget(heap_,execution_charge);
        prepaid_ = true;
        const auto result = invoke(entry, encoded.data(), initial_depth);
        if(result%4) throw Declined{"non-integer return"};
        return {result/4,return_site_};
    }
    std::string run() {
        const auto result = invoke(code_.entry, nullptr, 1);
        if ((result & 3) == 1) {
            std::string text = "[";
            for (const auto v : array(result)) {
                if (cancelled_.load(std::memory_order_relaxed)) throw zzy::Cancelled{};
                if (text.size() > 1000000) throw Declined{"experimental output capacity"};
                if (text.size() > 1) text += ", ";
                text += std::to_string(integer(v));
            }
            return text + "]\n";
        }
        if (result == 2 || result == 6) return result == 6 ? "true\n" : "false\n";
        return std::to_string(integer(result)) + "\n";
    }
};
}
