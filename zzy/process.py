"""Bounded capture with owned process trees, including exceptional exits."""
import os
import signal
import subprocess
import tempfile
from threading import Event, Thread


class ProcessTree:
    """Start suspended on Windows so no descendant escapes job assignment."""
    def __init__(self):
        self.process = None
        self.job = None
        if os.name == "nt":
            from .windows_job import Job
            self.job = Job()

    def start(self, command, **kwargs):
        try:
            flags = ({"creationflags": kwargs.pop("creationflags", 0) | 4}
                     if self.job else {"start_new_session": True})
            self.process = subprocess.Popen(command, **kwargs, **flags)
            if self.job:
                self.job.assign_and_resume(self.process)
            return self.process
        except BaseException:
            try:
                self.close()
            finally:
                if self.process:
                    for stream in (self.process.stdout, self.process.stderr):
                        if stream is not None:
                            stream.close()
            raise

    def terminate(self):
        if self.job:
            self.job.terminate()
        elif self.process:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def close(self):
        try:
            self.terminate()
        finally:
            try:
                if self.process:
                    # Also handles a failure before job assignment.
                    if self.process.poll() is None:
                        self.process.kill()
                    self.process.wait(timeout=5)
            finally:
                if self.job:
                    self.job.close()


def run_bounded(command, *, cwd, env, timeout=10, output_limit=1024**2, stdin=b"", stderr_limit=None):
    """Capture exact bytes; timeout, cancellation and overflow always reap the tree."""
    stderr_limit = output_limit if stderr_limit is None else stderr_limit
    with tempfile.TemporaryFile() as input_stream:
        input_stream.write(stdin)
        input_stream.seek(0)
        return _capture(command, cwd, env, timeout, output_limit, stderr_limit, input_stream)


def _capture(command, cwd, env, timeout, output_limit, stderr_limit, input_stream):
    buffers = [bytearray(), bytearray()]
    exceeded = Event()
    read_errors = []
    tree = ProcessTree()
    process = None
    threads = []
    try:
        process = tree.start(command, cwd=cwd, env=env, stdin=input_stream,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def collect(stream, buffer, limit):
            try:
                while chunk := stream.read1(4096):
                    if len(buffer) + len(chunk) > limit:
                        exceeded.set()
                        tree.terminate()
                        return
                    buffer.extend(chunk)
            except Exception as error:
                read_errors.append(error)

        threads = [Thread(target=collect, args=(stream, buffer, limit), daemon=True)
                   for stream, buffer, limit in zip((process.stdout, process.stderr), buffers,
                                                    (output_limit, stderr_limit))]
        for thread in threads:
            thread.start()
        process.wait(timeout=timeout)
    finally:
        # Reap descendants even when the direct child exits successfully while a
        # grandchild still holds the output pipes. Never wait for those pipes first.
        try:
            tree.close()
        finally:
            for thread in threads:
                if thread.ident is not None:
                    thread.join(timeout=5)
            if process:
                process.stdout.close()
                process.stderr.close()
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("CLI output reader did not stop")
    if read_errors:
        raise AssertionError(f"CLI output read failed: {read_errors}")
    if exceeded.is_set():
        raise AssertionError("CLI output exceeded capture limit; not a passing truncated result")
    return process.returncode, *(bytes(buffer) for buffer in buffers)
