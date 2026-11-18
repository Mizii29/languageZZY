# N4-03 SQLite 原生验收

2026-11-19 在 Windows x64 完成 N4-03。原生版本 `0.0.0-n4-03-dev`，Python 默认入口和 P12/P13 保持不变。本阶段只接入 `db.transaction(String, Function)` 与 `db.query(String, Array)`，不进入 Web、Sketch 或 GUI。

实现位于 `native_runtime/include/zzy_native/sqlite_host.hpp`、`database_library.hpp`、`execution.hpp` 和 `core_hosts.hpp`。MSVC 默认 `ZZY_NATIVE_SQLITE=ON`；该宿主通过 `LoadLibraryExW` 固定从 `%SystemRoot%\System32\winsqlite3.dll` 导入经过审核的 SQLite API 表，程序不接收 DLL 路径或函数名，也不向仓库复制 DLL。`ZZY_NATIVE_SQLITE=OFF` 仍编译核心和静态识别 db 签名，执行时稳定返回 E402/1；MinGW 显式 ON 在配置期拒绝。

SQLite 依赖证据：Windows SDK `10.0.22000.0` 头文件声明 API floor `3.29.0`；本机 DLL 版本 `3.53.4`，source id 为 `2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc`，SHA-256 `a9148fbbbb59e40e0be60b6f0f85d286ac55a4558a8a3b1e4ccdcac41bfacfab`，路径 `C:\Windows\System32\winsqlite3.dll`，Authenticode `Valid`，签名主体 `Microsoft Windows`。系统组件由 Windows 更新负责，发布包不携带它。

每个事务创建同线程、按请求所有权的连接，执行 `BEGIN IMMEDIATE`；零参数回调必须返回 `Result`，成功 Result 在 transaction 返回前提交，失败 Result、ZZY 错误、取消或资源失败回滚并关闭。查询只能在当前事务内执行，参数使用绑定，只接受 Null、Int（有符号 64 位）、有限 Float 和 String；Bool、容器、Blob、原生句柄和越界 Int 不转换。authorizer 拒绝手工事务、SAVEPOINT、ATTACH/DETACH、PRAGMA 和加载扩展；多语句、错误 SQL、坏 UTF-8 和锁失败归 E401。每条查询包含准备、执行和逐行转换的 1 秒期限，进度回调每 1000 条 SQLite 指令观察取消；锁等待上限 250ms。SQLite 内部页缓存不冒充 ZZY 逻辑配额，连接预留对象/槽并在所有路径释放。

实际命令和结果：

```powershell
$env:Path = "$env:LOCALAPPDATA\Programs\CMake\4.5.0\bin;$env:Path"
cmake --preset native-debug -S native_runtime                 # 0
cmake --build build/native-debug --config Debug                # 0
ctest --test-dir build/native-debug -C Debug --output-on-failure --no-tests=error  # 75/75
cmake --preset native-release -S native_runtime               # 0
cmake --build build/native-release --config Release            # 0
ctest --test-dir build/native-release -C Release --output-on-failure --no-tests=error # 75/75
```

四个同进程 C++ 探针 `native-sqlite-tests.exe` 的 `lifecycle`、`cancellation`、`concurrency`、`resources` 在两配置均通过。它们固定验证：核心与 check 不加载 SQLite；真实提交/失败 Result/运行期错误后的回滚；重复关闭、Windows 文件可重命名、连接和逻辑配额归还；250ms 锁冲突；四个并发请求各自提交且不串状态；SQLite 进度取消、事务回滚和下一请求恢复；对象/槽/载荷上限及 `bad_alloc` 注入不跨越提交点。

独立 PowerShell 黑盒 `tools/test-sqlite.ps1` 以 50 个独立 `.zzy` 程序和外部固定答案通过，覆盖参数/类型/Int64 边界、Unicode 与持久化、事务回滚、SQL 限制、资源 L-1/L/L+1、超时、错误恢复、check 无副作用和空 PATH/无效 PYTHONPATH；脚本拒绝空集合并检查错误不泄漏 SQLite/Python 堆栈。Debug/Release 均为 `50/50`。`test-sqlite-modules.ps1` 在实际进程期间观察 System32 DLL、微软签名、无 Python/Tk/子进程，均通过。CLI acceptance 两配置各记录 82 个过程；Release 安装到新前缀并复制到仓库外中文/空格目录后，通用 smoke `9/9`、文件/JSON `33/33`、SQLite `50/50` 和模块检查均通过。

保留的回归证据：既有核心清单 Debug/Release 各 `550/550`，CLI 各 `72/72`；`.venv\Scripts\python.exe -X utf8 -m unittest tests.test_database native_runtime.tests.test_inventory tests.test_p05_cli -q` 实收 `379` 项、155.880 秒、无跳过、退出 0；`scripts.ci static` 和 `git diff --check` 实际通过。SQLite OFF 的独立 Release 构建执行 `sqlite-disabled` 与 `cli-info`，`2/2` 通过，`db.transaction` 不建库并返回 E402/1。

独立演示 `native_runtime/examples/sqlite.zzy` 连续运行两个新原生进程，第一次输出 `(^_^)([[1, 原生 SQLite 留言]])`，第二次输出两条记录，证明重启后的磁盘持久化。原生数据库文件在临时目录中，校园任务管家原有文件格式和 Python 应用未改。

未验证：真实人工 Ctrl+C、Sanitizer、其他操作系统、没有 Microsoft VC Runtime 的干净主机、Windows 更新后的所有 SQLite 版本组合、N4-04 Web、N4-05 Sketch headless、N4-06 GUI 和 N5 test。锁等待/SQLite 计算取消是协作边界；文件系统永久阻塞不承诺硬抢占。N4-03 已完成，不代表完整 N4。

最终 Debug/Release CLI SHA-256 分别为 `6b1a2c2a313738669f7caa3cf5e4a9f1ef5b3a21118ba3aa6bf3534e11971749`、`8c31073acfa2af1009a8036c20d214bf5dca74ad1a6bd452271a5b4b25d5277f`。CTest 两配置墙钟为 128.94/54.81 秒（各 `-j 2`）；数字是测试耗时，不是语言性能对照。Release `/MD`、Debug `/MDd` 保持，Debug 不发布，未安装工具链或修改系统 PATH。正式 CTest 收集清单、构建/安装/模块/失败记录及 152 个原生文件指纹在[证据归档](../../benchmarks/results/native/n4-03-msvc-20261119/README.md)中，审计报告同时确认 51 个无关用户文件指纹不变。原始工作目录保留；本轮无远端推送。
