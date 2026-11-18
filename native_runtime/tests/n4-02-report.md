# N4-02 文件与严格 JSON 原生验收

2026-11-18，原生版本 `0.0.0-n4-02-dev`。本阶段接入 `io.read_text`、`io.write_text`、`io.write_atomic`、`io.replace_file`、`data.parse` 和 `data.stringify`，共 35 个核心宿主签名。Python 解释器和默认入口保持不变；SQLite、Web、Sketch 和 GUI 不在本阶段。

文件实现使用 Windows 宽字符 API。普通写入在资源准备完成后覆盖目标；原子写入在目标同目录以 `CREATE_NEW` 创建临时文件，分块写入并关闭，取消检查通过后用 `MoveFileExW(REPLACE_EXISTING)` 提交。提交前的错误、资源超限和取消保留旧文件并清理临时文件；提交成功后不提供回滚或断电持久性保证。读取与写入保留 BOM、CRLF 和 UTF-8 字节，坏编码、目录、缺失路径和关闭错误返回失败 `Result`；错误参数数量/类型分别为 E202/E201。

JSON 使用请求内迭代读写器，不执行用户函数、默认值、Lazy、I/O 或 GUI。解析按字面量区分 Int/Float；文件 JSON 允许任意精度 Int，Float 必须有限，拒绝重复键、孤立代理、无效数字、非支持值和当前路径环。Map/shape 顺序保持，DAG 共享允许；Result、Lazy、Range、Machine、Quantity、函数和原生句柄不自动转换。复合值深度、数字位数、文本码点、有效载荷、容器项、工作缓冲和取消均沿用资源契约。

环境：Windows x64、PowerShell 7.6.9、CMake/CTest 4.5.0、VS2022 Build Tools、MSVC 19.40.33812.0、Windows SDK 10.0.22000.0、CPython 3.12.14。Debug/Release 均以 `BUILD_TESTING=ON` 配置，当前收集 69 项 CTest，分别 `69/69` 通过，耗时 187.40/92.11 秒；最后仅等价整理探针的默认预算恢复表达式，再补跑两配置各 3/3 受影响探针。新增 `library-files`、`library-file-commit`、`library-json` 三个 C++ 探针；固定库各 `126/126`、文件/JSON 固定清单各 `58/58`，合计全部 184 个 P05 run 期望；新增文件/JSON CLI 黑盒各 `33/33`。核心固定清单 Debug/Release 各 `550/550`，CLI 各 `72/72`，Python 相关回归 `391/391`。Release 安装到新目录后，源码外中文/空格发布副本 smoke 为 `9` 个通用命令加 `33/33` 文件/JSON，全部通过；发布验收的 PE 导入、实际模块/进程树、空 PATH 和无效 PYTHONPATH 未发现 Python。

独立演示为 `examples/file-json.zzy`，在新的临时工作目录实际生成并读回 `native-state.json`，固定内容含 `9007199254740993`。专项命令见 [native README](../README.md)。构建、CTest、安装、固定清单、失败首轮和修复后的 JSON 均保存在本阶段本地证据目录；历史失败原件不覆盖。

可提交的[证据归档](../../benchmarks/results/native/n4-02-msvc-20261118/README.md)保留 89 份原始记录的 gzip，含失败原件、正式结果和 Python 391 项日志。[audit.json](../../benchmarks/results/native/n4-02-msvc-20261118/audit.json)核对当前 145 个原生源码/夹具指纹、每配置 9 个 EXE、安装副本、固定数量及归档字节哈希。全量工作原件仍在 `dist/native-n4-02-work`。标准 CMake/MSVC 两配置各 78 条源码外过程（各含一条预期强杀，单列，不作为运行时清理证据）；协作取消与配额归还由同进程探针证明。

最终 Debug/Release CLI EXE SHA-256 分别为 `456ac30822e762bfe8bc0d79d0aa3633495c4a6db9e2d953d2bf3112e8c2ab57` 与 `c416195bb2959736a57c9ef374efab14f1839d2075f2e3cb33027b4ed3054c6d`。Release `/MD`、Debug `/MDd` 方案不变；Debug 不发布。本机 UCRT 来自 `C:\Windows\System32\ucrtbase.dll`，版本 `10.0.26100.9711`，微软签名 Valid；VC runtime 具体加载路径、版本和 SHA 在模块报告中。仅测试 EXE 的 `_lock_file/_unlock_file` 新导入允许精确 filesystem API-set，发布 CLI 未增加该权限。

未验证：真实手动 Ctrl+C、Sanitizer、其他平台、干净缺少 VC Runtime 的机器、SQLite/Web/Sketch/GUI、N5 test 和真实性能。N4-02 完成不等于完整 N4；下一项为 N4-03 SQLite。
