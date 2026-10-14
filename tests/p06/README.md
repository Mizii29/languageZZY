# P06 测试、指南与运行器验收

本阶段把 33 条核心覆盖规则落实到已有及新增真实 CLI 证据。下面每格是独立外部期望的代表；完整边界族仍保留在 P01—P05 清单，不以每格一个例子代替整条规则。`coverage.json` 由测试检查规则全集、引用存在与正常/错误退出属性，避免文档空列或悬空引用。

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m tests --report dist/p06-all-tests.json
& .\.venv\Scripts\python.exe -X utf8 -m tests.blackbox --report dist/p06-blackbox-report.json
```

第一条是一键完整入口，包含全部独立 CLI、正常 spec、故障注入和生命周期测试；第二条只重跑外部清单，两者计数重合。报告目录 dist 需已存在；不传 --report 时不需要此目录。空收集、少执行、skip、expected failure、失败、超时或输出超额均非成功。

P06 新增 129 项外部期望（64 run / 65 check），默认外部总计 1588。正常 spec 的输出还由独立宿主期望检查，不只依赖 `(o_o)` 自身。最终计数/命令/环境以开发日志为准。

## 逐条核心映射

| 规则 | 正常代表 | 边界代表 | 错误代表 |
|---|---|---|---|
| LEX-01 | [lex:fixed-symbols](../../tests/lex/inputs/fixed-symbols.zzy) | [lex:bom-crlf](../../tests/lex/inputs/bom-crlf.zzy) | [lex:fullwidth-parenthesis](../../tests/lex/inputs/fullwidth-parenthesis.zzy) |
| LEX-02 | [lex:comments-not-tokens](../../tests/lex/inputs/comments-not-tokens.zzy) | [lex:end-boundaries](../../tests/lex/inputs/end-boundaries.zzy) | [lex:unclosed-comment](../../tests/lex/inputs/unclosed-comment.zzy) |
| LEX-03 | [lex:adjacent-operators](../../tests/lex/inputs/adjacent-operators.zzy) | [run:p04-quantity-units-independent](../../tests/p04/inputs/quantity-units-independent.zzy) | [run:p04-quantity-unknown](../../tests/p04/inputs/quantity-unknown.zzy) |
| MACHINE-01 | [run:p05-module-type](../../tests/p05/inputs/module-type.zzy) | [run:p04-machine-self-loop](../../tests/p04/inputs/machine-self-loop.zzy) | [run:p04-machine-duplicate](../../tests/p04/inputs/machine-duplicate.zzy) |
| MACHINE-02 | [run:p04-machine-state](../../tests/p04/inputs/machine-state.zzy) | [run:p04-machine-empty-send](../../tests/p04/inputs/machine-empty-send.zzy) | [run:p04-machine-readonly](../../tests/p04/inputs/machine-readonly.zzy) |
| UNIT-01 | [run:p04-quantity-exact](../../tests/p04/inputs/quantity-exact.zzy) | [run:p04-quantity-zero](../../tests/p04/inputs/quantity-zero.zzy) | [run:p04-quantity-add-dimension](../../tests/p04/inputs/quantity-add-dimension.zzy) |
| UNIT-02 | [run:p05-unit-conversion](../../tests/p05/inputs/unit-conversion.zzy) | [run:p04-quantity-float](../../tests/p04/inputs/quantity-float.zzy) | [run:p05-unit-dimension](../../tests/p05/inputs/unit-dimension.zzy) |
| STR-01 | [lex:strings](../../tests/lex/inputs/strings.zzy) | [lex:backslash-not-escape](../../tests/lex/inputs/backslash-not-escape.zzy) | [lex:dangling-escape-eof](../../tests/lex/inputs/dangling-escape-eof.zzy) |
| EXPR-01 | [run:p02-numeric-precedence](../../tests/p02/inputs/numeric-precedence.zzy) | [run:p02-exact-comparison](../../tests/p02/inputs/exact-comparison.zzy) | [run:p02-bool-add](../../tests/p02/inputs/bool-add.zzy) |
| EXPR-02 | [run:p03-evaluation-order](../../tests/p03/inputs/evaluation-order.zzy) | [run:p03-short-circuit-function](../../tests/p03/inputs/short-circuit-function.zzy) | [run:p03-arg-error-stops-rest](../../tests/p03/inputs/arg-error-stops-rest.zzy) |
| BIND-01 | [run:p03-shared-cell](../../tests/p03/inputs/shared-cell.zzy) | [run:p03-assignment-location-once](../../tests/p03/inputs/assignment-location-once.zzy) | [run:p03-captured-immutable-write](../../tests/p03/inputs/captured-immutable-write.zzy) |
| ARRAY-01 | [run:p02-array-alias-copy](../../tests/p02/inputs/array-alias-copy.zzy) | [run:p02-array-copy-during-iteration](../../tests/p02/inputs/array-copy-during-iteration.zzy) | [run:p05-callback-pop-last](../../tests/p05/inputs/callback-pop-last.zzy) |
| ARRAY-02 | [run:p02-array-iteration](../../tests/p02/inputs/array-iteration.zzy) | [run:p03-return-releases-iteration](../../tests/p03/inputs/return-releases-iteration.zzy) | [run:p03-array-active-call](../../tests/p03/inputs/array-active-call.zzy) |
| SHAPE-01 | [run:p02-shape-defaults](../../tests/p02/inputs/shape-defaults.zzy) | [run:p02-default-after-explicit](../../tests/p02/inputs/default-after-explicit.zzy) | [run:p02-shape-explicit-type-order](../../tests/p02/inputs/shape-explicit-type-order.zzy) |
| SHAPE-02 | [run:p02-shape-order-with](../../tests/p02/inputs/shape-order-with.zzy) | [run:p02-shape-types-with](../../tests/p02/inputs/shape-types-with.zzy) | [run:p02-with-field-list-first](../../tests/p02/inputs/with-field-list-first.zzy) |
| CTRL-01 | [run:p02-loops](../../tests/p02/inputs/loops.zzy) | [run:p02-empty-range-identity](../../tests/p02/inputs/empty-range-identity.zzy) | [run:p03-cross-break](../../tests/p03/inputs/cross-break.zzy) |
| FN-01 | [run:p03-factorial](../../tests/p03/inputs/factorial.zzy) | [run:p03-for-capture-local](../../tests/p03/inputs/for-capture-local.zzy) | [run:p03-return-implicit-type](../../tests/p03/inputs/return-implicit-type.zzy) |
| RES-01 | [run:p04-result-values](../../tests/p04/inputs/result-values.zzy) | [run:p04-propagate-loop](../../tests/p04/inputs/propagate-loop.zzy) | [run:p04-propagate-lazy](../../tests/p04/inputs/propagate-lazy.zzy) |
| LAZY-01 | [run:p04-lazy-once](../../tests/p04/inputs/lazy-once.zzy) | [run:p04-lazy-reference](../../tests/p04/inputs/lazy-reference.zzy) | [run:p04-lazy-mutual-cycle](../../tests/p04/inputs/lazy-mutual-cycle.zzy) |
| QUERY-01 | [run:p04-query-basic](../../tests/p04/inputs/query-basic.zzy) | [run:p05-module-once](../../tests/p05/inputs/module-once.zzy) | [run:p04-query-clause-order](../../tests/p04/inputs/query-clause-order.zzy) |
| QUERY-02 | [run:p04-query-stable](../../tests/p04/inputs/query-stable.zzy) | [run:p04-query-take-zero-no-yield](../../tests/p04/inputs/query-take-zero-no-yield.zzy) | [run:p04-query-take-zero-order](../../tests/p04/inputs/query-take-zero-order.zzy) |
| QUERY-03 | [run:p05-query-pure-library](../../tests/p05/inputs/query-pure-library.zzy) | [run:p04-query-repeated](../../tests/p04/inputs/query-repeated.zzy) | [run:p05-kind-query-rejected](../../tests/p05/inputs/kind-query-rejected.zzy) |
| PIPE-01 | [run:p04-pipe-chain](../../tests/p04/inputs/pipe-chain.zzy) | [run:p04-pipe-order](../../tests/p04/inputs/pipe-order.zzy) | [run:p04-pipe-source-error](../../tests/p04/inputs/pipe-source-error.zzy) |
| IO-01 | [run:p02-input-lines](../../tests/p02/inputs/input-lines.zzy) | [run:p02-input-eof-empty](../../tests/p02/inputs/input-eof-empty.zzy) | [run:p02-input-type](../../tests/p02/inputs/input-type.zzy) |
| LIB-01 | [run:p05-sum-reference](../../tests/p05/inputs/sum-reference.zzy) | [run:p05-stats-empty](../../tests/p05/inputs/stats-empty.zzy) | [run:p05-callback-error-stop](../../tests/p05/inputs/callback-error-stop.zzy) |
| JSON-01 | [run:p05-json-roundtrip](../../tests/p05/inputs/json-roundtrip.zzy) | [run:p05-json-sharing](../../tests/p05/inputs/json-sharing.zzy) | [run:p05-map-missing](../../tests/p05/inputs/map-missing.zzy) |
| JSON-02 | [run:p05-kind-closed](../../tests/p05/inputs/kind-closed.zzy) | [run:p05-kind-cyclic](../../tests/p05/inputs/kind-cyclic.zzy) | [run:p05-kind-query-rejected](../../tests/p05/inputs/kind-query-rejected.zzy) |
| MOD-01 | [run:p05-module-diamond](../../tests/p05/inputs/module-diamond.zzy) | [run:p05-module-once](../../tests/p05/inputs/module-once.zzy) | [run:p05-module-cycle](../../tests/p05/inputs/module-cycle.zzy) |
| TEST-01 | [run:p04-assert-once](../../tests/p04/inputs/assert-once.zzy) | [run:p04-spec-run-skipped](../../tests/p04/inputs/spec-run-skipped.zzy) | [run:p04-assert-false](../../tests/p04/inputs/assert-false.zzy) |
| CLI-01 | [run:hello](../../tests/run/inputs/hello.zzy) | [check:empty](../../tests/run/inputs/empty.zzy) | [check:missing-file（故意缺文件）](../check/cases.json) |
| CLI-02 | [run:p06-doc-syntax-2](../../tests/p06/guide/syntax-2/main.zzy) | [check:bom-crlf-name](../../tests/check/inputs/bom-crlf-name.zzy) | [run:p06-diagnostic-unit](../../tests/p06/inputs/diagnostic-unit.zzy) |
| RESOURCE-01 | [check:ast-at](../../tests/run/inputs/ast-at.zzy) | [run:p03-depth-64](../../tests/p03/inputs/depth-64.zzy) | [run:p03-depth-65](../../tests/p03/inputs/depth-65.zzy) |
| RESOURCE-02 | [run:p06-resource-runtime_payload_bytes-at](../../tests/p06/inputs/resource-runtime_payload_bytes-at.zzy) | [run:p06-resource-runtime_payload_bytes-below](../../tests/p06/inputs/resource-runtime_payload_bytes-below.zzy) | [run:p06-resource-runtime_payload_bytes-over](../../tests/p06/inputs/resource-runtime_payload_bytes-over.zzy) |

## 公开库与不可在语言中捕获的状态

库签名逐项正常/空值/错误证据沿用 [P05 映射](../p05/README.md)：array 的 sum/stats/sorted/map/filter、text 全部函数、math.abs、data 全部 Map/JSON/kind、unit.make/format，以及基础 len/str/range/wake、io 全部接口。P05 arity-*、outer-type-* 覆盖新增接口参数校验；旧接口边界在 P01—P04。data.kind 七类和 other、循环不遍历、Lazy 不唤醒、Result 不解包及查询拒绝在 kind-*；本次 [练习](../../examples/agent-practice/task.md) 进一步验证先分类再校验业务、失败保留旧文件。

ARRAY-02：P02/P03/P05 宿主测试覆盖结构/内容版本、遍历 active 在普通错误、取消、资源和 MemoryError 后归零；当前没有元素校验缓存。LAZY-01：P04 验证缓存普通错误原位置/当前 wake notes，资源和取消恢复 NEW；ZZY 无 try/catch，不能虚构致命错误后在同一脚本继续观察。MACHINE-02：P04/P05 宿主测试验证嵌套冻结、预留失败前状态不提交。MOD-01/TEST-01：P05 验证同 Program 多次执行的模块状态隔离、旧字节快照、新准备读取变化、spec 删除依赖后仍按收集图执行。上述宿主补充随一键入口实际运行，和 CLI 证据分开计数。

## 资源证据及范围

全部 20 个已生效限额均有小配置 L-1/L/L+1：固定工作量时分别把容量设为需求+1、需求、需求-1，等价检查低于/等于/超过上限。对象/槽/载荷计量基于契约的逻辑存储，非 RSS。

| 限额 | 小配置证据 | 默认值证据 |
|---|---|---|
| source_file_bytes / source_total_bytes | test_p06_resources.test_source_graph_and_file_adjacent_limits | 2 MiB / 16 MiB 相邻三值，真实 check |
| module_count / import_depth | 同上，入口计 1 | 127/128/129 与 31/32/33，真实依赖图 |
| tokens_per_file / ast_nodes_total | inputs/resource-* 三例 | 249999/250000/250001 Token；499999/500000/500001 AST，AST 实验显式仅提高 Token 容量避免先撞另一限制 |
| syntax_depth / call_depth / value_depth | inputs/resource-* 与 P03/P05 深度组 | P01/P03/P02/P05 已有 63/64/65，完整回归重跑 |
| numeric_digits / integer_bits / quantity_exponent_abs | inputs/resource-* | 4095/4096/4097 位、65535/65536/65537 bit、63/64/65 指数，真实 CLI |
| text_codepoints / io_payload_bytes | inputs/resource-*，输入 stdin 独立期望 | 文件读取 4 Mi 码点 / 16 MiB 相邻三值；IO 字节实验提高 text_codepoints 4 个码点以隔离限制 |
| container_items / runtime_objects / runtime_slots / runtime_payload_bytes | inputs/resource-*；P02/P03/P05 别名、共享载荷、逐槽计费、释放、引用环 | 最大默认容量压力未验证；不把缩小配置通过等同百万容器/128 MiB 实分配通过 |
| stdout_bytes / stderr_bytes | inputs/resource-stdout_*；test_stderr_exact_utf8_adjacent_and_final_reserve | 1 MiB 相邻三值；stderr 多条完整 JSON Lines，溢出保留此前记录并只追加一次 ≤4 KiB 最终诊断 |
| program_cache_entries / program_cache_bytes | 仅配置/指纹校验 | N/A：尚无长期 Program 缓存，容量淘汰、宽缓存转紧策略在 P07 实施后验收，不宣称缓存命中 |

配置错误（Bool/零/负/重复/未知/版本/编码/64KiB）在 test_resources/test_cli；每条黑盒报告保留生效策略和指纹。P05 同 Program/不同上下文与资源回收、P06 进程超时清理一同回归。默认大 stdin 的性能没有完成验收：一次 1 MiB 逐字符输入探针超出 60 秒外部预算，已回收；默认 stdout 容量改由受限文件读取供值验证，未将该性能探针标为通过，留 P07 调研。

## 诊断、进程和平台

四个正式诊断原文独立保存在 inputs/diagnostic-*.zzy，分别按 run/check 的不同阶段检查。test_p06_diagnostics 额外验证文本/JSON 一致、BOM/CRLF/中文/空格/补充平面字符/Tab/EOF 零宽，以及执行中宿主缺陷保持 internal_error/1。缺文件 null span、跨文件调用、Lazy 主位置/notes、trace 与 error、输入编码在既有 CLI/P03/P04/P05 回归。

Windows 使用 Job Object 管理测试进程树，CREATE_SUSPENDED 后先加入 job 再恢复；所有正常或异常出口均回收后代，并等待 Job 的 active process 归零；包含不继承输出管道、持有文件句柄的孙进程。超时、持续输出、父进程先退出、取消、设置 job 失败、管道与临时目录回收及重复启动句柄数量均实测。参考 [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[OpenThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openthread)。POSIX 实现进程组清理，但本轮没有 POSIX 执行证据。

真实 Ctrl+C 在隐藏独立控制台运行 run 和 test，以 GenerateConsoleCtrlEvent 发送到该控制台；没有向用户控制台广播，也没有用注入 KeyboardInterrupt 代替。程序到达无分配 while 循环的准备点后触发，验证 cancelled/code=null/130 及 spec 目录清理。阻塞输入或单次宿主调用的中断延迟未单独测量，测试硬超时仍由进程树隔离提供。修复从桌面父进程继承 ignore-Ctrl+C 标志的问题。故障注入只用于补充明确的 setup/internal_error 等不可稳定制造边界。

## 指南与 Agent 练习

[guide/manifest.json](guide/manifest.json) 穷举 skills/syntax.md 的 13 段及 skills/guide.md 的 2 段，按字节内容回归，模块双文件保持同目录依赖。每段 check/run 的独立答案在 cases.json；语法 spec、累加 spec、JSON 文件函数的正常/错误 spec 在 test_p06_guides 中执行。AI SKILL 是路由与步骤，没有未验证的可执行代码块。

[specs/metamorphic.zzy](specs/metamorphic.zzy) 九例验证 sum 复制/排列、stats 独立循环、with/别名、JSON 结构往返、Quantity 精确换算、Machine 状态失败/环、query 分阶段稳定插入参考、pipeline 一次求值、sorted 幂等和固定值。每例独立进程，外部同时检查九行固定 stdout 和精确汇总。

Agent 练习的任务、源码与真实记录见 [examples/agent-practice](../../examples/agent-practice/README.md)。当前 Agent 按指南完成，非未接触项目的第三方盲测；没有编造其他 Agent/他人使用记录。

未验证/未实现边界：其他 Python/OS、GUI 与 sketch、公开 Web/嵌入共享冻结、优化缓存/VM、性能收益、断电持久化及对抗恶意进程逃逸。它们属于 E/P07/P08/P09/P10/P11 或明确不承诺的范围；不会因 P06 测试通过而成为可用 API。
