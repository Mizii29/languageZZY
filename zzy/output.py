"""UTF-8 output budgets with a separate one-shot final diagnostic reserve."""

from .diagnostics import Diagnostic, ResourceExceeded, render
from .resources import ResourceMeter


class Output:
    def __init__(self, stdout, stderr, meter: ResourceMeter, format: str = "text"):
        self.stdout, self.stderr = stdout, stderr
        self.meter, self.format = meter, format
        self._final_written = False

    def write(self, text: str, *, stderr: bool = False):
        key = "stderr_bytes" if stderr else "stdout_bytes"
        size = 0
        for start in range(0, len(text), 4096):
            size += len(text[start:start + 4096].encode("utf-8", errors="backslashreplace"))
            self.meter.check(key, self.meter.used(key) + size)
        self.meter.consume(key, size)
        stream = self.stderr if stderr else self.stdout
        stream.write(text)
        stream.flush()

    def diagnostic(self, diagnostic: Diagnostic):
        self.write(render(diagnostic, self.format), stderr=True)

    def final(self, diagnostic: Diagnostic):
        if not self._final_written:
            self._final_written = True
            self.stderr.write(render(diagnostic, self.format))
            self.stderr.flush()

    def failure(self, diagnostic: Diagnostic):
        try:
            self.diagnostic(diagnostic)
        except ResourceExceeded as error:
            self.final(error.diagnostic)
