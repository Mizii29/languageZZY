# 原生 AOT 原型：作业边界、实现及实测

2026-11-17。此报告只针对 `experiments/aot` 的 Int64 小范围原型；**课程主交付仍是现有解释型 ZZY 与其黑盒测试**。项目原文 `docs/requirement.md` 第 1、2、3 项和 `docs/final_requirement.md` 所保存课程 PDF 第 14、16、18 页明确要求解释器、完整 ZZY 黑盒测试及 ZZY/Python 同功能比较。因此 AOT 是额外研究成果，不能把编译结果替代原解释器的 P12 主表。未改 `docs/requirement.md`、`zzy/` 产品运行时或主 CLI。

## 实施与选择

使用现有 ZZY Lexer、Parser、Resolver 及准备阶段限额，从真实 AST 和解析好的符号引用生成 C11，再由本机 GCC `-O3` 构建独立 EXE。实验支持顶层 Int 函数、直接调用、局部变量、赋值、分支、while、整数算术/比较；表达式先落临时变量，保持从左到右求值。`objdump -p` 实查样例 EXE 只导入 KERNEL32、msvcrt、PSAPI DLL，不加载 CPython。拒绝数组、模块、I/O、递归、闭包等未实现能力；溢出时明确报错。样例/代码/复现及与 ZZY 语义的差异见 [实验目录](../../experiments/aot/README.md)。

这证明“用自己定义的 ZZY 语法和语义、用别的语言实现编译后端”技术上可行；语言是否面向对象由语法和运行时对象模型决定，和解释/编译方式是两个维度。当前 ZZY 提供固定字段 shape、函数/闭包和可变对象，但无类、方法/继承体系，可称多范式脚本语言，不宜称完整面向对象语言。

## 验证方法

环境：Windows 11、CPython 3.12.14、MinGW GCC 8.1.0，具体 OS/资源指纹、源码 SHA-256 和编译选项在 `experiments/aot/results/round-*/environment.json`。用两个实际 `.zzy` 源文件及独立手写 C/Python 对照：X01 平方和 n=10,000；X02 奇偶分支/函数 n=1,000。答案用闭式公式核对，批量调用还核对校验和。每单元 3 次预热、15 次独立进程正式样本，固定种子交错；失败和超时保留原始记录，不填零。两轮各 144 条记录、0 失败；每单元 15/15 正式样本。原始记录、统计和生成 C 源码均归档在 `experiments/aot/results/`；本机可执行文件保留在忽略的 `dist/`。

`execute` 是每次函数调用均值：AOT/C 在程序内用 Windows QPC 测 10,000 或 100,000 次调用；CPython 在独立进程内对 100 或 1,000 次函数调用计时；ZZY 经公开嵌入 API 调用一次，含逐调用上下文/转换。各自完整进程总时长的批次数不同，**不能跨语言按 `wall_ns` 列算完整 CLI 比值**。内存是进程级 `PeakWorkingSetSize`，包括 Python 宿主及测量代码；不是 `runtime_payload_bytes`，也不是长期应用负载的峰值。

| 用例 | 原生 AOT 每调用中位数 | 手写 C 每调用中位数 | CPython 每调用中位数 | 解释型 ZZY 嵌入调用中位数 |
|---|---:|---:|---:|---:|
| 平方和 n=10,000 | 6.221 µs | 6.237 µs | 443.821 µs | 264.224 ms |
| 分支函数 n=1,000 | 0.384 µs | 0.381 µs | 71.141 µs | 62.704 ms |

上表取第一份最终代码轮次；第二份平方和为 AOT/C 6.075/6.108 µs，分支为 0.382/0.376 µs，完整 MAD 与其他语言结果见两份 `summary.json`。AOT 和 C 的细小差值在离散范围内，**没有“ZZY 超过 C”的证据**。本原型在这两个程序中达到手写 C 同量级、明显快于 CPython；这首先是原生机器码和静态 Int64 语义的效果，不能外推到 ZZY 的 Array、String、Quantity、Web、GUI 或完整解释器。

第一份最终代码轮次的峰值工作集（十进制 MB）：AOT 平方和 4.485 MB、C 4.485 MB、CPython 17.424 MB、解释型 ZZY 23.691 MB；分支用例对应约 4.485/4.485/17.560/23.720 MB。两份原生 EXE 与 C 对照 EXE 各约 58 KB。本地 AOT 构建包括 ZZY 前端与 GCC，每个样例约 0.78–0.83 秒；手写 C 的 GCC 构建约 0.72 秒。**没有验证其他 OS、不同 C 编译器、应用内存峰值或完整 ZZY 语义。**

## 失败与后续门槛

首轮 `python -m experiments.aot.compile_int experiments/aot/sum_squares.zzy dist/aot-sum.exe` 被 `-Werror=unused-function` 拒绝，查明生成器把未用辅助函数也声明为普通 `static`；只将纯辅助函数改为 `static inline` 后重新编译通过，未降低告警级别。加入 Windows 内存输出时，MinGW 的旧格式检查拒绝 `%zu`；改用 `<inttypes.h>` 的 `PRIu64` 后专项通过。正式计时只在修复完成后采样。

验收命令（仓库根目录）：`./.venv/Scripts/python.exe -X utf8 -m unittest experiments.aot.test_pilot -v`：8/8、退出 0；`-m compileall -q experiments/aot`：退出 0；`-m scripts.ci static --output dist/aot-pilot-static`：`passed=true`；`-m experiments.aot.measure --output dist/aot-pilot-20261117-final --samples 15` 及 `--output dist/aot-pilot-20261117-final-repeat`：各 144 条/0 失败。归档审计验证每轮 16 个语言/阶段单元计数、7 个源码哈希、结果文件失败数及两轮生成 C 一致，退出 0。核心解释器源码未改，完整 `python -m tests` **本轮未重跑**，不能沿用历史结果称为本轮通过；GUI/Web/人工亦未重验。

继续原生路线前，必须先决定是否允许独立的“性能版”语义：当前任意精度 Int、逐节点资源/取消和精确错误定位尚未移植。若要求同一 ZZY 程序全语义等价，需要原生大整数、容器/别名、闭包、Lazy、结构、宿主 ABI 和资源机制；不能将这个 Int64 原型直接宣传为兼容编译器。下一步研究宜先做带注解的连续 Int 数组和真实业务场景，配对 C/CPython/解释器测算术、内存及编译成本；未达同答案/同边界则不作性能结论。P12-03—05 与 P10-03 状态保持原样。
