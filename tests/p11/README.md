# P11 优化验证

- handover.json / planning.patch.gz：接手时已有规划差异和身份，不是本轮运行时实现。
- p10-source-review.json：P10 源码记录与当前 HEAD 的归一 LF 核对。
- 01-inventory.json：当前测试 ID，保留原2041，新增3项驱动验证。
- 01-specialist.json：驱动、校园、Python嵌入、SQLite真实专项；01-http.json：23项真实HTTP/Schema（默认/shared、合约、SQLite、恢复）。
- 性能原始记录：../../benchmarks/results/p11；方法及结果：../../docs/runtime/optimization-report.md。

命令（项目根目录）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_p11_benchmarks -v
.\.venv\Scripts\python.exe -X utf8 -m tests.web_http --report tests/p11/http-new.json
.\.venv\Scripts\python.exe -X utf8 -m benchmarks.p11 --before HEAD --after WORKTREE --output benchmarks/results/p11/new-pair
```

核心完整入口仍是 `python -X utf8 -m tests`，新增 test_*.py 自动收集；没有用例/跳过/失败均不通过。基线未重跑旧全量，不把历史通过用于后续改动。GUI、人工 Ctrl+C 和云端另行记录，不由 headless 代替。

## P11-02 映射

`tests.test_p11_locations`：成功检查/预留及取消不触发定位；BOM/CRLF/中文/非BMP/EOF固定坐标；完整text/JSON记录与计数；定位OSError/MemoryError不掩盖E211；16个共享Program并发上下文；cwd；真实CLI跨模块主位置/调用notes及check不执行。`tests.test_p07_locations`保留现有cwd/8.3路径回归；`tests.test_resources`保留限额/取消规则。

专项16/16（02-specialist.json），真实HTTP/Schema23/23（02-http.json）；完整核心2049/2049（02-core.json）；21组1496条配对测量成功，全部正式组15样本。02-source.json锁定源码；02-error-profile单独记录冷路径调查，不作速度样本。初始跨模块夹具把plus列号23写错，逐字符枚举和优化前HEAD实跑均证实为24，修正固定答案；原失败日志保留dist/p11-02-specialist-initial.log。

## P11-03 映射

`tests.test_p11_meter`：计数/取消顺序、多项事务、MemoryError与取消登记失败归零、构造/复制/赋值故障、幂等release、弱引用/子类、别名/循环/GC重试、随机独立账本及12并发计量上下文。弱引用登记旧版本真实失败日志在dist/p11-03-fault-before.log；修复后25项专项通过，03-specialist.json。完整2054/2054（03-core）、HTTP23/23（03-http）；884条计时成功（03-meter），独立内存观察03-memory，源码03-source。故障前日志另存03-fault-before.txt。

## P11-04 映射（评估后撤回）

`test_p11_integers`的5项覆盖固定/固定种子答案、正负零/进借位/抵消/1..4096位、全部取消点、紧配额精确回退、严格标签与Float、不支持操作，逐事件对照实验守卫与发布通用路径。候选20专项及279真实P02 CLI、13旧算术/驱动专项通过；撤回后21专项通过。04-candidate-*保留原计时源码与补丁，04-integers为919条计时记录，收益不足已撤回，不算发布能力。tests内实验类只有语义用途，不作为原速度复现；准确复现步骤见优化报告。

04-core：最终交付状态2059/2059、867.953秒；04-delivery-source确认运行时等于03，未启用候选，所有新增实验测试仍收集执行。

## P11-05 映射（评估后撤回）

`tests.test_p11_sum_stats`的4项含14次真实CLI固定答案/失败、空/单项/正负/重复、输入alias、Bool/String/Float精确错误位置、最终抵消前部分和超限及合法紧预算、检查/累加交错、取消归零与后续上下文恢复。候选专项20/20；462条独立计时未证实收益，原库已恢复。候选库/patch/身份05-candidate-*，数据05-sum-stats；新测试继续接入完整入口，不删除/跳过。

05-core：交付状态2063/2063，979.672秒；05-delivery-source确认原库未变。新的调用notes故障审查与修复在07单独记录，不以这些通过掩盖待修项。
