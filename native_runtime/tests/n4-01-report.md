# N4-01 核心标准库验收

2026-11-18，原生版本 0.0.0-n4-01-dev。范围为 io 已有 print/input、全部 array 聚合/排序/回调、text trim/contains/join/split/replace/safe_int、math.abs、data Map/kind 和 unit.make/format；文件、严格 JSON、SQLite、Web、Sketch、GUI 不在本任务。

实现入口是 core_hosts.hpp、core_library.hpp 与 execution.hpp。参数数量和外层类型在回调前检查；Bool 不作为 Int；Map/Array 只通过统一 append/write 入口；排序稳定且返回新数组。map/filter 在显式调用帧中执行 callback，源 Array 的活动计数用 RAII 清除；资源、取消、类型错误均清理后才结束请求。标准 C++17/CRT 外无依赖、无新增线程、网络、GUI 或进程缓存。

专项：

- Debug/Release 完整 CTest 各 64/64（N3 57 项加 N4-01 专项 7 项，包括空选择和 126 项固定库清单）；
- P05 选中的 126/126 既有标准库 run 期望，两配置分别通过；旧 P02 array.sum 延期已迁移；
- C++ 探针覆盖回调失败、别名增删 E206、回调取消后 active=0、稳定排序保留元素身份、array.Stats 请求内名义身份、文本/排序配额 L-1/L/L+1、同进程下一请求恢复；
- examples/core-library.zzy 在 Release 实际输出固定为：[4, 13, -2, 7]、[-2, 1, 7, 7]、[7, 2, 7, 1]、[7, 7, 1]、ZZY native、[a, , b, ]、bAnAnA、(^_^)(42)。

Debug/Release 最终 EXE SHA-256 分别为 `ad5570b54b087acd5ade05f167ec2fa728a48ec96a48a86c370af73c3e832956` 和 `5fe2ee609fc787ac9502519149b018dbc1fca760dd5aba892c6267839f97d898`。失败原件保留在 `dist/native-n4-01-work/build-library.txt`（首轮探针夹具引号错误）、`library-release-final.json`（并行构建尚未结束时使用旧二进制的 E402，不计最终结果）和 `library-first.json`（首轮 Debug 过程记录）。最终证据另保存构建、CTest、126 项结果、核心 550/550、CLI 72/72、安装 smoke 及进程依赖报告。

未验证：文件/JSON、SQLite、Web、Sketch、GUI、N5 test、N6 全量清单、手动 Ctrl+C、Sanitizer、其他平台和性能。N4-01 完成后进入 N4-02。
