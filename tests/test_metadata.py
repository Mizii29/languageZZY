import subprocess
import sys
import unittest

from zzy.native.metadata import Extension, MetadataRegistry, NativeFunction, NativeType


class MetadataTests(unittest.TestCase):
    def test_registration_identity_and_no_runtime_implementation(self):
        registry = MetadataRegistry()
        metadata = Extension("sketch", "design-only", (
            NativeType("sketch.Canvas", True, "ExecutionContext", "identity"),), (
            NativeFunction("sketch.canvas", ("Int", "Int", "String"), "Canvas",
                           ("allocate",), ("E201", "E202", "E211")),))
        registry.register(metadata)
        self.assertIs(registry.extensions["sketch"], metadata)
        with self.assertRaises(ValueError):
            registry.register(metadata)
        with self.assertRaises(TypeError):
            registry.extensions["other"] = metadata
        with self.assertRaises(ValueError):
            MetadataRegistry().register(Extension("other", "1", metadata.types))

    def test_imports_do_not_load_gui_or_optional_dependencies(self):
        result = subprocess.run([sys.executable, "-c",
            "import sys; import zzy.cli, zzy.native.metadata; "
            "assert not {'tkinter', 'turtle', 'numpy', 'fastapi'} & sys.modules.keys()"],
            capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
