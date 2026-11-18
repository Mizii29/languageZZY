# N0-03 / N1 正式 CMake/MSVC 验收

2026-11-18，分支 `codex/native-runtime-plan`。候选起点为 `2cb4649c2675c5b198b2642fec44651f0107c9bc`，加本轮协议测试与验收脚本修改；原生源码和产物身份由原始报告逐项固定。本轮没有进入 N2，没有修改 Python 默认入口、语言语义、requirement 或 P12/P13 状态。

N0-03 和 N1 的正式构建技术门禁通过，先前“缺工具链/只通过GCC”的结论为历史。[N0报告](n0-report.md)、[N1 GCC报告](n1-report.md)与全部旧失败原件保留。本地提交状态以开发日志为准。

## 环境与实际产物

- Windows 11 x64，系统版本 10.0.26200；PowerShell 7.6.9。
- CMake / CTest **4.5.0**，使用用户已有 `C:\Users\13691\AppData\Local\Programs\CMake\4.5.0\bin`，仅当前命令会话添加 PATH。
- VS Build Tools 2022 / MSBuild 17.10.4，生成器 `Visual Studio 17 2022`，架构 x64。
- MSVC 工具目录 14.40.33807，`cl.exe` 文件版本 **19.40.33812.0**；Windows SDK **10.0.22000.0**。C++17，保留 `/W4 /WX /utf-8 /EHsc /permissive-`。
- Debug `/MDd`，Release `/MD`；CMake 默认 Debug `/Od`、Release `/O2 /Ob2 /DNDEBUG`。没有更改 CRT 方案，没有下载、安装编译器或运行库，也没有修改系统 PATH。
- 无项目级第三方库，configure/build/CTest/install 没有下载步骤。Python 只作额外开发测试/证据审计的协调器，CMake、CTest固定清单和发布程序不依赖 Python。

环境与编译器哈希见 [environment.json](../../benchmarks/results/native/msvc-20261118/environment.json)，构建过程日志和收集清单在同目录。

| 产物 | 位置 | SHA-256 |
|---|---|---|
| MSVC Debug CLI | build/native-debug/Debug/zzy-native.exe | 659854eb460ae5a5efa10cd7845cee54b2a827f0a15c39a9a0fe0d9d17eb831c |
| MSVC Release CLI | build/native-release/Release/zzy-native.exe | d9928c543d28a353b5213414b23b4439404d7927d1ebfc253c25841034c7368f |
| 正式安装及源码外发布副本 | dist/native-stage/bin/zzy-native.exe；外部路径见 published-path.txt | 与 Release CLI 相同 |

外部发布目录为 `C:\Users\13691\AppData\Local\Temp\ZZY Native Published 20261118 中文 0582b719152c476f9644b6a5056524b8`，只含 Release CLI，不包含测试 EXE、Python、虚拟环境或 Debug CRT。临时目录保留供复核，后续若被系统清理，应按 README 在新目录重建，不把旧路径存在视为永久保证。

## 实际门禁与数量

| 验证 | Debug | Release | 原始证据 |
|---|---:|---:|---|
| CMake preset 配置和构建，BUILD_TESTING=ON | 通过 | 通过 | configure-*.txt / build-*.txt |
| CTest真实收集与执行，--no-tests=error | 32/32，45.82秒 | 32/32，9.38秒 | collection-*.json / ctest-*.txt |
| 固定词法/源码清单，纯PowerShell | 87/87 | 87/87 | fixed-*.json |
| 相同固定清单，Python开发协调器 | 87/87 | 87/87 | frontend-*.json |
| CLI、limits配置、资源与输出边界 | 62/62 | 62/62 | cli-*.json |
| 源码外过程/堆/前端/生命周期及无Python | 47记录 | 47记录 | debug/report.json / release/report.json |
| 安装目录实际EXE smoke | 不分发Debug | 9/9 | installed-smoke.json |
| 仓库外中文空格目录发布副本 smoke | 不分发Debug | 9/9 | install-smoke.json |

这些入口存在有意重复，不相加宣传为独立用例总数。32项CTest明确为：固定清单1、原生前端12、协议1、CLI2、堆12、生命周期4。纯PowerShell固定清单的87项来自原62项及新增25条独立期望，未减少用例或修改原有期望。

每种47过程记录分别含 **46条正常完成记录 + 1条预期强杀超时记录**。该条 timed_out=true，保留真实退出码、process_exited及恢复结果；不是语言执行成功，也不能证明强杀会执行 C++ RAII。协作取消/异常后的对象、槽位和载荷三项清零与下一次成功另有独立测试。空堆/前端选择均非零；真实扫描线程取消和解码/行表/SHA取消安全点已验证。

安装与发布副本分别运行 info/source-info/lex、check/run/test，以及三项固定副作用源码的拒绝检查。后两类都必须 E402/2、stdout为空，且没有生成 native-side-effect.txt。每个子进程 PATH为空、PYTHONPATH无效，工作目录在仓库外。

相关 Python 回归实际命令为：

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_source tests.test_lexer tests.test_lexer_cli tests.test_cli tests.test_resources tests.test_diagnostics native_runtime.tests.test_inventory -q
```

**105/105，无跳过，30.285秒，退出0**，见 python-regression.txt。文档与交接完整落地后，现有项目static门禁再次passed=true/退出0，git diff --check退出0，见[最终静态报告](../../benchmarks/results/native/msvc-20261118/static-delivery.json)。未运行的门禁不能由本表推断通过。

## 依赖、CRT与源码外运行

先用已有 VS 的 `dumpbin /dependents` 检查每种配置5个EXE，再更新 acceptance.ps1 的精确直接导入白名单。没有允许任意DLL，也没有用MinGW标签描述MSVC。

- Debug直接导入：KERNEL32、MSVCP140D、VCRUNTIME140D、VCRUNTIME140_1D、ucrtbased。
- Release直接导入：KERNEL32、MSVCP140、VCRUNTIME140、VCRUNTIME140_1；另为明确列出的 `api-ms-win-crt-{runtime,stdio,heap,math,locale}-l1-1-0.dll`，不是API-set通配放行。
- 实际CLI在词法输出管道形成稳定观察点时枚举模块及子进程。模块名、加载路径、文件版本、公司与SHA均在report.json的module_details内；同一Release发布副本直接接受观察，不用仓库内EXE代替。
- 已有系统 `C:\Windows\System32` 加载的Release VC库均为 **14.50.35719.0**，公司字段Microsoft Corporation；VC runtime注册表为 `v14.50.35719.00`。系统ucrtbase为 **10.0.26100.9711**。Debug VC库为 **14.40.33810.0**，ucrtbased为 **10.0.22000.832**。没有复制这些库到发布目录或重新安装。
- 上述“来源”指实际加载路径与本机已有VC runtime登记，不声称追溯了旧安装包的下载来源。未测试缺CRT机器，不承诺一个EXE可在没有VC runtime的任意Windows运行。
- PE导入、实际模块和进程树均没有Python或GUI运行库。个别进程出现Windows控制台辅助 `conhost.exe`，依既有规则单列，不视为语言子进程；仍拒绝其他未登记子进程。未来原生test worker或宿主进程尚未实现，不能外推其进程树。

## 修复及失败保留

1. 首次Debug构建失败：协议测试的常量条件触发MSVC C4127，`/WX`导致C2220。原始 [build-debug-first.txt](../../benchmarks/results/native/msvc-20261118/build-debug-first.txt)保留；改成等价static_assert，保留退出码协议和警告即错误。随后Debug构建/32项CTest、Release构建/32项CTest与全部专项通过，没有重写Lexer。
2. 发布复制命令最初将通配符用于Copy-Item -LiteralPath，复制未发生。保留空的首次临时目录，改为Get-ChildItem枚举再Copy-Item；使用全新目录与新smoke报告，未把空发布目录当作通过。安装命令本身退出0。
3. 开发用证据审计最初误要求子进程严格空列表；实际仅有已按规则分类的conhost。按既有验收规则精确核对该系统辅助进程，没有放行其他子进程。随后发现.NET ReadAllText去除UTF-8 BOM，而Python首次审计未去除，修正开发协调器的相同文本规范化后，逐项匹配42个原生文件和5个EXE；验收脚本与产物未因此更改。审计失败信息见 failure-notes.md，未篡改原始report。

独立审计命令及[结果](../../benchmarks/results/native/msvc-20261118/audit.json)：

```powershell
& ./.venv/Scripts/python.exe -X utf8 benchmarks/results/native/msvc-20261118/audit.py
```

## 复现、未验证范围及出口判断

完整逐步命令见 [README](../README.md)。所有Output使用新路径，失败立即检查退出码；不能覆盖旧报告、禁用测试或把空集合算通过。

真实手动Ctrl+C、Sanitizer、clang-cl、其他OS/架构、Windows10实机、缺CRT干净主机均未验证；本轮未重跑全Python核心、Web、GUI、wheel安装或性能测量。前端相关回归不能替代它们，也没有相对Python/C的性能/内存结论。

按原生计划，N0出口为离线构建、非空CTest、冻结决策、环回收/配额及明确拒绝无回退；N1出口为固定词法、位置/中文空格路径、无Python、坏输入非崩溃。以上技术出口均满足。人工Ctrl+C等仍是显式未验证边界，不是把N5/N8发布或人工验收提前标为通过。下一项为 **N2-01 Parser/AST**，本轮停止，不提前实现。

本地Git交付仍受限：当前会话将.git设为只读，实际git add创建index.lock返回Permission denied；没有暂存或新提交，HEAD仍为2cb4649。本轮专属补丁dist/native-msvc-work/reviewed.patch与文件清单已准备，并通过git apply --check --cached校验；共享文档只包含本轮原生差异。应先在允许Git写入的会话完成审查和本地提交，再进入N2，不要整体暂存用户已有修改。
