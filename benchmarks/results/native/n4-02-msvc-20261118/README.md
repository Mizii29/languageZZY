# N4-02 MSVC evidence archive

This directory contains preserved final configuration/build/CTest/install, acceptance, fixed-list, CLI file/JSON, and static-check outputs for N4-02. Raw records use `.gz` compression; decompress to obtain the exact original bytes. `failures/` preserves the first failed builds, CLI fixtures and acceptance attempts. The full working evidence remains in ignored `dist/native-n4-02-work`. The checked files were produced from the local `codex/native-runtime-plan` worktree on 2026-11-18.

- Windows 11 x64; PowerShell 7.6.9; CMake/CTest 4.5.0; VS2022 Build Tools; MSVC 19.40.33812.0; Windows SDK 10.0.22000.0; CPython 3.12.14.
- `ctest-debug-delivery.txt` and `ctest-release-delivery.txt`: 69/69 each, `--no-tests=error`.
- `library-*-delivery.json`: 126/126; `file-json-*-final.json`: 58/58; `files-cli-*-delivery.json`: 33/33; core fixed 550/550 and CLI 72/72.
- `acceptance-*-delivery/report.json`: 78 process cases each; Release install and external Chinese/space publication smoke (9 commands + 33 file/JSON cases each) are preserved.
- Final CLI SHA-256: Debug `456ac30822e762bfe8bc0d79d0aa3633495c4a6db9e2d953d2bf3112e8c2ab57`; Release `c416195bb2959736a57c9ef374efab14f1839d2075f2e3cb33027b4ed3054c6d`.
- `ucrt-reviewed.json` and `library-reviewed-imports.txt` record the signed Microsoft UCRT and the precise filesystem API-set used only by the native library test executable.
- `audit.json` verifies current native source fingerprints (145 files), all 9 executables per configuration, fixed counts, installation/publication hashes and all 89 compressed original records. Source normalization matches the PowerShell producer: remove UTF-8 BOM and normalize CRLF to LF.

Manual Ctrl+C, Sanitizer, other platforms, clean machines without VC Runtime, optional hosts, N5 test and performance remain unverified.
