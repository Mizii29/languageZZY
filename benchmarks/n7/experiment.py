"""Create separate MSVC source trees for N7 probes and one-change candidates."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]


def replace(path, old, new):
    source = path.read_text(encoding='utf-8')
    if source.count(old) != 1:
        raise ValueError(f'expected one patch anchor in {path}: {old}')
    path.write_bytes(source.replace(old, new).encode('utf-8'))


def overlay(output, mode):
    output.mkdir(parents=True)
    native = output/'native_runtime'
    shutil.copytree(ROOT/'native_runtime', native, ignore=shutil.ignore_patterns('__pycache__'))
    data = output/'benchmarks'/'n7'
    data.mkdir(parents=True)
    shutil.copy2(ROOT/'benchmarks'/'n7'/'probe.cpp', data/'probe.cpp')
    heap = native/'include'/'zzy_native'/'runtime_heap.hpp'
    if mode == 'lookup':
        replace(heap, '''        if(closed || h.owner!=owner || !nodes.count(h.id)) throw std::logic_error("foreign or released runtime value");
        return *nodes.at(h.id);''', '''        if(closed || h.owner!=owner) throw std::logic_error("foreign or released runtime value");
        const auto found=nodes.find(h.id);
        if(found==nodes.end()) throw std::logic_error("foreign or released runtime value");
        return *found->second;''')
        return
    shutil.copy2(ROOT/'benchmarks'/'n7'/'profile.hpp', heap.with_name('n7_profile.hpp'))
    replace(heap, '#include "bigint.hpp"', '#define ZZY_N7_PROFILE 1\n#include "n7_profile.hpp"\n#include "bigint.hpp"')
    for label, anchor in {
        'get': 'RuntimeNode& get(Handle h) const {',
        'pin': 'Value pin(Handle h) {\n        get(h);',
        'check': 'void check(const std::string& key,std::uint64_t value,NodeId site=no_node) const {',
        'reserve': 'void reserve(Charge x,NodeId site=no_node) {',
        'collect': '    void collect() {\n        point();',
        'allocate': 'allocate(RuntimeNode node,Charge charge,NodeId site=no_node) {',
    }.items():
        opening, rest = anchor.split('{', 1)
        replace(heap, anchor, opening+'{\n        n7_profile::Scope n7_scope(n7_profile::'+label+');'+rest)
    execution = heap.with_name('execution.hpp')
    replace(execution, '            task.action();',
            '            {n7_profile::Scope scope(n7_profile::dispatch);task.action();}')
    probe = data/'probe.cpp'
    replace(probe, '        n7_profile::report(std::cerr);',
            '        n7_profile::report(std::cerr);\n'
            '        std::cerr<<"{\\"RuntimeNode_bytes\\":"<<sizeof(RuntimeNode)'
            '<<",\\"RootToken_bytes\\":"<<sizeof(RootToken)'
            '<<",\\"Value_bytes\\":"<<sizeof(Value)<<"}\\n";')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('profile', 'lookup'))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    overlay(args.output.resolve(), args.mode)
