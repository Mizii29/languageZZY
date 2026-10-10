"""Subprocess isolation and bounded I/O shared by all external CLI cases."""

import subprocess
import tempfile
from threading import Event, Thread


def run_bounded(command, *, cwd, env, timeout=10, output_limit=1024**2, stdin=b"", stderr_limit=None):
    """Bounded concurrent capture for the P01 CLI, which spawns no children."""
    stderr_limit = output_limit if stderr_limit is None else stderr_limit
    with tempfile.TemporaryFile() as input_stream:
        input_stream.write(stdin)
        input_stream.seek(0)
        return _capture(command, cwd, env, timeout, output_limit, stderr_limit, input_stream)


def _capture(command, cwd, env, timeout, output_limit, stderr_limit, input_stream):
    buffers = [bytearray(), bytearray()]
    exceeded = Event()
    read_errors = []
    with subprocess.Popen(command, cwd=cwd, env=env, stdin=input_stream,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        def collect(stream, buffer, limit):
            try:
                while chunk := stream.read1(4096):
                    if len(buffer) + len(chunk) > limit:
                        exceeded.set()
                        process.kill()
                        return
                    buffer.extend(chunk)
            except Exception as error:
                read_errors.append(error)

        threads = [Thread(target=collect, args=(stream, buffer, limit), daemon=True)
                   for stream, buffer, limit in zip((process.stdout, process.stderr), buffers,
                                                    (output_limit, stderr_limit))]
        for thread in threads:
            thread.start()
        try:
            process.wait(timeout=timeout)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for thread in threads:
                thread.join(timeout=5)
        if any(thread.is_alive() for thread in threads):
            raise AssertionError("CLI output reader did not stop")
        if read_errors:
            raise AssertionError(f"CLI output read failed: {read_errors}")
        if exceeded.is_set():
            raise AssertionError("CLI output exceeded capture limit; not a passing truncated result")
        return process.returncode, *(bytes(buffer) for buffer in buffers)
