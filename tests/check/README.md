# P01 非执行检查黑盒

运行 `python -X utf8 -m unittest tests.test_check_cli -v`，或使用统一入口 `python -X utf8 -m tests.blackbox`。

[cases.json](cases.json) 的 105 项均经真实 `python -m zzy check` 子进程检查。93 项复用 run 的独立 `.zzy` 文件并保存单独的 check 期望：词法、语法、名称及前端资源错误仍退出 2；执行时的类型、调用、只读写入和运行预算错误不由 check 提前触发。check 成功时 stdout/stderr 均为空，退出 0。

其余 12 项覆盖极小执行预算、不能调用/注解错误也不执行、运行错误之后的未知名字、源码/Token 配额、diagnostics 的名称/注释例、BOM/CRLF/Tab/Unicode、中文空格路径、不同 cwd 和缺文件。两份 CRLF 文件通过 .gitattributes 保留原始字节。清单的期望按前端/执行边界维护，不由被测解释器产生。

P02 已扩展数组、结构和控制流，原六类不支持语法的期望按新能力迁移，文件名保留历史。模块、用户函数及 spec 仍明确拒绝。新增 P02 清单验证 check 不运行输入、循环、结构默认值或数组修改；成功不承诺程序运行时无错。
