# ZZY 文档导航

更新：2026-10-10｜核心语法：v0.6｜标准库：v0.6.1｜绘图扩展目标：sketch 1.0

本目录维护设计与开发计划，项目介绍见 [根目录 README](../README.md)，使用文档见同级 [skills](../skills/README.md)。P00/P01 最小执行链已完成，有宿主及统一 lex/run/check CLI 黑盒测试；zzy test、后续语法、完整黑盒集、性能数据和应用尚未实现。文件按用途归类，详细版解释整体设计，skills 提供语法参考和开发指南；精确规则由各专题契约维护。

## 1. 从哪里开始读

- 想编写 ZZY 程序：读 [语法规则参考](../skills/syntax.md) 和 [开发指南](../skills/guide.md)；AI 先读 [项目 SKILL](../skills/zzy/SKILL.md)，再按任务查阅本目录契约。示例仍待运行验证。
- 想了解完整方案：读 [设计详细版](design详细版.md)，它串起语法、特色、运行机制和交付要求。
- 准备写解释器：先读 [阶段计划](development/roadmap.md) 与 [待办状态](development/todo.md)，再对照 [语法契约](language/syntax.md)、[标准库契约](language/stdlib.md) 和 [实现流程](runtime/interpreter.md)。
- 准备落实补充设计：看 [资源限额](runtime/resources.md)、[诊断样例](language/diagnostics.md)、[性能基准清单](runtime/performance.md) 和 [应用保存/恢复](development/campus-app.md)。
- 准备接手续做：先看 [开发记录](development/development-log.md) 的最新条目，再核对实际文件；P01 已验收，下一项 P02-01，实际状态以 todo 为准。

## 2. 文件分类

```text
docs/
  README.md                       文档入口
  requirement.md                  作业原文，禁止修改
  design详细版.md                  全项目设计总览
  language/                       语言语法与标准库
    syntax.md
    stdlib.md
    diagnostics.md
  features/                       已选特色与扩展设计
    innovation.md
    query.md
    machine-units.md
    sketch.md
  runtime/                        解释器与性能设计
    interpreter.md
    performance.md
    resources.md
  development/                    开发、验证与交接
    roadmap.md
    todo.md
    test-coverage.md
    development-log.md
    campus-app.md
```

| 类别 | 文件 | 负责的内容 |
|---|---|---|
| 总览 | [requirement.md](requirement.md) | 不可修改的作业要求、评分与八项交付物 |
| 总览 | [design详细版.md](design详细版.md) | 系统结构、设计理由、约束和各专题关系 |
| 语言 | [syntax.md](language/syntax.md) | Token、EBNF、类型、作用域、求值顺序和诊断 |
| 语言 | [stdlib.md](language/stdlib.md) | 库签名、参数/返回、I/O、JSON 和副作用边界 |
| 语言 | [diagnostics.md](language/diagnostics.md) | 文本/JSON Lines 诊断、源码坐标、错误与修复样例 |
| 特色 | [innovation.md](features/innovation.md) | 已选设计、工程措施与可选研究的区别 |
| 特色 | [query.md](features/query.md) | A：集合查询、纯性、稳定排序和函数封装 |
| 特色 | [machine-units.md](features/machine-units.md) | C/D：状态机、精确数量和量纲规则 |
| 特色 | [sketch.md](features/sketch.md) | E：画笔、图层、撤销/回放、事件及图案库导出 |
| 运行 | [interpreter.md](runtime/interpreter.md) | Lexer、Parser、Resolver、运行时、宿主库的实现流程 |
| 运行 | [performance.md](runtime/performance.md) | 扫描成本、优化边界、稳定性和公平测量方法 |
| 运行 | [resources.md](runtime/resources.md) | default-v1 容量、配置、取消、测试超时和扩展限额 |
| 开发 | [roadmap.md](development/roadmap.md) | 阶段依赖、开发顺序、完成标准和交付路径 |
| 开发 | [todo.md](development/todo.md) | 唯一任务状态清单；记录 70 项代码任务的实际完成情况 |
| 开发 | [test-coverage.md](development/test-coverage.md) | 黑盒覆盖计划及扩展/资源验证要求 |
| 开发 | [development-log.md](development/development-log.md) | 实际修改、验证、失败与交接证据 |
| 开发 | [campus-app.md](development/campus-app.md) | P09 文件格式、业务校验、保存恢复、ID 与撤销 |

## 3. 文档之间怎样分工

用户指示优先，作业交付约束以 requirement 原文为准。核心语法以 syntax 为准，核心库以 stdlib 为准；query、machine-units 是核心规则的细化，sketch 是独立扩展契约。design 和 skills 只归纳说明，不另定一套语法。发现冲突应按对应契约核对并同步说明，不能通过改弱规则掩盖实现不足。

开发顺序写在 roadmap，完成状态只更新 todo，实际证据写在 development-log。覆盖计划不是测试通过报告，性能设计不是性能测量报告。

resources 细化容量策略，diagnostics 细化诊断格式，campus-app 只规定默认应用，不给核心语言添加任务业务。语法仍为 v0.6，标准库 v0.6.1 仅新增 data.kind；资源策略、诊断与应用文件各有独立版本。基准文件路径及 CLI 新选项均为待实现设计，不是当前可运行命令。

A/C/D 已纳入 P04；E 是已选扩展，按 E1—E4 开发。Web/Python 互联属于可选 P08，VM、自动缓存等属于有条件的 P10；B 自动依赖刷新及其他兴趣场景未采用。核心主线仍从 P00 开始，E 不自动替换 P09 的不少于 200 行 ZZY 应用。

## 4. 旧文件位置对照

历史记录保留当时的文件名称；当前入口和链接使用新位置。未列出的 README、requirement 保留原路径。

| 原 docs 下的位置 | 当前位置 |
|---|---|
| design.md | [design详细版.md](design详细版.md) |
| design简版.md、design简单版.md | 当前已无此文件；整体方案读 [详细设计](design详细版.md)，编程入门读 [开发指南](../skills/guide.md) |
| syntax.md、stdlib.md | language/ 下的同名文件 |
| innovation.md、query.md、machine-units.md、sketch.md | features/ 下的同名文件 |
| interpreter实现流程.md | [runtime/interpreter.md](runtime/interpreter.md) |
| performance简单.md | [runtime/performance.md](runtime/performance.md) |
| process.md | [development/roadmap.md](development/roadmap.md) |
| todo.md、test-coverage.md、development-log.md | development/ 下的同名文件 |

使用者的语法参考和开发指南已放到同级 skills，AI 文档为 skills/zzy/SKILL.md；language 继续维护正式语法与库契约。后续真实性能报告放 runtime，交付索引放 development，报告与交付索引尚未建立。
