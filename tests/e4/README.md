# Sketch E 最终验收

E1→E2→E3→E4 顺序实现；核心版本 0.6.0a1、语法 v0.6、核心标准库 v0.6.1 不变。最终全量1982/1982、898.39秒通过，真实GUI 11/11、离线新环境验收通过；失败修复过程见 [开发记录](../../docs/development/development-log.md)。真实 GUI 与默认 headless 回归是两个独立门禁。

## 复现命令

在仓库根目录使用 CPython 3.12.14：

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m tests --report tests/e4/results/all-tests.json
& ./.venv/Scripts/python.exe -X utf8 -m tests.blackbox tests/e4/cases.json --report tests/e4/results/cli.json
& ./.venv/Scripts/python.exe -X utf8 -m tests.gui_sketch --report tests/e4/results/gui.json
& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.run --repeats 3
& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.render --all --repeats 3
```

GUI 命令需要真实桌面及可用 Tk；缺环境会失败，不跳过。默认一键入口不运行 GUI 文件，也不初始化 Tk。统一测试入口要求 collected > 0、collected = tests_run、无失败/错误/跳过/expected failure；外部清单逐项检查退出码、双流及诊断，不通过空收集或超时。

## 覆盖映射

| 契约 | 真实用例与检查 |
|---|---|
| SKETCH-01 几何/归属 | e1/cases.json；test_e1_runtime：坐标、正负圆弧、曲线误差、输入复制、冻结别名、跨线程/上下文、配额与取消 |
| SKETCH-02 图层/填充/文字/对象 | test_sketch_svg、test_sketch_layers、test_sketch_objects_events；e2/e4 CLI；真实 GUI 像素检查 evenodd、裁剪；移动复制删除与锁层 |
| SKETCH-03 历史/确定回放 | test_sketch_history；e3 CLI；gui_sketch 的 seek/step/编辑退出，原笔状态不变，共享路径与有界缓存 |
| SKETCH-04 数据/失败原子性 | test_sketch_patterns、test_sketch_project、test_sketch_svg：坏 schema、引用与历史不一致、原子替换失败、取消、旧文档/文件与预算保留、实际 CLI 重启 |
| SKETCH-05 函数导出/Lazy | test_sketch_patterns：真实前端校验、导入调用、首次/再次解码计数、执行隔离、名字注入和转义；性能单列首次与缓存 |
| SKETCH-06 GUI/事件/取消 | gui_sketch：真实鼠标/键/定时器、固定 arity、回调错误与嵌套 show、队列溢出、长回调关闭、Tk 主线程与工作线程分离、两次 show、清理；e4 CLI 非法注册/时间/状态 |

GUI 测试在 Windows 11、Tk 8.6.12 运行，使用实际 Tk 控件、event_generate 和 Windows GDI 像素读取。缺显示故障注入仅验证失败转换；它不代替真实窗口成功用例。进程结束、后台 Tcl 异常或预算泄漏均不算通过。

## 离线安装

使用本机已有 setuptools/pip，`--no-index --no-deps --no-build-isolation` 构建 wheel；在新 `--without-pip` venv 离线安装。将 [installed_probe.py](installed_probe.py) 与 [studio.zzy](../../examples/sketch/studio.zzy) 复制到中文/空格临时工作目录，用新环境 `python -I -X utf8 installed_probe.py` 运行。探针断言包来自该环境，实际运行 check/headless、真实 GUI、关窗后项目保存及另进程重启/undo/图案库复用。安装命令、输出、源码文本哈希与 wheel 哈希保存在 results/installed.json。

## 证据范围

results 下旧子阶段报告保留各自时间和源码语义；最终 all-tests/gui/installed 报告才是本轮完整门禁。性能基线原始样本、资源失败及版本清单见 [benchmarks/sketch](../../benchmarks/sketch/README.md)，不把超限算成快速成功。

没有验证其他 OS/Python、所有字体/DPI、真实操作系统 ACL、断电落盘、多写者事务、每种最大资源组合或所有阻塞宿主调用的关闭时序。PNG 没有独立后端并明确返回失败 Result；窗口截图仅用于验收，不作为 PNG 导出实现。P08/P10/P11 不在本次 E 开发范围。

离线构建/安装/探针的完整可复现驱动（installer须为本机已有pip/setuptools的Python，不联网）：

```powershell
& ./.venv/Scripts/python.exe -X utf8 tests/e4/install.py --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe
```

该驱动也把当前.venv同步到同一wheel，以免离开仓库cwd时调用旧包。新环境的39个Python源码按统一换行文本逐项核对，原始字节及文本SHA均保存；不将换行差异当成代码变化。当前安装验收真实显示8个对象、704×504画布，并由后续新进程得到8→undo→7→复用新ID9的固定答案。

最终门禁：collected=tests_run=1982，failures/errors/skipped/expected_failures全0；其中1738项独立外部CLI。GUI11项另算。66个登记接口/ABI1.0，PNG明确不可用。验收索引见[acceptance.json](results/acceptance.json)；冻结代码/夹具1019项，旧失败报告与修正后的完整重跑分开保留。
