# P03 函数与闭包验收

`python -X utf8 -m tests.blackbox tests/p03/cases.json` 运行 234 个外部 CLI 期望（115 run、119 check），使用 118 个独立输入和 functions 示例。固定输出、失败位置及调用 notes 按契约/源码独立维护，不从解释器生成期望。所有普通 run 都有 check 对照；四个 check 专用输入含 I/O、无限循环、无效运行时类型和递归，不允许执行。

| 覆盖编号 | 用例族 | 验证内容 |
|---|---|---|
| FN-01 | factorial、fibonacci、higher-order、lambda-precedence、native-higher-order | 具名/匿名、自递归、高阶/原生函数传递、链式调用、尾逗号 |
| FN-01、BIND-01 | shared-cell、captured-parameter、transitive-cell/value、block-escape、local-block-escape | 逃逸后捕获仍存活、兄弟闭包共享修改、多层传递捕获、每调用隔离 |
| BIND-01、ARRAY-01 | immutable-alias、array-argument-alias、late-update、new-array-each-call | 固定绑定不冻结容器，参数重绑不改变调用者绑定，修改容器保留别名，新字面量独立 |
| BIND-01、CTRL-01 | for-capture-global/local、while-capture、loop-control-capture、named-function-each-iteration | 模块块/局部槽位两条路径均逐轮新绑定，continue/break 清理，逐轮具名函数身份独立 |
| FN-01 | nested-recursion、nested-self-escape、declared-mutual、lambda-recursion | 自身引用与外层捕获可逃逸，先声明可变占位再赋函数的显式递归可用；未声明互递归仍拒绝 |
| FN-01、EXPR-01 | evaluation-order、bad-callee-order、arity-order、type-order、callee-error-stops-args、arg-error-stops-rest、callee-fixed-before-args | 先固定被调用值，再求所有参数，最后检查调用/个数/类型；错误只保留此前副作用 |
| FN-01、SHAPE-02 | annotation-*、parameter-*、shape-argument/return-type、captured-write-type | 参数可变，重绑仍检查注解；名义身份、注解声明环境/创建时快照、Bool 不作为 Int、Int 不作为 Float、Array 只查外层 |
| FN-01、CTRL-01 | null-returns、return-flow、return-type/bare-type/implicit-type、caller-loop | 显式/隐式 Null，嵌套 return 穿透循环，返回类型失败；函数自己的循环合法 |
| BIND-01、CTRL-01 | cross-break/continue、nested-cross-break、return-outside/in-block、forward-*、duplicate-*、*-scope-leak | 未调用/不可达函数也做名称与控制流检查；禁止跳出调用者循环、参数/同层局部重复、前向引用和局部泄漏 |
| FN-01、LEX/语法 | default-parameter、lambda-return-annotation/block、missing-arrow、parameter-leading/double-comma、function-extra-semicolon | 不放宽既有 EBNF，无默认参数、匿名块体或额外函数结尾分号 |
| ARRAY-02、EXPR-01 | array-active-call、return-releases-iteration、index-write-revalidate、assignment-location-once | 通过函数也不能增删活动数组；return 释放活动计数，右侧调用改变长度后重查，目标只定位一次 |
| RESOURCE-01/02（P03 部分） | depth-63/64/65、depth-small-*、deep-ast-calls、native-depth | 默认调用深度相邻边界、syntax_depth=64 的 AST 与 64 次活动调用组合；原生调用不计 ZZY 深度 |
| RESOURCE-01/02（P03 部分） | frame-slots-*、cell-slots-*、immutable-capture-slots、function-objects-*、discarded-return/callee-release、live-return-not-released | 槽位/共享 Cell/对象配额的相邻边界；已丢弃返回值及时释放，仍被绑定持有的值不提前释放 |
| DIAG/CLI | call-notes、resource-call-notes、return-type、check-no-function-execution、check-no-types-or-defaults、check-unused-recursion、check-types-not-run | 原始表达式主位置，内到外调用 notes，check 不执行任何函数/类型求值/默认值/I/O |

`test_p03_runtime.py` 的 10 项宿主测试补充语言致命错误之后不可观察的状态：只读 Program 布局、同一 Program/Interpreter 重用、普通局部直接存值与捕获 Cell 分配、兄弟闭包实际共享 Cell、嵌套活动数组/栈帧在诊断/取消/MemoryError/资源失败后清理、Frame 分配失败、闭包引用环回收、多上下文输入隔离、返回错误范围、类型名传递捕获。宿主故障注入不替代真实 CLI 用例。

运行器新增 notes 的严格比较，并针对零收集、执行数不符、跳过/未观测结果补防假成功测试；继续运行既有坏清单、错误答案、真实超时、输出超额和进程启动失败测试。全量入口包括原有 539 项，其中历史 unsupported-function 的两项期望按 P03 迁移为成功，其余旧期望不变。

P03 提供共享捕获布局和 Cell 基础；Lazy 的 AST 接入、捕获分析、状态与唤醒仍属 P04-02，当前明确拒绝 Lazy。跨文件/模块、库 map/filter 回调、完整 RESOURCE/CLI、真实终端 Ctrl+C、其他 Python/OS 和性能结论未验证。本阶段不代替 P04/P05/P06 验收。
