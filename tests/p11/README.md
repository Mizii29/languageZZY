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
