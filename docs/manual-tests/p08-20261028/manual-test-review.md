# P08 人工测试核验记录

核验日期：2026-10-29。操作者已完成本轮测试，核验基于[原始 DOCX 报告](manual-test-result.docx)的全部 11 张截图、[终端记录](runs/20261029-002147-330cf17/terminal.txt)及实际 SQLite 数据库；未代替操作者重新运行服务器或人工测试。

结论：本轮人工主流程符合预期，未发现阻塞性功能问题。W03 共享模式按操作者备注确认通过，独立截图只证明带 `--shared` 启动；不扩写为逐项截图或并发隔离证明。无需为本轮主流程额外补测。

## 候选与执行材料

- 完整提交号：`330cf1754fa991bd72b4f56bc89fdaa57ce8d2ff`，见[candidate.txt](runs/20261029-002147-330cf17/candidate.txt)。[工作区记录](runs/20261029-002147-330cf17/working-tree.txt)保留当时文档改动，不能表述为干净工作区。
- 运行目录：`runs/20261029-002147-330cf17/`。Windows 终端为 VS Code 内的 PowerShell 5.1.26100.9711；端口 18765 / 18766。
- 本轮复制的 Web / SQLite 共四份 `.zzy`、`.html` 与当前项目逐字节相同；`tests/p08/source-05.json` 的七个冻结文件哈希仍匹配。完整 Python / 浏览器版本没有在本次 DOCX 和 transcript 中独立留存，不补填为已核验版本。

## W01—W07 对照

“图 N”按原 DOCX 的图片顺序编号，不是页面编号。

| 项目 | 实际证据 | 核验结论 |
|---|---|---|
| W01 默认 GET / 中文 POST | 图1显示默认模式启动、页面 GET 与 `/api/hello` 返回 200；图2为 `你好，小明` | 已展示主流程符合预期；GET 正文的 `language` 字段未单独截图，字段断言仍由自动 HTTP 用例覆盖 |
| W02 拒绝及恢复 | 图3空姓名返回 HTTP 422、`name长度应为1至80`；图4下一次 Ada 请求成功 | 通过，错误后服务可继续使用 |
| W03 shared 冒烟 | 图5含 `--shared`，新 PID 37252 启动；随后原文备注“一切正常，与上述无异，不再重复记录” | 操作者确认通过；重复 GET / POST / 422 未分别留图，不用本项证明并发隔离 |
| W04 Python 嵌入 | 图6输出 `{"status": 200, "body": {"message": "你好，Ada"}}`，退出码 0 | 通过 |
| W05 SQLite 添加 / 刷新 | 图7显示两条记录：`1 / 人工任务一`、`2 / O'Reilly`；最终数据库与之相同 | 通过，中文及单引号标题完整保留；初始空库画面未单独留图 |
| W06 空标题拒绝 | 图8为 `请求失败 422` 和标题长度原因；图10及最终数据库仍仅有上述两条 | 通过，没有新增空标题记录 |
| W07 停服 / 新进程恢复 | 图9为失联提示；图10旧 PID 45652 完成 shutdown，新 PID 24148 启动并 GET 200，页面两条数据不变；图11新进程正常结束，`Test-Path=True` | 通过，实际换进程恢复，不只是刷新页面 |

## 实物与日志校验

只读打开 [tasks.sqlite3](runs/20261029-002147-330cf17/examples/sqlite/tasks.sqlite3)，查询得到 `[[1,"人工任务一"],[2,"O'Reilly"]]`；`PRAGMA integrity_check` 为 `ok`。读取前后文件 SHA-256 相同，未改动数据库。DOCX 与终端记录同样保持原件。

| 文件 | SHA-256 |
|---|---|
| 原始 DOCX | `de847465191ec00602c115bc5a0bc344db65b0518ec8daf85daf62fbe22fd9ff` |
| 终端记录 | `1d11602838b515f1f9b7a20e3c41476330708f87f155fabfc155a8c92457a2a4` |
| SQLite 数据库 | `12ec1577227c4d28b8d63d95f7fa2d8fcc374e3dcc4136070d5c0da26f7bfec8` |

图1的 `/favicon.ico 404` 是浏览器请求站点图标，示例没有该资源，不影响业务接口。transcript 中 Ctrl+C 附近出现 PowerShell 的“管道已被停止”，但截图显示 Uvicorn 完成 application shutdown / finished server process，未看到应用崩溃堆栈；不能仅按 transcript 该文字判定程序故障。

PowerShell transcript 没有完整捕获原生 Python / Uvicorn 输出，本轮以 DOCX 截图补足，不能宣称 `terminal.txt` 独立包含全部请求日志。原 DOCX 没有 W01—W07 表格，本页只归纳已出现的截图、操作者备注与实物证据，不改写原始测试材料。

本轮未重新执行全量自动测试、Tk GUI、性能或云端 CI；已有自动报告与人工结果分开保存。额外 DPI、物理断网、手工并发压测和模拟断电沿用方案的可跳过范围，P11 交付任务仍独立验收。
