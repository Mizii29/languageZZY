# ZZY 语言

ZZY 是赵梓伊在程序设计实践课程中设计的通用脚本语言，计划使用 Python 实现解释器，用 ZZY 编写测试、性能脚本和完整应用。

**当前状态：P00 与 P01-01 词法扫描已实现，语言执行尚未实现。** 包版本 0.1.0a1；核心语法 v0.6、标准库设计 v0.6.1。CLI、源码、资源/诊断基础及 Lexer 已有真实测试，其中词法使用独立 `.zzy` 文件与外部期望清单通过 CLI 验证。Parser、AST 执行器、完整语言黑盒、性能报告和应用仍待后续阶段。

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
zzy/                      CLI、Token/Lexer、源码、诊断、资源及原生元数据基础
tests/                    宿主测试与 lex CLI 的 .zzy 文件/外部清单
examples/                 源码读取与词法样例（不执行）
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

当前不创建空 Parser/执行器，也不提供返回假成功的 run/check/test。

## 现在可以运行的命令

已验证环境：CPython **3.12.14**，64 位 Windows 11（10.0.26200），Unicode 15.0.0。`requires-python` 暂限定实际验收的 3.12.14；其他版本/系统尚未验证，扩展范围时再调整。核心运行和宿主测试只用标准库，源码目录直接运行无需安装。

```text
python -m zzy --help
python -m zzy info
python -m zzy source-info examples/source-sample.zzy
python -m zzy source-info missing.zzy --diagnostic-format json
python -m zzy lex examples/lexer.zzy
python -m zzy lex tests/lex/inputs/unclosed-comment.zzy --diagnostic-format json
python -X utf8 -m unittest discover -s tests -v
```

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

CLI 文件参数和配置路径相对进程工作目录；不会自动切换目录。源码加载器为后续 use 保留相对导入文件的路径接口，当前未实现 use 分析。标准流使用 UTF-8、输出 LF；[诊断](docs/language/diagnostics.md) 提供文本/JSON Lines。内部执行阶段 E211/退出 1 和取消/130 的出口已测试，但尚无 ZZY 执行循环；真实终端 Ctrl+C 验收留到执行链建立后。

## 运行方式与交付目标

下面是**待实现的 CLI 约定**，现在不能作为可运行命令使用；示例路径也待建立：

```text
python -m zzy check examples/hello.zzy
python -m zzy run examples/hello.zzy
python -m zzy test tests/
```

Web、NumPy 和字节码 VM 属于可选后续工作。P00 的资源计量接口不等于所有未来值/AST/缓存都已接入限额，当前验证范围见 [测试说明](tests/README.md) 与 [开发记录](docs/development/development-log.md)。

课程交付包括语法文档、解释器、ZZY 黑盒测试、与 Python 的性能比较、人和 AI 的指南、不少于 200 行的完整 ZZY 应用及开发记录、Git 历史和 PPT。原始约束见 [作业要求](docs/requirement.md)。默认应用是校园任务管家，画笔扩展不自动替代应用交付。

`docs` 维护正式规则，`skills` 将其组织为学习和开发入口。指南存在不代表接口已经实现；后续以真实代码、测试结果和开发记录更新能力状态。
