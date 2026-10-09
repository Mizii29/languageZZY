# 示例目录

P00 的 [source-sample.zzy](source-sample.zzy) 只用于真实 UTF-8 读取与摘要验证：

```text
python -m zzy source-info examples/source-sample.zzy
```

该命令不切词、不检查语法、不执行程序。P01 接通解释链后加入可运行的 hello 示例。

P01-01 的 [lexer.zzy](lexer.zzy) 可执行 `python -m zzy lex examples/lexer.zzy` 查看 Token、解码字符串和原文位置。只验证词法，不会打印程序中的值；run/check 尚未实现。
