# ZZY 语言

P10-01 / P10-06 已完成并验收：显式 shape 合约使用同一静态描述完成字段校验、Map 默认值填充和 OpenAPI 3.1.1 生成。入口为 `python -m zzy.contracts` 与 Web `--contracts FILE`；核心无需 Web/GUI 依赖。见[独立演示](examples/contracts/README.md)、[正式契约](docs/runtime/web.md)、[测试与测量](tests/p10/README.md)。最终阶段结果以 todo/开发记录为准；不包含 VM、热更新、自动缓存或其他 P10 项。

ZZY 是赵梓伊在程序设计实践课程中设计的通用脚本语言，使用 Python 实现解释器，用 ZZY 编写测试、性能脚本和完整应用。

**当前状态：P00—P07及P09已完成，运行时版本仍为 0.6.0a1；核心语法、io/array/text/math/data/unit 标准库、Map/严格 JSON、原子文件保存及模块已接通。B01—B09 性能基线与一项已验证优化已有实测；校园任务管家业务已实现并通过专项验证；Sketch 1.0 的 E1—E4 已全部验收。** 核心语法 v0.6、标准库契约 v0.6.1 不变。Python AST 树遍历；run/check/test 共用前端准备。独立外部 CLI 期望与宿主状态/运行器测试覆盖当前能力，阶段证据见开发记录。

## 项目特色

- `(zno)` / `(zyes)` 区分固定绑定与可变绑定，`:=` 初始化、`<-` 赋值。
- `zzysay:` 与 `zzysayalot: … zzyend` 注释，`[OoO]` 字符串转义。
- 笑脸/哭脸 Result、显式 Lazy 和 `~>` 管道。
- `?>` 集合查询、箭头状态机、精确带单位数值。
- 已选 sketch 画笔扩展：E1—E4 实现及验收入口见 [Sketch 指南](docs/features/sketch-guide.md) 与 [tests/e4](tests/e4/README.md)。

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
examples/                 读取/词法样例、hello.zzy 、grades.zzy 成绩菜单与 functions.zzy 函数示例及 features/features-spec 特色示例与 library/ 模块/库示例
benchmarks/               B01—B09 配对程序、原始数据、剖析与交错复测工具
apps/                     ZZY校园任务管家、启动配置与真实Agent记录
docs/                     权威契约、设计、实施计划和验证记录
skills/                   面向使用者和 AI 的文档
  README.md               文档导航与使用方式
  syntax.md               ZZY 语法规则参考
  guide.md                ZZY 开发指南
  zzy/
    SKILL.md              AI 工作入口，按需查阅 docs
```

当前 `run/check` 支持 v0.6 核心语法与 P05 标准库/模块；扩展接口按各自阶段开放，`zzy test` 已注册为隔离 spec 运行器。

## 现在可以运行的命令

已验证环境：CPython **3.12.14**，64 位 Windows 11（10.0.26200），Unicode 15.0.0。`requires-python` 暂限定实际验收的 3.12.14；其他版本/系统尚未验证，扩展范围时再调整。核心运行和宿主测试只用标准库，源码目录直接运行无需安装。

```text
python -m zzy --help
python -m zzy info
python -m zzy run examples/hello.zzy
python -m zzy check examples/hello.zzy
python -m zzy run examples/features.zzy
python -m zzy test examples/features-spec.zzy
python -m zzy source-info examples/source-sample.zzy
python -m zzy source-info missing.zzy --diagnostic-format json
python -m zzy lex examples/lexer.zzy
python -m zzy lex tests/lex/inputs/unclosed-comment.zzy --diagnostic-format json
python -X utf8 -m tests.blackbox
python -X utf8 -m tests
```

`run examples/hello.zzy` 输出 `5`。`python -m zzy run examples/grades.zzy` 运行 P02 成绩菜单：输入姓名，再输入 `1`，固定四门成绩的总分为 344、平均分 86.0、最高分 100；其他菜单输入退出，姓名输入 EOF 输出“输入结束”。业务计算、循环与分支都在 ZZY 中。

`python -m zzy run examples/functions.zzy` 输出 `720`、`[1, 2, 11]`、`[0, 1, 2]`，演示自递归、独立计数器和逐轮闭包。函数注解的定义身份在函数创建时确定；具名函数隐式返回 Null，返回注解仍检查。错误保留发生处源码范围，并在 notes 中追加内到外调用位置。

当前已实现：

- Int、有限 Float、String/raw、Bool、Null，四则运算、Int 向下整除/取余、严格比较和 Bool 短路。大 Int 与 Float 比较保留数学精度；Bool 不隐式充当 Int。比较链必须显式分组。
- 声明、赋值、块作用域、遮蔽、条件、while/for、半开 Range、break/continue；每轮 for 是新的只读绑定。
- Array 字面、索引、替换、浅复制、push/pop；别名共享，活动遍历期间先拒绝增删，允许替换并读取后续元素的新值。数组的结构/内容版本由统一写入口维护。
- 顶层 shape、名义类型注解、显式字段、每次构造求默认值、字段写入、浅层 with。默认 `[]` 每实例新建，默认外部数组保持共享；with 不重跑默认值。
- 具名/匿名函数、高阶调用、return、自递归、可选参数/返回注解、词法闭包。每次调用使用独立局部槽位；可变捕获共享 Cell，不可变捕获保留对象别名，逐轮绑定独立。尚未声明的相互递归报 E302，跨函数 break/continue 报 E304。
- 基础入口包括 `io.print/input`、`len/str/range/wake`、`array.copy/push/pop`；完整库已在 P05 接通，见下文。len 接受 Array/String/Map/Range；str 接受基础标量和 Quantity。io.input 输出并 flush 提示，去掉一组 LF/CRLF，空行为 String，EOF 为 Null；输入不经过 ZZY 字符串转义。Map、严格 JSON、文件、统计/回调、文本和单位库均已实现。

普通运算从左到右，调用先求被调用对象及全部实参，再检查可调用性/数量。赋值先定位并检查目标可写性，再求右侧，写入前重新检查下标/类型。zno 禁止重新绑定但不冻结容器；错误不回滚此前副作用。可选注解支持 `(Int)/(Float)/(String)/(Bool)/(Null)/(Array)/(Range)/(Function)` 、`(Map)/(Result)/(Lazy)/(Machine)/(Quantity)` 及已定义 shape/machine 的身份。

`check FILE` 完成整文件词法、语法、词法名称、控制流位置及数字字面准备，成功双流为空、退出 0。它不建立执行器，不计算表达式、不调用输入输出、不运行循环、构造或结构默认值。运行时类型/调用/写入错误不提前报出，因此 check 成功不保证 run 成功。未知/自引用名称 E302、重复声明 E301、非法控制流 E304、语法 E103 在执行前退出 2；运行时类型 E201、调用 E202、写入 E203、下标 E204、除零 E205、活动遍历修改 E206、数值范围 E208 退出 1。结构构造/with 字段清单错误使用 E203，字段访问不存在使用 E302。容量错误统一 E211，依发生阶段退出 2/1。

Result 的失败载荷必须 String；匹配载荷只在分支内有效，`?` 仅用于显式 Result 具名函数。Lazy 首次 wake 读取当前捕获值，缓存值/普通错误；资源中止和取消清理为 NEW。管道只接受一个直接 @ 参数，顺序为源、被调用对象、其余参数、调用。状态机成功先准备 Result 再改状态，失败保持状态；Quantity 使用精确有理数及量纲，不退化为 Float。查询只允许纯 AST 和 stdlib 固定白名单中的实际原生绑定，依次执行输入、take、全部 keep、全部键、稳定排序、投影；take=0 也不跳过前序校验。详见 [P04 验收映射](tests/p04/README.md)。

`test FILE_OR_DIR [--timeout SECONDS]` 按路径收集 `.zzy`，先全部检查，再为每个顶层 spec 新建子进程，重新执行公共初始化，单独执行该 spec。默认每例 10 秒，独立工作/临时目录及空 stdin（EOF）；run 跳过 spec，check 仍检查其名字。stdout 保留程序输出，末行 JSON 汇总 tests/passed/failed/timed_out/collection_errors；stderr 保留错误与 trace。空收集、收集错误、失败、超时均退出 1；非法参数退出 2。有收集错误时不执行任何初始化。对非法源码使用外部清单，不要 `test tests/` 混收负例。

P05 的完整核心标准库见 [stdlib](docs/language/stdlib.md)，模块与库示例见 [library/main.zzy](examples/library/main.zzy)，失败/边界证据见 [P05 测试映射](tests/p05/README.md)。`array.sum/stats` 只接受 Int；`sorted` 返回新数组；`map/filter` 共用语言调用与活动遍历规则。JSON 不自动解包 Result/Lazy，不接受 Machine/Quantity，格式错误返回失败 Result，资源错误保持 E211。

从项目根目录运行（本机将 python 换为 `.venv/Scripts/python.exe`）：

```text
python -m zzy check examples/library/main.zzy
python -m zzy run examples/library/main.zzy
python -m zzy test examples/library/spec.zzy
```

`use` 路径相对导入文件，普通文件路径相对进程工作目录。模块仅导出顶层具名函数、shape 和 machine 定义；同一上下文规范路径相同只初始化一次。每次 run/spec 创建独立模块状态；spec 使用整个依赖图的收集快照。`check` 递归检查依赖，不初始化模块或执行文件操作。`io.write_atomic` 独占创建同目录临时文件，写入并关闭后替换；预期 I/O 失败为 Result，未替换前保持旧文件，不承诺断电持久化。

`python -X utf8 -m tests.blackbox` 当前运行 1738 个独立外部用例；失败、超时、输出超额及空/坏清单返回 1。清单、可选 JSON 报告和资源指纹见 [测试说明](tests/README.md)。

`source-info` 仅做有界 UTF-8 读取，输出字节数、码点数、行数和同一字节快照的 SHA-256；`syntax_checked` 固定为 false，不代表语法检查或执行成功。空文件计 1 行，末尾换行后保留空行。缺文件、非法 UTF-8 和参数错误为 E401/退出 2；前端资源超限为 E211/退出 2。`info` 输出完整宿主版本、Unicode/平台、生效资源配置和指纹。

`lex` 按 v0.6 扫描完整文件，成功后向 stdout 输出 Token JSON Lines，最后一项为零宽 EOF；每项包含 `schema_version: 1`、`kind`、`lexeme`、`value`、`raw`、`span`。字符串 value 为解码后的文字，raw 表示该字符串是否由 `(raw)` 修饰；其余 Token 的 value 为 null，数字原文保存在 lexeme，不转成 Python 数值。位置采用原文 Unicode 码点，BOM 不占列，注释不生成 Token。

`lex` 不检查括号配对、语句结构、名称、类型或执行结果。裸保留名输出 RESERVED_NAME；`(zno )` 不作为关键字，`--x` 切成 STATE_EDGE 和 IDENT，`1e3` 切成 INTEGER 和 IDENT，后续 Parser 再拒绝不合法组合，不能将 lex 成功当作 check 成功。错误字符/未闭合字符串或注释/raw 缺字符串为 E101，错误转义为 E102，均退出 2。完整扫描失败时 stdout 为空；若在输出阶段超限，可能保留此前完整记录，但会报 E211 并非零退出，不可当作完整 Token 流。

词法覆盖与清单格式见 [tests/lex/README.md](tests/lex/README.md)。仅运行词法 CLI 验证可执行 `python -X utf8 -m unittest tests.test_lexer_cli -v`；此入口与 `zzy test` 的 spec 验证相互独立。

本机 PATH 中没有 `python`/`py`。本轮用以下实际解释器创建了项目内虚拟环境；也可将 `$zzyPython` 换成自己安装的已验证版本，不需修改系统 PATH：

```powershell
$zzyPython = 'C:\Users\13691\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $zzyPython -m venv --without-pip .venv
& .\.venv\Scripts\python.exe -m zzy --help
& .\.venv\Scripts\python.exe -X utf8 -m tests
```

可选安装：在已有 pip/setuptools（构建要求 setuptools>=68）的 Python 3.12.14 环境中执行 `python -m pip install --no-deps --no-build-isolation .`，随后可用 `zzy --help`。源码运行和宿主测试不要求 pip；GUI/Web/NumPy 不会随 CLI 初始化。

`--limits limits.json` 和 `--diagnostic-format text|json` 可放在命令前后。配置键、单位与默认值见 [资源契约](docs/runtime/resources.md)；未知/重复字段、Bool、非正整数、坏版本、超过 64 KiB 的配置均拒绝。`info` 中的指纹覆盖补齐默认后的全部有效值和宿主十进制上限。帮助/版本直接显示，不加载配置文件。

CLI 文件参数和配置路径相对调用者工作目录；run/check 不切换目录，test 的 worker 使用私有临时目录。模块加载器使用规范绝对路径去重，诊断保留实际出错依赖文件的位置。标准流使用 UTF-8、输出 LF；[诊断](docs/language/diagnostics.md) 提供文本/JSON Lines。前端 E211/退出 2、执行 E211/退出 1 已通过 CLI 验证；取消出口、执行清理及 Windows 真实 Ctrl+C 已有专项证据，其他环境需另验收。

## 运行方式与交付目标

语言内测试入口已可用，例如 `python -m zzy test examples/library/spec.zzy`。外部负例仍用 tests.blackbox，不能对含故意错误源码的整个 tests/ 执行 zzy test。

P08已选并完成HTTP、共享隔离与Python嵌入；NumPy和字节码VM仍属可选后续工作。P00 的资源计量接口不等于所有未来值/AST/缓存都已接入限额，当前验证范围见 [测试说明](tests/README.md) 与 [开发记录](docs/development/development-log.md)。

课程交付包括语法文档、解释器、ZZY 黑盒测试、与 Python 的性能比较、人和 AI 的指南、不少于 200 行的完整 ZZY 应用及开发记录、Git 历史和 PPT。原始约束见 [作业要求](docs/requirement.md)。默认应用是校园任务管家，画笔扩展不自动替代应用交付。

`docs` 维护正式规则，`skills` 将其组织为学习和开发入口。指南存在不代表接口已经实现；后续以真实代码、测试结果和开发记录更新能力状态。

## P06 一键验收与已验证指南

`python -X utf8 -m tests` 运行全部 CLI、spec 和宿主回归，当前收集 2041 项；空收集/跳过/少执行/失败均返回非零。`--report dist/p06-all-tests.json` 保存计数、环境与默认策略指纹（目录需存在）。外部黑盒仍可单独运行。映射、15 个指南片段、9 个变形 spec、资源验证范围见 [P06 验收](tests/p06/README.md)；真实 Agent 练习见 [分钟汇总](examples/agent-practice/README.md)。Windows 11 的真实 Ctrl+C/run/test、派生进程树回收和临时目录清理已经专项验证；其他平台及未测大容量范围明确列在验收页。GUI 已在后续 Sketch E 阶段实现并独立验收，Web/Python的P08-01—03能力见文末；长期Program缓存仍未实现。

最终验收按 [测试阶段计划](docs/development/final-test-plan.md) 执行；本机 VS Code 的详细步骤、历史结果与本次 P08 补测见 [人工测试资料](docs/manual-tests/README.md)。[GitHub Actions 工作流](.github/workflows/ci.yml) 已配置静态检查、Windows 全量回归、隔离 wheel 安装及汇总门禁，本地复现和云端待验证事项见 [CI 设计与实施](docs/development/ci-design.md)。CI 不代替真实 GUI、人工操作及正式性能验收。

CI回归日志已读取 [logging.json](docs/runtime/logging.json)，按1MiB轮转、保留4份gzip备份并自动淘汰更旧片段；CLI继续使用UTF-8和固定错误码，查看与调整方法见 [日志配置说明](docs/runtime/logging.md)。


## P07 性能实测

[性能报告](docs/runtime/performance-report.md) 和 [复现说明](benchmarks/README.md) 保存完整 CLI、准备、初始化、纯执行与清理的边界。基线先固定，再单独剖析与优化；默认资源配置未放宽。基线1644条记录含1260条正式样本（1259成功、1超时），另有12预检超时和24配对未测量，不把失败当作0ms。

路径显示的重复计算是已测热点；执行上下文内复用显示路径、cwd改变时失效，未缓存用户值或Program。B01/B04在n=10000的两版交错复测中，纯执行中位数分别加快3.38/3.33倍、完整CLI加快2.22/2.29倍；准备和清理没有一致收益，完整数据及局限见报告。基线中ZZY仍慢于Python，没有承诺跨任务、平台或所有规模的统一加速。

优化后的完整回归为1744/1744（含原1588条外部CLI），无失败/跳过；两版性能复测152条记录全成功。运行时版本号保留0.6.0a1，具体性能版本按Git提交区分。该次P07验收不包括应用；公开嵌入/长期Program缓存和GUI仍未实现。

## P09 校园任务管家

[应用指南](apps/zzy-campus/README.md)提供完整逐行菜单：增删改、完成、筛选搜索/稳定排序、统计、TSV导出、JSON保存加载和撤销/重做。全部业务由7个ZZY模块实现，采用v1文件、先校验再替换、ID高水位和100步历史。源码504总行/493有效行，排除纯标点仍406行；[行数报告](apps/zzy-campus/line-count.json)可复算。

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m zzy run apps/zzy-campus/main.zzy --limits apps/zzy-campus/limits.json
```

应用随仓库源码分发，wheel只安装通用解释器；需保留整个应用目录。4MiB单次文件/JSON限额在读取时生效，路径相对启动工作目录，默认不自动保存。首次新建→新增→10保存；重启选2打开。完整演示、测试及限制见应用指南与[验收说明](tests/p09/README.md)。

P09最终全量回归1791/1791、806.968秒通过（包括1588项既有外部CLI），无跳过。应用专项22/22，实际映射与未测范围见验收说明；当时下一项为E1-01，当前交接见todo。

## Sketch 绘图扩展

真实使用范围、固定配额和窗口启动见[Sketch 指南](docs/features/sketch-guide.md)，独立阶段验收与未测范围见[tests/e4](tests/e4/README.md)。默认 run/check/test 不初始化 Tk；显式 `python -m zzy run examples/sketch/studio.zzy --gui` 打开小画室。关闭窗口后例程保存项目，可在下次执行加载并继续编辑。

几何、SVG、文字/多层、分组撤销、确定回放、图案函数库、事件与项目已实现，E1—E4已全部验收，扩展ABI为1.0；PNG没有独立后端，明确返回失败。核心info仍报告P06核心阶段/0.6.0a1，扩展ABI单独版本化。性能见[实际测量](benchmarks/sketch/README.md)，不能将headless通过当GUI验收。

## 已选 P08 Web

P08已选，P08-01 HTTP已验收，P08-02共享冻结与并发隔离已验收（显式--shared）；P08-03公开Python嵌入已验收，SQLite实现、整体验收与人工验收已通过并交付；P10扩展见文首。[启动和演示](examples/web/README.md)、[集中接口契约](docs/runtime/web.md)、[专项证据](tests/p08/README.md)。可选安装`pip install ".[web]"`，核心依赖保持为空。

P08-04/05本轮新增SQLite事务与独立任务示例；实际db签名、提交/回滚与取消边界以[集中契约](docs/runtime/web.md)为准。SQLite专项、真实HTTP重启、安装和完整回归证据见tests/p08；当前验收状态见todo。
