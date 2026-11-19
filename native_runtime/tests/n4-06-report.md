# N4-06 原生 Sketch 窗口验收（2026-11-19）

新增 `zzy-native-gui.exe run FILE --gui`。UI 线程拥有 HWND、GDI 和 STA 文件对话框，解释器线程执行回调、历史及保存。通过真实 Windows 桌面上的 HWND 消息驱动固定测试。`PrintWindow(PW_CLIENTONLY)` 走实际绘制路径并核对黑色图形与白色背景。套件包含四个进程场景。

1. 点击、拖动、释放、键盘、一次定时触发及取消、回放定位与单步、撤销重做、对话框取消、通过实际对话框导出和保存重开、关闭后脚本继续、再次打开窗口而旧回调不再生效。
2. 关闭窗口中断正在执行的循环回调，回到调用者继续执行。
3. 在繁忙回调期间填满输入队列，得到 E211 并释放窗口。
4. 回调内嵌套 show 得到 E214 并释放窗口。

Windows 11 x64 build 26200，CMake/CTest 4.5.0，MSVC 14.40.33807，SDK 10.0.22000。Debug 和 Release 源码外中文目录安装副本各通过 4/4。测试客户端以空 `PATH` 和无效 `PYTHONPATH` 启动待测进程并记录实际模块。GUI PE 导入 `USER32.dll`、`GDI32.dll`、`ole32.dll` 和既有 Windows/VC CRT，核心 PE 无这些 GUI 导入。`Install` 后两程序 check 都通过。窗口进程模块含系统 Win32/COM 和 CRT，未观察到 Python 或 Tk。Debug/Release GUI SHA-256 分别为 `7ecaf6e12c4786c4ac15b1c5311aea66b7f30a2aff0397cad878955958d5fd21`、`fea9bda8690f5e493761ec6f56de02686d47d25c98d7d2a2269a86dad6388866`。

原始记录位于 `dist/native-n4-05-complete/gui-debug-reopen.json`、`gui-installed-reopen.json`。旧式对话框取消后改变了 CWD，改为带 `FOS_NOCHANGEDIR` 的 COM 文件对话框并复测。屏幕遮挡导致旧像素探针超时，改为读取窗口绘制路径。还修复了 `WM_NCCREATE` 未交给默认处理器时首次标题为空，以及探针过早读取文件名控件。

真实窗口自动化覆盖上述场景。逐项人工操作所有工具、字体、DPI/多显示器，以及按终端 Ctrl+C 仍待验证。系统提供的阻塞 I/O 只有返回到执行器后才能协作取消。界面文本使用本机字体度量。
