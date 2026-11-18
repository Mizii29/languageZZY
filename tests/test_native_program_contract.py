"""Static frontend evidence wiring; native behavior runs in nonempty CTest.

Core Python installation does not require an installed C++ toolchain or EXE.
"""
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]


class NativeProgramContractTests(unittest.TestCase):
    def test_native_check_keeps_all_external_manifests(self):
        inventory=json.loads((ROOT/'native_runtime/tests/inventory.json').read_text(encoding='utf-8'))
        manifests=json.loads((ROOT/'native_runtime/tests/program/manifests.json').read_text(encoding='utf-8'))
        self.assertEqual(manifests,list(inventory['manifests']))
        cases=[(p,c['id']) for p in manifests
               for c in json.loads((ROOT/p).read_text(encoding='utf-8'))['cases'] if c['mode']=='check']
        self.assertEqual(len(cases),848)
        self.assertEqual(len(cases),len(set(cases)))

    def test_all_frozen_host_metadata_without_function_pointers(self):
        inventory=json.loads((ROOT/'native_runtime/tests/inventory.json').read_text(encoding='utf-8'))
        text=(ROOT/'native_runtime/include/zzy_native/host_metadata.hpp').read_text(encoding='utf-8')
        strings=r'"(?:\\.|[^"\\])*"'
        matches=re.findall(r'\{('+strings+'),('+strings+r'),(true|false)\}',text)
        actual={json.loads(name):json.loads(json.loads(desc)) for name,desc,_ in matches}
        self.assertEqual(len(matches),103)
        self.assertEqual(actual,inventory['native_functions'])
        pure=sorted(('core.'+name if name in {'len','str'} else name)
                    for name,desc in actual.items() if desc['pure'])
        self.assertEqual(pure,inventory['pure_calls'])

    def test_publication_exposes_only_readonly_data(self):
        text=(ROOT/'native_runtime/include/zzy_native/program.hpp').read_text(encoding='utf-8')
        self.assertIn('std::shared_ptr<const ProgramData> data_;',text)
        self.assertIn('const ProgramData& data() const',text)
        self.assertNotIn('heap_prototype.hpp',text)
        for kind in ('Cell','Value','Frame','LazyState'):
            self.assertNotRegex(text,rf'\b{kind}\s*[*&<]')
        # Compile-time and actual concurrent snapshot checks are separate
        # native tests, not inferred as proved by these source assertions.
