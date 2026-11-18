# N4 原生标准库与宿主接入

本文件维护原生接入方式和阶段范围，不复制语言字段规则。[标准库契约](../language/stdlib.md)、[资源](../runtime/resources.md)、[语法](../language/syntax.md)仍规定实际可观察行为。Python 默认入口不变；没有 Python fallback。

## N4-01 核心库

沿用已有 C++17/MSVC 运行时和冻结的宿主元数据。执行签名集中于 `core_hosts.hpp`，参数值从左到右求值完毕后，先验证数量、再验证所有外层类型。Bool 不满足 Int；内层元素检查及错误位置遵守原有标准库与固定黑盒。纯调用名单不变，不能因为已移植就允许查询调用 array.map、data.kind 等非名单接口。

N4-01 接入全部数组、文本、数学和单位接口，以及 Map 与已有 core/io.print/io.input。文件接口与 data.parse/stringify 现由下文 N4-02 接入。`array.Stats` 是每请求缓存的固定结构定义，count/sum 注解 Int，min/max 无注解；构造和 with 遵循普通 shape 规则，实例各自独立。

原生依赖仅 C++ 标准库及既有 Windows/CRT，不新增下载项、工作线程、网络、GUI 或进程缓存。所有函数在所属 ExecutionContext 的线程中执行；回调沿用显式调用帧和捕获布局，宿主不持有请求外的 Value。map/filter 对源 Array 设置 RAII 活动计数：读取当时的项，增删先 E206，普通替换允许；退出、类型/资源错误与取消均释放计数。filter 保留原元素引用，sorted 稳定排序并返回新 Array，不复制元素。

分配前预留总量和单体资源；排序缓冲计 3n 槽，聚合逐项检查整数中间值，文本按码点和在用载荷计费，safe_int 的格式失败和 E211 分开。长遍历、比较、整数转换及文本搜索有协作取消点。无文件提交或长期句柄，因此无新增 close 入口；清理由幂等的请求关闭负责。阻塞 stdin 的中断边界沿用 N3，不宣称任意 C++ 标准库操作都可立即抢占。

Unicode trim 冻结为已验收 Python 3.12 / Unicode 15.0 的空白集合，非 ASCII 字符串按码点处理；safe_int 只裁掉 ASCII 空格、Tab、CR、LF，不接受 Unicode 数字或 NBSP。

## N4-02 文件与严格 JSON

沿用标准库第 2、5 节的六个签名、Result 和资源错误边界。继续使用 C++17、现有 Windows 系统库和 CRT。文件与 JSON 在请求线程同步执行，句柄和临时缓冲随调用释放。`check` 只读取登记信息。

文件路径相对进程工作目录，使用 Windows 宽字符路径。UTF-8 读写保留 BOM 和换行原字节，读入时校验 Unicode 标量。每次操作独立计 UTF-8 字节数、码点数和工作缓冲。普通写入可以覆盖目标。原子写入先组装完整字节并准备成功 Result，再用 `CREATE_NEW` 独占同目录临时文件。写完并关闭后检查取消，再用 `MoveFileExW` 替换。该调用是提交点，成功后不回滚。替换前失败或取消关闭并删除临时文件。`io.replace_file` 使用相同替换调用，源文件由调用者预先关闭。两者均按同卷替换语义执行，不启用跨卷复制。

同步系统调用之间检查取消，单次阻塞系统调用返回后才响应取消。清理可重复。系统拒绝删除时保留原始取消或资源诊断。验收覆盖旧目标保留、句柄关闭、替换前清理和同进程下一次请求。断电持久性不在契约内。

JSON 由请求内的迭代读写器处理。读取按 JSON 拼写区分 Int 和 Float，完整校验解码后的重复键和代理对。输出保留 Map/shape 字段顺序，用当前路径检测环。数字、深度、单体容量、工作缓冲和输出分别计量。格式错误或不支持的值返回失败 Result，容量和取消传播为执行错误。持久化继续使用现有紧凑 JSON 字节布局。

文件 JSON 的 Int 不附加 HTTP 安全整数限制。Float 转换使用请求局部 C 数字 locale，接受有限次正规数及带符号下溢零，溢出失败；不修改进程 locale。`data.stringify` 不解包 Result、不唤醒 Lazy。Array/Map/shape 为复合深度，根复合值深度为 1，标量不额外加层；共享无环引用允许，当前路径上的环拒绝。JSON 扫描和输出不依赖宿主递归栈。

Win32 提交规则参见 [MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)；Float 转换参见 [CRT strtod 系列](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/strtod-strtod-l-wcstod-wcstod-l)。这些是宿主实现依据，不能覆盖本项目更严格的 JSON 及资源规则。

## 后续宿主

N4-03 SQLite、N4-04 Web、N4-05 Sketch headless、N4-06 GUI 分别验收。每项开始前须登记原生依赖、线程、取消、资源及关闭规则。SQLite/Web 以 [互联契约](../runtime/web.md) 为准，Sketch 以 [独立契约](../features/sketch.md) 为准。
