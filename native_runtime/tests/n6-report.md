# N6 双后端与应用兼容验收

前置基线为本地 N5 提交 `69eedc3` 及 N4 核心和宿主报告。N6 默认配置使用 Windows x64、MSVC SQLite ON、独立原生 Web/GUI 以及 Python 3.12.14。每个后端分别读取同一份版本控制固定答案。宿主专项引用各自适用的固定期望及生命周期探针，重叠场景分表统计。

## 外部保证映射

| 领域 | 固定期望及原生可执行证据 |
|---|---|
| 词法、语法、类型、名称和诊断 | `tests/lex`、`check`、`run`、`p02` 至 `p06` 的固定清单。`external-parity` 使用清单原 cwd、输入、配额、输出上限、期限及错误文件/区间/备注。`program-fixed`、`frontend-fixed` 及 `program-*` 覆盖源码快照、绑定和 check 无副作用 |
| 运行顺序、数值与对象 | 同一清单覆盖整数/浮点/布尔区别、求值、别名、闭包、Lazy、Result、查询/稳定排序、Machine、Quantity。`execution-*`、`runtime-values-*` 与 `heap-*` 覆盖失败取消清理、环回收、配额压力及下一请求 |
| 文件、JSON、spec 与安全退出 | `cli-boundaries`、`file-json-integration`、`library-file-commit`、`library-json`、`spec-process`、`lifecycle-*` 覆盖固定提交点、资源耗尽、真实控制台取消、快照/进程隔离及恢复。Python 路线使用 `tests.test_p06_process`、原有资源/文件回归 |
| 校园应用 | `campus-parity` 复用 P09 固定断言，涵盖菜单、校验矩阵、EOF、CRUD、稳定视图/TSV、历史、容量、取消及保存恢复。实际 Windows 文件共享冲突验证读写失败与状态保留。Python 的定点 write/close/replace 模拟仍由原测试提供，原生 `library-file-commit` 核对提交边界。`persistence-parity` 双向验证固定 UTF-8 v1 文件及重启 |
| SQLite | 原生 `sqlite-fixed`、`sqlite-*` 与 Python `tests.test_database` 验证参数、事务回滚、并发、配额、取消/连接释放。`persistence-parity` 让一端写入、另一端重开，并以独立 SQLite SELECT 和 integrity_check 核对固定行及数据库完整性 |
| Web / OpenAPI | 原生 `web-http`、Python `tests.web_http` 对真实 TCP 分别验证路由、严格 JSON、默认/shared、并发隔离、冻结、请求容量/超时/断连恢复、关闭、shape/OpenAPI 和 SQLite 事务及重启。测试数量单位为各自的测试方法，不能按 1:1 对齐。Python ASGI startup/embedding 内部接口有独立现有测试 |
| Sketch headless | `tests/e1` 至 `e4` 全量原清单，原生 `sketch-geometry-fixed` 另核对 SVG 及对象回收、撤销和重做、图层、事件注册与定时配额。`sketch-project-fixed` 双向互读 v1、函数导出、历史、损坏拒绝和恢复 |
| GUI | 原生 `test-sketch-gui.py` 实际 HWND 及像素，Python `tests.gui_sketch` 实际 Tk。对照输入/事件、导出/历史、关窗与下一次运行，按各控件接口使用固定期望。两者均由自动化操作真实桌面 |
| 安装与无 Python | `native_ci.py` 的 install、PE、installed-cli、installed-spec 与 SQLite 模块枚举。空 PATH 与受控 PYTHONPATH，在源码外中文目录执行。旧 N5 人工/系统环境限制继续单列 |

## 差异处理

| 分类 | 现象 | 处理与固定复验 |
|---|---|---|
| 测试驱动 | 首轮原生缺失文件与中文相对路径两例失败，驱动把相对路径改成基于仓库根的绝对路径 | 传入原始 `file` 和 `cwd`，缺失文件的源码哈希留空。原 1738 断言和诊断文件字段均保留 |
| 原生实现 | 9999/10000 项校园容量测试各超过原 180 秒期限，诊断性放长到 600 秒仍超时 | 堆中容器持有的可达子对象没有独立根引用，不能用“节点数减根数”近似垃圾量。按上次回收后的分配次数做主动回收，配额不足仍立即扫描并原子预留。保留 180 秒期限和三个相邻容量断言。Release 的三个容量场景合计 55.625 秒通过，原文件格式与额度保持 |
| 契约 | 原生入口、Python 嵌入 API 与桌面后端采用不同宿主接口 | 对外相同的值、诊断结构、状态和文件内容独立断言。Python 包嵌入 API 的原生等价接口、PNG 成功导出仍在能力矩阵之外。PNG 返回失败 Result 的现有负例仍执行 |

## 验收结果

| 集合 | 总量 | 适用 | 通过 | 失败 | 超时 | 延期 |
|---|---:|---:|---:|---:|---:|---:|
| 既有 CLI，原生 Release | 1738 | 1738 | 1738 | 0 | 0 | 0 |
| 既有 CLI，Python | 1738 | 1738 | 1738 | 0 | 0 | 0 |
| 校园固定场景，原生 Release | 21 | 21 | 21 | 0 | 0 | 0 |
| 校园固定场景，Python | 21 | 21 | 21 | 0 | 0 | 0 |
| 校园 JSON 和 SQLite 双向互读 | 4 | 4 | 4 | 0 | 0 | 0 |
| 原生 SQLite 独立集成 | 50 | 50 | 50 | 0 | 0 | 0 |
| 原生 Web / Python Web | 6 / 23 | 6 / 23 | 6 / 23 | 0 | 0 | 0 |
| 原生 Sketch 固定场景 / 项目互读步骤 | 101 / 8 | 101 / 8 | 101 / 8 | 0 | 0 | 0 |
| 原生 HWND / Python Tk 自动化场景 | 4 / 11 | 4 / 11 | 4 / 11 | 0 | 0 | 0 |
| Python 校园、前置与数据库回归 | 53 | 53 | 53 | 0 | 0 | 0 |
| Python Sketch 内部与外部专项 | 24 | 24 | 24 | 0 | 0 | 0 |
| 最终 CTest，Debug / Release | 86 / 86 | 86 / 86 | 86 / 86 | 0 | 0 | 0 |
| 原生额外能力，PNG 成功导出和 Python 嵌入接口等价项 | 2 | 0 | 0 | 0 | 0 | 2 |

两端 CLI 各自对照 12 个保留清单，原生通过率不包含延期项。容量首轮的 2 个超时按子用例列在历史证据中。最终报告按上表各自的用例或测试方法统计，避免重复加总。Web 和桌面自动化使用实际网络/窗口，但当前工作区没有新增人工验收结果。

最终门禁使用 Windows 11 x64 26200、CMake 4.5.0、VS2022 MSVC 14.40 和 SDK 10.0.22000，代码提交 `ac8f373`。Debug 和 Release 的源码指纹均为 `a44e9254534f6fc16c9e91bbf8aa7b3a3da11f1de4df5c866e2f00be7a46694b`。核心二进制 SHA-256 分别为 `22f191532f2efb3433a886e80e29088c1c32d4bf9ac1e8606dd5d0d359f55b46` 和 `f697f08b0336bb34522ff036ca98cb7d72e2cf1adbb3993d940ae25e43279add`。每配置源码外安装之后的 CLI 83/83、spec 19/19、smoke 9/9、文件/JSON 33/33 和 SQLite 50/50 均通过。Release 安装副本的 HWND 复跑为 4/4。静态检查通过，远端 CI 本轮未运行。

最初 Debug 的 CTest 外层 900 秒期限耗尽。第二轮 CTest 86/86，通过安装检查后因脚本和指纹输入在运行期间更新而拒绝整体结果。最终使用固定版本重跑，Debug 和 Release 门禁均成功，耗时约 341.20 和 244.39 秒。最终可用的命令仍使用原来的清单期限，调高的是整个 CTest 进程的外层期限。

原始证据可在 `dist/native-n6/delivery-debug` 与 `dist/native-n6/delivery-release` 查阅。压缩记录包含逐例输入来源、实际诊断、超时和安装报告，按原始内容 SHA-256 校验。[证据索引](../../benchmarks/results/native/n6-20261121/manifest.json)

## 复现

```powershell
$native = 'build/native-release/Release/zzy-native.exe'
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/test-parity.py --exe $native --backend both --output dist/native-n6/parity-new
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/test-campus.py --exe $native --backend both --output dist/native-n6/campus-new
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/test-persistence-parity.py --exe $native --sqlite ON
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/native_ci.py --configuration Release --output dist/native-n6/release-new
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/native_ci.py --configuration Debug --output dist/native-n6/debug-new
```

桌面窗口单独执行 `test-sketch-gui.py --exe <GUI EXE> --core <CLI EXE>` 和 `python -m tests.gui_sketch`。人工逐项操作、缺 VC Runtime 的干净机器、其他平台、Sanitizer 与物理断网没有本轮验收证据。校园原工作区的 P12 批量修改保留，证据中的应用哈希记录了实际受测内容。
