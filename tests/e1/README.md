# E1-01 几何与受控类型验收

更新：2026-10-17。本目录只覆盖 E1-01，不表示 SVG、GUI、撤销、回放或完整 sketch 1.0 已完成。接口子集和固定配额见 [使用指南](../../docs/features/sketch-guide.md)，正式行为见 [sketch](../../docs/features/sketch.md)。

## 实际测试

- cases.json：110 项外部 run/check 期望，包含 54 个独立程序和一个公开示例的两种模式。输出、退出码、诊断文件/行列固定，不由运行输出反写答案；失败源单独存放。
- tests/test_e1_runtime.py：17 个宿主测试方法；通过真实解释器执行 ZZY 后观察只读几何，另在同一原生入口注入归属/冻结、配额与取消失败。9999/10000/10001 点边界再次运行独立 CLI。
- 全量自动发现包含这 127 项；默认 tests.blackbox 已纳入 E1 清单，共 1698 项（原1588 + 本轮110），不把宿主内循环和复测重复相加。

前置核验命令 `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_p05_integration tests.test_p06_guides tests.test_metadata -q`：25/25，13.168秒通过。既有 P05/P06 完成状态同时核对了当前文件、todo 和开发记录。

首轮84项外部清单发现12项失败：Bool夹具用了错误拼写、字段定位期望不正确；修正为语言规定的 `(true)` 及已有字段标识符位置后，联合首批16个宿主方法100/100、31.122秒通过。扩展到125项时，拒绝原生 `::{}` 的位置期望仍错误；按既有构造节点定位修正为类型标识符，未改解释器定位规则。

[cli-108-before-demo.json](results/cli-108-before-demo.json)保留之后108/108外部CLI的实际命令、退出码和资源指纹。它在加入公开示例的2项及最终冻结入口修复前运行；不是当前110项全部完成的报告。内部归属复核修复了跨上下文冻结及跨线程工厂调用的拒绝，最终17个宿主方法5.596秒通过。中途主动中断旧代码快照全量测试，退出1，不计作通过。最终全量结果单独记录，不能用这次中断或旧专项代替。

## 契约对应与边界

| 契约/风险 | 证据 |
|---|---|
| SKETCH-01 初态/移动/样式 | initial/movement/pen-up-jump 等 CLI；defaults、input_copy 宿主方法检查实际路径、背景、抬笔与点 |
| 正负半径/extent、闭合 | 四个 arc 固定答案、重复整圈；圆心/半径/弓高独立校验 |
| 贝塞尔与批量复制 | bezier CLI；独立1001点采样与线段投影；输入数组后改、末点错误不留前半路径 |
| 受控类型/顺序/隔离 | 类型注解、构造/方法/属性拒绝、Color值相等、JSON拒绝、参数先求值后检查；冻结别名、跨画布/上下文/线程、Program重用及过期句柄 |
| SKETCH-02 的 E1 填充子集 | fill-* CLI；完整颜色快照/笔状态恢复、evenodd、闭合不描边、不移动、其他笔/文档操作拒绝 |
| E211与取消 | 每个路径/填充准备分配点逐次注入；失败状态和预算不变；曲线内部取消后清草稿；真实默认最大笔/曲线段/文档段/对象及超一项 |
| check与后续接口 | 独立进程禁止GUI导入并核对文件未改；check不导入几何模块；headless不导入Tk；show/svg_text/undo仍明确E302 |

SKETCH-02 的文字/公开图层操作在 E2，对象擦除在 E4；SVG解析在 E1-02，历史与回放在 E3。不会把跨阶段覆盖表的整行提前标为通过。图层锁和错误画布归属目前是宿主注入检查，未宣称存在可调用的 set_layer/lock_layer 接口。

每画布百万路径段及十万对象的边界采用真实分配；小阈值故障测试另外用于精确检查原子提交。对应限额 e1-01-v1 与上下文核心预算同时生效。有效载荷统计是逻辑计量，非RSS；其他OS/Python、默认最大值的全部组合、输出、窗口线程/关闭、历史/回放未验证。当前宿主 Windows11 / CPython3.12.14。

## 复现

在项目根目录执行：

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_e1_cli tests.test_e1_runtime -q
& ./.venv/Scripts/python.exe -X utf8 -m tests.blackbox tests/e1/cases.json --report dist/e1-cli.json
& ./.venv/Scripts/python.exe -X utf8 -m tests --report dist/e1-all-tests.json
```

报告父目录须存在；既有运行器拒绝空清单、未执行、超时、跳过及失败。正式阶段验收只依据最终完整执行结果，未完成任务保持未勾选。

最终全量 **1918/1918，729.36秒**，收集/执行一致，失败/错误/跳过/expected failure均0；[汇总](results/all-tests.json)、[环境/配额/源码验收](results/acceptance.json)、[隔离安装](results/installed.json)。E1-01已达到完成标准；E1完整阶段仍待E1-02 SVG。

本地.venv已同步同一wheel，-I示例check/run另2/2通过，29文件文本一致；记录在installed.json的local_venv_sync，未把这两次复测累加到1918项全量。
