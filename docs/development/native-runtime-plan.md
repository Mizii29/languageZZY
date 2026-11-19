# ZZY 全原生运行时开发阶段

**阶段代号：NATIVE-01｜当前已完成 N0/N1 正式验收及 N2 静态前端；未实现运行时求值，逐项状态以 todo 为准**

建立：2026-11-17｜前置：现有 Python 解释器、黑盒测试、P12 性能证据和稳定版候选
范围：让 ZZY 的发布运行时不加载 Python，同时保留现有解释器作为课程兼容实现

## 1. 目标和作业边界

课程原文要求设计**解释型**通用脚本语言并实现解释器，还要求完整黑盒测试、ZZY/Python 性能比较、指南和 ZZY 应用。因此本阶段不能把解释器改成只有 AOT 编译器，也不能用原生后端替代现有 `zzy run/check/test` 作为课程证据。

本阶段的目标是新增一个由 C++17 实现的原生 ZZY 运行时：

```text
ZZY 源码 -> 原生 Lexer/Parser/Resolver -> 原生 Program/Bytecode
                                      -> 原生 ZZY Interpreter -> 结果
```

运行 `zzy-native` 时不启动 `python.exe`，不导入 Python 扩展，也不通过子进程回退 Python。它仍然是**解释器**：读取 ZZY 源码，建立运行时值和栈帧，逐条执行解释计划。AOT 是在此基础上的另一条可选路径：

```text
ZZY 源码 -> 原生前端 -> 受支持子集的本机代码 -> 独立 EXE
```

原有 Python 实现继续保留，直到原生实现逐项通过同一套黑盒与生命周期验收。任意功能未实现时，原生入口必须明确报“不支持”，不能偷偷调用 Python。

### 1.1 “全部不加载 Python”的定义

本阶段以**运行时不加载 Python**为第一发布条件：

- `zzy-native run/check/test` 的进程依赖中没有 `python*.dll`、`python.exe` 或 Python 扩展；
- 核心语言、资源计量、诊断、标准库和测试运行器由原生代码提供；
- 编译器构建脚本可以在过渡期使用 Python，但生成的发布程序和运行测试不依赖它；
- Web、GUI、SQLite 属于可选原生宿主包。若某个宿主尚未有原生实现，原生核心明确拒绝该入口，不退回 Python。

如果以后要求“连构建工具也不用 Python”，再增加自举阶段：用已发布的 `zzy-native` 或独立 C++ 工具生成自身前端。它不是 NATIVE-01 的第一验收条件。

## 2. 推荐架构

### 2.1 原生前端

在 `native/` 下实现 Lexer、Parser 和 Resolver，保留现有 `.zzy` 语法、Token 位置、错误码和求值顺序。第一版可以生成紧凑的只读字节码，而不是把每个 AST 对象完整复制到运行时：

- 常量池保存字符串、源码位置和任意精度整数的原文/二进制表示；
- 指令保存操作码、操作数和源范围；
- 函数表保存参数、局部槽、捕获布局和返回类型；
- Program 只读，可由多个请求共享；
- 请求状态、Cell、Frame、Lazy 和容器绝不能写入共享 Program。

`check` 只做读取、解析、名称/控制流/资源静态准备，不执行默认表达式、用户函数、I/O、Lazy 或 GUI。原生前端的诊断需要与现有 Python 前端逐项比较，不允许因为新后端而放宽语法。

### 2.2 原生值和内存

运行时使用带标签的 `Value`：`Null/Bool/Int/Float/String/Array/Map/Shape/Function/Result/Lazy/Machine/Quantity`。正式 ZZY 的 Int 是任意精度，因此不能把当前 AOT 的 Int64 直接冒充完整实现；需要独立的 `BigInt`，并在每次中间运算前检查 `integer_bits`。

推荐的生命周期策略是“请求区域 + 可追踪堆”：

1. Frame、临时表达式和一次请求内确定不可逃逸的对象从 ExecutionArena 分配；
2. 捕获 Cell、闭包、Lazy、容器和跨调用对象进入受计量的堆；
3. 用引用图标记清扫处理数组/Map/闭包环，不能依靠 C++ 引用计数单独解决循环；
4. 每个拥有的对象记录对象数、槽位、载荷和深度，释放和取消必须幂等；
5. 容器写入口统一维护别名、版本、活动遍历和冻结状态。

实际对象大小只用 Windows 工作集/Private Bytes 等系统指标测量；`runtime_payload_bytes` 仍是逻辑预算，不能当作 RSS。

### 2.3 原生解释器和宿主 ABI

解释器采用显式调用栈和指令分派循环，避免把 ZZY 的 `call_depth` 绑定到 C++ 宿主栈。宿主库通过固定 ABI 注册：参数类型、返回类型、资源需求、纯性、取消点和错误码全部是静态元数据。禁止开放任意 C++ 反射、动态库符号、脚本 `eval/exec` 或 Python 属性访问。

标准库按现有契约逐项移植：`io`、`array`、`text`、`math`、`data`、`unit`、文件/JSON、SQLite、Web 和 Sketch 分开登记。先完成核心无 I/O 路径，再移植文件和数据库；Web/GUI 不得被核心 `check` 或 headless 路径隐式初始化。

## 3. 执行模式和用户入口

稳定交付期间保留三种明确入口：

| 入口 | 运行时依赖 | 用途 |
|---|---|---|
| `python -m zzy ...` | CPython | 兼容实现、课程基线和尚未移植的功能 |
| `zzy-native run/check/test ...` | 原生运行库 | 目标中的全原生解释器 |
| `zzy-native build ...` | 构建机工具链，生成 EXE | 受支持静态子集的 AOT |

第一版不自动根据“看起来像算法”切换引擎。自动切换会让同一源码出现不同整数宽度、错误位置、资源计数和副作用顺序。用户必须显式选择 `zzy-native` 或兼容入口；原生编译遇到不支持的结构在构建阶段失败。

当原生解释器达到完整语义门槛后，才可以把它设为某些独立 CLI/算法程序的默认入口。Web/GUI 请求中的热点 AOT 只有在 ABI、取消、内存所有权和错误映射验收后才能接入；频繁小调用应优先留在同一原生进程，避免进程通信抵消收益。

## 4. 分阶段任务和完成标准

### N0：冻结语义和对照

- 锁定 syntax、stdlib、resources、diagnostics、web/sketch 契约版本；
- 建立 Python 解释器为 oracle 的固定答案、错误码、stdout/stderr、退出码和资源清理清单；
- 选 X00—X03、校园任务管家核心、错误/取消/别名/闭包/大整数样例；
- 完成标准：任何原生差异都能定位到源码范围、阶段和独立期望。

### N1：原生前端和 Program

- 实现 Lexer、Parser、Resolver、依赖图、源码快照和静态 `check`；
- 生成只读 Program/字节码，支持中文/空格路径和原有诊断坐标；
- 完成标准：原生 `check` 与 Python `check` 在全部合法/非法黑盒上结果一致，且不运行副作用。

### N2：核心值和资源运行时

- 完成 BigInt、Float、String、Array、Map、Shape、Result、Quantity 的标签和值生命周期；
- 完成对象/槽位/载荷/深度/整数位数、取消和清理；
- 完成标准：资源边界 L-1/L/L+1、别名、环、宿主 MemoryError 映射和取消恢复与现有证据一致。

### N3：原生解释器核心

- 实现声明、赋值、块作用域、分支、while/for、函数、递归、闭包 Cell、短路、查询和 Lazy；
- 保持从左到右求值、函数调用栈、错误 notes 和返回值交接；
- 完成标准：核心语言黑盒、P03/P04 特色值和变形关系全部通过，原生进程无 Python 依赖。

### N4：标准库和应用宿主

- 按契约移植 io/array/text/math/data/unit、严格 JSON、文件原子保存、SQLite 事务；
- 再实现 Web/Sketch 的原生 headless 接口，GUI 放入独立可选包；
- 完成标准：宿主注册表、参数绑定、错误和资源计量与 Python 版本一致；核心路径不加载 Web/GUI。

### N5：原生 CLI、测试和安装

- 提供 `zzy-native info/run/check/test`、JSON/text 诊断、独立测试进程和进程树清理；
- 生成源码外可运行的 Windows 发布目录或安装包；
- 完成标准：清除 `PATH/PYTHONPATH` 后仍可运行；进程模块枚举、导入表和依赖检查没有 Python。

### N6：迁移和双实现一致性

- 对全量黑盒、P09 应用、P08/P10 Web/SQLite、Sketch headless 和适用 GUI 分别跑双后端；
- 任何未移植功能保持显式延期，不改变 ZZY 语法或静默降级；
- 完成标准：新增后端不减少原测试集合，失败/超时/空收集均非零，原应用文件格式保持兼容。

### N7：性能、内存和 AOT 评估

- 分开测前端准备、解释执行、AOT 构建、完整 CLI、CPU 时间、峰值工作集和逻辑资源；
- 与 CPython、手写 C、必要时其他无 JIT 运行时做同工作量配对；
- 完成标准：至少两轮独立样本、完整答案/错误校验、失败单列。只有稳定收益才保留快路径；不承诺普遍快过优化 C。

### N8：发布门禁

- 核对源码外安装、中文/空格路径、离线环境、无 Python 进程、核心/Web/GUI 分层依赖；
- 建立原生版本号、契约版本和回滚方式；
- 完成标准：完整核心回归、安装 smoke、真实 HTTP/Sketch 适用专项、人工演示和 Git 提交都指向同一候选 SHA。

## 5. 测试和禁止事项

每个阶段必须保留独立固定答案，不让原生后端和 Python 后端互相生成期望。至少检查：

- `Int`/`Bool`/`Float` 严格区别，任意精度和中间溢出；
- 求值顺序、别名、闭包捕获、Lazy 状态、稳定排序和错误路径；
- `check` 不执行函数、默认值、I/O、GUI 或模块业务初始化；
- 资源超限、取消、宿主错误和失败后的下一请求/下一进程恢复；
- Web/SQLite/Sketch 的线程、连接、关闭、持久化和状态隔离；
- 原生 EXE 的依赖导入表、子进程树和环境变量，证明运行时没有 Python。

不能采用以下“优化”：降低资源检查频率、删掉诊断和 notes、把任意精度改成静默 Int64 截断、把不支持功能交给 Python、在 check 阶段执行用户代码、用静态检查代替真实运行，或因原生后端失败而减少黑盒用例。

## 6. 风险、取舍和首个可执行子任务

最大的风险不是把循环翻译成 C，而是复制完整 ZZY 语义：BigInt、容器环、闭包/延迟状态、模块图、资源释放和标准库 ABI 都必须同时成立。原生解释器可能比 CPython 更轻，却不一定比优化 C 快；AOT 也可能因编译时间、代码体积或宿主边界变慢。每个结论都要用实测而非设计文档证明。

首个实现子任务建议为 **N0-01：冻结 X00—X03 与核心错误/资源期望**，不改语言语义、不改 Python 解释器。N0-01 完成后再做 N1 的原生 Lexer；在 N3 之前不把 `zzy-native` 宣传为完整 ZZY，在 N8 之前不切换默认入口。

本文件是开发计划，不表示任何 N0—N8 已完成，也不改变 P12/P13 当前任务状态。

## N1 顺序例外（2026-11-17，用户明确授权）

N0-01/02/04/05 的语义、逐特性能力、E402、所有权及固定 golden 证据已复核；N0-03 仍未完成，N0 总出口未通过。本轮仅暂缓 CMake configure/build、CTest 与安装验收，使用已有 GCC 8.1.0 实现并验证 N1-01—04。此授权覆盖原有“未过 N0 不进入 N1”的顺序限制，不覆盖正式构建门禁；不安装工具链，不进入 N2，不修改 Python 默认入口，不回退 Python。

N1 通过时只能记录“N1 实现与 GCC 验证完成，正式 CMake/CTest 验收待补”。以后必须对最新代码重新执行 Debug/Release 配置、构建、非空 CTest、install 与源码外 smoke，不能沿用 N0 原型证据。

## N0-03 正式补验收说明（2026-11-18）

上文N1顺序例外保留为历史。用户本次明确要求对最新N1代码补齐正式构建：已有CMake4.5.0、VS2022/MSVC19.40，Debug/Release各32项非空CTest、Release安装及仓库外发布副本已实测。没有改变任务编号、依赖或出口标准；详细结果与未验证边界见[正式报告](../../native_runtime/tests/msvc-report.md)，当前状态只维护于todo。

N0出口要求离线构建、非空CTest、冻结决策、环回收/配额和未支持能力拒绝；N1出口要求固定词法、位置/路径、无Python和坏输入。上述证据已具备。手动Ctrl+C、Sanitizer与干净缺CRT主机仍未执行，本阶段不声称这些验证通过；后续对应N5/N8门禁不得豁免。下一阶段N2需另行开展，本次不实现。

## N2-01—04 实施记录（2026-11-18）

用户确认 N1 技术验收后，按 N2-01→04 实际实现 Parser、不可变 AST、Resolver、绑定/传递捕获布局、精确静态字面描述、规范路径模块图和 `check`/`program-info`。不进入 N3，不求值、不创建 Cell/Frame/Value/模块实例，不执行默认表达式、函数、Lazy、spec、I/O、SQLite、Web 或 GUI。集中接口见 [Program契约](native-program-contract.md)。

Parser/Resolver 由 `native_runtime/include/zzy_native/{ast,parser,program,resolver,literals,prepare,program_dump}.hpp` 提供；宿主仅以 `host_metadata.hpp` 的冻结描述参与名称/纯性判断。`main.cpp` 的 check 成功返回0且静默，run/test仍E402/2；program-info 是确定性 JSONL 观察接口，不是可读缓存。

独立原生10项单测、848条既有check固定期望、850条PowerShell固定期望和17项Program观察器通过。GCC和直接MSVC Debug/Release构建均真实运行；CMake目录在当前会话访问被拒，正式 CMake/CTest/install 尚未对 N2 最新源码重跑，不能沿用 N1 的32项结论。AST/Resolver/模块图和check边界已验收，实际值执行、跨请求隔离及宿主运行能力留给N3/N6。

## N2 正式构建与交付补跑（2026-11-18）

上文N2实施记录中的CMake/CIM/Git权限限制是补跑前历史。用户恢复工具访问并要求补跑后，已对最新N2源码执行正式CMake/MSVC Debug、Release配置/构建，各44/44非空CTest、固定词法87/check850/CLI62/Program观察17、各58条过程验收及Release安装/源码外副本各9/9。没有沿用N1旧32项结果；失败修复、产物SHA与未验证范围见[N2报告](../../native_runtime/tests/n2-report.md)。N0-03/N1及N2静态出口已满足，下一项N3-01；本次不求值，不改P12/P13或默认入口。

### N4-02 交接更新（2026-11-18）

N4-02 已按依赖完成：四个文件和两个 JSON 接口已在 C++17 原生运行时接线，使用请求所有权、Windows 宽字符文件 API、同目录临时文件和 MoveFileExW 提交；JSON 使用请求内显式栈，不依赖第三方解析器或用户代码。MSVC Debug/Release CTest、固定清单、CLI 文件黑盒、安装副本和相关 Python 回归均有新证据，详见 `native_runtime/tests/n4-02-report.md`。N4-03 SQLite、N4-04 Web、N4-05 Sketch headless、N4-06 GUI 继续保持未完成。

### N4-03 交付更新（2026-11-19）

N4-03 已按集中 SQLite 契约完成。`db.transaction`/`db.query` 使用 Windows SDK 系统 SQLite，连接和事务均请求所有权、同线程、幂等关闭；authorizer、绑定、1 秒查询期限、250ms 锁等待、取消和逻辑配额均有实现。MSVC Debug/Release CTest 各 75/75，四个同进程探针与 50 个独立 CLI 程序各通过；OFF 构建返回 E402/1；Release 安装和仓库外副本再次通过。报告、DLL sourceid/签名/哈希、失败原件及复现命令见 `native_runtime/tests/n4-03-report.md` 和本轮 `dist/native-n4-03-work`。没有把 SQLite 内部 RSS 当作语言配额，没有加载 Python，也没有修改 Python 应用文件格式。

未验证人工 Ctrl+C、Sanitizer、其他 OS、缺 VC Runtime 主机、Web/Sketch/GUI 及全量 N5 test；下一项 N4-04 Web。

### N4-04 交付更新（2026-11-19）

原生 Web 已按 [集中契约](../runtime/web.md#n4-04-原生-http-宿主) 接入独立可选 EXE，离线构建使用固定版本 cpp-httplib 与 Winsock。真实 HTTP 覆盖默认/显式 shared、冻结与交错请求、shape 合约及静态 OpenAPI、容量/超时/断连/关闭、SQLite 取消回滚及重启。MSVC 两配置各 76/76 CTest，源码外安装副本和模块审计通过，见 [N4-04 报告](../../native_runtime/tests/n4-04-report.md)。下一项 N4-05，N4-06 仍待实现，Python 默认入口不变。

### N4-05 首批交付（2026-11-19）

几何、图层、分组历史与 SVG 已有 [首批实现/验收报告](../../native_runtime/tests/n4-05-geometry-report.md)。按 N4 分轮规则保留 N4-05 未完成；其余 headless 项目读写/对象/图案/回放/事件继续作为下一批，N4-06 不提前进入。
