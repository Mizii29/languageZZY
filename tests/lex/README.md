# P01-01 词法 CLI 黑盒

执行 `python -X utf8 -m unittest tests.test_lexer_cli -v`；运行全部回归使用 `python -X utf8 -m unittest discover -s tests -v`。

[cases.json](cases.json) 是独立维护的外部期望清单，每例指定 `.zzy` 路径、工作目录、超时、退出码，可覆盖资源配置。成功 tokens 的每项按 `[kind, lexeme, value, raw, [起行, 起列, 终行, 终列]]` 保存，包含 EOF；失败保存错误码、位置及可选消息片段，不依赖完整消息措辞。输出资源错误不对应源码，file/span 可为 null。

用例通过真实 `python -m zzy lex` 子进程执行，不导入 Lexer 来生成期望。stdout/stderr 分别检查，双管道有界捕获；超额、超时、启动失败、空清单或坏清单均失败。lex 不执行用户程序、不创建派生进程；该辅助器仅负责词法用例，P01-04/P06 的 run/check/spec 收集、执行隔离和派生进程树清理仍未完成。

覆盖固定关键字/类型/颜文字、最长符号、Unicode 标识符不归一化、数字原文、普通/raw 字符串、全部转义、两种注释/结束词边界、BOM/CRLF/Tab/EOF、非法字符和首错、数字/Token/解码字符串限额。`fixed-symbols`、`operators`、`numbers-retain-text` 等是词法探针，故意不满足完整语法，不能作为已验证可执行的程序。非法源码各自独立，不与正常输入合并。

普通括号中的旧名字不变成关键字，裸保留名作为 RESERVED_NAME 留给 Parser 拒绝。`(zzysay:)` 的左括号单独成 Token，其后的裸注释起始仍进入注释；它不是新关键字，完整形式会由后续 Parser 检查。三份 CRLF 文件由 .gitattributes 保留原始字节。

宿主 `test_lexer.py` 补默认 250,000 Token 边界、每文件独立计数、宿主十进制限额、扫描期间取消，以及长名字/大量结束词候选的边界检查次数。它不代替上述 CLI 黑盒，也不证明 Parser 深度或运行时值的资源限制已完成。
