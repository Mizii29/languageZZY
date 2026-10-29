# 人工测试资料

更新：2026-10-29。按验收轮次保存方案、人工结果与证据；自动报告继续保存在 `tests/`，不当作人工通过记录。

| 轮次 | 方案 / 指南 | 结果与证据 | 状态 |
|---|---|---|---|
| P06 后早期测试 | 原始材料 | [原截图](P06结束后的手动测试.png) | 保留原件，不另推断覆盖范围 |
| 2026-10-27 核心、校园应用、Sketch | [详细指南 M01—M18](core-sketch-20261027/manual-test-guide.md) | [原始 DOC 报告](core-sketch-20261027/manual-test-result.doc)、[证据说明](core-sketch-20261027/README.md) | 已有人工结果，具体通过/跳过范围见原记录；候选为 b598043 加当时工作区修改 |
| 2026-10-29 P08 互联 | [简要方案 W01—W07](p08-20261028/manual-test-plan.md) | [原始 DOCX 结果](p08-20261028/manual-test-result.docx)、[逐项核验记录](p08-20261028/manual-test-review.md)、该轮 `runs/` 内的日志和测试数据库 | 主流程核验通过；W03 按操作者确认，未另存重复截图；候选为 330cf17 加当时文档改动 |

```text
manual-tests/
  README.md
  P06结束后的手动测试.png
  core-sketch-20261027/
    README.md
    manual-test-guide.md
    manual-test-result.doc
    evidence/                 上次终端记录、安装报告、合成存档和导出文件
  p08-20261028/
    manual-test-plan.md
    manual-test-result.docx    操作者原始结果，11张截图
    manual-test-review.md     本次逐项核验结论与证据边界
    runs/                     已保存终端记录和测试数据库
```

P08-01—05 的实现及自动验收已完成：现存全量报告 2027/2027、SQLite 6/6、真实 HTTP 14/14、安装后 HTTP 14/14；见 [P08 自动证据](../../tests/p08/README.md)及[最新开发记录](../development/development-log.md)。2026-10-29 操作者完成本轮人工测试后，已逐张核验新增 DOCX 的 11 张截图、运行记录及数据库；本次核验没有代替操作者重跑测试。

本次已补网页正常/错误交互、共享模式冒烟、Python 嵌入和数据库重启持久化，具体证据强度见核验记录。上次 GUI 的逐按钮扩展、额外 DPI、物理断网可继续跳过；并发、事务回滚、资源限额等以自动专项核验。后续仍需独立推进 P11 交付核对，不能直接等同最终全部验收完成。
