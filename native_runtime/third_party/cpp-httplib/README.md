# cpp-httplib, pinned native HTTP dependency

- Upstream: https://github.com/yhirose/cpp-httplib
- Version: **0.66.0**, commit `cdcd2ac6e6d5548b5a9130fb39ab76d2c6c614b0`.
- Header source: https://raw.githubusercontent.com/yhirose/cpp-httplib/v0.66.0/httplib.h
- License: MIT, preserved in `LICENSE` and the header.
- Unmodified `httplib.h` SHA-256: `51ddd1482c67acb31f3064e48329aade14acc7dd0fab31ee5397193697ea1c35`.
- `LICENSE` SHA-256: `4b45cbe16d7b71b89ae6127e26e0d90a029198ca5e958ad8e3d0b8bbed364d8b`.

Only the separate optional `zzy-native-web` executable includes this library.
TLS, compression, WebSocket, file mounts and proxy headers are not enabled by
the ZZY adapter. Winsock is the Windows transport dependency. No runtime Python,
GUI or network fetch at configure/build/install time. Source was retrieved from
the upstream tag on 2026-11-19. Upgrades require re-audit and new HTTP tests.
