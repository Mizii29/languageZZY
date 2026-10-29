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

## P11-06 映射

`tests.test_p11_query`的7项覆盖真实CLI固定升降序、±2^53附近混合Int/Float、负零/重复键、Unicode、Quantity通用路径、浅别名、完整阶段及take0后部错误、原输入下标notes、44档槽位、真实比较栈取消与四个共享Program上下文屏障交错。GenericSort只在测试中保留原比较器，固定答案不依赖它产生。24专项/23HTTP通过；06-source为计时前身份，06-delivery-source含最后增加的负数/交错用例，运行时不变。306条计时记录见06-query，B07/Q01支持保留，其他小幅变化不夸大。完整回归结果另列06-core.json，不以专项代替全量。

06-core：最终交付状态2070/2070，983.422秒；零失败/错误/跳过。static门禁通过，06保留，07尚未验收。

## P11-07 最终累计验收

- `07-source.json`：冻结44个运行时、6个P11测试模块及实验驱动的归一LF哈希；`07-supporting-source.json`补公共worker/CI/配置身份；`07-runtime.patch.gz`是接手基线a480ecc到累计运行时的完整差异。测量、回归、wheel的运行时一致，版本仍0.6.0a1，以Git/哈希区分。
- `07-id-retention.json`：旧2041 ID全保留，新增31至2072，外部CLI仍1738。新增两项位置测试在三种调用备注故障和查询备注分配故障下保留原E211及净计量；旧实现失败日志07-notes-before.log.gz保留，初稿测试自身subTest作用域错误另存initial日志，不隐去失败。
- `07-specialist.json`：37/37，4.656秒；`07-core.json`：2072/2072，931.875秒，零失败/错误/跳过；原完整输出07-core.log.gz。
- `07-http.json`：23/23，6.687秒，真实TCP默认/shared/合约/SQLite/恢复；`07-gui.json`：真实Tk11/11，5.563秒，GUI几何/交互/关闭和线程清理；GUI自动操作不作为人工记录。核心含headless/校园/嵌入/SQLite/自动取消。
- `07-installed-core.json`：隔离无第三方核心环境，中文/空格路径、check无副作用、headless/校园/SQLite/嵌入/合约；`07-installed-http.json`：新wheel重装到独立Web环境（复用dist/p10-web-installed这个目录名），Python -I在源码目录外运行23/23、6.578秒，44源码全部一致；不是复用P10旧结果。
- `07-ci-{static,regression,package,gate}.json`：同一源码指纹的最终本地门禁全部通过；云端未推送/未执行。归档新增报告文件后指纹会包含新证据，运行时/用例仍按07-source逐文件确认未变；归档后另做static审查，不把其新元数据身份混入旧汇总门禁。
- `07-manual-script-precheck.json`及`07-manual-powershell-parse.json`只证明四个ZZY脚本check和三段PowerShell解析通过。[人工方案与待填结果](../../docs/manual-tests/p11-20261030/README.md)的M01/M02仍未验证；用户明确要求先勾选07、稍后补做，不能当作已人工通过。
- `benchmarks/results/p11/07-cumulative`：25组、1800条成功测量记录，全部正式组15，3次独立预热；累计收益/冷路径退化和全部离散程度见优化报告；07-error-profile只作独立诊断，不作速度样本。

本轮实际最终命令（项目根目录，生成目录不得与历史结果冲突）：

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m tests.web_http --report dist/p11-final/http.json
& ./.venv/Scripts/python.exe -X utf8 -m tests.gui_sketch --report dist/p11-final/gui.json
& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.p11 --before a480ecc --after WORKTREE --output benchmarks/results/p11/07-cumulative
& ./.venv/Scripts/python.exe -X utf8 -m scripts.ci static --output dist/p11-final/static
& ./.venv/Scripts/python.exe -X utf8 -m scripts.ci regression --output dist/p11-final/regression
& ./.venv/Scripts/python.exe -X utf8 -m scripts.ci package --output dist/p11-final/package --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe
& ./dist/p10-web-installed/Scripts/python.exe -I -X utf8 scripts/ci_web_installed_probe.py --report dist/p11-final/installed-http.json
& ./.venv/Scripts/python.exe -X utf8 -m scripts.ci gate --artifacts dist/p11-final --output dist/p11-final/gate
```

regression实际调用完整`python -X utf8 -m tests --report ...`，没有缩减测试。安装HTTP前已用bundled pip向独立Web环境执行`install --force-reinstall --no-index --no-deps`安装本轮wheel，具体wheel SHA/包源码在报告中。重跑请整体更换输出目录，保留历史证据；正式测量与回归分开。
