# CTest 收集证据格式补记

2026-11-18 恢复 Git 写入后，暂存检查发现 CTest 原生 JSON 输出的140行行末空格。两份 collection JSON 仅清理行末空白，解析后的 JSON 完全相同；原始逐字节输出保存为对应的 collection-*.raw.json.gz，不改测试数量、命令、结果或历史失败记录。此格式修复用于满足 git diff --cached --check，不代替重新测试。
