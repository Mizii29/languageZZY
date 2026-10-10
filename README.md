# ZZY 语言

ZZY 是赵梓伊在程序设计实践课程中设计的通用脚本语言，计划使用 Python 实现解释器，用 ZZY 编写测试、性能脚本和完整应用。

**当前状态：P00—P02 已实现，P02 验收结果见开发记录。** 包版本 0.2.0a1；核心语法 v0.6、标准库契约 v0.6.1。Python AST 树遍历解释器支持基础数据、控制流、数组、结构与基础 I/O；`run/check` 共用前端。539 个外部 CLI 用例使用独立 `.zzy` 和期望清单，不依赖 spec。用户函数/闭包从 P03 开始；`zzy test`、特色语法、其余库、性能报告和完整应用尚未实现。

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
pyproject.toml            包配置，核心无第三方运行依赖
zzy/                      CLI、Lexer/Parser/AST、准备/执行、源码、诊断和资源基础
tests/                    宿主测试及 lex/run/check 的 .zzy 外部清单和统一运行器
examples/                 读取/词法样例、hello.zzy 与 grades.zzy 成绩菜单
benchmarks/               基准目录说明；P07 实现
apps/                     应用目录说明；P09 实现
docs/                     权威契约、设计、实施计划和验证记录
skills/                   面向使用者和 AI 的文档
  README.md               文档导航与使用方式
  syntax.md               ZZY 语法规则参考
  guide.md                ZZY 开发指南
  zzy/
    SKILL.md              AI 工作入口，按需查阅 docs
```

当前 `run/check` 只处理下述已实现子集；不支持的语法明确拒绝，`zzy test` 尚未注册。

## 现在可以运行的命令

已验证环境：CPython **3.12.14**，64 位 Windows 11（10.0.26200），Unicode 15.0.0。`requires-python` 暂限定实际验收的 3.12.14；其他版本/系统尚未验证，扩展范围时再调整。核心运行和宿主测试只用标准库，源码目录直接运行无需安装。

```text
python -m zzy --help
python -m zzy info
python -m zzy run examples/hello.zzy
python -m zzy check examples/hello.zzy
python -m zzy source-info examples/source-sample.zzy
python -m zzy source-info missing.zzy --diagnostic-format json
python -m zzy lex examples/lexer.zzy
python -m zzy lex tests/lex/inputs/unclosed-comment.zzy --diagnostic-format json
python -X utf8 -m tests.blackbox
python -X utf8 -m unittest discover -s tests -v
```

`run examples/hello.zzy` 输出 `5`。`python -m zzy run examples/grades.zzy` 运行 P02 成绩菜单：输入姓名，再输入 `1`，固定四门成绩的总分为 344、平均分 86.0、最高分 100；其他菜单输入退出，姓名输入 EOF 输出“输入结束”。业务计算、循环与分支都在 ZZY 中。

当前已实现：

- Int、有限 Float、String/raw、Bool、Null，四则运算、Int 向下整除/取余、严格比较和 Bool 短路。大 Int 与 Float 比较保留数学精度；Bool 不隐式充当 Int。比较链必须显式分组。
- 声明、赋值、块作用域、遮蔽、条件、while/for、半开 Range、break/continue；每轮 for 是新的只读绑定。
- Array 字面、索引、替换、浅复制、push/pop；别名共享，活动遍历期间先拒绝增删，允许替换并读取后续元素的新值。数组的结构/内容版本由统一写入口维护。
- 顶层 shape、名义类型注解、显式字段、每次构造求默认值、字段写入、浅层 with。默认 `[]` 每实例新建，默认外部数组保持共享；with 不重跑默认值。
- 基础库仅有 `io.print/input`、`len/str/range`、`array.copy/push/pop`。len 接受 Array/String/Range；str 接受基础标量。io.input 输出并 flush 提示，去掉一组 LF/CRLF，空行为 String，EOF 为 Null；输入不经过 ZZY 字符串转义。完整 Map/Quantity 等类型及其他 stdlib 接口按后续阶段实现。

普通运算从左到右，调用先求被调用对象及全部实参，再检查可调用性/数量。赋值先定位并检查目标可写性，再求右侧，写入前重新检查下标/类型。zno 禁止重新绑定但不冻结容器；错误不回滚此前副作用。可选注解支持 `(Int)/(Float)/(String)/(Bool)/(Null)/(Array)/(Range)/(Function)` 及已定义 shape 的身份。

`check FILE` 完成整文件词法、语法、词法名称、控制流位置及数字字面准备，成功双流为空、退出 0。它不建立执行器，不计算表达式、不调用输入输出、不运行循环、构造或结构默认值。运行时类型/调用/写入错误不提前报出，因此 check 成功不保证 run 成功。未知/自引用名称 E302、重复声明 E301、非法控制流 E304、语法 E103 在执行前退出 2；运行时类型 E201、调用 E202、写入 E203、下标 E204、除零 E205、活动遍历修改 E206、数值范围 E208 退出 1。结构构造/with 字段清单错误使用 E203，字段访问不存在使用 E302。容量错误统一 E211，依发生阶段退出 2/1。

用户函数、return、spec、模块、Result/Lazy、管道、查询、Machine/Quantity、GUI 等仍明确拒绝或报告接口尚未实现。完整语言设计示例不能作为已实现能力清单。执行覆盖见 [P02 验收](tests/p02/README.md)。

`python -X utf8 -m tests.blackbox` 运行 539 个外部用例；失败、超时、输出超额及空/坏清单返回 1。清单、可选 JSON 报告和资源指纹见 [测试说明](tests/README.md)。

`source-info` 仅做有界 UTF-8 读取，输出字节数、码点数、行数和同一字节快照的 SHA-256；`syntax_checked` 固定为 false，不代表语法检查或执行成功。空文件计 1 行，末尾换行后保留空行。缺文件、非法 UTF-8 和参数错误为 E401/退出 2；前端资源超限为 E211/退出 2。`info` 输出完整宿主版本、Unicode/平台、生效资源配置和指纹。

`lex` 按 v0.6 扫描完整文件，成功后向 stdout 输出 Token JSON Lines，最后一项为零宽 EOF；每项包含 `schema_version: 1`、`kind`、`lexeme`、`value`、`raw`、`span`。字符串 value 为解码后的文字，raw 表示该字符串是否由 `(raw)` 修饰；其余 Token 的 value 为 null，数字原文保存在 lexeme，不转成 Python 数值。位置采用原文 Unicode 码点，BOM 不占列，注释不生成 Token。

`lex` 不检查括号配对、语句结构、名称、类型或执行结果。裸保留名输出 RESERVED_NAME；`(zno )` 不作为关键字，`--x` 切成 STATE_EDGE 和 IDENT，`1e3` 切成 INTEGER 和 IDENT，后续 Parser 再拒绝不合法组合，不能将 lex 成功当作 check 成功。错误字符/未闭合字符串或注释/raw 缺字符串为 E101，错误转义为 E102，均退出 2。完整扫描失败时 stdout 为空；若在输出阶段超限，可能保留此前完整记录，但会报 E211 并非零退出，不可当作完整 Token 流。

词法覆盖与清单格式见 [tests/lex/README.md](tests/lex/README.md)。仅运行词法 CLI 验证可执行 `python -X utf8 -m unittest tests.test_lexer_cli -v`；这不是尚未实现的 `zzy test` 或 spec 运行器。

本机 PATH 中没有 `python`/`py`。本轮用以下实际解释器创建了项目内虚拟环境；也可将 `$zzyPython` 换成自己安装的已验证版本，不需修改系统 PATH：

```powershell
$zzyPython = 'C:\Users\13691\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $zzyPython -m venv --without-pip .venv
& .\.venv\Scripts\python.exe -m zzy --help
& .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

可选安装：在已有 pip/setuptools（构建要求 setuptools>=68）的 Python 3.12.14 环境中执行 `python -m pip install --no-deps --no-build-isolation .`，随后可用 `zzy --help`。源码运行和宿主测试不要求 pip；GUI/Web/NumPy 不会随 CLI 初始化。

`--limits limits.json` 和 `--diagnostic-format text|json` 可放在命令前后。配置键、单位与默认值见 [资源契约](docs/runtime/resources.md)；未知/重复字段、Bool、非正整数、坏版本、超过 64 KiB 的配置均拒绝。`info` 中的指纹覆盖补齐默认后的全部有效值和宿主十进制上限。帮助/版本直接显示，不加载配置文件。

CLI 文件参数和配置路径相对进程工作目录；不会自动切换目录。源码加载器为后续 use 保留相对导入文件的路径接口，当前未实现 use 分析。标准流使用 UTF-8、输出 LF；[诊断](docs/language/diagnostics.md) 提供文本/JSON Lines。前端 E211/退出 2、执行 E211/退出 1 已通过 CLI 验证；取消出口及执行清理通过宿主注入测试，真实终端 Ctrl+C 尚未验收。

## 运行方式与交付目标

下面是**待实现的 spec/语言测试 CLI 约定**，现在不能作为可运行命令使用：

```text
python -m zzy test tests/
```

Web、NumPy 和字节码 VM 属于可选后续工作。P00 的资源计量接口不等于所有未来值/AST/缓存都已接入限额，当前验证范围见 [测试说明](tests/README.md) 与 [开发记录](docs/development/development-log.md)。

课程交付包括语法文档、解释器、ZZY 黑盒测试、与 Python 的性能比较、人和 AI 的指南、不少于 200 行的完整 ZZY 应用及开发记录、Git 历史和 PPT。原始约束见 [作业要求](docs/requirement.md)。默认应用是校园任务管家，画笔扩展不自动替代应用交付。

`docs` 维护正式规则，`skills` 将其组织为学习和开发入口。指南存在不代表接口已经实现；后续以真实代码、测试结果和开发记录更新能力状态。
