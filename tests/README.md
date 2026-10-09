# 基础设施与词法测试

从项目根目录运行 `python -X utf8 -m unittest discover -s tests -v`。只使用标准库 unittest，实际启动 CLI 子进程并检查 stdout、stderr、退出码；宿主层验证资源预留/释放、源码坐标、词法容量和异常边界。

P01-01 已增加 [词法 CLI 用例与外部清单](lex/README.md)，不依赖 spec；P01-02/03 后再通过 run/check 验证 AST 与执行。这些不是作业要求的完整语言黑盒测试集，P06 才完成覆盖。取消出口通过注入 KeyboardInterrupt/Cancelled 验证，另在实际扫描中检查取消；尚未做真实终端按键与未来执行循环的取消验收。
