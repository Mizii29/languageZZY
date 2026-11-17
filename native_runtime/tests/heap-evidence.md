# N0-04 堆实验边界与固定答案

只验证所有权、可达性和三项逻辑计量，未实现 ZZY 容器/闭包执行。图中的边是 owner/id 句柄；不是拥有引用。
每个请求独立 Heap/Budget；Root 使用弱引用的根登记表，根晚于 Heap 销毁也可安全析构；跨堆/过期 owner/id 拒绝。
Program 不含此可变图。ID 不复用；根 metadata 的实现内存不伪装为语言 runtime_slots。

| 原生用例 | 独立固定答案 |
|---|---|
| array-cycle | A→A：收集前(1对象,1槽,0字节)，去根收集1个后(0,0,0) |
| map-cycle | M→K、M→M，单码点键K：收集前(2,2,4)，去根收集2个后全0 |
| closure-cycle | A→F→Cell→A：(3,3,0)，去根收集3个后全0 |
| reachable-alias | 根别名→A→M→K/M：去掉其他根仍保留(3,3,4)，去最后根全收集 |
| quota-gc-retry | 对象上限1，自环垃圾占额时下一分配先GC，旧槽归还，新Text得到(1,0,4)，旧ID无效 |
| atomic-limits | Map两个引用槽预留在上限1时原子失败；多个限制先 objects；UINT64_MAX请求不整数回绕 |
| allocation-rollback | 成功预留后注入 bad_alloc，分配与写边均退预留，原图不变 |
| ownership | 跨请求边/旧owner/关闭后句柄拒绝；重复close幂等；根可晚析构 |
| cancellation | 已取消上下文不能分配/修改，close后计数0；下一请求成功 |
| unwind-roots | 普通错误展开RAII roots后环可回收 |
| iterative-graph | 5000节点环：有根全部保留，去根全部回收；非递归遍历 |
| repeated-collection | 同一请求1000次闭包环，每次回收3节点，配额每次归零；不是只在请求结束清空 |

Debug与Release均实际通过12/12；空/未知用例选择实际退出1，不能空集合成功。
原始命令、编译参数和产物哈希以[阶段报告](n0-report.md)为准。
语言 golden 的6条固定外部期望由稳定Python CLI核对，原生仍E402，未将其计为原生语言通过。
Sanitizer/MSVC/真实GUI未测；逻辑计数归零不等于已证明RSS没有碎片或所有未来宿主不会泄漏。
