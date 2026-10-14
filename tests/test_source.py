import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zzy.diagnostics import Cancelled, DiagnosticError, Phase, Position, ResourceExceeded
from zzy.resources import ResourceMeter, ResourcePolicy
from zzy.source import Source, SourceLoader


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def loader(self, **limits):
        loader = SourceLoader(ResourceMeter(ResourcePolicy(limits), Phase.FRONTEND))
        self.addCleanup(loader.close)
        return loader

    def test_bom_crlf_unicode_tab_and_eof(self):
        raw = b"\xef\xbb\xbf" + "中😀\tX\r\n尾\n".encode("utf-8")
        source = Source.from_bytes(self.root / "中文.zzy", raw)
        self.assertEqual(source.raw, raw)
        self.assertEqual(source.text, "中😀\tX\r\n尾\n")
        self.assertEqual(source.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(source.position(3), Position(1, 4))
        self.assertEqual(source.position(6), Position(2, 1))
        self.assertEqual(source.position(len(source.text)), Position(3, 1))
        self.assertEqual(source.span(8, 8).start, source.span(8, 8).end)
        for offset in (-1, 9):
            with self.assertRaises(ValueError):
                source.position(offset)

    def test_empty_file_and_only_one_bom_removed(self):
        self.assertEqual(Source.from_bytes(self.root, b"").position(0), Position(1, 1))
        self.assertEqual(Source.from_bytes(self.root, b"\xef\xbb\xbf" * 2).text, "\ufeff")

    def test_file_limit_and_total_limit(self):
        path = self.root / "输入 空格.zzy"
        for size in (2, 3, 4):
            path.write_bytes(b"a" * size)
            loader = self.loader(source_file_bytes=3)
            if size <= 3:
                self.assertEqual(len(loader.read(path).raw), size)
            else:
                with self.assertRaises(ResourceExceeded) as caught:
                    loader.read(path)
                self.assertEqual(caught.exception.key, "source_file_bytes")
                self.assertEqual(loader.meter.used("source_total_bytes"), 0)
        first = self.root / "first.zzy"
        second = self.root / "second.zzy"
        first.write_bytes(b"aa")
        second.write_bytes(b"bb")
        loader = self.loader(source_total_bytes=3)
        loader.read(first)
        with self.assertRaises(ResourceExceeded) as caught:
            loader.read(second)
        self.assertEqual(caught.exception.key, "source_total_bytes")
        self.assertEqual(loader.meter.used("source_total_bytes"), 2)

    def test_default_source_boundaries(self):
        limit = 2 * 1024**2
        path = self.root / "large.zzy"
        for size in (limit - 1, limit, limit + 1):
            path.write_bytes(b"a" * size)
            with self.loader() as loader:
                if size <= limit:
                    self.assertEqual(len(loader.read(path).raw), size)
                else:
                    with self.assertRaises(ResourceExceeded):
                        loader.read(path)
        with self.loader() as loader:
            for index in range(8):
                file = self.root / f"{index}.zzy"
                file.write_bytes(b"a" * limit)
                loader.read(file)
            self.assertEqual(loader.meter.used("source_total_bytes"), 16 * 1024**2)
            extra = self.root / "extra.zzy"
            extra.write_bytes(b"a")
            with self.assertRaises(ResourceExceeded) as caught:
                loader.read(extra)
            self.assertEqual(caught.exception.key, "source_total_bytes")

    def test_snapshot_canonical_alias_and_importer_path(self):
        folder = self.root / "模块 空格"
        folder.mkdir()
        file = folder / "input.zzy"
        file.write_bytes(b"old")
        loader = self.loader(source_total_bytes=3, module_count=1)
        source = loader.read("input.zzy", importer=folder / "main.zzy")
        file.write_bytes(b"new")
        self.assertIs(loader.read(folder / ".." / folder.name / "input.zzy"), source)
        self.assertEqual(source.raw, b"old")
        self.assertEqual(loader.meter.used("module_count"), 1)
        self.assertEqual(loader.meter.used("source_total_bytes"), 3)
        self.assertEqual(self.loader().read(file).raw, b"new")

    def test_read_failures_rollback_and_close_handles(self):
        loader = self.loader()
        bad = self.root / "bad.zzy"
        bad.write_bytes(b"\xff")
        for path in (self.root / "missing.zzy", self.root, bad):
            with self.assertRaises(DiagnosticError) as caught:
                loader.read(path)
            self.assertEqual(caught.exception.diagnostic.code, "E401")
            self.assertIsNone(caught.exception.diagnostic.span)
            self.assertEqual(loader.meter.used("module_count"), 0)
            self.assertEqual(loader.meter.used("source_total_bytes"), 0)
        bad.unlink()  # Also proves the read handle was closed on Windows.

    def test_module_and_import_depth_boundaries(self):
        loader = self.loader(module_count=2, import_depth=2)
        for index in range(3):
            file = self.root / f"{index}.zzy"
            file.write_bytes(b"")
            if index < 2:
                loader.read(file, import_depth=index + 1)
            else:
                with self.assertRaises(ResourceExceeded) as caught:
                    loader.read(file)
                self.assertEqual(caught.exception.key, "module_count")
        with self.assertRaises(ResourceExceeded) as caught:
            loader.read(self.root / "0.zzy", import_depth=3)
        self.assertEqual(caught.exception.key, "import_depth")
        loader.close()
        self.assertEqual(loader.meter.used("module_count"), 0)

    def test_cancel_and_host_failure_release_reservations(self):
        file = self.root / "input.zzy"
        file.write_bytes(b"abc")
        for failure in (Cancelled(), MemoryError(), RecursionError()):
            loader = self.loader()
            with patch.object(Source, "from_bytes", side_effect=failure):
                with self.assertRaises(type(failure)):
                    loader.read(file)
            self.assertEqual(loader.meter.used("module_count"), 0)
            self.assertEqual(loader.meter.used("source_total_bytes"), 0)
        file.unlink()
