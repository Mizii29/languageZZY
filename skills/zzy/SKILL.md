---
name: zzy
description: 在 ZZY 课程项目中编写或审查 .zzy 程序、实现解释器或标准库、维护语言设计、编写测试及应用时使用。按任务查阅仓库 docs 中的语法、接口、运行时和开发契约，保持自定义语法与实现状态一致；不凭示例推断未实现的能力。
---

# ZZY 项目 AI 使用指南

## 确定任务与当前状态

本文件位于仓库 `skills/zzy/`，下面的 `../../docs/` 路径均相对本文件。它是项目内技能入口；文件存在不代表已安装到某个 AI 工具的全局技能目录，使用时保留整个仓库的相对路径。

先读 [文档导航](../../docs/README.md)、[任务状态与交接栏](../../docs/development/todo.md) 和 [开发记录的最新条目](../../docs/development/development-log.md)，再核对实际文件。不要把历史记录中的旧计数或下一步当作当前事实。

截至 2026-10-17，P00—P07与P09全部已完成，版本 0.6.0a1；核心语法、io/array/text/math/data/unit 标准库、Map/严格 JSON、原子文件保存及模块已接通。B01—B09性能基线与诊断路径优化已实测；校园任务管家已实现；Sketch真实GUI与headless分别验收。check 仅做前端准备，不执行用户表达式；test 对每个 spec 启动独立进程。一键完整回归为 python -X utf8 -m tests；独立外部清单入口仍为 python -X utf8 -m tests.blackbox。P06 已补指南片段、变形 spec、真实 Windows Ctrl+C 与进程树验收，证据和未测范围见 tests/p06/README.md。P07证据见 benchmarks/results 和 docs/runtime/performance-report.md；版本以Git区分，超时不算通过。P09应用入口为 apps/zzy-campus/main.zzy，必须使用同目录limits.json，业务全部为ZZY；启动、行数、失败/恢复验收见该目录README及tests/p09。E1—E4已全部验收，sketch ABI 1.0；实际状态以todo为准，使用范围与配额见docs/features/sketch-guide.md，真实GUI/安装证据见tests/e4；用户现已选择P08，当前下一项以文末与todo为准；原P11交付阶段已于2026-10-29顺延为P12；当前先按新P11优化计划推进，最新状态见文末和todo；先核对 README、todo、最新记录、代码和 Git。语法 v0.6/标准库 v0.6.1 规则不变。

遵循用户任务范围与适用的仓库指示。只整理文档时不启动实现；只要求审查时不扩展成语言重设计。作业约束查 [requirement](../../docs/requirement.md)，保留原文。

## 按任务读取权威文档

先读完成任务必需的文档，再按遇到的接口展开。下面是路由表，不要求无关任务加载所有全文。

| 任务 | 必读文档 |
|---|---|
| 写或审查 ZZY 程序 | [syntax](../../docs/language/syntax.md)、涉及调用的 [stdlib](../../docs/language/stdlib.md) |
| 整体设计、定位功能范围 | [design详细版](../../docs/design详细版.md)、[innovation](../../docs/features/innovation.md) |
| Lexer/Parser/Resolver、作用域与执行 | [syntax](../../docs/language/syntax.md)、[interpreter](../../docs/runtime/interpreter.md) |
| 查询与纯性 | [query](../../docs/features/query.md)，并核对语法及库白名单 |
| 状态机或单位 | [machine-units](../../docs/features/machine-units.md) |
| 画笔、事件、导出、回放与 GUI | [sketch](../../docs/features/sketch.md)，按 E 阶段实施 |
| 错误、源码坐标、CLI 输出 | [diagnostics](../../docs/language/diagnostics.md)、syntax 中的错误语义 |
| 配额、取消、缓存或大输入 | [resources](../../docs/runtime/resources.md)、[interpreter](../../docs/runtime/interpreter.md) |
| 黑盒测试与验收 | [test-coverage](../../docs/development/test-coverage.md)、[roadmap](../../docs/development/roadmap.md) |
| 性能比较与优化 | [performance](../../docs/runtime/performance.md)、resources |
| 校园应用、JSON 保存加载与撤销 | [campus-app](../../docs/development/campus-app.md)、stdlib |
| 开发阶段与交接 | [roadmap](../../docs/development/roadmap.md)、todo、development-log |

核心语法以 syntax 为准，标准库签名以 stdlib 为准；专题细化对应规则，sketch 独立版本化。总览、指南与历史日志不能覆盖正式契约。发现矛盾时核对并指出具体位置，必要时同步修正说明；不要为迁就实现而默默放宽规则。人用教程可辅助阅读 [开发指南](../guide.md)，但不能替代契约。

## 生成或修改程序

1. 查当前实现状态，列明输入、预期输出、边界及依赖；未实现功能只能给明确标注的契约示例。
2. 直接按 syntax 的 Token/EBNF 写源码，不将 Python/JavaScript 习惯搬入 ZZY。使用 `zzysay:`、`zzysayalot: ... zzyend` 注释和 `[OoO]` 转义；声明、赋值、分支、Result 匹配等拼写逐一核对。
3. 对每个宿主调用核对命名空间、参数顺序/数量、类型、返回和副作用。不要虚构裸 print、泛型、字典字面量、默认参数、异常捕获或未登记的 Web 接口。
4. 对外部 JSON 先 data.kind，再检查键与业务约束，最后构造结构；可恢复失败显式 Result。注意 zno 不冻结对象、with/copy 仅浅复制、Lazy 不自动刷新、query 不允许任意用户调用。
5. 保留用户修改，修改相关文件并补必要用例。多模块示例给出全部文件关系和启动工作目录；将正常示例和故意错误样例明确分开。
6. 只有仓库实际提供解释器及对应 CLI 时才执行 check/run/test。执行后如实报告命令、结果与限制；静态链接、围栏或语法外形检查不能写成“程序运行通过”。

## 实现与交付

按 roadmap 的依赖选择 todo 中的任务，先打通树遍历核心执行链，再扩展；不跳过基础直接做 VM、Web 或性能宣传。只将达到完成标准的任务标为完成，真实操作与验证写入 development-log。新增语法或接口必须同步权威契约、覆盖计划及使用说明，版本按影响调整，不复制第二份完整 EBNF 到本技能。

测试以 ZZY 黑盒为主，非法源码独立文件，外部清单检查诊断及退出码。测试无用例、失败、超时或输出超额均不能报成功；优化后确认行为和资源语义保持。性能结论必须来自等价工作量的真实记录。

交接时说明修改文件、实际验证、未验证部分和下一项；区分“设计完成”“接口实现”“测试通过”。应用业务写在 ZZY 中，满足 requirement 的行数与交付要求；Agent 记录来自真实开发，不补造历史。

## P08已选（2026-10-28）

继续Web前读取[集中接口契约](../../docs/runtime/web.md)、todo交接及最新日志。P08-01用可选Starlette/Uvicorn、宿主固定路由和默认每请求完整实例化；web.get/web.serve没有语言接口，不能凭旧设计示例调用。后续任务按依赖继续，不提前实现P10。

P08-02已实现显式shared=True/--shared，默认逐请求模式保留；共享Lazy/可变绑定/Cell闭包/原生句柄拒绝。P08-03公开Python入口zzy.embedding.load_module/call/close，每调用独立上下文、自动严格转换与清理，CallResult含value/stdout/stderr；不传内部Value。详细规则只维护在Web契约，阶段验收数字与下一项看todo及最新日志；SQLite事务接口和独立示例已实现，验收见todo。

P08-04/05本轮新增SQLite事务与独立任务示例；实际db签名、提交/回滚与取消边界以docs/runtime/web.md为准。SQLite专项、真实HTTP重启、安装和完整回归证据见tests/p08；当前验收状态见todo。


## P10-01 / P10-06 已实现并验收

2026-10-29用户已显式选择本范围。shape合约读取[集中接口契约](../../docs/runtime/web.md)的P10-01节和[演示](../../examples/contracts/README.md)。使用zzy.contracts生成及Web --contracts显式启用；check不自动启用合约。严格Int/Float标签不能靠通用JSON Schema完全验证；Array/Map不推断元素类型。业务仍接收Map，不调用shape默认表达式。正式验收及延期项看todo；不得扩大为P10-08完成。

## P11已选优化与P12交付（2026-10-29）

P10-01/06已完成。用户选择诊断位置、资源计量、小整数、sum/stats、查询排序五项，新增P11-01—07；原P11-01—05一一顺延为P12-01—05，历史日志/报告的旧编号不重写。P11-01—05已评估（04/05收益未证实而撤回，无生产小整数快路径或sum分离），下一项P11-06；整体终验含notes故障补修；当前进度以todo为准。

实施必读[优化计划](../../docs/runtime/optimization-plan.md)、[性能方法](../../docs/runtime/performance.md)、[资源](../../docs/runtime/resources.md)、[覆盖计划](../../docs/development/test-coverage.md)及相关诊断/stdlib/query/Web契约。顺序01基线→02诊断位置→03计量→04小整数→05sum/stats→06查询排序→07累计验收→P12交付。每项先验证再单独测量并记录去留，不预设加速倍数，不通过弱化配额/错误顺序/取消换速度；无收益可撤回并如实标注评估结论。

P10未选项保留，逐项利弊见[创新取舍](../../docs/features/innovation.md#6-p10-候选保留与取舍2026-10-29)。小整数快路径和必要对照仅落实相关子范围，不将P10-03/08整体勾选，不擅自实现VM、结果缓存或热切换。优化证据和报告的计划路径不代表文件/命令已经存在；实际创建后补映射，人工结果只记录真实执行。
