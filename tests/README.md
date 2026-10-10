# 基础设施、词法与最小执行测试

从项目根目录运行 `python -X utf8 -m unittest discover -s tests -v`。只使用标准库 unittest，实际启动 CLI 子进程并检查 stdout、stderr、退出码；宿主层验证资源预留/释放、源码坐标、词法容量和异常边界。

P01-01 已有 [词法 CLI 用例与外部清单](lex/README.md)，P01-02 增加 [run 执行黑盒](run/README.md)，均不依赖 spec。check 待 P01-03，完整语言覆盖待 P06。取消出口及执行清理通过注入 KeyboardInterrupt/Cancelled 验证，另在扫描和算术安全点检查取消；尚未做真实终端按键验收。
