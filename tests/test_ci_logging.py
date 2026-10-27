"""Rotation must bound disk use without hiding failures or breaking UTF-8."""
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts import ci_logging


class CILoggingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ZZY 日志 验收 ')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / 'tests.log'
        self.config = ci_logging.LogConfig(max_bytes=4096, backup_count=2)
        self.stats = {}

    def run_child(self, source, timeout=10):
        return ci_logging.run_logged([sys.executable, '-I', '-X', 'utf8', '-c', source],
                                     cwd=self.directory, path=self.path,
                                     config=self.config, timeout=timeout, stats=self.stats)

    def retained(self):
        parts = []
        for index in range(self.config.backup_count, 0, -1):
            archive = Path(f'{self.path}.{index}.gz')
            if archive.exists():
                parts.append(gzip.decompress(archive.read_bytes()))
        parts.append(self.path.read_bytes())
        return parts

    def test_nondefault_configuration_controls_real_rotation_threshold(self):
        config_file = self.directory / 'logging.json'
        config_file.write_text('{"schema_version":1,"max_bytes":8192,"backup_count":1}', encoding='utf-8')
        self.config = ci_logging.load_config(config_file)
        self.assertEqual(self.run_child('import os;os.write(1,b"x"*6000)'), 0)
        self.assertEqual(self.path.read_bytes(), b'x' * 6000)
        self.assertFalse(Path(f'{self.path}.1.gz').exists())

    def test_rejects_unbounded_malformed_and_ambiguous_configuration(self):
        config_file = self.directory / 'logging.json'
        valid = dict(schema_version=1, max_bytes=4096, backup_count=2)
        records = [dict(valid, max_bytes=x) for x in [0, -1, True, '4096', 67108865]]
        records += [dict(valid, backup_count=x) for x in [0, -1, True, 11, 1.0]]
        records += [dict(valid, schema_version=x) for x in [True, 2]]
        records += [dict(valid, typo=1), {}, []]
        texts = [json.dumps(record) for record in records]
        texts += ['{', '{"schema_version":1,"max_bytes":4096,"backup_count":1,"backup_count":2}', ' ' * 65537]
        for text in texts:
            with self.subTest(text=text[:100]):
                config_file.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    ci_logging.load_config(config_file)

    def test_utf8_bytes_and_newlines_survive_rotation(self):
        original = ('中文日志 🙂\n' * 600).encode('utf-8')
        self.assertEqual(self.run_child('import os;os.write(1,("中文日志 🙂\\n"*600).encode("utf-8"))'), 0)
        parts = self.retained()
        self.assertEqual(b''.join(parts), original)
        for part in parts:
            self.assertLessEqual(len(part), self.config.max_bytes)
            part.decode('utf-8')
        self.assertNotIn(b'\r', b''.join(parts))
        self.assertFalse(self.stats['older_logs_discarded'])

    def test_oldest_backups_are_deleted_and_latest_tail_is_complete(self):
        original = ''.join(f'{index:06} fixed diagnostic E211\n' for index in range(3000)).encode()
        source = 'import os;os.write(1,"".join(f"{i:06} fixed diagnostic E211\\n" for i in range(3000)).encode())'
        self.assertEqual(self.run_child(source), 0)
        self.assertEqual({p.name for p in self.directory.iterdir()},
                         {'tests.log', 'tests.log.1.gz', 'tests.log.2.gz'})
        parts = self.retained()
        self.assertTrue(all(len(part) <= self.config.max_bytes for part in parts))
        retained = b''.join(parts)
        self.assertTrue(original.endswith(retained))
        self.assertIn(b'002999 fixed diagnostic E211\n', parts[-1])
        self.assertGreater(self.stats['rotations'], self.config.backup_count)
        self.assertTrue(self.stats['older_logs_discarded'])

    def test_invalid_utf8_and_incomplete_final_sequence_are_visible(self):
        original = b'x' * 511 + '中'.encode() + b'\xff\xe4'
        self.assertEqual(self.run_child(f'import os;os.write(1,{original!r})'), 0)
        expected = 'x' * 511 + '中\\xff\\xe4'
        self.assertEqual(self.path.read_text(encoding='utf-8'), expected)

    def test_nonzero_exit_and_both_streams_are_preserved(self):
        self.assertEqual(self.run_child('import os;os.write(1,b"out\\n");os.write(2,b"err\\n");raise SystemExit(7)'), 7)
        self.assertEqual(self.path.read_bytes(), b'out\nerr\n')

    def test_timeout_keeps_log_and_stops_reader(self):
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_child('import os,time;os.write(1,b"READY\\n");time.sleep(60)', timeout=0.5)
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(self.path.read_bytes(), b'READY\n')
        self.assertFalse(any(t.name == 'zzy-ci-log-reader' for t in threading.enumerate()))

    def test_log_write_error_fails_and_cleans_up_child(self):
        with patch.object(ci_logging._UTF8RotatingHandler, 'emit', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.run_child('import os\nwhile True:os.write(1,b"x"*1024)')
        self.assertFalse(any(t.name == 'zzy-ci-log-reader' for t in threading.enumerate()))

    def test_compression_error_preserves_current_log_and_fails(self):
        with patch.object(ci_logging.gzip, 'open', side_effect=OSError('archive failed')):
            with self.assertRaisesRegex(OSError, 'archive failed'):
                self.run_child('import os;os.write(1,b"x"*20000)')
        self.assertGreater(self.path.stat().st_size, 0)
        self.assertFalse(list(self.directory.glob('*.tmp')))

    def test_descendant_holding_pipe_cannot_block_successful_parent(self):
        started = time.monotonic()
        source = ('import os,subprocess,sys;'
                  'subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
                  'os.write(1,b"parent done\\n")')
        self.assertEqual(self.run_child(source), 0)
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(self.path.read_bytes(), b'parent done\n')


if __name__ == '__main__':
    unittest.main()
