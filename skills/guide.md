# ZZY 语言开发指南

更新：2026-10-14｜语法 v0.6、标准库 v0.6.1｜完整语言指南；最小可运行示例见根 README

本指南说明怎样编写 ZZY 程序，以及怎样参与解释器开发。语法速查见 [syntax.md](syntax.md)，完整规则和接口分别以 [语法契约](../docs/language/syntax.md)、[标准库契约](../docs/language/stdlib.md) 为准。AI 接手入口是 [zzy/SKILL.md](zzy/SKILL.md)。

## 1. 先确认能做什么

P00—P07及P09应用业务已实现，版本 0.6.0a1；核心语法、io/array/text/math/data/unit 标准库、Map/严格 JSON、原子文件保存及模块已接通。性能报告和校园任务CLI应用已有真实实现；Sketch 的真实GUI与headless分别验收，见扩展指南。使用 `python -m zzy run examples/features.zzy` 和 `python -m zzy test examples/features-spec.zzy` 运行特色示例；独立外部期望仍由 `python -X utf8 -m tests.blackbox` 验证。check 不执行用户表达式。本文 2 段完整代码已保存至 tests/p06/guide/，逐段 check/run，另补正常/失败 spec；库/模块例子见 examples/library/；应用启动与验收见 apps/zzy-campus/README.md，后续任务先核对 todo、最新开发记录和 Git。

解释器使用 Python，核心运行只依赖标准库。P00 已验证 CPython 3.12.14、Windows 11、Unicode 15.0.0；实际运行和安装命令见项目 README。没有依赖清单时不要凭空执行安装命令；GUI 和后续 Web 等可选依赖不应成为普通 CLI/check 的前提。

目录分工：

- `zzy/`：词法、语法、名字解析、运行时、标准库与 CLI。
- `examples/`：可独立运行的示例及必要输入。
- `tests/`：ZZY 正常/错误程序、输入和期望清单、外部黑盒运行器。
- `benchmarks/`：等价 ZZY/Python 程序、驱动与原始测量结果。
- `apps/zzy-campus/`：默认校园任务管家应用。

上述根目录已建立；当前已有 P05 库/模块与 P04 特色语法及此前解释器、宿主与 CLI 测试、hello/grades/functions/features/features-spec 示例；校园应用子目录及后续语言功能仍待实现。已有文档位置见 [项目 README](../README.md)。

## 2. 编写第一份程序

下面示例已保存并验证为 `examples/total-up-to.zzy`。其他函数示例见 [functions.zzy](../examples/functions.zzy)，不要用此段覆盖已有 hello.zzy。

```zzy
(addnew) total_up_to(limit: (Int)) -> (Int) {
    (zyes) total := 0;
    (for) number (in) 1..<(limit + 1) {
        total <- total + number;
    }
    (return) total;
}

io.print(total_up_to(5));

(spec) "累加正常值与空区间" {
    (o_o) total_up_to(5) == 15;
    (o_o) total_up_to(0) == 0;
}
```

先检查语法和名字，再运行程序，最后运行测试。total-up-to.zzy 的 check/run/test 均已验证；hello.zzy 输出 5，本节程序输出 15：

```text
python -m zzy check examples/total-up-to.zzy
python -m zzy run examples/total-up-to.zzy
python -m zzy test examples/total-up-to.zzy
```

对于上述示例，check 不打印；run 的预期 stdout 为 `15` 加换行，跳过 spec 的执行；test 会在每例独立环境重新初始化公共部分，顶层打印也属于初始化行为。为避免测试噪声，正式库模块只放定义，交互启动放入口文件。

check 检查 spec 内语法和名字，并读取依赖源码，但不执行用户初始化、结构默认值、Lazy、查询或 GUI。测试未收集到用例不能算成功。诊断和退出码详见 [diagnostics](../docs/language/diagnostics.md)。

## 3. 从需求到 ZZY 程序

1. 写清输入、输出和失败情况，先列一两个固定答案。例如“输入非负整数，输出累计和；坏输入返回可解释的失败”。
2. 用标量、Array 和 shape 定义数据。需要任意 String 键时使用 data.map，不虚构字典字面量或泛型。
3. 把业务拆成具名函数，参数数量固定；默认选 zno，需要重新赋值的名字才用 zyes。类型注解帮助发现错误，但 Array 注解不能保证每个元素类型。
4. 将 I/O 放在入口或明确的边界函数。可恢复的坏输入用 Result；类型、下标和资源错误应修复程序，不能指望 Result 自动捕获。
5. 先完成最小正常流程，再增加边界、失败恢复和测试；按实际已实现能力选用查询、状态机、单位与绘图。

变量声明遵循顺序，自递归允许，提前调用后声明的函数或相互递归不允许。模块路径相对导入文件；普通文件路径相对启动进程的工作目录，因此运行说明要写清启动位置。模块导出具名函数、结构和状态机定义，不导出普通变量。

## 4. 处理输入、JSON 与保存

`io.input(prompt)` 返回 String 或 EOF 的 Null，先判断 EOF 再传给文本函数。`text.safe_int` 的格式失败返回 Result；不要用未声明的 `int()` 或将 Bool 当作数字。

读取文件与解析 JSON 是两次可能失败的操作。`data.parse` 不保证得到对象，必须逐层检查类别、必需键、业务范围，最后才构造带注解的业务结构。以下示例只检查根对象的 tasks 数组，并非完整校园任务文件校验器：

```zzy
(addnew) load_task_values(path: (String)) -> (Result) {
    (zno) content := io.read_text(path)?;
    (zno) root := data.parse(content)?;
    (zif?:) data.kind(root) != "map" {
        (return) (T_T)("文件根值必须是对象");
    }
    (zif?:) (not) data.has(root, "tasks") {
        (return) (T_T)("文件缺少 tasks");
    }
    (zno) values := data.get(root, "tasks");
    (zif?:) data.kind(values) != "array" {
        (return) (T_T)("tasks 必须是数组");
    }
    (return) (^_^)(values);
}

(addnew) save_json(path: (String), value) -> (Result) {
    (zno) content := data.stringify(value)?;
    io.write_atomic(path, content)?;
    (return) (^_^)((null));
}
```

这段代码只定义函数，没有在顶层读取或写入文件。完整应用还须按 [campus-app](../docs/development/campus-app.md) 校验版本、每个任务字段、ID 唯一性与高水位等；所有检查成功后才替换当前状态。加载失败不能静默清空数据，保存失败不能清除未保存标记。

保存时先把状态转换为可序列化的数据，再 stringify，最后 write_atomic。Machine 取 `.state` 并按业务格式保存；Result 先处理，Lazy 按业务意图显式 wake，Quantity 需要显式约定表示，不能让 JSON 自动猜测。原子替换保护替换前失败时的旧文件，不承诺断电持久化或多进程事务。

## 5. 选用语言特色时的边界

| 需求 | 推荐入口 | 必须理解的限制 |
|---|---|---|
| 筛选、稳定排序与投影 | [query](../docs/features/query.md) | 只接受 Array；纯表达式与原生白名单；不调用任意用户函数 |
| 表达合法状态转换 | [machine-units](../docs/features/machine-units.md) | 发送返回 Result；失败不改变状态；无动作回调 |
| 精确的时间或长度计算 | [machine-units](../docs/features/machine-units.md) | 固定单位与量纲；无量纲仍是 Quantity |
| 延后一次计算 | [语法参考](syntax.md) | Lazy 缓存首次结果，不随依赖变化自动刷新 |
| 图形、回放与交互 | [sketch](../docs/features/sketch.md) | E1—E4已验收，sketch 1.0；GUI 独立验收 |

zno、array.copy 和 with 都不是深冻结/深复制。为实现撤销，应创建新的 Task 和外层数组；如果字段还包含 Array/Map，另行决定复制策略。状态机实例及 Lazy 载荷引用共享，也不能当作自动历史快照。

不要在遍历数组时通过任何别名增删或原地重排；元素替换允许，但要考虑后续迭代看到的新值。查询对输入取浅快照，不能据此推断所有嵌套对象都已深复制。

## 6. 测试与定位错误

覆盖要求以 [test-coverage](../docs/development/test-coverage.md) 为准，测试至少包含正常、边界和适用的失败场景。固定答案须独立确定；变形测试可补充，不能替代独立答案。

- 正常语义写 `.zzy` 与 spec，使用 `(o_o)` 断言。每例新的上下文，模块初始化和可变对象不得串例。
- 非法语法、未声明名字、致命类型错误另存独立 `.zzy` 文件；期望诊断、stdout/stderr 和退出码放外部清单。不能把错误源码放入正常 spec，再声称能够捕获。
- 使用 `(@_@)` 观察一次求值及位置，输出走 stderr；不要把观察信息写入正常 stdout 答案。
- 默认不匹配宿主堆栈或对象地址。按稳定错误类别、源码 span 和规范化消息验证，格式以 diagnostics 为准。
- 为无限循环、深递归、大输入、输出洪水、文件失败及取消建立有界测试。限额按 [resources](../docs/runtime/resources.md)，超时后必须清理子进程和临时资源。

单文件 check/run 的成功为 0，前端或 CLI 错误为 2，执行错误为 1，取消为 130；test 的用例失败汇总为非零，外层运行器再按清单核对具体子进程退出码。一次静态检查不能证明运行行为，headless 测试不能证明 GUI 可用。

## 7. 参与解释器实现

执行顺序以 [roadmap](../docs/development/roadmap.md) 为准，具体部件见 [interpreter](../docs/runtime/interpreter.md)。核心主线是 P00 → P01 → P02 → P03 → P04 → P05 → P06，再完成 P07 测量、P09 应用和 P11 交付；分支依赖见阶段表，不把文档讲解顺序当作开发依赖。

后续先核对仓库和环境，再从 P07-01 开始 B01—B09 配对基准，保留完整回归。不要先建 VM，或一次性实现所有扩展。E 在 P05/P06 后分阶段推进；Web/Python 互联 P08 在 P09 后可选，P10 优化依据测量决定。

每个实现任务按以下过程收尾：

1. 从 todo 选符合依赖的一项，读取相应契约和覆盖项，说明本次行为边界。
2. 实现实际代码和必要的黑盒用例。宿主接口通过登记与统一调用入口，不能开放任意 Python 属性、eval 或 exec。
3. 执行与修改匹配的检查，保留命令、环境、结果及失败；缺依赖或未实现时直接说明，不能填“通过”。
4. 达到该项完成标准才在 todo 勾选，将证据写入 development-log；只更新设计不等于完成代码任务。
5. 同步受影响的正式契约、示例和指南。准备提交时再核对差异，是否提交遵循用户指示。

特别注意统一维护绑定/对象语义、数组版本与活动遍历计数、资源配额、错误传播和模块状态。可复用的 Program 不得携带跨运行共享的可变环境；缓存键包括依赖内容和生效配置，避免复用绕过更严格的限额。

## 8. 性能、应用与提交

性能测量按 [performance](../docs/runtime/performance.md) 的 B01—B09 清单进行。先证明相同输入与结果，再按相同范围比较 ZZY/Python；分别记录启动、准备和执行，不把已加载运行与完整启动混比。保留原始数据、版本、配置、重复次数及离散程度，测量后才写优化结论。

默认应用是校园任务管家，业务用 ZZY 编写，Python 只提供通用宿主能力。实际 ZZY 源码至少 200 行，建议有效代码也达到要求，不靠注释和重复代码凑数。绘图演示不自动替代该交付物，变更应用主题时仍须满足作业要求。

最终按 [requirement](../docs/requirement.md) 核对八项交付物：语法规则、解释器源代码、ZZY 黑盒测试集、性能报告、开发及 AI 指南、应用源代码及 Agent 开发记录、所有工作的 Git 历史、系统介绍 PPT。本文完整代码块已有逐段验证；当前 Agent 按指南完成的练习见 [实际记录](../examples/agent-practice/README.md)，没有第三方盲测证据。


## P05 库与模块的已验证用法

完整签名、参数顺序和错误以 [stdlib](../docs/language/stdlib.md) 为准。可运行的多文件示例为 [library/main.zzy](../examples/library/main.zzy)，依赖同目录 [helpers.zzy](../examples/library/helpers.zzy)，测试为 [spec.zzy](../examples/library/spec.zzy)。从根目录执行 `python -m zzy run examples/library/main.zzy`；模块路径相对 main.zzy，不依赖当前工作目录。普通文件路径仍相对工作目录，spec 每例有私有目录，示例 report.json 随该目录清理。

Map 使用 data.map/has/get/set/keys；get 缺键为 E204，显式 Null 值仍算存在。JSON parse 的成功值先用 data.kind 分类，再访问成员；失败 Result 用匹配分支处理。保存可先 data.stringify，成功后 io.write_atomic；类型/资源诊断不会自动变为可恢复 Result。write_text 是普通覆盖，只有 write_atomic 提供临时文件关闭后替换的旧文件保护。

sum/stats 逐项检查 Int，Bool/Float 不混入；stats 的 min/max 空值为 Null。sorted 稳定且不修改源；map/filter 从左到右调用一次，允许替换输入元素，禁止通过任何别名增删活动输入。回调错误停止处理，不能拿到部分结果。结构、Map 和数组的赋值仍共享引用，copy/with 只浅复制。

查询白名单固定为 len/str、math.abs、text.trim/contains、unit.make/format；不可把库别名、动态函数或 data.kind 放进查询条目。普通具名函数可以封装整个查询并通过模块导出。unit.format 使用精确分数；unit.make(Float, unit) 保留该 Float 的实际二进制值。

宿主注册元数据、失败注入、模块/文件/spec 隔离的证据索引见 [P05 测试映射](../tests/p05/README.md)。P06 的逐段执行、资源/诊断/进程矩阵与未验证范围见 [验收映射](../tests/p06/README.md)。GUI、其他操作系统及性能收益仍未验证。

## 一键回归与指南练习

从根目录运行 `python -X utf8 -m tests`；本机使用 `.venv/Scripts/python.exe -X utf8 -m tests`。该入口包含独立外部期望、正常 spec 和宿主清理测试，不能用 `zzy test tests/` 替代，因为 tests 中含故意非法源码。只运行语言 spec 可以执行 `python -m zzy test tests/p06/specs`；预期 9/9。全部 15 个语法/指南片段及固定答案由 tests/p06/guide/manifest.json 管理，修改片段必须同步对应文件与期望。练习要求及源码见 [Agent 练习](../examples/agent-practice/task.md)。

## 已实现的完整CLI应用

[校园任务管家](../apps/zzy-campus/README.md)展示逐层JSON校验、候选加载提交、原子保存、内容dirty、ID高水位与浅快照撤销；所有业务模块可直接阅读。启动必须带应用limits.json，测试使用临时目录和独立磁盘/输出答案，不自动改用户文件。当前没有GUI/Web，其他平台和最坏容量组合不由本轮结果推断通过。

## Sketch 已实现子集

[sketch使用指南](../docs/features/sketch-guide.md)提供真实程序、受控类型、配额及GUI启动说明；[tests/e4](../tests/e4/README.md)分别记录headless、桌面窗口、离线安装和性能证据。PNG不可用；缺环境返回失败，不把窗口截图作为PNG导出。

## P08-01 Web

可选安装、页面和HTTP调用见[Web示例](../examples/web/README.md)，规则只维护在[Web契约](../docs/runtime/web.md)。不要生成未注册的web.get/web.serve或db接口；公开Python嵌入见下节；SQLite实现见examples/sqlite，验收见todo。

P08-02可用--shared启动显式冻结共享模式，默认仍按请求实例化。不要修改共享模块数据或放置共享Lazy/可变捕获；初始化、取消和关闭边界见Web契约。

## Python调用ZZY

核心安装提供`from zzy.embedding import load_module`，用`with load_module(path) as module`拥有源码快照，再用`module.call(name, *arguments)`调用顶层导出函数；结果为CallResult，业务数据在`.value`，本次输出在`.stdout/.stderr`。加载不执行初始化，每调用独立运行并自动清理；参数不是源码，不解码[OoO]。精确数据类型、拒绝规则、取消/close及Python整数与HTTP安全整数的区别以[集中契约](../docs/runtime/web.md)为准；[同一业务函数示例](../examples/web/README.md)可直接运行。不把内部Value或任意Python对象交给ZZY。

P08-04/05本轮新增SQLite事务与独立任务示例；实际db签名、提交/回滚与取消边界以docs/runtime/web.md为准。SQLite专项、真实HTTP重启、安装和完整回归证据见tests/p08；当前验收状态见todo。


## P10 显式 shape 合约

本次仅选 P10-01/P10-06。[独立演示](../examples/contracts/README.md)包含请求/响应 shape、静态生成、HTTP 成功/字段路径错误及修改字段后的同步演示；规则以[Web 集中契约](../docs/runtime/web.md)为准。新增公开入口 `zzy.contracts.generate_openapi`、`python -m zzy.contracts`、Web `--contracts` 和启用后的 `/openapi.json`。生成器不执行用户初始化；请求校验后保持 Map，按显式状态码校验响应。类型校验不替代非空/长度业务规则，Int/Float 附加标签不能靠通用 Schema 工具完整执行。核心不加载 Web/GUI，其他 P10 项仍延期。
