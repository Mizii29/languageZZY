# P00 宿主基础设施测试

从项目根目录运行 `python -m unittest discover -s tests -v`。只使用标准库 unittest，实际启动 CLI 子进程并检查 stdout、stderr、退出码；宿主层验证资源预留/释放、源码坐标和异常边界。

这些不是作业要求的完整 ZZY 黑盒测试集。P01 开始增加 `.zzy` 正常/非法源码与外部期望清单，P06 完成语言覆盖。取消出口通过注入 KeyboardInterrupt/Cancelled 验证，尚未做真实终端按键与未来执行循环的取消验收。
