"""The native fingerprint must detect build, dependency and fixture changes."""
from pathlib import Path
import tempfile
import unittest
from native_runtime.tools.native_ci import fingerprint_files, fingerprint


class NativeFingerprintTests(unittest.TestCase):
    def test_each_input_changes_digest(self):
        names = ["src/main.cpp", "include/value.hpp", "CMakeLists.txt", "case.cmake",
                 "third_party/library.h", "third_party/dependencies.json", "test/golden.zzy"]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in names:
                (root/name).parent.mkdir(parents=True,exist_ok=True)
                (root/name).write_bytes(b"original")
            before = fingerprint_files(root,names)
            for name in names:
                (root/name).write_bytes(b"changed")
                self.assertNotEqual(before["sha256"],fingerprint_files(root,names)["sha256"],name)
                (root/name).write_bytes(b"original")
            self.assertEqual(before,fingerprint_files(root,list(reversed(names))))

    def test_real_source_set(self):
        result=fingerprint(); files=result["files"]
        self.assertIn("native_runtime/src/main.cpp",files)
        self.assertIn("native_runtime/CMakeLists.txt",files)
        self.assertIn("apps/zzy-campus/main.zzy",files)
        self.assertIn("apps/zzy-campus/limits.json",files)
        self.assertIn(".github/workflows/native-ci.yml",files)
        self.assertTrue(any(p.endswith(".cmake") for p in files))
        self.assertTrue(any("third_party/" in p and p.endswith(".h") for p in files))
        self.assertTrue(any(p.endswith(".zzy") for p in files))


if __name__ == "__main__":
    unittest.main()
