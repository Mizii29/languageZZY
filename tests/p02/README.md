# P02 数据与控制流验收

`python -X utf8 -m tests.blackbox tests/p02/cases.json` 运行 279 个独立 CLI 期望（139 个 run、140 个 check）。普通运行用例都有 check 对照；另有包含输入、无限循环、默认值副作用、数组修改和除零的 check 专用程序，在运行预算仅 1 时仍零执行。期望答案和坐标按契约/源码维护，不从待测解释器生成快照，不使用 spec。

| 覆盖编号 | 实际用例族 | 验证边界 |
|---|---|---|
| EXPR-01/02 | numeric-precedence、exact-comparison、division-identity、short-circuit、short-circuit-input、arithmetic-left-to-right | 正负整除变形关系、Float/大 Int、严格 Bool、比较链、除零/溢出、跳过输出/输入/修改 |
| BIND-01、CTRL-01 | branches、loops、nested-loops、for-source-outer-binding、inner-self-reference | 各分支、零次/嵌套循环、每轮绑定、块隔离、名称/控制流在执行前检查、String 码点、正负 Range |
| ARRAY-01/02 | array-alias-copy、array-iteration、active-push/pop、assignment-recheck/location | 负/Bool/Float/越界下标、空 pop、浅别名、最后一轮也先拒绝增删、旧目标保存、右侧缩短数组后重查 |
| SHAPE-01/02 | shape-defaults、shape-order-with、shape-lexical-default、default-after-explicit、shape-types-with | 显式值源码顺序、默认值声明顺序/词法环境、新建与共享、不重跑默认值、名义身份、错字段/类型及错误前副作用 |
| IO/CLI | input-lines、input-eof-empty、input-lone-cr、grades-menu/eof/exit | 提示、UTF-8、原始输入、CRLF、空行/EOF、真实成绩菜单 |
| RESOURCE-01/02（P02 部分） | array-capacity-*、input-text/bytes-*、value-depth-*、integer-exact-byte-budget、array-cycle-reclaim | L-1/L/L+1、默认 64 层显示、有限缓冲、Int 位数/载荷边界、环回收、不以保守乘积上界误报 |

宿主 `test_p02_runtime.py` 补语言致命错误后无法观察的义务：结构/内容版本分别更新，拒绝 push/pop 保留内容/版本/槽，嵌套活动计数在错误/取消/内存异常后归零，同一 Program 复用容器/输入隔离，输入失败不变 EOF，提示先 flush，循环引用释放计量；整数宽度探测对照独立宿主算术。既有运行器测试确认空收集、坏清单、超时、错误答案/诊断和输出超额不会成功。

P03 的函数/闭包/跨函数跳转现见 [P03 验收](../p03/README.md)；P05 的 map/filter 回调与数组校验缓存、完整 RESOURCE/CLI 矩阵仍未验证；当前数组没有原地重排公开接口。此验收不声称完成 P06、GUI/派生进程树回收、真实终端 Ctrl+C 或其他宿主平台。

P01 六类原“不支持”输入保留原文件名用于历史回归：Float、Bool、数组、块、一元负号现在成功；Float 注解赋 Int 的 run 改为 E201，check 成功。spec 仍为 E103。清单没有删除这些回归。

P03 保留 unsupported-function.zzy 历史文件名，将其 run/check 期望迁移为成功；函数不再被当作不支持语法，其余 277 项 P02 期望保持不变。
