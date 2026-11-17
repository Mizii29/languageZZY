# P12 自动验证映射

2026-11-17。`tests.test_p12_app` 使用独立临时目录、实际 `python -m zzy run` 子进程、固定任务 JSON 和 stdout/磁盘答案；由 `python -m tests` 自动收集，不接受 0 用例成功。

| 场景 | 固定答案与用例 |
|---|---|
| 筛选后按原任务顺序预览、只改变匹配项、保存和新进程恢复 | `test_batch_preview_confirm_undo_redo_and_restart`：ID 10/8 预览，只有 10 改变；存档顺序 10/3/8，next_id=11，重开未保存=false |
| 确认前取消、输入结束 | `test_cancel_and_eof_at_confirmation_preserve_saved_document`：无脏状态和磁盘变动 |
| 无匹配、目标状态已满足 | `test_no_match_and_no_change_skip_confirmation`：不请求确认，不写文件 |
| 批量一次历史、整批撤销/重做、ID 高水位 | `test_batch_uses_one_history_entry_and_preserves_highwater`：独立 ZZY 程序打印固定数组/状态，undo 长度 0→1→0→1 |
| 旧菜单与原应用业务 | `tests.test_p09_app` 22 项保留，仅菜单输出追加选项 14 |

应用源码使用 `python -m tests.p09.count_lines` 的 Lexer 规则重新计算：547 总行、534 有效行、439 实质代码行，七个文件的 SHA 见 `apps/zzy-campus/line-count.json`。P12-03 的全量回归和性能预检另记，不把此专项当最终阶段验收。

2026-11-17 实跑：`./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_p09_app tests.test_p12_app -q` 为 **26/26，65.076 秒，退出 0**；完整一键回归 `./.venv/Scripts/python.exe -X utf8 -m tests --report dist/p12-20261117-core.json` 为 **2076/2076，978.131 秒，零失败/错误/跳过/预期失败，退出 0**。新增四项相对原 2072 项递增，旧测试未删。

P12 分段补测：`tests.test_p12_benchmarks` 3 项验证 X00—X03 小样例在真实 CLI 与分段 worker 中都满足固定公式；X03 批内三次重建数组；错答案必须失败；返回成功但父进程墙钟超预算必须拒绝。`python -X utf8 -m unittest tests.test_p12_benchmarks -v` 实跑 3/3、7.574 秒。完整一键回归 **未在新增这三项之后重跑**，上述 2076/2076 仅对应补测前的源码；不把历史报告冒充当前清单。
