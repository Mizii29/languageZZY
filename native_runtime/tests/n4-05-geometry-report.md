# N4-05 首批：原生几何、图层、历史与 SVG

2026-11-19，分支 `codex/native-runtime-plan`，接续 `d123ccac944df90e2f8425014222181d5cf01d90`。按 N4 允许的大任务分轮规则完成可独立验证的第一批，**N4-05 整项仍未完成**。

## 实现范围

新增 `sketch_hosts.hpp`、`sketch_model.hpp`、`sketch_library.hpp`、`sketch_geometry.hpp`。Canvas/Pen/Layer/Color 受控值、只读 Position/LayerInfo、坐标/朝向、直线/圆弧/Bezier/填充/文字、图层显示/锁定/排序、历史分组/undo/redo、SVG 内存生成与原子导出已接入原生 AST 解释器。48 个签名含 `show` 的 headless 失败 Result 和 `save_png` 的缺后端失败 Result；不能理解为 GUI 或 PNG 已实现。

接口沿用 [Sketch 契约](../../docs/features/sketch.md)，所有权/资源/取消见 [集中宿主契约](../../docs/development/native-stdlib-contract.md#n4-05-原生-sketch-headless几何图层历史svg)。未接入函数继续 E402/1，不回退 Python。默认 Python 入口、校园文件格式及 requirement 原文未改。

## 环境与验证

Windows x64，VS Build Tools 2022 / MSVC 14.40.33807，SDK 10.0.22000.0，CMake/CTest 4.5.0，PowerShell 7.6.9，Python 3.12.14 只用于开发测试。Debug `/MDd`，Release `/MD`，CRT 策略未变，无新增下载依赖。

| 实际命令/门禁 | 结果 |
|---|---|
| `cmake --preset native-debug -S native_runtime`、Debug build | 退出 0；SQLite 测试目标 `/bigobj` 修复后成功 |
| `cmake --preset native-release -S native_runtime`、Release build | 退出 0；之后对 `/bigobj` 变更重建 SQLite 测试并复跑六项 |
| `ctest --test-dir build/native-debug -C Debug -j 4 --output-on-failure --no-tests=error` | 78/78，67.93 秒 |
| 同命令 Release | 78/78，46.46 秒；包含真实 HTTP、SQLite、文件/JSON、核心、前端、资源、取消与生命周期 |
| 新增线程归属探针后，重建两配置 `native-library-tests`，`ctest -R "^library-"` | 各 11/11；Debug 12.83 秒，Release 8.69 秒 |
| `test-sketch.ps1`（含于 CTest） | 各 71/71；66 个既有独立 check/run 期望加五项新黑盒 |
| Python `-m unittest native_runtime.tests.test_inventory tests.test_sketch_svg tests.test_sketch_layers tests.test_sketch_history -q` | 17/17，1.429 秒，无跳过 |
| `python -X utf8 native_runtime/tools/test-core-existing.py --exe build/native-{debug,release}/{Debug,Release}/zzy-native.exe --output ...` | 两配置各 550/550，声明延期 0；独立固定核心清单无删减 |
| Release install、仓库外中文/空格目录发布副本 | 安装退出 0；发布副本 Sketch 71/71，空 PATH/无效 PYTHONPATH |
| `acceptance.ps1` 两配置、Release 指定仓库外安装副本 | 各 82 条过程通过；各含一条预期父进程强杀，不能用于证明 RAII |
| `dumpbin /dependents`、实际模块、CIM 子进程 | 审核白名单通过；绘图后等待输入的真实进程也无 Python/Tcl/Tk，正常结束 |
| `python -X utf8 -m scripts.ci static --output dist/native-n4-05-geometry/ci-static` | 退出 0，`passed=true`；完整清单核对不冒充执行全部 Python 测试 |
| `examples/sketch-geometry.zzy` 独立演示 | check 不写文件；运行输出 `(^_^)(null)`，XML 验证三个图形对象 |

资源测试独立检查 E211 前后画笔位置、对象、历史、ID 和计费不变；取消 undo 不改文档；Canvas 冻结经 Pen 别名仍拒绝；撤销不倒退 ID，clear_history 归还几何/差量配额；关闭后同进程新上下文可成功，再次关闭幂等。新增真实 C++ 线程读取拒绝 E203，原线程继续执行。

SVG 用系统 XML 解析器比对独立固定路径、原点/y 轴翻转、裁剪、对象顺序、填充/描边、样式和中文转义；资源失败保留旧 SVG 并清理临时文件；check 没有创建输出。测试驱动拒绝空选择与遗漏计数，没有用原生生成结果反过来制造期望。

## 复现

从仓库根目录，使用当前会话的 CMake PATH 运行标准 Debug/Release preset、build 和 CTest。专项：

```powershell
pwsh -NoProfile -File native_runtime/tools/test-sketch.ps1 -Executable build/native-release/Release/zzy-native.exe -Output dist/native-sketch-new.json
cmake --install build/native-release --config Release --prefix dist/native-stage-new
.\.venv\Scripts\python.exe -X utf8 -m unittest native_runtime.tests.test_inventory tests.test_sketch_svg tests.test_sketch_layers tests.test_sketch_history -q
```

演示源码 `native_runtime/examples/sketch-geometry.zzy`，在新建目录中执行绝对路径 EXE 与源码，生成 `native-sketch.svg`。仅导出 SVG，不启动窗口。

Debug CLI SHA-256：`a57fb0d75361154c838aac9d123de72f7c79a81cdf7f4c542232cbc3de3871a6`。Release/安装/发布副本：`eb43fafb0ffd0321f7ecac298a5efd93723d0f560f278116fb938da7775ebf70`。旧产物版本字符串暂保留 N4-03，不以版本字符串声明整个 N4-05 完成；逐接口能力矩阵已更新。

本轮原始证据在 `dist/native-n4-05-geometry/`，归档索引见 `benchmarks/results/native/n4-05-geometry-20261119/`。首次 MSVC C4702、快照类型/Color 比较问题修复后重建；Debug SQLite C1128 通过仅对测试目标增加 `/bigobj` 修复，两配置相关回归通过。首次黑盒报告保留于 debug-first.json；调试中修正夹具裸 true 和资源错误期望行号，最终采用契约语法 `(true)` 及真实第 18 行，没有放宽错误码或配额断言。

## 剩余与限制

- 项目 v1 双向读写、对象编辑、Drawing/图案/函数导出、确定回放、事件/定时器尚未实现，继续 N4-05 后续批次。
- 图层撤销后其失活元数据和句柄边仍由请求持有；字体/名称采用保守累计计量。高频修改可能更早触及配额，不声称逻辑配额等于 RSS。
- 尚未穷举所有 Sketch 固定配额的 L-1/L/L+1；本批有对象、导出和失败原子性证据，完整边界交给 N4-05 累计验收。
- GUI、真实人工 Ctrl+C、Sanitizer、其他 OS、缺 VC Runtime 的干净主机、全量 Python/GUI 回归、性能与长时间压力未验证。
- N4-06 GUI 未进入；headless 测试不能替代 GUI 验收。本地提交不推送、不修改默认入口或 P12/P13 状态。
