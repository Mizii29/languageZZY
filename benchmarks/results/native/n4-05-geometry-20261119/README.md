# N4-05 首批原生画笔证据

2026-11-19，几何、图层、历史与 SVG 子集，N4-05 整项未完成。实现及命令见 [专项报告](../../../../native_runtime/tests/n4-05-geometry-report.md)。

`index.json` 列出 42 份原始记录的相对路径、解压后字节数及 SHA-256；`raw/` 是 gzip 无损归档。保留 debug-first.json 的失败记录，不能把它算为最终通过。`audit.json` 记录本轮源码、EXE、发布副本及 requirement 指纹。

两配置 CTest 各 78/78，后补线程探针后库回归各 11/11；核心固定清单各 550/550；发布副本画笔 71/71。通用 acceptance 复用已有 N4-03 脚本并记录 CMake/MSVC 来源，其报告 scope 沿用该基础门禁，Sketch 验证由单独黑盒、同进程探针及 drawing-modules.json 提供。各 82 条过程中的预期父进程强杀独列，不能证明资源归还。

人工 Ctrl+C、GUI、Sanitizer、其他平台、全量 Python 回归及性能未验证。此归档不宣称原生 Sketch 1.0 或完整 N4-05 已验收。
