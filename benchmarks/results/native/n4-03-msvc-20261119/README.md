# N4-03 SQLite MSVC evidence

Raw command outputs and reports use gzip compression, preserving their original bytes. Full local working originals remain in ignored `dist/native-n4-03-work`; old N4-02/GCC evidence is untouched. `audit.json` checks source and executable hashes, test counts, installation/publication identity and preserved user files. It does not infer manual acceptance from automatic results.

- MSVC Debug/Release: 75/75 CTest each, all 69 previous tests retained; `BUILD_TESTING=ON` and `--no-tests=error`.
- SQLite: four same-process named probes plus nonempty selection gate; 50 CLI fixed answers per configuration. Actual CLI modules record the reviewed System32 SQLite component, Microsoft signature, no Python/GUI and no child process.
- Existing core fixed selection: 550/550 per configuration; existing CLI: 72/72. Python related tests: 379, no skips.
- Release install/publication: 9 general smoke cases, 33 file/JSON and 50 SQLite fixed cases, actual published-copy module inspection.
- SQLite OFF Release: `cli-info` and `sqlite-disabled`, 2/2. This is an explicitly selected OFF gate, not full OFF CTest.
- `acceptance-*-final/report.json` contains 82 records each: 81 normal expected results and one separately recorded parent-enforced timeout/kill. A killed process is not evidence of destructor cleanup; the in-process probes provide that evidence.
- `build-sqlite-first.txt` preserves the failed test compilation (Windows SDK `small` macro collision). `sqlite-debug-first.json` preserves the invalid test-only NUL escape; `sqlite-debug-second.json` preserves the incorrect stdout resource-location expectation. Both were corrected against existing syntax/diagnostic contracts, without changing product rules.
- First resource-injection trial printed `allocation failure was not injected` in the tool transcript. This was a test hook defect; final tests reserve capacity at a fixed context boundary and directly verify rollback, zero accounting and the next request. The transcript-only failure is described here, not presented as an independently saved raw log.

DLL source id and signature are recorded in `sqlite-version.txt` and `sqlite-dependency.json`; `dependencies.json` in the project records the system component strategy. OS patches may change the DLL and require renewed evidence. No dependency was downloaded or installed.

Unverified: real manual Ctrl+C, Sanitizer, other OS/older Windows, clean hosts without VC Runtime, all possible system SQLite versions, native Web/Sketch/GUI, N5 test and performance. The next task is N4-04 Web.
