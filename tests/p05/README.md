# P05 标准库、模块和文件验收

`python -X utf8 -m unittest tests.test_p05_cli tests.test_p05_integration -q` 运行本阶段专项。独立 CLI 清单为 [cases.json](cases.json)，369 项（184 run、185 check），其中包含 library/main、library/spec、total-up-to 三个真实示例。固定答案、错误码、原文坐标独立维护，未从解释器生成快照；全局运行器默认包含本清单。

另有 18 项 [集成/宿主测试](../test_p05_integration.py)，其中文件、依赖限额与 spec 通过真实 CLI/worker 运行；故障注入只覆盖语言不能捕获的宿主中止、资源所有权和磁盘替换边界。两类计数分开；完整 unittest 已含所有外部期望，不能再与 blackbox 总数相加。

| 覆盖类别 | 独立源码/外部期望 | 补充证据 |
|---|---|---|
| LIB-01 | sum/stats 对固定答案和手写循环；empty、sorted-copy、map-order/replacement、filter-alias、callback-*、bulk-argument-order | 相同排序键保留 Value 身份顺序；异常/取消/内存/资源后 active=0，所有预留释放 |
| TEXT/NUM/UNIT | text-*、safe-int-*、math-abs、unit-*、outer-type-*、arity-*、empty-library | Unicode trim、ASCII 整数格式、Int 位数和数字数；单位 Float 保留实际二进制值 |
| JSON-01/02 | map-*、kind-*、json-*：重复解码键、非标准数、surrogate、cycle/shared、nested Machine、Quantity/Module/Definition 拒绝 | 默认 JSON 深度 63/64/65；Map 键序/版本/别名、嵌套 Machine 冻结；kind 不遍历或 wake |
| MOD-01 | module-* 与 modules/：相对路径/规范去重/菱形依赖、定义名义身份、查询封装、私有成员、只读、缺文件/扩展名/循环/依赖错误 | 同 Program 多次上下文状态独立；旧 Program 保存旧快照、新 prepare 读取新依赖；默认导入深度 32/33，模块数/总字节相邻边界 |
| FILE/CLI-02 | check-library-noexecution；所有文件接口 arity/outer-type；library/spec 真实往返 | UTF-8/BOM/非法编码/NUL/缺文件、工作目录基准、空文件、原子覆盖/replace；write/close/replace 失败旧文件不变；交错的两次写入同时持有不同独占临时文件 |
| QUERY-03 | query-pure-library/grouped-native/shadow-library/library-alias/nonwhite-library | 固定真实原生身份白名单；注册 pure 元数据不会自动开放任意扩展 |
| TEST-01/RESOURCE | check 对每项源码前端对照；独立 spec 示例 | 每例模块/Lazy/全局/文件/stdin 隔离；收集后删除依赖仍按原图运行；坏依赖阻止所有初始化，导入错误显示实际文件 |

原 P02 `unimplemented-library` 的 `array.sum([]);` 在 P05 已合法，保留源码，仅将 run 期望迁移为退出 0、空输出；其余既有外部期望保持。统一校验保留 len/str 原有调用括号错误定位，新增库类型错误定位实参。结果/IO 格式错误为失败 Result；配额、取消与 MemoryError 穿过普通错误转换。

不据本阶段通过宣称完整 P06 矩阵、全部指南片段、真实终端 Ctrl+C、其他 Python/OS、Program 缓存优化、公开 Web 共享冻结、GUI/进程树或性能已验收。临时目录测试只能证明本次注入故障下清理成功；断电持久化不属于 write_atomic 承诺。实测命令/计数/时长和最终提交见 [development-log](../../docs/development/development-log.md)。
