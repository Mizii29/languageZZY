# N0-01：现有实现冻结清单

2026-11-17。机器可复核清单见 [inventory.json](../../native_runtime/tests/inventory.json)，由
[只读盘点工具](../../native_runtime/tools/inventory.py)读取 Python AST、宿主元数据和全部默认 CLI manifest。
它不运行用户模块，不是语义 golden 的生成器，也不是原生程序的运行依赖。

## 权威与迁移边界

正式语义继续采用 [syntax](../language/syntax.md)、[stdlib](../language/stdlib.md)、
[interpreter](../runtime/interpreter.md)、[resources](../runtime/resources.md)、
[diagnostics](../language/diagnostics.md)。查询、状态机/单位、Sketch、Web 的细则继续由各专题维护。
requirement 原文、Python 默认入口和所有既有测试保留。P12/P13 原状态保持；原生状态单独登记。

| 盘点对象 | 实现与不可改变的保证 |
|---|---|
| 词法/语法 | tokens.py 固定拼写、保留名；parser.py 的 AST kinds 全列于 JSON。保留注释、转义、raw、BOM/CRLF/Tab/EOF、严格 UTF-8 和码点位置；不另造一份 EBNF |
| 标量 | Null/Bool/Int/Float/String；Bool 与 Int 分开，Int 任意精度，有限 Float，比较不先丢失大整数精度；String 按码点 |
| 用户复合值 | Array/Map/Shape/Function/Result/Lazy/Machine/Quantity/Range；身份、浅复制、别名、活动遍历、精确有理量、Lazy 状态均保留 |
| 定义/内部值 | Module/Namespace/Definition/MachineDefinition/NativeType；Cell/Binding/Frame/Closure 为内部布局而非语言数据类别；NativeFunction 运行时也标为 Function |
| 原生值 | sketch.Canvas/Pen/Layer/Color/Drawing 的登记身份；Position/LayerInfo 及 array.Stats 是普通 Shape，不伪造额外值标签 |
| Resolver | Reference: global/self/local/capture；Symbol: owner/slot/mutable/cell；Capture: source/symbol；FunctionPlan: locals/captures/blocks。递归自身、可变捕获 Cell、逐轮绑定、结构默认值捕获环境保持 |
| Program | 不可变 Node + prepared literals、模块源码、符号/注解/函数布局映射；当前 id(node) 是 Python 进程局部标识，原生须换为 Program 内稳定 ID，不能持久化 Python 地址 |
| 宿主 | JSON 保存全部注册签名、外层类型、effects/errors/pure、ABI 和所有权；core/io/array/text/math/data/unit 为核心，db/sketch 与 Web 嵌入是可选迁移包 |
| 资源 | default-v1 22 个配置键，其中 2 个 cache 键保留且未实现缓存；完整生效记录/指纹冻结。逻辑对象/槽位/载荷不等于 RSS；预留原子性、失败释放、取消安全点不弱化 |
| 诊断 | schema_version=1；既有错误码、span、notes、stdout/stderr 分工及 0/1/2/130 协议不变。原生未移植不冒充语法错 |
| 测试 | DEFAULT_MANIFESTS 的 12 个清单逐例登记（包括失败期望/模式），不减少或搬走旧清单；内部宿主测试与真实 HTTP/GUI 专项仍由既有入口保留 |
| 应用 | 校园 main.zzy + limits.json 与原文件格式；独立 web/sqlite/contracts 示例；具体存在的入口及宿主入口见 JSON，未提交的应用补充也保持原样 |

## 已发现的实现差异与限制

- Resolver 的 BUILTIN_NAMES 未列 db，而 IMPLEMENTED_NAMES 由注册表包含 db；这影响顶层同名声明限制。此轮只登记事实，不擅自修复 Python 语义，也不把差异偷偷冻结成新语言规则；原生移植该行为前须对照 syntax 的名称约束补固定用例。
- Python 的 Int 十进制宿主上限是 4300，default-v1 的有效 numeric_digits 是 4096；原生不伪报 CPython 宿主限制。
- Sketch PNG 原本不可用；Web 文档中的 web.get 等方向示例不是已登记语言接口。
- 盘点 JSON 的 source_sha 是盘点时基线，source_hashes 冻结实际运行时代码；不以脏工作区上的 HEAD 冒充全部文件来源。
- 除12个统一CLI清单之外，tests/p09/validation-cases.json 是应用数据校验夹具、tests/p06/guide/manifest.json 是指南片段清单；它们不是 lex/run/check schema，分别由 test_p09_app 和 test_p06_guides 读取。P12 应用场景在 test_p12_app 的独立固定输入中，HTTP/GUI 使用独立运行器；不纳入1738默认CLI数字，也不删除或视为已原生化。

复核命令：` .\.venv\Scripts\python.exe -X utf8 native_runtime/tools/inventory.py --check native_runtime/tests/inventory.json`。
原生 capability 和 N0 出口证据另行维护，不将盘点成功写成移植完成。
