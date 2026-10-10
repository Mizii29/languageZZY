# P01 最小执行黑盒

从项目根目录执行：

```text
python -X utf8 -m unittest tests.test_run_cli -v
python -X utf8 -m unittest discover -s tests -v
python -m zzy run examples/hello.zzy
```

`cases.json` 的 93 项均指向独立 `.zzy` 文件，经真实 `python -m zzy run` 子进程执行；不依赖 spec。清单显式记录 cwd、10 秒超时、完整 stdout、退出码，以及错误的 code/file/span。span 为原文 Unicode 码点的半开区间，null 用于输出预算等无源码位置诊断。期望依据契约维护，不从执行器导出答案；消息只在资源场景检查限制键。

覆盖声明/重新绑定/别名、Int 加法与 String 拼接、注释和一次解码、分组/左结合、注解、函数引用和调用顺序、只读目标先检查、首个错误/既有输出保留、词法/语法/名称先于执行。未实现的 Float、Bool、负号、数组、块、spec 等独立用例明确失败，不按完整语言运行。

资源用例包括 AST 总数、源码/AST 深度、整数位数、默认 4096 位十进制转换、文本/UTF-8 输出、在用标量载荷/别名/替换释放和绑定槽。额外宿主测试覆盖 AST 范围、Program 复用、精确加法位数、执行失败/取消时的计量清理；保留异常 traceback 时也须释放上下文预算。默认深度 64 的允许边界在实际 Python 3.12.14 上执行通过。

捕获器复用 `test_lexer_cli.run_bounded`，每流最多 1 MiB，超额或超时即失败；对成功输出不做 strip，也不忽略额外行。当前语言子集不能启动子进程，因此只终止当前 CLI；P06 的进程树回收尚未完成。P01-04 将整合 lex/run/check 清单与运行器验证，不能把本目录当成已实现的 `zzy test` 或完整语言测试集。

深度计量包含 Program、语句和显式分组节点：叶为 0，每条父子边加 1；源码括号嵌套另行检查。原生 io 命名空间/print 函数在运行上下文中占两个对象、两个引用槽，声明各占一个槽，调用实参缓冲各占一个槽。标量别名共享载荷，打印的临时文本与整数计算临时存储仍占预算，紧限额用例据此记录。
