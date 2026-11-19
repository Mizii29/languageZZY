# N4-05 原生 Sketch headless 验收（2026-11-19）

本批完成对象拾取、复制、移动和删除，不可变 Drawing、图案导入和 ZZY 函数导出、项目 v1、独立回放状态以及回调和定时器登记。原生 check 沿用静态准备，核心 EXE 没有窗口库导入。前批几何证据见 [首批报告](n4-05-geometry-report.md)。

| 实测 | 结果 |
|---|---|
| CMake/CTest 4.5.0，VS 2022 MSVC 14.40，Windows SDK 10.0.22000，x64 Debug/Release | 各 80/80，含原生 Web 和 SQLite 回归 |
| `native_runtime/tools/test-sketch.ps1` | 两配置各 101/101，含固定 CLI、SVG、画笔、图层、对象、历史及资源探针 |
| `native_runtime/tools/test-sketch-project.py --exe … --python .venv/Scripts/python.exe` | 两配置 CTest 及 Release 安装副本各 8/8。Python 与原生双向读取项目和导出函数，拒绝损坏历史、非法目标、高水位和额外字段 |
| `native-library-tests sketch-replay` | 两配置均通过。分组、来回定位、取消、实时文档独立及配额归还 |
| 原生库存、Python Sketch 与相关 N4 接口回归 | 43 项通过 |
| Release 仓库外中文目录安装与 `install-smoke.ps1` | 9 条过程，另含文件/JSON 33/33、SQLite 50/50 与模块检查 |

Debug/Release 核心 EXE SHA-256 分别为 `8d189552c300c59e07a0036ec551dfc665875e6a0686fb6c8e76629e24f53f1c`、`d131588d64413e219404b43860f61631502f61fd271046ae125a9a0d54f7e95d`。这些是累计验收产物，包含独立 GUI 阶段同时构建时的能力字段。命令、原始日志与 SHA 位于 `dist/native-n4-05-complete/`。实际加载模块和静态导入的 GUI 专项见下一阶段报告。

原生项目的正 ID 高水位采用有符号 64 位字段，更大的外部项目 ID 会返回失败 Result。`save_png` 返回明确的缺后端 Result。构建时 MSVC 对增长后的解释器及其测试启用 `/bigobj`。历史入口的缺项目测试现在期望失败 Result，未支持命令 E402 的测试继续保留。未执行其他操作系统、Sanitizer、主机完全缺 CRT 和完整 Python 回归。
