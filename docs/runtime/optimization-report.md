# P11 优化实测记录

## 方法与基线（P11-01）

接手 feature/a480eccfb5265140158114d41ab0dcf20214aef8；在 codex/p11-interpreter-optimization 开发。19 份已有规划文档及新 optimization-plan 是用户此前工作，本轮保留并随基线归档；原差异与哈希见 tests/p11/planning.patch.gz、handover.json。requirement 和人工原件不改。

44 个运行时文件以 HEAD 冻结；P10 source 列出的 13 个源码/测试/示例文件逐一核对；contracts.py 的 CRLF 导致原始字节比较不同，归一 LF 后与提交完全一致。历史 P10 2041 项全量仅作为未改代码的基线证据，不用于证明后续优化通过。

驱动 `python -X utf8 -m benchmarks.p11 --before REF --after WORKTREE --output NEW_DIR` 创建临时源码快照，不切换工作树、不修改产品开关。B01—B09 使用原算法和独立固定答案；B04/stats 为 10/100/1000，其他 B 为 100，查询重复键/筛选/零 take、headless 100 步、检查/超限/预留释放 1000 次。完整输入与答案在 manifest.json。独立 Python stats 参考仅用于非负计时输入的等价预检，完整正负/非法输入由产品专项验收。

每个样本独立进程/状态，固定种子串行交错，3 次预热、15 次正式样本；CLI 总耗时与另进程的 read/prepare/initialize/execute/validate/cleanup 分开。profile 单独采集（含导入，不能将其耗时当执行计时），不与回归并行。全部失败/超时保留，不用缺失样本或失败样本计算加速比。统计 min/max/median/MAD，环境、CPU、GC、版本、依赖、default-v1、源码/驱动哈希全保存。

基线命令：`.venv/Scripts/python.exe -X utf8 -m benchmarks.p11 --before HEAD --output benchmarks/results/p11/01-baseline --profile`。762 条记录成功、零失败；正式每组均 15。原始记录在对应目录 raw.jsonl，summary.json 记录各阶段统计，environment.json 记录可复现身份。初始预检 50 条成功单独保留；随后补入 stats Python 参考，正式测量前再次运行全部预检。基线不是加速声明。

热点证据：B04/1000 的 profile 记录 6017 次 Interpreter.reserve、9267 次 Source.span、18534 次 position；D01/1000 的 1000 次成功 check 仍调用 span。先研究按需定位，再按依赖逐项评估。CLI 短任务启动噪声较大，不能由执行阶段收益推断整个 CLI 等比例加速。

后续单项与累计结果在完成实测后追加。
