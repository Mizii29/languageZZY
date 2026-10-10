# 示例目录

P00 的 [source-sample.zzy](source-sample.zzy) 只用于真实 UTF-8 读取与摘要验证：

```text
python -m zzy source-info examples/source-sample.zzy
```

该命令不切词、不检查语法、不执行程序。P01-02 已加入 [hello.zzy](hello.zzy)：执行 `python -m zzy run examples/hello.zzy` 输出 `5` 并退出 0。

P01-01 的 [lexer.zzy](lexer.zzy) 可执行 `python -m zzy lex examples/lexer.zzy` 查看 Token、解码字符串和原文位置。只验证词法，不会打印程序中的值；现在可用 run 执行已支持子集；check 已接入，执行 `python -m zzy check examples/hello.zzy` 无输出、退出 0。

P02 的 [grades.zzy](grades.zzy) 是可运行的成绩菜单：`python -m zzy run examples/grades.zzy`，输入姓名和 `1` 得到总分 344、平均分 86.0、最高分 100、及格科目 4。菜单退出和姓名 EOF 也进入外部黑盒清单；`check` 不读取交互输入。它只使用已实现基础库，没有提前依赖 P05 的 sum/stats 或 safe_int。
