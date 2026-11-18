# N4 原生标准库与宿主接入

本文件维护原生接入方式和阶段范围，不复制语言字段规则。[标准库契约](../language/stdlib.md)、[资源](../runtime/resources.md)、[语法](../language/syntax.md)仍规定实际可观察行为。Python 默认入口不变；没有 Python fallback。

## N4-01 核心库

沿用已有 C++17/MSVC 运行时和冻结的宿主元数据。执行签名集中于 `core_hosts.hpp`，参数值从左到右求值完毕后，先验证数量、再验证所有外层类型。Bool 不满足 Int；内层元素检查及错误位置遵守原有标准库与固定黑盒。纯调用名单不变，不能因为已移植就允许查询调用 array.map、data.kind 等非名单接口。

本阶段接入全部数组、文本、数学和单位接口，以及 Map 与已有 core/io.print/io.input。文件接口与 data.parse/stringify 属于 N4-02；它们在 run 中继续报 E402，不提供假实现。`array.Stats` 是每请求缓存的固定结构定义，count/sum 注解 Int，min/max 无注解；构造和 with 遵循普通 shape 规则，实例各自独立。

原生依赖仅 C++ 标准库及既有 Windows/CRT，不新增下载项、工作线程、网络、GUI 或进程缓存。所有函数在所属 ExecutionContext 的线程中执行；回调沿用显式调用帧和捕获布局，宿主不持有请求外的 Value。map/filter 对源 Array 设置 RAII 活动计数：读取当时的项，增删先 E206，普通替换允许；退出、类型/资源错误与取消均释放计数。filter 保留原元素引用，sorted 稳定排序并返回新 Array，不复制元素。

分配前预留总量和单体资源；排序缓冲计 3n 槽，聚合逐项检查整数中间值，文本按码点和在用载荷计费，safe_int 的格式失败和 E211 分开。长遍历、比较、整数转换及文本搜索有协作取消点。无文件提交或长期句柄，因此无新增 close 入口；清理由幂等的请求关闭负责。阻塞 stdin 的中断边界沿用 N3，不宣称任意 C++ 标准库操作都可立即抢占。

Unicode trim 冻结为已验收 Python 3.12 / Unicode 15.0 的空白集合，非 ASCII 字符串按码点处理；safe_int 只裁掉 ASCII 空格、Tab、CR、LF，不接受 Unicode 数字或 NBSP。

## 后续宿主

N4-02 文件/严格 JSON、N4-03 SQLite、N4-04 Web、N4-05 Sketch headless、N4-06 GUI 尚未以本文件声明实现。每项开始前须链接其集中契约，并登记原生依赖、线程、取消、资源及关闭规则；验收后才更新能力矩阵。SQLite/Web 以 [互联契约](../runtime/web.md)为准，Sketch 以 [独立契约](../features/sketch.md)为准。不能用 Starlette/Uvicorn/Tk 的 Python 依赖代替原生实现。
