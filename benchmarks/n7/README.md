# N7 测量方法

冻结已通过 N6 的原生 Release CLI、同一源码版本构建的独立阶段探针、Git 中未修改的 Python ZZY 包、CPython 3.12.14 本体与 DLL 哈希、具体输入和 `default-v1` 限额。直接 Python 与 Python 版 ZZY 使用同一个 CPython 进程入口，避开 Windows 虚拟环境的重定向器。两种 ZZY 的逻辑资源限额相同，各自的对象与槽位计费模型由其本身实现。直接 Python 使用对应的原生类型与常规运算，没有 ZZY 的资源计量、安全点和诊断开销。

每个样本创建一个进程。每一轮先执行 3 次预热，再执行 15 次正式测量。每次重复分别打乱同一夹具的各变体顺序与夹具执行顺序，种子写入结果。两轮顺序执行，禁止覆盖已存在的结果目录。每次校验完整输出、退出码、标准错误和计数器状态，任何失败或超时保留原始数据并使轮次命令非零退出。同组提供中位数、MAD、四分位数和范围。每次 `wall_ns` 包含创建进程、CLI 工作、回收退出状态及管道输出。

分段探针测量固定单文件，无模块导入。读取为取文件原始字节，准备为 UTF-8 源映射与 Lexer/Parser/Resolver 生成 Program，直接 Python 调用 `compile`。初始化到请求上下文及内建就绪为止，脚本顶层语句、业务计算和一次输出均计入执行。清理包括释放请求及 Program 引用，不强制执行 CPython 全堆 GC，也不包含进程退出。探针捕获输出后一次校验。两种正式测量使用独立样本，不从 CLI 耗时减去分段数据来估算差值。

子进程退出后通过保留的句柄读取 `GetProcessTimes` 和 `K32GetProcessMemoryInfo`。工作集峰值以驻留内存计，Private Bytes 峰值以私有提交量计。CPU 原始单位为 100 ns，短进程可报告零。逻辑配额另开一轮采集，Python 的峰值计量只在那里开启。工作集、Private Bytes 和逻辑配额不可互换。 [Windows 进程内存计数器](https://learn.microsoft.com/en-us/windows/desktop/api/psapi/ns-psapi-process_memory_counters_ex)

在仓库根目录运行。第二个 `cmake` 目标只构建阶段探针，冻结命令要求真正的 N6 Release CLI，匹配其 SHA-256。留存的冻结目录可直接复跑两轮。

```powershell
cmake --preset native-release -S native_runtime -DZZY_NATIVE_BENCHMARK=ON
cmake --build build/native-release --config Release --target native-n7-probe
$py = '.\.venv\Scripts\python.exe'
& $py -X utf8 -m benchmarks.n7.run freeze dist/native-n7/frozen build/native-release/Release/zzy-native.exe build/native-release/Release/native-n7-probe.exe
& $py -X utf8 -m benchmarks.n7.run run dist/native-n7/frozen dist/native-n7/replay-1 --seed 701
& $py -X utf8 -m benchmarks.n7.run run dist/native-n7/frozen dist/native-n7/replay-2 --seed 702
& $py -X utf8 -m benchmarks.n7.run run dist/native-n7/frozen dist/native-n7/replay-logical --seed 703 --logical
```
