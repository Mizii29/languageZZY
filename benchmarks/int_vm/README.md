# ZZY 整数算法字节码实验

当前原生 `zzy-native run` 默认仅加速符合条件的整数循环调用图，`--engine ast` 可禁用 VM。下文早期原型和 A/B 的 `mixed` 模式也允许无循环函数进入 VM，用于解释为何正式入口采用循环门槛。测量探针的 `auto` 模式与 CLI 共用选择逻辑。 [原生 CLI 契约](../../docs/development/native-cli-contract.md#原生-run-执行方式)

实验执行器从既有 Lexer、Parser、Resolver 生成的 Program 降低为栈式字节码。局部变量沿用 Resolver 的槽位，整数以 64 位带标签值存储，整数数组连续保存这些值。数组引用通过编号表示，两个变量引用同一个数组时修改可见。缩小的执行器覆盖整数运算、Bool 条件、循环、直接调用已定义的函数、整数数组构建和遍历。

MSVC Release 编译后可显式指定 `vm` 或 `ast`。独立实验入口的 `auto` 会先完成前端检查，然后尝试 VM。在拒绝的情况下由 AST 从头执行，返回路径及拒绝原因。纯子集在提交结果前只有请求内的临时状态，输出集中在最后一次 `io.print`。自定义资源策略直接走 AST，超出整数表示、出现不支持的构造或达到实验容量时也可走 AST。前端诊断和取消直接退出。

实验使用有界值栈、调用、数组和步数，检查算术溢出与取消。独立 VM 与默认资源策略及完整 ZZY 值语义仍有差距。后续的混合原型用同一个 `ExecutionContext` 做调用点检查、配额预留、回退和诊断，但只支持可编译的纯整数函数图，不改变默认后端。要把它发展成通用语言运行时，仍需让两个执行器统一所有 ZZY 值类别、资源策略、源位置、宿主调用与容器所有权，超出内联表示时应在准确的运算位置升级为大整数或交还同一个调用帧。

## 复现

从仓库根目录运行。准备冻结 N7 输入的方法见 [N7 测量](../n7/README.md)。已冻结的目录可以直接复用，每次指定新输出路径。

```powershell
cmake --preset native-release -S native_runtime -DZZY_NATIVE_VM_EXPERIMENT=ON
cmake --build build/native-release --config Release --target native-int-vm
$py = '.\.venv\Scripts\python.exe'
$vm = 'build/native-release/Release/native-int-vm.exe'
& $vm auto dist/native-n7/frozen/X01.zzy dist/native-n7/frozen/limits.json
& $py -X utf8 -m benchmarks.int_vm.run dist/native-n7/frozen $vm dist/native-int-vm/replay-1 --seed 731
& $py -X utf8 -m benchmarks.int_vm.run dist/native-n7/frozen $vm dist/native-int-vm/replay-2 --seed 732
```

每轮先运行 18 条固定答案和路径守卫，再随机交错五组工作量和三种后端。每个变体 3 次预热、15 次正式，逐次核对 stdout、stderr、退出码和 Windows 内存计数器。每个样本都用新进程。执行段包含用户脚本和一次输出格式化，前端准备和字节码生成分别计时。Private Bytes 和工作集均为整个测量子进程的生命周期峰值，包含各探针自身开销。

## 本机结果

Windows 11 build 26200，Core Ultra 5 125H，MSVC 19.40 Release x64，直接 CPython 3.12.14。比较的是整数 VM、N7 冻结原生 AST 探针、同算法的直接 CPython 脚本。两轮各 225 个正式样本和 45 个预热，共 540 次进程运行，失败和超时为零。两轮各通过 18 条固定答案及守卫测试。原始输出、计数器、样本分布和可执行文件哈希见 [实测归档](../results/native-int-vm.tar.gz)。各格为两轮独立中位数的范围。

| 工作负载 | 整数 VM 执行（ms） | 原生 AST 执行（ms） | 直接 CPython 执行（ms） |
| --- | ---: | ---: | ---: |
| 常量函数 | 0.0043–0.0047 | 0.076–0.086 | 0.012–0.013 |
| 1 万次平方和 | 0.341–0.396 | 117.62–119.72 | 0.453–0.516 |
| 1 万次函数调用与分支 | 0.606–0.623 | 240.01–255.04 | 0.786–0.866 |
| 1 万元素数组 | 0.545–0.559 | 144.35–145.51 | 0.687–0.704 |
| 4 万元素数组 | 2.047–2.116 | 917.88–973.14 | 2.708–2.773 |

四组算法的 VM 中位数相对 AST 快约 260–460 倍，相对直接 CPython 快约 1.14–1.51 倍。4 万元素数组的峰值 Private Bytes 分别为 VM 1.63–1.64 MiB、AST 30.14–30.16 MiB、CPython 9.36–9.46 MiB。峰值工作集分别为 6.07–6.16 MiB、34.28–34.30 MiB、15.68–15.77 MiB。

VM 使用实验性容量保护和取消安全点。其运行期资源计量与 AST 契约存在差距，性能表反映这套精简原型的完整成本。1 万次平方和的原生前端约 6.4 ms，生成字节码额外约 0.011 ms。进程墙钟包含各自测量程序的启动和 JSON 输出，纯执行表用于比较运行内核。Release 既有执行、堆、生命周期、CLI 边界及 CI 指纹专项共 23 项通过。

## 按函数选择的混合原型

`native-mixed-vm` 是单独的实验目标，只有以 `-DZZY_NATIVE_VM_EXPERIMENT=ON` 配置时才生成。它仍由完整 AST 解释器负责读取、解析、名称解析、宿主调用、输出和错误诊断。每次用户函数调用在同一个 `ExecutionContext` 中先做参数和调用深度检查，再由编译器尝试降低该函数及其直接纯整数调用图。成功时只把返回整数交给原解释器的后续任务，失败时在同一调用点执行原 AST。编译图拒绝递归、数组和宿主副作用，因此没有把副作用调用重放到两个后端。

在 Windows 11 build 26200、Core Ultra 5 125H、MSVC 19.40.33812.0 Release x64、CPython 3.12.14 上，`mixed-replay-20261121-f` 和 `mixed-replay-20261121-g` 各包含 3 个工作负载、3 个后端、每组 3 次预热和 15 次正式样本，共 135 个正式样本和 27 个预热样本。两轮固定答案和 11 个隔离/回退守卫均通过，失败和超时为零。探针 SHA-256 为 `fca7ba40fc210a909421099bb0f2e72c8a5b3c301ae6eb8356779cf68f7a1ee5`，冻结 N7 清单 SHA-256 为 `dffa7e4599a892d66c1686dcd89cd0cf8d98a1512fa1aac34873a6be86f2babe`。完整原始 JSONL、环境、摘要和哈希保存在 `dist/native-int-vm/mixed-replay-20261121-f`、`dist/native-int-vm/mixed-replay-20261121-g` 以及 `dist/native-int-vm/mixed-smoke-20261121-final`。早期 `mixed-replay-20261121-a/b` 是修正测试期望前的有效旧轮次，`mixed-final-1` 则保留了一个错误选择器的失败原件，均不作为最终结果。

| 工作负载和后端 | 执行中位数（ms） | 完整墙钟中位数（ms） | Private Bytes 峰值（MiB） |
| --- | ---: | ---: | ---: |
| 1 万次平方和，AST | 124.22–155.13 | 157.98–202.33 | 3.85 |
| 1 万次平方和，混合 | 0.46–0.56 | 37.42–48.99 | 0.95 |
| 1 万次平方和，直接 CPython | 0.45–0.86 | 80.75–117.63 | 7.77–7.78 |
| 1000 次纯整数 helper 调用，AST | 27.06–30.42 | 65.10–75.04 | 3.71 |
| 1000 次纯整数 helper 调用，混合 | 0.49–0.56 | 35.96–46.81 | 0.94–0.95 |
| 1000 次纯整数 helper 调用，直接 CPython | 0.079–0.088 | 89.34–110.77 | 7.74–7.76 |
| 单次纯整数调用，AST | 0.132–0.152 | 33.20–35.99 | 0.95 |
| 单次纯整数调用，混合 | 0.106–0.123 | 31.75–35.88 | 0.92–0.94 |
| 单次纯整数调用，直接 CPython | 0.012–0.014 | 86.72–94.74 | 7.71–7.77 |

按两轮分别配对，平方和混合执行比 AST 快约 268–279 倍，与 CPython 执行段同量级，一轮慢约 3%，另一轮快约 36%，波动还不足以宣称稳定胜过 CPython。1000 次 helper 调用的 VM 执行比 AST 快约 53–54 倍，但比 CPython 慢约 6.4 倍。单次调用的 VM 执行比 CPython 慢约 8.6–9.2 倍。编译本身再增加约 0.057–0.065 ms，单次 tiny 用例把编译和执行相加后仍没有胜过 AST。完整墙钟里混合程序看起来比 CPython 快，主要受各可执行程序启动成本影响，不能据此说混合执行内核有同等倍数优势。这些实测支持把较大的纯计算调用图整体降低用于密集算法的方向，同时明确显示当前栈式 VM 仍需要降低指令分派和调用开销。实验目标没有改变默认 `zzy-native`，也没有把原型的有限整数范围、数组排除和资源预算差异宣称为完整 ZZY 语义。

复现命令如下，每次使用新的输出目录，脚本拒绝覆盖已有证据：

```powershell
cmake --preset native-release -S native_runtime -DZZY_NATIVE_VM_EXPERIMENT=ON
cmake --build build/native-release --config Release --target native-mixed-vm
$py = '.\.venv\Scripts\python.exe'
& $py -X utf8 -m benchmarks.int_vm.mixed dist/native-n7/frozen build/native-release/Release/native-mixed-vm.exe dist/native-int-vm/mixed-replay-20261121-f --seed 759
& $py -X utf8 -m benchmarks.int_vm.mixed dist/native-n7/frozen build/native-release/Release/native-mixed-vm.exe dist/native-int-vm/mixed-replay-20261121-g --seed 760
```

## 2026-11-22 指令分派和函数图优化

AST 和字节码 VM 都是以 C++ 编写的 ZZY 解释器。源文件仍由 ZZY 的 Lexer、Parser 和 Resolver 处理，VM 逐条解释项目定义的指令。CPython 只用于测量驱动和对照程序。作业要求实现自己的通用脚本语言与解释器，实现语言不限。

实验入口在准备后按顶层声明顺序构建共享字节码函数图。Resolver 已确定调用引用的声明，已生成的纯整数辅助函数可被多个调用者复用。动态调用、闭包内部声明、递归、数组和宿主操作继续由 AST 处理。VM 入口按最大活动调用链一次预留帧预算和核查调用深度，避免每次内部调用重复查资源限额。加减和比较直接使用带标签整数，`i <- i + 常量` 合并为一条指令，仍执行原四条指令的计步和取消检查。超出支持范围时从原调用点执行 AST，保留已有诊断。

先冻结上一版混合探针，再随机交错旧探针、新探针、同一新探针的纯 AST 模式和 CPython 3.12.14。使用 N7 冻结的默认资源配置，Windows 11 build 26200、Core Ultra 5 125H、MSVC 19.40.33812.0 Release x64。每轮每变体 3 次预热、15 次正式样本，最终两轮合计 480 个正式样本和 96 个预热样本，逐次校验固定输出、后端选择和计数，失败与超时为零。表中各格为两轮中位数的范围，单位为毫秒。

| 工作负载和计时范围 | 原生 AST | 旧混合 | 新混合 | CPython |
| --- | ---: | ---: | ---: | ---: |
| 1 万次平方和，执行 | 141.91–147.11 | 0.464–0.508 | 0.409–0.410 | 0.512–0.519 |
| 1000 次辅助调用，执行 | 26.29–28.49 | 0.507–0.678 | 0.160–0.167 | 0.080–0.090 |
| 共享函数图，字节码生成 | — | 1.402–1.808 | 0.185–0.333 | — |
| 共享函数图，执行 | 6.544–6.589 | 0.534–0.801 | 0.309–0.312 | 0.046–0.051 |
| 共享函数图，完整进程 | 221.47–241.88 | 223.26–228.72 | 212.27–227.31 | 96.06–102.73 |
| 单次整数调用，执行 | 0.134–0.175 | 0.124–0.165 | 0.116–0.117 | 0.018–0.025 |

共享函数图的 48 个分支调用者复用 12 个辅助函数，连同入口共 61 个字节码函数。字节码生成快 5.4–7.6 倍，原生前端准备仍约 180–186 ms。1000 次辅助调用比旧混合快 3.0–4.2 倍，执行段仍比 CPython 慢约 1.9–2.0 倍。平方和执行段的新旧差异为 12%–19%，本机两轮的中位数均低于 CPython，分布仍有重叠。单次调用加上字节码生成成本后，完整进程中位数两轮均高于纯 AST。简单三个负载的新混合进程峰值 Private Bytes 中位数约 0.93–0.95 MiB，CPython 约 7.74–7.80 MiB。较大的共享图约 2.18–2.19 MiB 和 8.14–8.15 MiB。这些是进程内存计数，独立于逻辑额度。

MSVC 初次构建的 `C4702` 来自模板中提前返回后的不可达语句，拆分比较指令后通过 `/W4 /WX`。最早候选的两轮记录在 `round-1` 和 `round-2`，平方和一轮退步。最终轮次在 `dist/native-int-vm/tuning-20261122/final-1` 和 `final-2`，含原始样本、环境、SHA-256、MAD 和四分位数。最终混合守卫 18/18，独立 VM 固定答案 18/18，原生 Release CTest 专项 23/23。优化留在可选实验入口。单机微基准的结论限于表中负载，完整应用、其他机器和编译器未测。

完成冻结后，在仓库根目录运行以下命令。基线可执行文件为现有的 `dist/native-int-vm/tuning-20261122/baseline.exe`，运行目录需使用新名称。

```powershell
cmake --preset native-release -S native_runtime -DZZY_NATIVE_VM_EXPERIMENT=ON
cmake --build build/native-release --config Release --target native-mixed-vm native-int-vm
$py = '.\.venv\Scripts\python.exe'
$run = 'dist/native-int-vm/tuning-20261122'
$exe = 'build/native-release/Release/native-mixed-vm.exe'
& $py -X utf8 -m benchmarks.int_vm.mixed dist/native-n7/frozen $exe "$run/replay-1" --baseline "$run/baseline.exe" --seed 775
& $py -X utf8 -m benchmarks.int_vm.mixed dist/native-n7/frozen $exe "$run/replay-2" --baseline "$run/baseline.exe" --seed 776
& $py -X utf8 -m benchmarks.int_vm.run dist/native-n7/frozen build/native-release/Release/native-int-vm.exe "$run/replay-standalone" --seed 777 --smoke-only
ctest --test-dir build/native-release -C Release -R '^(execution-|heap-|lifecycle-|cli-boundaries$|native-ci-fingerprint$)' --output-on-failure --no-tests=error
```
