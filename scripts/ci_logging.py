"""Bounded UTF-8 CI logs using the standard library's rotation handler."""
import codecs
from dataclasses import dataclass
import gzip
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import subprocess
from threading import Thread

from zzy.process import ProcessTree


@dataclass(frozen=True)
class LogConfig:
    max_bytes: int
    backup_count: int

    def __post_init__(self):
        if type(self.max_bytes) is not int or not 4096 <= self.max_bytes <= 64 * 1024**2:
            raise ValueError('log max_bytes must be an integer in [4096, 67108864]')
        if type(self.backup_count) is not int or not 1 <= self.backup_count <= 10:
            raise ValueError('log backup_count must be an integer in [1, 10]')


def load_config(path):
    def unique_keys(pairs):
        record = {}
        for key, value in pairs:
            if key in record:
                raise ValueError(f'Duplicate logging configuration key: {key}')
            record[key] = value
        return record
    with Path(path).open('rb') as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError('Logging configuration exceeds 64 KiB')
    record = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_keys)
    if (type(record) is not dict or set(record) != {'schema_version', 'max_bytes', 'backup_count'}
            or type(record['schema_version']) is not int or record['schema_version'] != 1):
        raise ValueError('Logging configuration requires schema_version=1 and exactly three keys')
    return LogConfig(record['max_bytes'], record['backup_count'])


def _gzip_rotate(source, destination):
    temporary = destination + '.tmp'
    try:
        with open(source, 'rb') as original, gzip.open(temporary, 'wb') as archive:
            shutil.copyfileobj(original, archive, length=65536)
        os.replace(temporary, destination)
        os.unlink(source)
    finally:
        Path(temporary).unlink(missing_ok=True)


class _UTF8RotatingHandler(RotatingFileHandler):
    terminator = ''

    def __init__(self, *args, **kwargs):
        self.rotations = 0
        super().__init__(*args, **kwargs)

    def _open(self):
        return open(self.baseFilename, self.mode, encoding='utf-8',
                    errors='backslashreplace', newline='\n')

    def shouldRollover(self, record):
        # The standard handler counts characters; this contract counts UTF-8 bytes.
        if self.stream is None:
            self.stream = self._open()
        message = self.format(record) + self.terminator
        return self.stream.tell() + len(message.encode('utf-8', errors='backslashreplace')) > self.maxBytes

    def handleError(self, record):
        # Disk/rotation failures must fail CI rather than silently discard evidence.
        raise

    def doRollover(self):
        super().doRollover()
        self.rotations += 1


def _handler(path, config):
    handler = _UTF8RotatingHandler(path, maxBytes=config.max_bytes,
                                   backupCount=config.backup_count, encoding='utf-8')
    handler.namer = lambda name: name + '.gz'
    handler.rotator = _gzip_rotate
    return handler


def run_logged(command, *, cwd, path, config, timeout, stats=None):
    """Stream merged output into bounded logs; always reap children and reader."""
    handler = _handler(path, config)
    tree = None
    process = reader = None
    errors = []
    try:
        tree = ProcessTree()
        env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        env.pop('PYTHONPATH', None)
        process = tree.start(command, cwd=cwd, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def collect():
            decoder = codecs.getincrementaldecoder('utf-8')(errors='backslashreplace')
            def write(text):
                if text:
                    handler.handle(logging.LogRecord('zzy.ci', logging.INFO, __file__, 0,
                                                     text, (), None))
            try:
                # At most 4096 output bytes even when every input byte needs escaping.
                while chunk := process.stdout.read1(512):
                    write(decoder.decode(chunk))
                write(decoder.decode(b'', final=True))
            except Exception as error:
                errors.append(error)
                tree.terminate()

        reader = Thread(target=collect, name='zzy-ci-log-reader', daemon=True)
        reader.start()
        status = process.wait(timeout=timeout)
    finally:
        try:
            # Reap descendants before waiting for a pipe they may still hold open.
            if tree is not None:
                tree.close()
        finally:
            try:
                if reader is not None and reader.ident is not None:
                    reader.join(timeout=5)
                if reader is not None and reader.is_alive():
                    raise RuntimeError('CI log reader did not stop')
            finally:
                if process is not None:
                    process.stdout.close()
                try:
                    handler.close()
                finally:
                    if stats is not None:
                        stats.update(rotations=handler.rotations,
                                     older_logs_discarded=handler.rotations > config.backup_count)
    if errors:
        raise errors[0]
    return status
