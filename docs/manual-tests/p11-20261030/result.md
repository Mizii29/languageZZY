# P11 人工测试结果

执行及复核：2026-10-31｜候选：`test / 4b4be85eaf2addd01aafb49de43a4e6a8db581d2`｜结论：**M01、M02 通过**。

操作人原始报告为 [result.doc](result.doc)，共 8 张截图，原件保持不变。本页是对原件、终端记录及产物的核验摘要，不是重新执行测试。方案见 [README](README.md)，此前自动证据复核及本轮说明见 [review](review.md)。

本轮证据目录：[runs/20261031-143117-4b4be85-3aae09](runs/20261031-143117-4b4be85-3aae09)。环境为 Windows 11、PowerShell 5.1、CPython 3.12.14。

| 项目 | 实际结果 | 依据 |
|---|---|---|
| 准备与源码身份 | `SOURCE_OK 44`，导入路径断言及运行时哈希断言通过；check 退出 0，执行前两个输出文件均不存在 | DOC 图 1—2、[source-check.txt](runs/20261031-143117-4b4be85-3aae09/source-check.txt)、[candidate.txt](runs/20261031-143117-4b4be85-3aae09/candidate.txt)；复核时冻结的 54 个运行时/测试/驱动文件也全部一致 |
| M01 真实取消 | 出现 READY，亲手 Ctrl+C 后提示操作已取消，退出码 **130**，未见 Python traceback | DOC 图 3、[terminal.txt](runs/20261031-143117-4b4be85-3aae09/terminal.txt) |
| M01 后续恢复 | 后续程序输出 **2**，退出码 **0** | DOC 图 3及终端记录 |
| M02 绘图与关闭保存 | 可见自由线和矩形；关闭后有三个 `(^_^)(null)`、退出 **0**；两个文件检查均 True | DOC 图 4—5及终端记录 |
| M02 SVG | 浏览器正常显示线和矩形；最终 SVG 与项目中的两个对象坐标逐点一致 | DOC 图 6、[manual.svg](runs/20261031-143117-4b4be85-3aae09/manual.svg) |
| M02 新进程重开 | 新进程加载后显示两个图形，正常关闭，重开退出 **0** | DOC 图 7、终端中的 `reopen.zzy` 调用及退出码 |
| M02 撤销/重做 | 按操作人“实际测试无问题”的说明确认；项目确实保存 `free`、`rectangle` 两条历史 | [manual.zzysketch](runs/20261031-143117-4b4be85-3aae09/manual.zzysketch)及 DOC 备注；没有独立保存按钮操作前后的截图，不把最终画面当作完整过程证据 |
| 结束 | 已恢复 PYTHONPATH 并停止转录 | DOC 图 8及终端记录 |

记录说明：

- 终端保留两次取消、三次首窗调用和一次重开。操作人已注明中途重新开窗画图，因此图 4 与后续图形形状不同；按最后一次保存的 SVG、项目和重开画面核对，不将旧画面强行视为同一份产物。此前被覆盖的绘图文件无法逐版复核。
- `source-check.txt` 的中文路径显示乱码，属于 UTF-8 输出经 Windows PowerShell 5.1 管道转码后的显示问题；同段代码的路径断言及 44 文件哈希断言已通过，不能据此认定加载了旧安装包。
- Ctrl+C 附近的 `TerminatingError(): 管道已被停止` 是 PowerShell 转录中的管道中断记录；结合 CLI 取消提示、退出 130 及恢复 2/0，未见解释器异常证据。原生程序输出有一部分未被转录捕获，已用截图补核。
- 最终项目使用 GUI 的 `studio` 画笔，仍保留脚本创建的“主画笔”；不影响本轮绘图、持久化与历史验收。

本轮无须补测即可关闭 P11 的这两个人工待补项。它不替代 [P10 合约网页六项人工核对](../../../examples/contracts/manual-acceptance.md)及 P12 最终验收；未扩大为其他平台或云端 CI 已通过。

原始 DOC SHA256：`9222e5d86624d21cca2535628405a98ffdd614ed545e5a6b5fe11aee8c0cf366`。
