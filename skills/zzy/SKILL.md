---
name: zzy
description: 在 ZZY 课程项目中编写或审查 .zzy 程序、实现解释器或标准库、维护语言设计、编写测试及应用时使用。按任务查阅仓库 docs 中的语法、接口、运行时和开发契约，保持自定义语法与实现状态一致；不凭示例推断未实现的能力。
---

# ZZY 项目 AI 使用指南

## 确定任务与当前状态

本文件位于仓库 `skills/zzy/`，下面的 `../../docs/` 路径均相对本文件。它是项目内技能入口；文件存在不代表已安装到某个 AI 工具的全局技能目录，使用时保留整个仓库的相对路径。

先读 [文档导航](../../docs/README.md)、[任务状态与交接栏](../../docs/development/todo.md) 和 [开发记录的最新条目](../../docs/development/development-log.md)，再核对实际文件。不要把历史记录中的旧计数或下一步当作当前事实。

截至 2026-10-09，P00 包、CLI 帮助/环境/源码摘要、资源策略和诊断基础已有实现与宿主测试；核心语法 v0.6、标准库 v0.6.1，尚无语言执行器、ZZY 黑盒或性能结果。后续接手时重新验证该状态；不要因为本文件写了接口或命令，就报告它们可用。

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
