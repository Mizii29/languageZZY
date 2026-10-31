# ZZY 文档导航

更新：2026-10-31｜核心语法：v0.6｜标准库：v0.6.1｜绘图扩展：sketch 1.0

本目录维护设计与开发计划，项目介绍见 [根目录 README](../README.md)，使用文档见同级 [skills](../skills/README.md)。P00—P07 已完成，有宿主及统一 lex/run/check 外部黑盒测试和隔离 spec 运行器；P06 核心覆盖映射与指南示例已验证；B01—B09基线和一项优化的实测报告已建立，校园任务管家已实现并有独立应用测试。文件按用途归类，详细版解释整体设计，skills 提供语法参考和开发指南；精确规则由各专题契约维护。

## 1. 从哪里开始读

- 想编写 ZZY 程序：读 [语法规则参考](../skills/syntax.md) 和 [开发指南](../skills/guide.md)；AI 先读 [项目 SKILL](../skills/zzy/SKILL.md)，再按任务查阅本目录契约。已运行示例见根 README，完整指南逐段验证见 [P06](../tests/p06/README.md)。
- 想了解完整方案：读 [设计详细版](design详细版.md)，它串起语法、特色、运行机制和交付要求。
- 准备写解释器：先读 [阶段计划](development/roadmap.md) 与 [待办状态](development/todo.md)，再对照 [语法契约](language/syntax.md)、[标准库契约](language/stdlib.md) 和 [实现流程](runtime/interpreter.md)。
- 准备落实补充设计：看 [资源限额](runtime/resources.md)、[诊断样例](language/diagnostics.md)、[性能基准清单](runtime/performance.md) 和 [应用保存/恢复](development/campus-app.md)。
- 准备接手续做：先看 [开发记录](development/development-log.md) 的最新条目，再核对实际文件；P07实测见性能报告，P09应用实现与验收见最新记录和[应用说明](../apps/zzy-campus/README.md)，E1—E4、P08及P10-01/06已有验收。P11-01—07已按[优化计划](runtime/optimization-plan.md)评估及自动验收，04/05撤回，人工M01/M02已于2026-10-31补完核验；下一项 **P12-01交付物索引**；原交付阶段顺延为P12，实际状态以todo为准。
- 准备最终完整测试：读 [最终测试计划](development/final-test-plan.md)；[人工测试统一目录](manual-tests/README.md)保存历次指南、结果与证据。当前P11优化后的[人工方案](manual-tests/p11-20261030/README.md)保留Ctrl+C/恢复和绘图/历史/导出/重开两项，[结果摘要](manual-tests/p11-20261030/result.md)已核验通过，撤销/重做按操作人确认；P08结果独立保留，P10合约网页六项仍待验。持续回归的实际工作流和本机复现见 [CI设计与实施](development/ci-design.md)；本地结果见最新开发记录，云端首跑单独记录。
- 配置输出与日志：读 [日志配置说明](runtime/logging.md)；[logging.json](runtime/logging.json) 已用于 CI 回归日志的大小轮转、压缩和自动淘汰，CLI 错误码与 stdout/stderr 协议沿用正式契约。

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
    optimization-plan.md         P11五项优化与验证计划
    optimization-report.md       P11逐项实测、保留与撤回
    resources.md
    logging.md
    logging.json
  development/                    开发、验证与交接
    roadmap.md
    todo.md
    test-coverage.md
    final-test-plan.md
    ci-design.md
    manual-test-guide.md          旧链接入口，正文已归档
    development-log.md
    campus-app.md
  manual-tests/                   按轮次统一归档人工资料
    README.md
    P06结束后的手动测试.png
    core-sketch-20261027/          上次详细指南、原始 DOC 与证据
    p08-20261028/                  本次简要方案、结果表与运行证据
    p11-20261030/                  当前候选人工方案、原始DOC、结果与复核
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
| 运行 | [optimization-plan.md](runtime/optimization-plan.md) | P11五项已选优化的顺序、实现边界、测试/测量及交接标准；状态见todo与optimization-report |
| 运行 | [resources.md](runtime/resources.md) | default-v1 容量、配置、取消、测试超时和扩展限额 |
| 运行 | [logging.md](runtime/logging.md)、[logging.json](runtime/logging.json) | 输出/诊断规则、CI日志轮转/压缩/淘汰的生效配置和本机查看方法 |
| 开发 | [roadmap.md](development/roadmap.md) | 阶段依赖、开发顺序、完成标准和交付路径 |
| 开发 | [todo.md](development/todo.md) | 唯一任务状态清单；原70项加P11七项，共77项，P11评估后撤回单列；当前勾选及待验见清单 |
| 开发 | [test-coverage.md](development/test-coverage.md) | 黑盒覆盖计划及扩展/资源验证要求 |
| 开发 | [final-test-plan.md](development/final-test-plan.md) | 最终测试阶段、自动化命令、18项人工清单、证据与放行标准 |
| 开发 | [ci-design.md](development/ci-design.md) | GitHub Actions触发、环境、回归/安装作业、汇总门禁及实施验收 |
| 人工验收 | [manual-tests/README.md](manual-tests/README.md) | 历次原始结果、当前P11人工方案与已核验结果、其他仍待验项目 |
| 开发 | [development-log.md](development/development-log.md) | 实际修改、验证、失败与交接证据 |
| 开发 | [campus-app.md](development/campus-app.md) | P09 文件格式、业务校验、保存恢复、ID 与撤销 |

## 3. 文档之间怎样分工

用户指示优先，作业交付约束以 requirement 原文为准。核心语法以 syntax 为准，核心库以 stdlib 为准；query、machine-units 是核心规则的细化，sketch 是独立扩展契约。design 和 skills 只归纳说明，不另定一套语法。发现冲突应按对应契约核对并同步说明，不能通过改弱规则掩盖实现不足。

开发顺序写在 roadmap，完成状态只更新 todo，实际证据写在 development-log。覆盖计划不是测试通过报告，性能设计不是性能测量报告。

resources 细化容量策略，diagnostics 细化诊断格式，campus-app 只规定默认应用，不给核心语言添加任务业务。语法仍为 v0.6，标准库 v0.6.1 仅新增 data.kind；资源策略、诊断与应用文件各有独立版本。已实现的基准与CLI用法见对应README及实际代码；文档中的后续设计不能视为已实现命令。final-test-plan规定最终验收组织，manual-test-guide给出本机详细步骤，ci-design说明持续集成实现及尚待验证的云端范围，均复用现有契约与测试。

A/C/D 已纳入 P04；E 已按 E1—E4 实现并验收。P08互联及P10-01/06已有验收，P10未选候选保留并说明取舍；B自动依赖刷新及其他兴趣场景未采用。P11的保留、撤回及验收证据见优化报告，两项人工已补完；随后做P12验收交付，P10合约网页六项仍需核对，E不替换P09的不少于200行ZZY应用。

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

使用者的语法参考和开发指南已放到同级 skills，AI 文档为 skills/zzy/SKILL.md；language 继续维护正式语法与库契约。真实性能报告已放到 [runtime/performance-report.md](runtime/performance-report.md)，交付索引仍待放到 development。

画笔扩展接手入口：[正式sketch契约](features/sketch.md)、[使用指南](features/sketch-guide.md)、[完整验收](../tests/e4/README.md)。核心/headless/真实GUI分别验收；PNG不可用，E1—E4全部验收，sketch ABI 1.0。

P08现已选择：集中接口见[Web契约](runtime/web.md)，实际HTTP演示见[示例](../examples/web/README.md)，进度以todo为准。


P10-01/P10-06已选择：[集中契约](runtime/web.md)、[独立合约演示](../examples/contracts/README.md)、[覆盖与测量](../tests/p10/README.md)。其余P10候选保持延期，实际完成情况见todo。
