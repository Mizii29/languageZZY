# P12 跨解释器 CLI 子集

从仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m benchmarks.p12.run --verify-only --output dist/p12-preflight-new
.\.venv\Scripts\python.exe -X utf8 -m benchmarks.p12.run --output dist/p12-pairs-new
.\.venv\Scripts\python.exe -X utf8 -m benchmarks.p12.run_stages --verify-only --output dist/p12-stages-preflight-new
.\.venv\Scripts\python.exe -X utf8 -m benchmarks.p12.run_stages --output dist/p12-stages-new
.\.venv\Scripts\python.exe -X utf8 -m benchmarks.p12.audit --cli dist/p12-pairs-new --stages dist/p12-stages-new
```

输出目录必须不存在。`manifest.json` 固定 X00、X01、X02、X03 的规模、3 次独立预热、15 次正式样本、30 秒超时与交错种子。`inputs/` 保留双方实际运行的源码；`raw.jsonl` 逐次保存命令、顺序、答案 SHA、耗时、退出码和失败；`environment.json` 保存宿主、提交号、脏工作区、资源策略及源码哈希；`summary.json` 给出中位数/MAD/最小/最大。全部通过独立公式或固定常量核对后才采样，不删失败。外部 `perf_counter_ns` 计完整子进程 CLI（包括启动和输出）；不能从 X00 的启动成本机械相减。

分段轮次在子进程内对同一生成源码读文件、准备 Program/编译、初始化独立上下文、调用 `bench()`、校验、清理逐段计时。ZZY 由真实 AST 解释器执行，Python 保留正常 CPython 编译/字节码执行；源码准备与初始化不混入 `execute`。短调用按预检执行时间决定批量，目标约 50ms、每个子进程至多 1 秒/100000 次；批内每次均新建解释器/namespace 和可变容器，结果逐次对独立答案核对。原始记录保存批次数，分段结果为每次调用均值的 15 个独立子进程样本。X00 极短调用接近计时分辨率，**不用于可信纯执行倍率**。当前未测 CPU 时间与峰值工作集。标准 Lua 对这组 ZZY/CPython 分段测量并非依赖；若以后补三方主表再装合格 PUC-Lua。

父进程还独立检查总墙钟预算，即使子进程返回成功，超过 30 秒也记失败。2026-11-17 首次分段数据中 X03/n=1000 有一条约 1055 秒的异常，已保留于 `benchmarks/results/p12/invalid-first-stage`，审计拒绝该轮；完整重跑通过，见 `benchmarks/results/p12/execute-stages`。匹配源码的 CLI 原始记录在相邻 `cli-staged-source`；`audit` 检查文件哈希、14 个正式单元各 15 条、答案/超时和无缺样本。

X01 同为 `while i<n` 的显式平方乘加；X02 每轮调用一次奇偶分支函数；X03 逐项构建数组并顺序遍历。X00 只输出常量。规模和答案见清单及生成源码。当前仅 ZZY/CPython 原生 Windows 配对；标准 PUC-Lua/Ruby 尚无合格可执行文件。X04—X06、应用压力、P11 同机前后、分段与空间测量仍按正式计划待办，当前报告不能称为 P12 完整性能验收。
