# 原生 AOT 小范围实验（不替代课程解释器）

`docs/requirement.md` 与课程 PDF 第 14、16、18 页要求**解释型**通用脚本语言、解释器、完整 ZZY 黑盒测试及 ZZY/Python 同功能性能比较。因此本目录只是额外的原生编译研究；`zzy run/check/test`、原有应用、P12 必交性能对照及测试集均不由它替代。语言由语法/语义定义，编译器是实现方式；当前 ZZY 有 shape、函数及闭包，没有类、方法和继承体系，不宜称为完整面向对象语言。

## 已实现的范围

`compile_int.py` 使用项目现有 `SourceLoader`、Lexer、Parser、Resolver 和资源限制完成准备，再把**只有顶层函数**的源码生成 C11，调用本机 GCC `-O3 -Wall -Wextra -Werror` 编成独立 EXE。函数及参数必须标注 `(Int)`；局部绑定可推断 Int，支持局部赋值、`while`、`if`、显式 `return`、直接顶层函数调用、`+ - * %` 与 Int 比较。生成器给所有表达式先建临时值，按 ZZY 从左到右求值；C 辅助函数检测加减乘溢出、零除，余数遵循 ZZY 向下取整规则。递归、模块、全局业务初始化、Array/Map/shape、I/O、动态调用、闭包等一律报 `Unsupported`，不执行源码中的业务表达式。入口必须为单参数、返回 Int 的函数。样例为 `sum_squares.zzy` 和 `branch_calls.zzy`。

**重要差异：** ZZY 的 Int 是受资源预算限制的任意精度整数，本原型只接受 Int64。越界时原型返回非零并写 `AOT subset error`，没有现有解释器的 E211、源码诊断及完整取消/配额语义；因此只能比较**已逐项确认落在 Int64 内的输入**，不能把本原型声明为兼容的第二解释器或已实现 P10-03。生成的 EXE 不加载 Python，但构建时需要本项目 Python 前端和 GCC。Windows 下 EXE 用 QPC 报告批次函数时间、用 `GetProcessMemoryInfo` 报告进程峰值工作集。

## 本机复现

从仓库根目录运行，GCC 8.1.0 已在 PATH；无需下载 Lua、Rust 或 LLVM：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest experiments.aot.test_pilot -v
.\.venv\Scripts\python.exe -X utf8 -m experiments.aot.compile_int experiments/aot/sum_squares.zzy dist/my-aot-sum.exe
.\dist\my-aot-sum.exe 5
.\dist\my-aot-sum.exe 10000 10000
.\.venv\Scripts\python.exe -X utf8 -m experiments.aot.measure --output dist/my-aot-measure --samples 15
```

最后一个输出路径必须不存在。实验脚本先为两个用例生成 AOT EXE，并以相同 GCC 选项编译独立手写 `reference.c`；另以 `reference.py` 和公开 `zzy.embedding` 调用同一 ZZY 函数。两用例均用独立数学公式核验每次答案及批次校验和；每单元 3 次预热、15 次独立进程样本，固定种子交错，失败/超时保留在 `raw.jsonl` 并终止统计。`environment.json` 保存版本、源文件哈希和资源指纹，`summary.json` 保存中位数/MAD、AOT/C 构建成本。结果及实际验收命令见 [实验报告](../../docs/runtime/aot-pilot-report.md)。

测量边界须分开读：原生 AOT/C 的 `execute_ns_per_call` 是 EXE 内部 QPC 对 10,000/100,000 次调用取均值；CPython 是新 Python 进程加载函数后对 100/1,000 次函数调用计时；ZZY 是公开嵌入 API 的一次调用，包含逐请求执行上下文和结果转换。`wall_ns` 又包含不同批次数及各自启动，因此**不能直接按该列计算语言总速度比**。峰值工作集是整个相应进程（含 Python 宿主及测量代码）的 OS 指标，不能代替相同业务规模长期运行的峰值内存结论。C 与 AOT 共享 GCC 和等价的 Int64 溢出检查，结果仍只代表这两项计算。
