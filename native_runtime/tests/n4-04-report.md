# N4-04 原生 Web 验收

2026-11-19，Windows x64；CMake/CTest 4.5.0，VS Build Tools 2022 / MSVC 14.40.33807，Windows SDK 10.0.22000.0，CPython 3.12（测试客户端）。依赖锁定 cpp-httplib 0.66.0 / MIT，详见[源码记录](../third_party/cpp-httplib/README.md)。新增可选 `zzy-native-web.exe`，业务依旧由 ZZY 处理；核心 `zzy-native.exe` 维持既有命令/版本，Python 仍是默认入口。

`web_main.cpp` 负责连接、固定路由、容量、超时和响应；`web_runtime.hpp` 桥接每请求 ExecutionContext、严格 JSON 与服务持有的冻结图；`web_contracts.hpp` 从 AST 和 Resolver 绑定编译同一份布局，供校验、缺省值填充和 OpenAPI 使用。详见[集中契约](../../docs/runtime/web.md#n4-04-原生-http-宿主)和[启动演示](../README.md#原生-web-演示)。

| 检查 | 结果 |
|---|---|
| `cmake --preset native-debug -S native_runtime` / `cmake --build build/native-debug --config Debug -j 2` / `ctest --test-dir build/native-debug -C Debug --output-on-failure --no-tests=error -j 2` | 76/76，通过，100.39 秒 |
| `cmake --preset native-release -S native_runtime` / `cmake --build build/native-release --config Release -j 2` / `ctest --test-dir build/native-release -C Release --output-on-failure --no-tests=error -j 2` | 76/76，通过，47.92 秒；最终版 HTTP 单项另复跑 1/1 |
| `python -X utf8 native_runtime/tools/test-web.py --exe build/native-debug/Debug/zzy-native-web.exe --sqlite ON` | 6/6 分组，无跳过；包含两个 handler 互相等候证明执行交错 |
| `cmake --install build/native-release --config Release --prefix dist/native-n4-04-work/install` | 两个 exe 和 MIT 许可证；复制到仓库外中文空格目录 |
| 发布副本 `install-smoke.ps1` 及 `test-web.py --exe <发布副本> --sqlite ON` | 核心 9/9、文件/JSON 33/33、SQLite 50/50 及模块检查；Web 6/6，空 PATH、无效 PYTHONPATH，合成控制台信号正常关闭 |
| `cmake -S native_runtime -B build/native-web-off -G "Visual Studio 17 2022" -A x64 -DZZY_NATIVE_WEB=OFF -DBUILD_TESTING=OFF` / Release 构建 / `zzy-native.exe check examples/web/app.zzy` | 通过；无 Web 产物 |
| `python -X utf8 -m tests.web_http`；`python -X utf8 -m unittest native_runtime.tests.test_inventory tests.test_embedding tests.test_contracts -q` | 23/23 和 29/29，通过，无跳过 |
| 独立 Draft 2020-12 校验 | 4/4 固定判断：普通输入、必填、未知字段、标准接受 1.0；实际原生 HTTP Int 拒绝 1.0 |
| `dumpbin /dependents`、`Get-Process .Modules` 与 CIM 子进程 | Debug、Release 和发布副本均过；Web 使用 WS2_32，无 Python/Tk；仅系统 System32 conhost.exe，核心无 WS2_32 直接导入 |

Web 固定测试覆盖：示例页面和同源 GET/POST、404/405、请求元数据顺序与重复、Chunked、严格 JSON、Int 安全边界、无效 Response、资源超限和恢复；shape 的嵌套路径、字面默认、未知键、Null 与严格数值、启动静态拒绝及生成零副作用；shared 冻结 Array/Map/嵌套 Machine、拒绝 Lazy/捕获 Cell/可变绑定/命名空间别名、真实请求交错和独立默认值；慢速读体、容量、执行超时、断连、合成 Ctrl+C 后销毁；SQLite 提交、失败与取消回滚、关闭重启后的持久化。

Web EXE SHA-256：Debug `c271356d2b8a394e3392d976ecb5dbbbfbec6715b1abf5dd15ab0aac4551c486`；Release、安装及仓库外副本 `5085d1ff0119068e2211c1f446ffae5e2ff485d5baed4fcc1a76d6c635fea659`。Debug /MDd 仅用于测试；Release /MD 使用系统 UCRT 和本机已装的 Microsoft VC Runtime。证据文件在 `dist/native-n4-04-work/`：`debug.log`、`release.log`、`web-*.log`、`install.log`、`core-published.json`、`audit.json`。

调试记录：首次 MSVC 编译发现本地配置类型与继承的 `Options` 同名，修正命名；Debug 对象节数超限，局部开启 `/bigobj`。测试夹具把 `raw` 用作函数名导致静态失败，改用合法名；随后慢速收体驱动仅读一个 TCP 分段，修复为完整消费临时响应。首次模块审计误把系统 `conhost.exe` 当作应用启动的依赖，复查全路径后只接受 System32 的系统控制台子进程。固定 HTTP 期待未放宽。

未执行：真实人工浏览器操作和亲手 Ctrl+C、Sanitizer、其他平台、缺 VC Runtime 的干净主机、完整 Python 核心和 GUI 回归、性能。原生 HTTP 固定本机回环；阻塞 OS I/O 不硬中断。N4-04 子项出口已满足，下一项 N4-05；不宣称完成全部 N4。
