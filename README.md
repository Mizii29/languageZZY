# ZZY 语言

ZZY 是赵梓伊在程序设计实践课程中设计的通用脚本语言，计划使用 Python 实现解释器，用 ZZY 编写测试、性能脚本和完整应用。

**当前状态：设计与指南阶段。** 核心语法 v0.6、标准库设计 v0.6.1；解释器、真实黑盒测试、性能报告和应用尚未实现。文档中的示例是预期写法，尚未运行验证。

## 项目特色

- `(zno)` / `(zyes)` 区分固定绑定与可变绑定，`:=` 初始化、`<-` 赋值。
- `zzysay:` 与 `zzysayalot: … zzyend` 注释，`[OoO]` 字符串转义。
- 笑脸/哭脸 Result、显式 Lazy 和 `~>` 管道。
- `?>` 集合查询、箭头状态机、精确带单位数值。
- 已选 sketch 画笔扩展：图层、撤销/回放、图案函数库与无窗口导出，全部待实现。

## 从哪里开始

| 目的 | 文档 |
|---|---|
| 学习语言写法 | [语法规则](skills/syntax.md) |
| 用 ZZY 开发程序 | [开发指南](skills/guide.md) |
| 让 AI 编写、修改或检查 ZZY | [AI 文档 / SKILL.md](skills/zzy/SKILL.md) |
| 浏览使用文档 | [skills 导航](skills/README.md) |
| 理解总体方案 | [详细设计](docs/design详细版.md) |
| 查阅正式契约 | [docs 导航](docs/README.md) |
| 继续实现项目 | [开发阶段](docs/development/roadmap.md)、[待办](docs/development/todo.md)、[实际记录](docs/development/development-log.md) |

## 当前目录

```text
README.md                 项目介绍
docs/                     权威契约、设计、实施计划和验证记录
skills/                   面向使用者和 AI 的文档
  README.md               文档导航与使用方式
  syntax.md               ZZY 语法规则参考
  guide.md                ZZY 开发指南
  zzy/
    SKILL.md              AI 工作入口，按需查阅 docs
```

`zzy/`、`tests/`、`benchmarks/`、`apps/` 是后续开发目录，当前尚未建立。

## 运行方式与交付目标

下面是**待实现的 CLI 约定**，现在不能作为可运行命令使用；示例路径也待建立：

```text
python -m zzy check examples/hello.zzy
python -m zzy run examples/hello.zzy
python -m zzy test tests/
```

核心计划只依赖 Python 标准库；支持的 Python 版本和平台在 P00 实际验证后公布。Web、NumPy 和字节码 VM 属于可选后续工作。

课程交付包括语法文档、解释器、ZZY 黑盒测试、与 Python 的性能比较、人和 AI 的指南、不少于 200 行的完整 ZZY 应用及开发记录、Git 历史和 PPT。原始约束见 [作业要求](docs/requirement.md)。默认应用是校园任务管家，画笔扩展不自动替代应用交付。

`docs` 维护正式规则，`skills` 将其组织为学习和开发入口。指南存在不代表接口已经实现；后续以真实代码、测试结果和开发记录更新能力状态。
