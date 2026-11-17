# P12 性能差距诊断与下一步候选

2026-11-17。本页是本机实测后的优化建议和**未并入产品**的小型实验，完整 P12 验收仍以 todo 为准。原始分段数据见 [同源函数测量](p12-partial-performance.md)；实验脚本和两轮原始样本见 `benchmarks/p12/reserve_demo.py` 与 `benchmarks/results/p12/optimization-demo/`。

## 观察到的原因

X01 平方和 n=10,000 的纯 `bench()` 调用中位数：ZZY 272.645 ms、CPython 0.47377 ms。完整 CLI 是 ZZY 631.7 ms、CPython 239.6 ms。它们是两种不同层级的成本，不能从 CLI 时间直接相减求执行时间。

对 ZZY 的 X01/n=10,000 单独运行 cProfile（开启 profiler 后的耗时**不进入**正式性能表）：约 333 万次 Python 函数调用；`Interpreter.evaluate` 约 11 万次、`binary` 4 万次、`integer_operation` 3 万次、`Interpreter.reserve` 7 万次，资源检查与取消检查达几十万次。`reserve` 原写法中的 `any(... for ...)` 为每次预留创建生成器。具体函数计数见 [profile-x01-10000.txt](../../benchmarks/results/p12/optimization-demo/profile-x01-10000.txt)。这说明热循环不只是做整数乘加，还逐节点进行 ZZY 标签、求值分派、值所有权、配额和取消检查；cProfile 的累计时间互相嵌套，不应相加当作各项独占成本。

CPython 3.12 在同一 `bench()` 实跑 20 次后的 `dis.dis(..., adaptive=True)` 显示 `COMPARE_OP_INT`、`BINARY_OP_MULTIPLY_INT`、`BINARY_OP_ADD_INT` 等已专门化指令。项目使用 Python 编写 AST 树遍历器，ZZY 的每个小表达式都要走多层 Python 调用；CPython 则在自身字节码解释循环中处理已识别的整数操作。[Python 3.12 dis 文档](https://docs.python.org/3.12/library/dis.html)、[PEP 659](https://peps.python.org/pep-0659/)说明这一机制。此处是对**具体实现与工作负载**的解释，不是语言规范速度定律。

对 X00 的 `-X importtime` 单独探针显示 `zzy.cli` 导入链累计约 108 ms（探针本身有开销）。X00 完整 CLI 仍需 ZZY 364.9 ms、CPython 233.7 ms，中短脚本还受进程启动/导入/准备影响；业务长循环主要受执行热路径影响。

## 小型实验：资源预留预检查

实验类 `LoopReserveInterpreter` 只把 `Interpreter.reserve` 的 `any(generator)` 改为等价顺序的显式 `for`，其余仍调用原 `ResourceMeter.reserve`、保留超限时 GC、错误定位和登记/失败释放。产品 `zzy/interpreter.py` **未修改**。命令：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m benchmarks.p12.reserve_demo --output dist/p12-reserve-demo-new
```

每轮每变体 3 次预热、15 次独立子进程正式样本；同源码、默认配额、固定种子交错，完整答案逐次校验。两轮各 114 条记录、0 失败。以下 `execute` 单位 ms，为各自 15 样本中位数；配对变化为逐轮 `(候选/基线−1)×100%` 的中位数：

| 任务 | 第一轮基线 → 候选；配对变化 | 第二轮基线 → 候选；配对变化 |
|---|---:|---:|
| X01 平方和 n=10,000 | 299.98 → 260.31；−14.7% | 297.74 → 292.30；−1.0% |
| X02 函数/分支 n=1,000 | 70.65 → 65.85；−9.7% | 69.80 → 68.72；−7.8% |
| X03 数组 n=1,000 | 39.20 → 33.86；−12.5% | 37.85 → 35.04；−6.0% |

第二轮 X01 的变化小于波动，X02/X03 的 MAD 也与变化接近。实验不足以证明稳定产品收益，**本次不保留运行时改动**。现有 `tests.test_p11_meter` 在产品基线及临时方法替换下各 5/5 通过，只支持小范围语义检查；尚未覆盖完整 E211/取消/并发/GUI/Web 回归，不能宣称该候选已验收。原始两轮与环境分别归档在 `round-1`、`round-2`。

## 可行的推进顺序

1. **先确定目标路径。** 对短 CLI 看启动/导入与准备；对校园应用长计算和 Web 已加载 Program 的请求看 `execute`。固定 X01/X02/X03 加真实应用路径的等价答案、资源配置、15 轮与第二会话复测。引入失败样本或结果变化立即停止。
2. **在 AST 路线上逐项缩减通用热路径成本。** 优先实验 `reserve`/值创建/引用读取的重复 Python 调用；用内部候选类或受控分支单独比较，保持求值顺序、Int/Bool 标签、大整数、每个现有取消点、E211 键/数量/位置、别名和清理。准备阶段可预存不可变的静态节点信息，但不能把请求状态写进共享 Program。达到稳定收益且完整回归通过才并入产品；这次 `reserve` 循环尚未过收益门槛。
3. **再研究 AST 常见节点专用执行器。** 对 `name`、整数算术、比较和循环做带守卫的节点路径，未命中回落通用解释；仍逐 AST 节点执行，不提前执行用户代码。先量热点调用数与实际减少量，再测所有成功、错误、紧配额、取消和 Web 共享隔离。此前 P11 的小整数候选曾因未证实稳定收益撤回，不能把类似方案写成现成提速。
4. **若目标是数量级差距，另立架构范围。** 当前 Python AST 树遍历方案无法从一次生成器微优化获得数百倍提升；字节码/VM、JIT 或原生执行器需要单独的语义、配额和诊断设计与大规模验收，当前 P10-03 仍未选择完成。它们不应混进本次 P12 报告或在没有等价证明时启用。

以上步骤不需要 Lua。标准 PUC-Lua 仅在按 P12 方案补三方性能比较时作为额外对照安装；不会改善 ZZY 自身执行速度。
