# 2026-10-27 人工测试归档

本轮针对核心语言、校园任务管家、Sketch 与离线安装。候选为 `b598043` 加当时工作区修改，不能当作 P08 新版本已人工通过。

- [原详细指南](manual-test-guide.md)：保留 M01—M18 编号、已核验结论及明确跳过范围，仅补归档说明并调整相对链接。
- [原始结果 DOC](manual-test-result.doc)：原二进制文件直接迁移，41 张截图及操作者备注均未改写。SHA-256：`3a8b6e107be09243812146a3cffcf4c2d321f4f5e2c824be3fa5dfdb1721f4ee`。
- [终端记录](evidence/terminal.txt)、[M17 安装及真实 GUI 报告](evidence/installed.json)：从原运行目录逐字节复制。
- `evidence/work/`：复制原中文/空格工作目录的全部顶层文件，包括 `tasks.json`、`manual.svg`、`manual.zzysketch`、脚本和故意构造的坏数据；这些不是生产数据。原件及目录结构仍保留在 `dist/manual-verification/20261027-133652-b598043/`。

安装报告中的绝对路径、wheel 哈希和运行环境均是当时记录，没有改成归档路径；其完整副本/环境仍在原 `dist/`，这里不复制虚拟环境或安装依赖。本次未重新运行人工/GUI/离线安装，历史 2002 项回归与 39 个源码计数保持原样；P08 当前自动统计另见[统一索引](../README.md)。
