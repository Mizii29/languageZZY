# P04 特色语法验收映射

本阶段使用 `inputs/*.zzy` 的 157 个独立输入、两个 examples 文件及 `cases.json` 的 317 项外部期望。每个正常/错误输入均走真实 run/check；check-no-execution 仅做 check，含非法初始状态、输入、无限循环和除零。固定输出/错误码/原文位置独立维护，不从解释器结果生成答案；即使 assert 有缺陷，外部期望仍能检出。

```text
python -X utf8 -m unittest tests.test_p04_cli tests.test_p04_runtime tests.test_p04_spec -q
python -X utf8 -m tests.blackbox tests/p04/cases.json
python -m zzy run examples/features.zzy
python -m zzy test examples/features-spec.zzy
```

| 契约类别 | 独立 CLI 证据（文件名前缀） | 宿主补充与本阶段边界 |
|---|---|---|
| RES-01 | result/propagate/match：标签、相等、别名、模式常量/顺序/覆盖/作用域、只读载荷、提前返回、不合法上下文 | Result 普通失败值缓存通过 CLI；不伪造致命错误后脚本可继续 |
| LAZY-01 | lazy：创建零执行、当前捕获、传递/逐轮捕获、别名、两次一次、缓存失败 Result、直接/间接环、注解、无刷新 | FAILED 原诊断位置/新 wake notes；取消/配额/MemoryError 后 NEW 与重试；调用深度共用、结束释放 |
| PIPE-01 | pipe：源/被调用对象/其他参数顺序、链式、唯一直接插槽、错误中止、不自动 wake/解包 | callable 的函数调用需分组 `(target())(@)`，遵循既有 EBNF |
| MACHINE-01/02 | machine：自环/环/不同源同事件、构造/名义注解、别名/独立实例、固定失败消息、空事件发送、只读属性、坏图/参数/连续发送 | 分配失败不提交状态；Array/Shape/Result 嵌套与循环冻结；重复上下文不共享状态。模块导出、JSON 留 P05 |
| UNIT-01/02 核心 | quantity：十进制精确、换算、实际 Float、派生维度/无量纲、规范显示、量纲/类型/零除、指数/分母/中间整数相邻配额、先约分 | Fraction 独立对照、状态释放；unit.make/format 与 JSON 拒绝在 P05 实施，本轮不宣称可用 |
| QUERY-01/02/03 核心 | query：条目顺序、作用域、固定 len/str 实际绑定、禁止 AST/动态/遮蔽调用、源一次、空集/take=0、稳定 asc/desc、混合数值/Quantity/String、别名/重复查询、错误顺序 | 逐阶段计数、原输入下标 notes、异常/取消/配额/MemoryError 清理、原数组 active=0。模块及 P05 纯库待实现 |
| TEST-01/CLI | assert/spec 输入与 test_p04_spec.py 中独立临时 .zzy：断言真/假/类型/一次，run 跳过但检查 spec；trace 输出与零隐式 wake | 真实 CLI 校验每例状态/EOF 隔离、路径排序、失败续跑、超时、空收集/不存在/坏源码非成功、输出超额；宿主验证私有 cwd/TMP 清理、同批字节快照、总量上限、启动/捕获/坏协议失败 |

12 项运行时宿主测试与 12 项 spec/trace/运行器测试随 unittest discover 收集；后者仍运行真实 ZZY，少数故障注入仅验证宿主边界。正常特色示例在外部清单中；features-spec 的 test 模式另实际运行并记录到开发日志。

旧 unsupported-spec 输入不删除，只将其 run/check 两项期望迁移为成功；其他既有期望不变。原运行器的零收集、跳过/执行数不足、超时/输出截断防假成功回归保留。

未验证：其他 Python/OS、真实终端 Ctrl+C、GUI/派生进程树、模块/文件库/JSON、公开共享上下文冻结、全默认大容量压力矩阵及性能。它们不由 P04 核心通过推断完成。`test tests/` 会收集故意非法输入并失败，应使用独立正常 spec 文件/目录。
