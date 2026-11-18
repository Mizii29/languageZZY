# N2：原生静态前端验收（2026-11-18）

N1 的正式验收见 [MSVC 报告](msvc-report.md)。本轮只实现 N2-01—04，不实现求值；Python 仍为默认入口。静态语义以既有正式契约为准，新增观察接口集中在 [Program 契约](../../docs/development/native-program-contract.md)。

**最新状态：正式 CMake/MSVC Debug、Release 各44/44 CTest、安装、源码外副本和完整进程验收已补跑通过。** 下方直接构建及权限失败记录保留为历史；本页“正式补跑”节对应最新产物，不外推运行时求值能力。

## 完成范围

| 编号 | 实现与证据 |
|---|---|
| N2-01 | 全部56种 AST kind、源码半开范围、不可变发布、完整 Parser；固定优先级及 all-syntax 独立夹具 |
| N2-02 | global/local/self/capture、传递捕获、可变绑定 Cell 标记、块槽位、静态导出、完整规范路径模块图；菱形依赖、别名、循环和快照更新测试 |
| N2-03 | 首错、名称/控制流/查询纯性、精确 Int/Quantity 字面准备、有限 Float、Machine 图和前端预算/取消；没有新增静态类型系统 |
| N2-04 | 静默成功的 check 和确定性 program-info JSONL；默认值、函数、Lazy、spec、I/O、SQLite/GUI 名称的副作用探针 |

Program 只持有只读 AST、绑定布局、静态描述和源码快照，没有请求 Cell/Value/Frame、运行期容器/模块实例、字节码、磁盘缓存或隐式进程缓存。两个线程读取同一 Program 的测试只证明描述可并发读取，不代表尚未实现的请求执行隔离已经验证。run/test 仍在读取用户源码前 E402/2；不回退 Python。

## 真实验证

原始命令、逐例输出、退出码、失败原件和 EXE 身份保存在 [N2 证据目录](../../benchmarks/results/native/n2-20261118/)。固定期望取自既有外部清单、正式契约和独立手写断言，测试时不调用 Python 后端生成答案。

| 检查 | 结果及范围 |
|---|---|
| GCC 8.1 Debug 直接构建 | 成功；check 848/848、独立 Program 观察17/17 |
| MSVC 19.40 Debug/Release 直接构建 | 均成功；/W4 /WX /utf-8 /EHsc /permissive-；分别 /Od /Zi /MDd 和 /O2 /DNDEBUG /MD |
| 原生单元专项 | Program 10/10、前端12/12、堆12/12、协议3项；Program 空选择必须退出1 |
| PowerShell 固定清单 | 最终 Debug/Release 各词法87/87、check 850/850（848条原清单+2个独立探针） |
| CLI 边界 | Debug/Release 各62/62，check 成功静默，run/test 未实现诊断不变 |
| 独立 Program 观察器 | 17/17；56种节点、确定性、Unicode坐标、完整记录输出、首错与副作用 |
| Python 相关回归 | 108/108，39.672秒，无跳过；没有声称完整核心/Web/GUI 回归 |
| Release 仓库外中文空格路径副本 | smoke 9/9；空PATH、无效PYTHONPATH、无副作用；这是直接构建副本，非本轮正式 cmake install |
| 依赖证据 | 6个 Release EXE 的 PE 导入无 Python/GUI；实际运行 CLI 模块枚举无 Python/GUI；完整进程树验收未通过，见下文 |

各入口有意重复覆盖同一行为，不将上述数字相加宣传为独立语言用例总数。最新正式产物和源码指纹见[补跑审计](../../benchmarks/results/native/n2-msvc-20261118/audit.json)；旧失败报告使用旧 EXE 身份，不替换成最终哈希。

环境为本机 Windows 11 x64；已有 MSVC toolset14.40.33807、SDK10.0.22000.0，未安装工具链或修改系统 PATH。Release /MD 沿用官方 VC Runtime/UCRT；实际加载路径、版本和 SHA 见 loaded-modules.json。CLI 与 Program 测试保留8MiB主线程栈（按需提交），以容纳未优化构建的默认语法深度64；不是降低语言资源上限。

## 实际失败和修复

1. 首轮 GCC check 847/848：管道 callee 中的 @ 被误当普通直接参数；定位 Resolver，与已有固定期望一致修复后848/848。
2. 首轮 MSVC Debug check 844/848：默认1MiB宿主栈在语法深度边界耗尽；CLI/Program测试明确预留8MiB，再跑全部固定清单通过，未放宽深度断言。
3. 观察器首轮16/17：独立坐标夹具把已计数的列29写成28；核对原始源码码点逐个计数修正夹具，并保留失败文件。未以原生输出生成期望。
4. 过程验收先暴露 Program 测试 CRLF 与输出契约不符，统一调用 configure_streams；随后暴露旧取消测试依赖 Sleep(1) 的竞态，改为真实工作线程与原子握手。取消可能发生在扫描入口安全点，不声称必定发生在扫描中段。
5. Program 测试使用 MSVC convert API-set；dumpbin 确认实际依赖后精确增加官方 DLL 名称到白名单，未关闭检查或允许任意 DLL。
6. 首轮 aggregate 全部子测试成功但遗留故意失败探针的 LASTEXITCODE=1；显式成功退出0，重新执行最终集合。首轮静态检查发现本报告缺失，补文档后重跑。

## 补跑前的限制（历史记录）

- 当前会话对已有 CMake4.5.0 安装目录访问失败；不能启动其 exe，因此 N2 最新源码的正式 configure/build/44项 CTest/install **未验证**。N1 的32/32历史结果不外推到本轮。没有下载或使用未经授权的新工具链。
- acceptance.ps1 在 Get-CimInstance 进程树查询处被系统拒绝，完整报告保持 passed=false。已分别保留可观察的 PE 导入和实际 CLI 模块列表；不能用它们冒充完整进程树/过程验收通过。
- 用户再次说明有完整权限后实际复查，git add 仍因创建 .git/index.lock 被拒绝（退出128），索引保持空、HEAD未变。本轮本地提交未完成；不绕过访问控制、不建替代 Git 库、不推送。
- 真实手动 Ctrl+C、Sanitizer、其他平台/Windows10、缺CRT干净主机、完整 Python核心/Web/GUI 回归与性能未验证。N2 没有运行时求值；实际别名/请求状态隔离留 N3/N6。

上述权限限制在用户恢复访问后已解除，以下正式补跑闭合构建和过程验收；Git交付见最新日志。手动操作、Sanitizer及未涉及运行能力仍未验证。本轮不实现 N3。

## 正式补跑（2026-11-18）

实际命令、失败原件、收集清单、逐例输出、环境和产物指纹保存在独立的 [n2-msvc-20261118](../../benchmarks/results/native/n2-msvc-20261118/)；未覆盖旧 GCC/直接 MSVC 或 N1 证据。CMake/CTest4.5.0、MSVC19.40.33812.0、SDK10.0.22000.0，VS2022 x64、多配置生成器；无新增依赖、下载或系统 PATH 修改。

| 正式门禁 | Debug | Release |
|---|---:|---:|
| native-debug/native-release preset 配置及构建，BUILD_TESTING=ON | 退出0 | 退出0 |
| CTest实际收集并运行，--no-tests=error | 44/44，133.38秒 | 44/44，56.61秒 |
| PowerShell固定词法/源码清单 | 87/87 | 87/87 |
| PowerShell固定check清单 | 850/850 | 850/850 |
| CLI配置/诊断/资源/输出边界 | 62/62 | 62/62 |
| 独立Program固定观察器 | 17/17 | 17/17 |
| acceptance.ps1源码外过程验收 | 58条 | 58条 |
| 正式安装目录实际EXE smoke | 不发布 | 9/9 |
| 仓库外新建中文空格目录发布副本 smoke | 不发布 | 9/9 |

44项CTest包含原32项、Program固定清单1项、Program原生单测10项与空选择失败门禁1项。每配置58条过程记录是57条正常完成和1条预期强杀超时，后者单列，不冒充语言执行成功或RAII清理。两配置各6个EXE的PE导入、实际CLI模块及进程树已查，无Python/GUI；Release直接观察安装后的仓库外发布副本。空子进程PATH、无效PYTHONPATH、Unicode路径、静态check副作用探针与失败后恢复通过。

相关Python回归108/108、42.061秒、无跳过，命令见下文，原始输出python-regression.txt。独立audit.py核对每配置62个原生源码/夹具/脚本指纹、6个EXE、44项收集清单、安装及发布SHA和加载CRT文件；结果passed=true。项目static和diff检查见同目录static-delivery.json及最新开发日志。

| CLI产物 | SHA-256 |
|---|---|
| Debug | ea64b8a7e41c22f9b788bcc9db5b923802cab2e30b1c157afd6c7cf5486d5abd |
| Release / 安装 / 发布副本 | 4fc0ff350bfd911f77a3817735616326c509bad88214689bc8f8d592e1e8b56f |

Debug保持/MDd、/RTC1，仅用于开发；Release保持/MD，实际System32的VC运行库14.50.35719.0与UCRT10.0.26100.9711，路径/公司/版本/SHA见两份report.json。未私装或分发CRT，不声称缺CRT干净主机可运行。

补跑实际失败与修复：

1. 首次Debug CTest42/44：program-fixed在构建目录启动时，将诊断相对路径错误地按协调器目录解析。修复test-fixed.ps1按用例cwd解析；保留850条原断言、错误文件/位置期望，补充失败信息后重新全部通过。
2. frontend-default-boundaries超出60秒等待；单独实际运行72.218秒且退出0。仅将这个完整4Mi码点边界用例的CTest/acceptance等待上限改为180秒；保留/RTC1、L−1/L/L+1输入、语言资源上限和所有断言，未把超时算通过。ctest-debug*.txt和default-boundaries-timing.json保留失败与最终运行。
3. 恢复N1暂存补丁时，发现旧补丁拼接损坏无末尾换行的JSON边界；本地先提交后发现。已对照原始intended-index恢复证据字节，解析全部JSON，并以独立修复提交d537ce2保存，不改写历史。N1原CTest collection的尾空格原件另存raw.gz，结构等值核对后仅清除展示文件行尾空格；本轮同样保留原件。详细说明见failure-notes.md。

N0/N1构建门禁和N2-01—04技术出口现均满足。未验证的手动Ctrl+C、Sanitizer、其他平台/Windows10、缺CRT主机、完整Python核心/Web/GUI/wheel及性能继续保留；N2没有求值，多请求执行隔离和运行期别名行为留N3/N6。下一项N3-01，需要下一轮按用户范围开展。

## 复现命令

从仓库根目录 PowerShell 执行，所有证据 Output 使用新路径，逐步检查退出码：

```powershell
& native_runtime/tools/build-msvc-direct.ps1 -Configuration Debug
& native_runtime/tools/test-n2.ps1 -BuildDirectory build/native-n2-msvc-direct-debug -Output dist/n2-new-debug
& native_runtime/tools/build-msvc-direct.ps1 -Configuration Release
& native_runtime/tools/test-n2.ps1 -BuildDirectory build/native-n2-msvc-direct-release -Output dist/n2-new-release
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-program-observer.py --exe build/native-n2-msvc-direct-release/zzy-native.exe --output dist/n2-new-observer.json
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-cli.py --exe build/native-n2-msvc-direct-release/zzy-native.exe --output dist/n2-new-cli.json
& build/native-n2-msvc-direct-release/zzy-native.exe check native_runtime/tests/program/no-execute.zzy --diagnostic-format json
& build/native-n2-msvc-direct-release/zzy-native.exe program-info native_runtime/tests/program/all-syntax.zzy
& ./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_source tests.test_lexer tests.test_lexer_cli tests.test_cli tests.test_resources tests.test_diagnostics tests.test_native_program_contract native_runtime.tests.test_inventory -q
& ./.venv/Scripts/python.exe -X utf8 -m scripts.ci static --output dist/n2-static-new
git diff --check
```

正式 CMake/CTest/install 与源码外验收使用 [native README](../README.md) 的完整命令；应收集44项而不是沿用32项，必须带 --no-tests=error。正式产物是 build/native-debug/Debug 和 build/native-release/Release；上述 direct 目录不能冒用为正式 CMake 来源。
