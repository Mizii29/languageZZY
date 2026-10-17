# ZZY 使用文档与 AI 技能

ZZY 是用 Python 构建解释器的自定义脚本语言，面向数组/结构处理、CLI 工具、数据查询和绘图扩展。完整项目介绍见 [根目录 README](../README.md)。本目录与 `docs` 同级，收录使用者和 AI 编写 ZZY 程序所需的文档。

更新：2026-10-15。文档依据核心语法 v0.6、标准库 v0.6.1。P00—P07及P09已有解释器、真实CLI验证、性能报告和[校园应用](../apps/zzy-campus/README.md)，已实现接口以 [根 README](../README.md) 为准；hello/grades/functions/features/features-spec/total-up-to 与 library/ 是可执行示例。语法参考 13 段、人用指南 2 段已逐段验收，映射见 [P06](../tests/p06/README.md)；GUI/Web 仍不可用。

| 文件 | 内容 | 适合谁 |
|---|---|---|
| [syntax.md](syntax.md) | 写法、运算优先级、类型/引用语义、特色机制、模块与测试 | 学习或查语法的开发者 |
| [guide.md](guide.md) | 从需求、数据结构到输入处理、持久化、测试、性能和交付 | 用 ZZY 开发应用的人 |
| [zzy/SKILL.md](zzy/SKILL.md) | AI 工作流程与按任务选择 docs 的索引 | 编程 Agent |

## 阅读方式

初次使用先读语法规则，再按开发指南完成一个小程序。写到查询、数量、绘图或资源处理时，沿文档链接进入对应契约。实现解释器时直接看 [开发阶段](../docs/development/roadmap.md) 和 [实现流程](../docs/runtime/interpreter.md)。

AI 文档不复制整套设计：请让 Agent 先读取 `skills/zzy/SKILL.md`，再根据任务读取其中指向的 `docs` 文件。这是仓库内的文件入口；创建此目录不等于已将技能安装或注册到某个 Agent。相对链接依赖本仓库布局，使用时保留同级的 `docs`。

可以这样说明任务：

> 请先阅读 skills/zzy/SKILL.md，根据它引用的 docs 契约，为 ZZY 编写一个输入校验函数；说明使用的接口是否已实现，并在解释器可用时运行对应测试。

## 文档维护

正式语法以 [docs/language/syntax.md](../docs/language/syntax.md) 为准，库签名以 [stdlib.md](../docs/language/stdlib.md) 为准，扩展规则以各专题为准。`skills/syntax.md` 是面向编程者的规则参考，完整 EBNF 留在正式契约中维护。

修改规则时同步相关指南与示例；实现后给示例补真实验证记录。当前的 70 项代码任务仍以 [todo.md](../docs/development/todo.md) 为唯一状态清单，语义验证记录见 P06 验收页，P07实测见 [性能报告](../docs/runtime/performance-report.md)，文档存在本身不是运行成功证据。

画笔扩展的已实现子集及边界见[sketch阶段指南](../docs/features/sketch-guide.md)，完整契约不等于已实现清单。
