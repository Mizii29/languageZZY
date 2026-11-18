# N3 Windows x64 正式证据

具体命令、环境、限制和分批结果见 [N3 验收报告](../../../../native_runtime/tests/n3-report.md)。本次在 CMake/CTest 4.5.0 和 MSVC 19.40.33812 上运行，两种配置各有 57/57 CTest、72/72 CLI、549/549 核心固定答案和 1 条显式延后。两配置另各有 70 条过程记录，其中 1 条为预期强杀超时。Release 的安装与源码外发布副本分别 9/9。

`debug/` 和 `release/` 中的 `.gz` 是原始记录逐字节压缩。包括 configure、build、CTest、既有核心固定清单、CLI 边界、所有相关测试产物 PE 导入、实际 CLI 模块与子进程、首轮 CRLF 断言失败报告。Release 另有两套安装 smoke。报告中的源码外工作目录及配置文件路径是当时的取证路径，不是复现时需要依赖的位置。
