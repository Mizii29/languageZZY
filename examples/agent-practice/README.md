# 按指南完成的 Agent 练习

任务见 [task.md](task.md)，库为 [summary.zzy](summary.zzy)，入口为 [main.zzy](main.zzy)，正常与边界 spec 在 [spec.zzy](spec.zzy)。从希望保存 report.json 的工作目录启动绝对路径 main.zzy，stdin 输入相对该目录的 JSON 文件路径。模块依赖相对 main.zzy；这两个路径基准不同。

```text
python -m zzy check examples/agent-practice/main.zzy
python -m zzy test examples/agent-practice/spec.zzy
python -X utf8 -m unittest tests.test_p06_agent -v
```

上面命令从项目根目录运行；交互运行使用 `python -m zzy run examples/agent-practice/main.zzy`。本机 python 替换为 `.venv/Scripts/python.exe`。

2026-10-14 实际记录：本轮 Agent 先阅读 SKILL、guide 和 syntax，再写明 task.md 的输入/输出/错误约束，按已读 stdlib 签名实现两个模块和 spec。程序仅使用指南已发布能力，未修改解释器来适配练习。首次运行 `-m unittest tests.test_p06_agent -v`：3/3 通过，4.281 秒；其中实际执行 7 组固定输入、坏 JSON/NaN/缺文件、EOF、check、保存目标为目录等独立子场景，以及 2 个 spec。正常 [30,15,0] 输出“共 3 项，45 分钟”，文件严格为 {"count":3,"minutes":45}；[] 得到 0/0；所有恢复失败保留已有目标。

使用中重点核对了三点：Array 注解不保证元素类型，因此先 data.kind；Bool 不能当 Int，不能直接对未检查的数据调用 sum；`?` 只能用于显式 Result 具名函数，所以入口用匹配分支。指南足以提供这些规则，练习没有遇到需新增语法或接口的阻塞。另在审查总 README 时发现旧“库仅有基础函数/Map 待实现”的能力描述与 P05 实现冲突，本轮同步更正。

这是真实当前 Agent 的开发练习，不是新 Agent 的盲测，也不是 P09 课程完整应用。没有测第三方学习效果，不能据此声称所有读者都能独立完成应用。详细自动期望见 [test_p06_agent.py](../../tests/test_p06_agent.py)，最终回归见开发日志。
