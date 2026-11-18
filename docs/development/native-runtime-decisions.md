# N0 原生实现决策冻结

2026-11-17。这是移植设计，不表示 N1—N8 已实现；[能力矩阵](native-runtime-capability.md)限定当前能力。

| 决策 | 采用方案与理由 | 替代/风险与验收阶段 |
|---|---|---|
| 目标/工具链 | Windows x64、最低目标 Windows 10；C++17、CMake >=3.21；首选 MSVC 2022 或 clang-cl；保留现有 GCC 8.1.0/MinGW 原型 | 2026-11-18已有CMake/CTest4.5与MSVC19.40完成正式Debug/Release各32项CTest和安装；MinGW不代替此证据，clang-cl和Windows10实机未验证 |
| CRT | 正式 MSVC Debug /MDd、Release /MD；只发布 Release，不私自安装运行库 | 已实测System32既有VC runtime14.50.35719.0与系统UCRT；精确DLL白名单、加载路径/版本/哈希见正式报告。缺CRT主机未验；MinGW原型保持静态libgcc/libstdc++与系统msvcrt |
| BigInt | 采用自有符号 + uint32_t 小端 limb 的任意精度实现；中间乘积用 uint64_t；按 integer_bits/载荷预算提前检查，负 //、% 向下取整，精确比较/有理数共享此实现 | cpp_int 可减少工作但本机无已锁定离线 Boost；N0 不下载。自有实现需 N3 固定跨 limb、负数除法、超限、中间值测试后才能算 Int 可用；本轮不拿 uint64_t 冒充 Int |
| UTF-8 | 严格 UTF-8 字节快照；Program 内保存码点→原字节/行列映射；BOM 不计列、CRLF 单换行、Tab 一码点、EOF 可零宽；String 按码点 | 不用 locale/wchar_t 长度当码点；Unicode 标识符/空白需冻结 Unicode 15.0.0 表，N1 离线提交有来源的数据后验收，不依赖运行时 Python |
| AST Program | 首版不可变 AST/源码快照/绑定布局，Program 内索引 ID；不保存 Python id 或跨请求可变 Value，不生成 VM/缓存/AOT | 解析器/Resolver N2 实现；P12 的独立 AOT demo 不复用为原生解释器 |
| 所有权 | Program 可共享；每请求独立 Heap、Frame、Cell、Lazy、模块实例、取消和计量。闭包捕获定义环境；结构默认值捕获运行环境放请求中 | shared Web 的只读 Program/描述可共享，含捕获的运行时图不得进入 Program；细则仍以 Web 契约为准 |
| 环回收 | 每请求非移动标记清扫堆；图边为带 owner/id 的非拥有句柄；显式 RAII roots；分配安全点先收集再重试配额，退出强制释放 | 拒绝 shared_ptr 单独管理有环图；只在请求结束释放的 arena 无法归还运行中配额；原型仅验证图/计量，非语言实现 |
| 根集合 | 所有 Frame/临时求值栈/Cell/闭包捕获/模块/Lazy 缓存/结构默认环境/宿主回调都必须可追踪；跨堆边拒绝，ID 不复用 | 漏根会提前回收；N3 每条执行路径和异常都补临时 Root，N4 句柄关闭/回调解绑在清堆之前 |
| 逻辑资源 | 沿用 default-v1 全键/单位/顺序与事务预留；String 4×码点、Int ceil(bits/8)、Float 8；宿主内存不冒充逻辑载荷。回收先退独占载荷及引用槽，别名不重复退对象 | 原型只实现 objects/slots/payload 三计数；动态 limits/深度/文本等正式接线留 N1—N5；不声称全部资源已经实施 |
| 策略指纹 | canonical JSON + SHA256，与 Python 规则一致；原生无 CPython 十进制宿主上限，host_decimal_digits=0、有效4096；info 声明默认策略，暂不接受 --limits | 指纹因此与 Python host4300 不同，不能伪造一致；N3 要独立验证中间 BigInt/十进制预算 |
| 异常/取消 | 错误值/普通诊断、LimitExceeded、Cancelled 分层；资源与取消不缓存为 Lazy 普通错误，清 RUNNING；bad_alloc→E211，未知异常→internal_error/code=null | RAII reservation、roots、连接/线程均幂等清理。取消为安全点协作，超时是父运行器终止进程树；不承诺任意阻塞宿主可硬取消 |
| 第三方 | N0 零项目级第三方依赖：JSON 只编码 info/诊断，不实现假 JSON 解码；BigInt 自有。C++ 标准库及编译器运行库属于工具链 | 后续 SQLite/Web/GUI 每项单独锁版本/来源/许可证并离线纳入，不在 CMake FetchContent/测试中下载；现有 Python 可选依赖保留不加载 |

信息入口报告编译器、指针位数、CRT 和声明策略。正式构建、安装、Unicode 数据来源和完整语言执行均须其阶段实际验证。
没有性能/内存相对 Python/C 的结论，本原型不等价于完整解释器。

## N1 实施补充（用户顺序例外）

N0-03 未过，按用户2026-11-17授权先实施 N1。以上 N0 冻结表是设计起点，以下覆盖其中的阶段性“未接线”状态，不改语义：

- Unicode15.0.0分类表已按锁定 CPython3.12.14 离线生成，元数据见 native_runtime/tests/unicode-tables.json；EXE 不调用 Python。
- 源码路径采用 Win32 W API/wmain，避开现有 GCC8.1 std::filesystem 编译错误；没有安装或修改工具链。
- --limits、前端活动资源、规范JSON/SHA已接线；22键全部保留，尚未执行的AST/运行时/缓存键不宣称已验证。
- 零第三方依赖保持；新增严格、有限深度的 limits 配置解析器，不是 N4 的语言JSON解码接口。
- 源码为 const 快照/码点映射，Token持有const Source；每个 SourceLoader/FrontendMeter 独立，失败不发布费用，退出幂等清理。

实现与证据见[前端契约](native-frontend-contract.md)、[N1 GCC历史报告](../../native_runtime/tests/n1-report.md)。以上顺序例外已在2026-11-18补齐正式CMake/MSVC/CTest/install，详见[正式报告](../../native_runtime/tests/msvc-report.md)；N0/N1技术出口满足，未扩展为完整语言或N5/N8发布验收。

## N2 表示补充（2026-11-18）

Program采用移动发布到const独立分配的节点表，NodeId为后序索引；Reference和Symbol/FunctionPlan记录静态绑定与捕获，不持有请求数据。模块图按SourceLoader规范路径去重，每次prepare重新读取有界快照。静态数字描述保留任意精度uint32 limbs，Quantity保留精确分数及量纲；不复用N0堆原型作为运行时容器。MSVC Debug实测默认深度需要更大宿主主线程栈，CLI/Program测试链接时预留8MiB、按需提交；语言syntax_depth=64不变。完整接口只维护于[Program契约](native-program-contract.md)。
