# N5 原生 CLI、spec 运行器与发布验收

本报告记录 N5-01—05 的实现与证据。Python 仅作为黑盒编排器；被测 `zzy-native.exe` 不加载 CPython。

环境：Windows 11 x64 10.0.26200、CMake/CTest 4.5.0、VS2022 MSVC 14.40.33807（编译器 19.40.33812）、Windows SDK 10.0.22000、CPython 3.12.14（外部测试客户端）。集中规则见 [CLI 契约](../../docs/development/native-cli-contract.md)。

## 固定命令

```powershell
cmake --preset native-debug -S native_runtime
cmake --build build/native-debug --config Debug
ctest --test-dir build/native-debug -C Debug --output-on-failure --no-tests=error
cmake --preset native-release -S native_runtime
cmake --build build/native-release --config Release
ctest --test-dir build/native-release -C Release --output-on-failure --no-tests=error
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/test-cli.py --exe build/native-release/Release/zzy-native.exe
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/test-spec.py --exe build/native-release/Release/zzy-native.exe
```

## 已验证

- N5 spec/进程清单 19/19：空收集、收集错误、失败、超时、输出超额、文本诊断、stdin EOF/UTF-8、模块隔离、冻结源码快照、目录稳定顺序、真实控制台 Ctrl+C、worker 异常退出、强杀父进程后的 worker 结束和下一请求恢复。
- CLI 清单 83/83：公开命令、选项位置/缺失/非法值、限制边界、固定 lex/source-info 答案、失败恢复、无副作用 check、UTF-8 输出与错误诊断。
- native CTest 采用 `--no-tests=error`，并包含 `spec-process`、`cli-boundaries` 和 `native-ci-fingerprint`；源码指纹覆盖 C++/头文件/CMake/依赖/测试夹具及独立 native workflow。
- Release 安装 smoke 从源码外中文/空格目录运行；子进程 `PATH` 为空、`PYTHONPATH` 无效并移除虚拟环境变量。PE 依赖与实际加载模块没有 Python、PyPy、Tcl 或 Tk。

| 最终门禁 | 实际结果 |
|---|---|
| `native_ci.py --configuration Debug --output dist/native-n5/gate-debug-final2` | configure/build/CTest/install 全通过；83/83 CTest；源码外 CLI 83/83、spec 19/19、smoke 9/9，文件/JSON 33/33、SQLite 50/50 |
| `native_ci.py --configuration Release --output dist/native-n5/gate-release-final3` | 同上，83/83；整个门禁 116.063 秒（含构建/安装，非语言性能测量） |
| `acceptance.ps1 -BuildOrigin CMakeMSVC -Configuration Release … -Output dist/native-n5/acceptance-release-final` | 82 个过程场景达到固定期望，其中一项预期父进程强杀单列；不把强杀当作 RAII 清理 |
| `python -m unittest native_runtime.tests.test_inventory native_runtime.tests.test_native_ci -q` | 6/6 |
| `python -m unittest tests.test_p06_process -q` | Python 原实现真实 Ctrl+C/进程树专项 4/4 |
| `python -m scripts.ci static --output dist/native-n5/static-final` | passed=true |
| `.\.venv\Scripts\python.exe -X utf8 -m tests --report dist/native-n5/python-regression-final.json` | 2083/2083，896.648 秒，失败/错误/跳过/预期失败 0，退出 0 |

最终将 CI 的最小数量门槛从 82 收紧至 83（同时要求三个新增测试存在），再完整执行 `native_ci.py --configuration Debug --output dist/native-n5/delivery-debug` 和 Release 的 `delivery-release`，两者 passed=true，各 83/83，安装与 CLI/spec 专项再次通过。最终指纹与前述历史轮次不同仅因为门禁脚本修改，完整文件清单见这两份 source-fingerprint.json；所有 EXE 哈希保持上表值。远端 CI 尚未执行。

两配置最终代码指纹均为 `b32d81fde78f06a9af2d92bf3b09ea097d9824d9890337b678edac5c81ecdb13`。Debug 核心 EXE SHA-256 为 `46d9fc20d8d60ceaa0536ebd70d18e0edfe2807d84ab3d7738149deef357c927`；Release 为 `4e286d58fdb23a0141a55e3abe80a2c61825dcbf8c86da6ce4f6b4ee89106bb2`。原始记录位于 `dist/native-n5`，归档见 `benchmarks/results/native/n5-20261121`。指纹枚举当前工作区的测试客户端/夹具；用户原有未提交材料仍在，不能把整个工作区声称为干净提交。

正式 Release 发布目录：`C:\Users\13691\AppData\Local\Temp\ZZY 发布 中文 空格 0s8h59h3`，包含 `bin/zzy-native.exe`、独立 Web/GUI EXE 和上游许可证；Debug 安装仅开发验证。可复制到新的中文/空格路径后再次运行 install smoke。VC Runtime 沿用现有 Microsoft System32 运行库；具体加载路径、文件版本及哈希保留在 acceptance/module 原始记录中，不附带 Debug CRT。

仓库内便于交付的等价 Release 目录为 `dist/native-n5-release`，另一次 `cmake --install` 及 `release-directory-smoke.json` 通过 9 条 smoke、33 条文件/JSON 和 50 条 SQLite。此发布目录不依赖测试脚本，复制后执行 `bin/zzy-native.exe --help`。

## 实际失败与复验

超时 worker 被终止后，Windows 短暂保留 cwd/文件锁，初次临时池断言失败。先确认进程 Job 活跃数归零，再对目录做有界重试，正常完成清理失败明确报错；19 项回归和双配置最终门禁通过。新增快照夹具最初使用不存在的 `(zvar)` 与非导出模块字段，按现有语法改为 `(zyes)`/`<-` 和导出函数，未改语言规则。

第一轮门禁运行期间新增 Markdown 报告使旧指纹自我变化；门禁正确拒绝，保留 gate-*-1 原件。指纹随后集中覆盖构建/源码/依赖/夹具，验收 Markdown 不参与；最终开始/结束相同。Release 的 `gate-release-final2` 曾在已有 Web 断连恢复测试遇到 503 busy（82/83）；同一专项原断言重跑 1/1、完整 final3 为 83/83。未改 Web 实现或放宽断言；该历史偶发时序现象仍登记。

旧 acceptance DLL 白名单拒绝新快照文件流使用的 `api-ms-win-crt-filesystem-l1-1-0.dll`；保留失败 PE 导入报告后，按 dumpbin 证据加入这个确切 UCRT API-set，并重跑 82 项通过，未笼统开放任意 DLL。测试命令曾误写不存在的 `tests.test_p06`，以及直接按文件启动导致包导入失败；正式 `-m unittest tests.test_p06_process` 为 4/4。

## 未验证和边界

本轮未断开网卡，离线结论限于不下载依赖和受控代理；未在缺少 VC Runtime 的干净机器运行。Sanitizer、其他平台和人工终端 Ctrl+C 仍未验证。Debug `/MDd` 仅开发验证，Release `/MD` 由系统 VC Runtime 提供。

外部强杀父进程后已验证 worker 结束，但系统不能执行被杀父进程的目录析构，可能遗留临时目录；常规退出、失败、超时和 Ctrl+C 的临时池为空。GitHub 工作流仅在本地用同一入口运行，未推送/触发远端 CI。没有进行 N6 应用双实现迁移或性能优化。
