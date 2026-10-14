# 性能基准目录

P07 按 [性能契约](../docs/runtime/performance.md) 建立 B01—B09 的配对程序、独立答案和内部测量驱动。运行时仍为 P06 的 0.6.0a1；测量工具不是公开嵌入 API。阶段进度以 todo 和实际记录为准。

在项目根目录使用 CPython 3.12.14：

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_p07_benchmarks -v
& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.run --verify-only --output dist/p07-equivalence
& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.run --output benchmarks/results/baseline
```

输出目录必须不存在，以防覆盖基线。`--cases B01 B04` 可选择子集；未知或空集合失败。正式清单固定三档规模、3 次预热、15 次样本、30 秒子进程上限、种子 20261008 和默认资源配置。每个配对/规模/计时范围先通过两种语言的完整答案校验，才进入计时；失败配对记为 not_measured，不能生成虚构样本。采样期间每个样本仍核对完整结果；任意错误、超时或门禁未通过均退出 1，结果保留。长任务超时包括该进程的准备和输入构造，不等于“纯执行用了 30 秒”。

`cases.json` 是工作量和边界清单，`expected-small.json` 是人工固定的 n=10 答案。普通源码可以直接执行；驱动仅替换唯一 n 声明。B06 生成函数体内 n 条不同名称的标量声明，两边调用函数返回最后一个值。生成后的源码及 SHA-256 随每次运行保存，循环算法绝不改成公式。

计时范围：

- `cli_total`：父进程开始受控运行至进程树回收、读完双流，包含进程管理、启动、模块加载、准备、输入构造、执行与打印完整结果。B05 同时打印结果和原数组，故这一栏包含较多输出。两边都包含这些工作，计时后才核对捕获字节。Python 在 Windows 的 CRLF 与 ZZY CLI 的 LF 分别精确匹配。
- `read`：读取同一生成文件的字节；`prepare`：持有字节后，ZZY `Source.from_bytes` + `prepare`，Python `compile`。ZZY 包含源码索引、哈希、Lexer、Parser、Resolver，Python 不伪造对应的内部阶段。无导入的基准仍走正式 prepare 路径。
- `initialize`：每次新建解释器/命名空间、定义、输入数组、结构或机器实例。ZZY 使用 `Interpreter.run` 和普通顶层语句；Python 使用编译结果的 `exec`。准备图/定义与任务计时分开。
- `execute`：ZZY `drive` 中的 `evaluate(bench())`（含调用分派、实参/返回边界），Python `bench()` 入口至返回。ZZY 被测循环/函数/查询/机器/数量全部来自配对 `.zzy`，没有 Python 代跑业务。
- `validate`：归一化、完整独立答案、排序频数/输入未变/相等键引用顺序检查；`cleanup`：释放本轮状态、返回值和配额。分别计时，不从 execute 减去估计值。
- `frontend_probe`：正式样本外再跑一次 Lexer/Parser/Resolver，记录三段成本与 Token/码点数。它是独立的阶段分解探针，不将三段相加冒充前面的 prepare，且不与 Python 内部阶段硬对齐。

短任务按预检执行时间选择批次数，目标累计执行 100ms，上限 1000；再按预检总成本将批量准备/构造/执行工作控制在约 5 秒内（估计不是超时保证）。实际批次数始终入原始记录；达到批上限仍不足 100ms 时如实保留。批内复用不可变 Program/编译结果，每次新建可变初态；无长期 Program 缓存或 Lazy 命中实验。read/prepare 每进程一次，其余各项保存批内累计纳秒及 batch，报告除以 batch。GC 始终开启；批外三次预热也是独立进程，不声称冷磁盘或完全隔离系统负载。

比较边界：B01—B03 是基础同算法；B04—B05 是检查后的库任务，Python 独立包装共享资源策略/计量器，B04 排除 Bool 并对每个非负部分和使用同样的位宽探测、临时/结果预算。该包装只为固定非负输入实现，不冒充完整 ZZY 标准库。B05 完整校验和复制，均稳定排序。B07 同快照、全部筛选、全部键、稳定比较排序、截取/投影；B08 同转移查表、Result 创建/匹配和状态更新；B09 同精确 Fraction、gcd 交叉乘法、量纲和中间位数检查。Python 不模拟 AST 分派、变量槽、每个 ZZY Value 的对象预算；这部分语言运行成本属于对照差异。B07/B09 不是“全资源运行时开销相同”的库微基准。B09 固定小操作数均在默认限制内，Python 检查中间整数的方式不构成任意恶意大数的公开安全接口。

`environment.json` 保存系统/CPU/物理内存、Python/Unicode/包版本、Git/脏状态、GC、资源配置及指纹、计时器；`tracked.diff` 保存跟踪文件差异。`raw.jsonl` 按真实顺序逐条 flush，包含命令、阶段、索引、结果、时间或失败；`summary.json` 提供中位数、最小/最大值、MAD、实际样本数与失败列表。新进程不是冷页缓存；逻辑资源预算不是 RSS。剖析和内存探针须另跑，不混入速度样本。
