# N1：源码与词法 GCC 验收

**当前状态：** 本文保留先前GCC阶段原始范围。2026-11-18另已完成[正式CMake/MSVC补验收](msvc-report.md)，N0-03和N1构建门禁已补齐；下文的“待补/缺工具链”均为历史，不能当作当前状态。

2026-11-17开发，2026-11-18最终验收。**N1-01—04 实现与 GCC 验证完成，正式 CMake/CTest 验收待补。** 用户明确允许暂缓 N0-03 后先做 N1；N0-03 仍未完成，N0 总体出口未通过。本轮没有进入 N2，没有修改 Python 默认入口，没有安装工具链、推送或改写历史。

## 实现范围

- N1-01：不可变 UTF-8 Source、规范 Unicode 路径、原始字节/码点边界与行列、Token、source-info/lex。
- N1-02：全部现有固定拼写、最长匹配、Unicode15标识符/空白、ASCII数字、原/普通字符串、转义、注释和非法输入。
- N1-03：schema1诊断、0/2/130前端退出、BOM/CRLF/Tab/EOF/补充平面字符、动态default-v1、源码/Token/数字/文本/输出限制和协作取消。
- N1-04：原62词法固定期望不变，新增25固定夹具；真实进程、原生生命周期和独立边界公式；无空选择或超时误报成功。

公开命令/所有权/拒绝协议集中在 [native-frontend-contract](../../docs/development/native-frontend-contract.md)。info报告 N1，check/run/test 仍 E402/2；lex 不做 AST/Resolver、数值转换或业务执行。

## 匹配源码和产物的最终结果

| 验证 | Debug | Release | 证据 |
|---|---:|---:|---|
| GCC C++17、警告即错误直接构建 | 通过 | 通过 | build-debug.txt / build-release.txt |
| 原生过程/依赖/清理验收 | 47场景通过 | 47场景通过 | debug/report.json / release/report.json |
| 固定词法/源码清单（纯PowerShell） | 87/87 | 87/87 | fixed-*.json |
| 同一固定清单（Python开发协调器） | 87/87 | 87/87 | frontend-*.json |
| CLI/配置/输出/源码边界 | 62/62 | 62/62 | cli-*.json |
| 直接GCC EXE的源码外smoke | 6/6 | 6/6 | smoke-*.json |

以上不同入口有意重复检验同一保证，不相加宣传为独立语言用例总数。47场景中每种构建**各含1项故意强杀超时探针**（timed_out=true，目的为退出/恢复），与46条正常过程记录分列，不能算语言运行成功。前端原生12项与堆12项均包含在过程验收；前端空选择退出1，真实扫描线程取消及解码/行表/SHA取消点、费用归还和后续恢复均验证。

本轮 Python 前端/诊断/资源/源码/词法CLI与盘点回归105/105，33.644秒，无跳过。现有 scripts.ci static 退出0，requirement哈希/测试清单/Markdown/行数/git diff --check 门禁通过；不是核心全量回归、原生正式构建或安装成功。

原始报告都在 [benchmarks/results/native/n1](../../benchmarks/results/native/n1)。[独立审计](../../benchmarks/results/native/n1/audit.json)核对每种构建42个原生源码/配置/夹具指纹、5个EXE、固定/CLI/smoke报告的EXE SHA完全对应；未拿N0旧指纹代替N1。

- Debug CLI SHA256：739035e630423b2e001e287e664bb39627cb4a093e5fc9c5f189560fd331b9ac
- Release CLI SHA256：b4b9d8a2276380ed8649fb7f4df23d47998c02956fe85aa667c5d2271b7ac847

Windows11 x64、现有 MinGW GCC8.1.0/SEH/Win32；Debug -O0 -g，Release -O2 -DNDEBUG；-std=c++17/-Wall/-Wextra/-Wpedantic/-Werror，静态libgcc/libstdc++、系统msvcrt；wmain/-municode。环境/编译器哈希/选项见 environment.json。离线构建没有项目第三方库或下载；源码外临时目录含中文/空格，原生子进程 PATH空、PYTHONPATH无效。实际CLI的模块枚举/进程树，以及每个EXE的PE导入表均检查，无Python/GUI依赖；不外推尚未实现的语言worker或宿主进程树。

## 实际复现命令

从仓库根目录 PowerShell，对每个配置执行（所有Output须为新路径）：

```powershell
& native_runtime/tools/build-direct.ps1 -Configuration Debug
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-debug -Output dist/n1-new-debug
& native_runtime/tools/test-fixed.ps1 -Executable build/native-direct-debug/zzy-native.exe -Output dist/n1-fixed-new.json
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-frontend.py --exe build/native-direct-debug/zzy-native.exe --output dist/n1-frontend-new.json
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-cli.py --exe build/native-direct-debug/zzy-native.exe --output dist/n1-cli-new.json
& native_runtime/tools/install-smoke.ps1 -Executable build/native-direct-debug/zzy-native.exe -Output dist/n1-smoke-new.json
# 另执行Release，路径中的debug相应改为release，Configuration为Release。
& ./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_source tests.test_lexer tests.test_lexer_cli tests.test_cli tests.test_resources tests.test_diagnostics native_runtime.tests.test_inventory -q
& ./.venv/Scripts/python.exe -X utf8 -m scripts.ci static --output dist/n1-static-new
```

原始执行命令、stdout/stderr、退出码、超时、策略/源码/EXE指纹都在JSON报告中。临时目录只允许路径归一化，未屏蔽码点位置/错误码/输出值。固定期望来自正式契约、现有清单、独立十六进制夹具/SHA向量与边界公式，不调用被测原生或Python解释器生成期望。

## 失败与修复

1. 最初 inventory --check 漏路径，argparse退出2；正确显式清单复核后56 AST/103宿主/12 manifests/1738 cases一致。
2. GCC8.1的 std::filesystem 头/宽路径fstream不能编译；保留独立复现失败 failed-filesystem-build.json，改用 Win32 W API+RAII，不安装工具链。
3. 能力矩阵新增顺序断言误写，4项中1项失败；PowerShell未在非零时停止导致93e9c08已提交。随后准确修复并4/4，单独提交ed09e9e，不重写历史。
4. CLI边界首轮60/62，JSON格式选择和子命令help读取配置错误；失败原样在 failed-cli-boundaries.json（旧EXE身份），按现有CLI规则修复后最终两种构建62/62。未删除、放宽用例或静默跳过。

## 限制、保留工作与下一步

- N0-03与N0总出口未通过。CMake/CTest/MSVC/clang-cl缺失，未安装；正式configure/build/CTest/install、CRT分发、真实手动Ctrl+C、其他平台、sanitizer均未验证。CTest已登记32项但没有运行。
- 本轮未重跑完整Python核心、Web或GUI，相关实现未修改；不能用前端/无头结果代替它们。无性能/内存胜过Python/C的结论。
- Python默认入口/全部原测试/requirement保留；P12/P13状态及人工原件不变。审计确认15个其他已修改文件逐字节未变；共享文档仅本轮原生段落与追加内容入索引，既有应用/规划修改未一起提交。
- 下一项是对**最新代码**补 N0-03 正式门禁；本轮不进入N2。完整命令也在 [README](../README.md)：

```powershell
cmake --preset native-debug -S native_runtime
cmake --build build/native-debug --config Debug
ctest --test-dir build/native-debug -C Debug --output-on-failure --no-tests=error
cmake --preset native-release -S native_runtime
cmake --build build/native-release --config Release
ctest --test-dir build/native-release -C Release --output-on-failure --no-tests=error
cmake --install build/native-release --config Release --prefix dist/native-stage
& native_runtime/tools/install-smoke.ps1 -Executable dist/native-stage/bin/zzy-native.exe -Output dist/native-installed-smoke-new.json
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-release/Release -Output dist/native-cmake-external-new
```

以上正式命令是待补步骤，**没有预填通过**。MinGW CMake辅助preset也可按README分别完整执行，仍不能用direct结果代替。N2需要后续授权。

## 2026-11-18 正式构建补验收

最新代码MSVC Debug/Release各32/32 CTest、固定87/87、CLI62/62、47过程（46正常+1预期强杀）通过；Release安装与仓库外中文空格目录副本各9/9 smoke。PE导入、实际CLI模块路径/版本/哈希与进程树、空PATH/无效PYTHONPATH重新验证无Python；原有GCC证据保留。

本轮Python相关回归105/105、30.285秒。源码/产物/安装身份由[独立审计](../../benchmarks/results/native/msvc-20261118/audit.json)复核，完整环境/命令/失败修复与限制见[正式报告](msvc-report.md)。N0/N1技术出口满足；真实手动Ctrl+C、Sanitizer、clang-cl、其他平台及缺CRT主机仍未验证，未重跑完整核心/Web/GUI。下一项N2-01，本轮不实现。
