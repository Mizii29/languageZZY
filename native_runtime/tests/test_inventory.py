"""Development inventory checks; not a dependency of native CTest or runtime."""
import json
from pathlib import Path
import tempfile
import unittest

from native_runtime.tools.inventory import ROOT, snapshot, main
from unittest.mock import patch


class InventoryTests(unittest.TestCase):
    def test_frozen_records_and_no_token_names_as_ast(self):
        record = snapshot()
        frozen = json.loads((ROOT/'native_runtime/tests/inventory.json').read_text(encoding='utf-8'))
        record.pop('source_sha'); frozen.pop('source_sha')
        self.assertEqual(json.loads(json.dumps(record)), frozen)
        self.assertEqual(len(record['manifests']), 12)
        self.assertEqual(sum(map(len, record['manifests'].values())), 1738)
        self.assertEqual(len(record['ast_kinds']), 56)
        self.assertTrue(all(k == k.lower() for k in record['ast_kinds']))
        self.assertEqual(record['reference_kinds'], ['capture','global','local','self'])

    def test_check_rejects_drift(self):
        record = snapshot(); record['ast_kinds'].remove('function')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'changed.json'
            path.write_text(json.dumps(record),encoding='utf-8')
            with patch('sys.argv',['inventory','--check',str(path)]):
                with self.assertRaisesRegex(SystemExit, 'Inventory drift'):
                    main()

    def test_check_accepts_json_roundtrip(self):
        with patch('sys.argv',['inventory','--check',str(ROOT/'native_runtime/tests/inventory.json')]):
            main()
