# ZZY 语言开发指南

更新：2026-10-09｜语法 v0.6、标准库 v0.6.1｜当前为开发前指南，示例未运行

本指南说明怎样编写 ZZY 程序，以及怎样参与解释器开发。语法速查见 [syntax.md](syntax.md)，完整规则和接口分别以 [语法契约](../docs/language/syntax.md)、[标准库契约](../docs/language/stdlib.md) 为准。AI 接手入口是 [zzy/SKILL.md](zzy/SKILL.md)。

## 1. 先确认能做什么

目前仓库只有设计和指南，没有解释器、安装包、黑盒测试、基准或应用。文中的程序是按契约编写的设计示例，不代表功能已实现。开始开发前先查看 [todo](../docs/development/todo.md) 和 [开发记录](../docs/development/development-log.md)，并核对实际代码；当前下一项是 P00-01。

解释器计划使用 Python，核心优先采用标准库。受支持的 Python 版本、操作系统、Unicode 数据版本及安装命令需在 P00 按真实环境确定。没有依赖清单时不要凭空执行安装命令；GUI 和后续 Web 等可选依赖不应成为普通 CLI/check 的前提。

计划中的目录分工：

- `zzy/`：词法、语法、名字解析、运行时、标准库与 CLI。
- `examples/`：可独立运行的示例及必要输入。
- `tests/`：ZZY 正常/错误程序、输入和期望清单、外部黑盒运行器。
- `benchmarks/`：等价 ZZY/Python 程序、驱动与原始测量结果。
- `apps/zzy-campus/`：默认校园任务管家应用。

上述目录尚未建立。已有文档位置见 [项目 README](../README.md)。

## 2. 编写第一份程序

解释器实现后，可将下列完整示例保存为 `examples/hello.zzy`。这是单文件示例，不依赖其他示例中的定义。

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

先检查语法和名字，再运行程序，最后运行测试。以下是拟议 CLI，当前不能执行；最终参数以实现后的帮助与验收结果为准：

```text
python -m zzy check examples/hello.zzy
python -m zzy run examples/hello.zzy
python -m zzy test examples/
```

按契约，check 不打印；run 的预期 stdout 为 `15` 加换行，跳过 spec 的执行；test 会在每例独立环境重新初始化公共部分，顶层打印也属于初始化行为。为避免测试噪声，正式库模块只放定义，交互启动放入口文件。

check 仍检查 spec 内语法和名字，并读取依赖源码，但不执行用户初始化、结构默认值、Lazy、查询或 GUI。测试未收集到用例不能算成功。诊断和退出码详见 [diagnostics](../docs/language/diagnostics.md)。

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
| 图形、回放与交互 | [sketch](../docs/features/sketch.md) | 已选但未实现的扩展；E1—E4 分阶段，GUI 单独验收 |

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

当前先核对仓库和环境，再打通源码、Token、AST、Resolver、树遍历执行和首批 CLI 黑盒。不要先建 VM，或一次性实现所有扩展。E 在 P05/P06 后分阶段推进；Web/Python 互联 P08 在 P09 后可选，P10 优化依据测量决定。

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

最终按 [requirement](../docs/requirement.md) 核对八项交付物：语法规则、解释器源代码、ZZY 黑盒测试集、性能报告、开发及 AI 指南、应用源代码及 Agent 开发记录、所有工作的 Git 历史、系统介绍 PPT。本文和 SKILL 目前只是指南草稿；P06 仍须实际运行示例，并验证他人或 Agent 能仅依靠指南完成任务。
