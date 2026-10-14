# P06 Agent 练习：分钟记录汇总

从项目根目录启动 main.zzy，stdin 输入 JSON 文件路径。文件根值必须是 Array，每项必须是非 Bool、非负 Int 分钟数。先检查 data.kind，再访问/计算；输入 EOF 输出“取消”，不改 report.json。成功输出“共 N 项，M 分钟”并原子保存紧凑 JSON {"count":N,"minutes":M} 到当前工作目录 report.json。业务校验失败输出“数据必须为分钟数组”或“分钟必须为非负整数”，保留已有 report.json。读取、JSON 格式、保存失败通过 Result 报告。

允许资料：skills/zzy/SKILL.md、skills/guide.md、skills/syntax.md 及其引用的 syntax/stdlib 契约。不得依赖未发布接口或修改解释器来迁就程序。程序拆成库与入口，补 spec；外部测试独立准备正常 [30,15,0]、空 []、Bool、负数、对象、坏 JSON、EOF、保存目录故障。此练习不替代 P09 的 200 行完整应用。
