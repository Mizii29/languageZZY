# Sketch 使用与验证指南

更新：2026-10-17｜核心 0.6.0a1｜扩展 ABI 1.0，E1—E4已验收；结果见 [验收入口](../../tests/e4/README.md)。

行为以 [sketch 契约](sketch.md) 为准。几何、SVG、图层、文字、历史、Drawing、事件和项目文件均有实际实现；完整1.0的四阶段门禁均已通过。PNG 没有独立渲染后端，save_png 明确返回失败 Result，不创建文件。

## 启动

在仓库根目录执行；默认 run/check/test 不导入 Tk。只有 run --gui 初始化窗口；check 没有 --gui 开关，也不执行用户表达式、绘图、文件保存或 Lazy 解码。

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m zzy check examples/sketch/studio.zzy
& ./.venv/Scripts/python.exe -X utf8 -m zzy run examples/sketch/studio.zzy --gui
```

[studio.zzy](../../examples/sketch/studio.zzy) 绘制六瓣花、盖章并导出 SVG/函数库；关闭窗口后保存可编辑项目。输出文件相对启动目录。不加 --gui 时 show 返回说明性失败 Result；无 Tk/显示环境同样失败，不自动安装依赖。Python 必须带 Tk；本次真实桌面证据为 Windows 11、CPython 3.12.14、Tk 8.6.12，其他平台未验证。字体默认 sans-serif 映射 Arial，缺少字体由 Tk/查看 SVG 的软件替代，不承诺不同设备像素一致。

仅需无窗口模型时可运行 [geometry.zzy](../../examples/sketch/geometry.zzy)，固定输出 Position 的 x=0.0、y=30.0 与 heading=0.0。SVG、项目和函数库导出均不需要 GUI。

## 接口与受控值

完整签名见正式契约；所有参数按核心规则从左至右求值，然后检查数量、类型、归属、冻结/图层锁、状态及数值。普通写操作返回 Null。

| 能力 | 成员 |
|---|---|
| 文档与样式 | canvas、pen、rgb、background、clear、color、fill_color、width、pen_up/down、show/hide_cursor、position、heading |
| 几何 | forward/backward、left/right、set_heading、move_to/jump_to、home、circle、polyline、bezier_to、dot |
| 填充/文字 | begin_fill/end_fill/cancel_fill、font、text_align、text |
| 图层 | add_layer、set_layer、layer_visible、lock_layer、rename_layer、move_layer、layer_info |
| 对象 | pick、translate_object、copy_object、delete_object |
| 历史 | begin_group/end_group、undo/redo、clear_history、frame_interval |
| 图案 | capture、stamp、drawing_text、drawing_from_json、save_function |
| 文件 | svg_text、save_svg、save_project、load_project；save_png 为明确不可用的可选能力 |
| 会话 | show、on_click/on_drag/on_release/on_key、every、cancel_timer |

Canvas/Pen/Layer/Drawing 按身份相等，Color 按 RGB 值相等；不能访问 Python 属性或直接构造原生值。Position、LayerInfo 是新的冻结普通结构快照，可用于查询；原生绘图调用不属于查询纯调用白名单。通用 JSON 拒绝原生值，使用 sketch 的显式格式。

句柄归本次执行上下文与执行线程；冻结 Canvas 同时禁止所属笔/层写入。锁层可选择不可编辑。上下文结束清理文档和回调；关窗只关闭会话，脚本随后仍能保存、修改和重新 show，重新显示前需重新注册回调。

## 几何、图层与填充

中心原点，X 向右、Y 向上，逆时针为正；朝向归一到 [0,360)。初始落笔、黑色、线宽 1、光标可见、白背景/default 层。圆弧正负半径及 extent 遵循契约有向圆心，完整圈直接恢复起点与规范朝向。零 extent、空 polyline 不产生历史，半径零仍非法。

圆弧弓高误差不超过 0.25 逻辑单位、单段转角不超过 90 度；贝塞尔 de Casteljau 二分直到两个控制点到端点线段均不超过 0.25，最大深度 24。规范展开路径保存于不可变 Block，SVG/Tk/历史/图案重复复用该版本与误差的结果，变换产生新块，最后引用释放时退还预算；没有跨上下文的曲线参数全局缓存。polyline 一次复制并校验输入，后改数组不影响路径。失败提交不留下前半条路径或位置/ID 修改。

填充在 begin 保存笔状态及填充色，只允许同笔连续路径/转向/描边样式与读取。end 至少三个不同顶点，evenodd 闭合填充、不补描边、不移动笔；cancel 恢复开始状态。活动填充禁止其他文档写入、保存/捕获/历史操作。错误/关闭清理草稿，不自动保存。SVG 与真实 Tk 的奇偶填充、裁剪各有独立验证。

图层按 z 序合成，隐藏层不导出/捕获，锁定层不能改图形。text 不移动笔，也不依赖落笔状态。pick 按最上可见对象命中，固定容差 4 逻辑单位；文字命中使用宽 0.6×字号×码点数、高为字号的逻辑框，不依赖字体测量。ID 单调分配，undo/redo 恢复原 ID，不复用已撤销 ID；删除擦除整个对象而非涂背景色。

## 交互、线程与关闭

工具栏提供自由线、直线、矩形、圆、拖曳多边形、文字、平移、选择、移动、复制、擦除及 callbacks 模式。多边形以拖曳采样点闭合；自由画笔的一次按下到松开组成一条历史。另有选笔、颜色、线宽、图层创建/显隐/锁定/命名/排序、缩放、网格、坐标。缩放/平移/网格仅改视图，不改几何和历史。

有鼠标回调时初始使用 callbacks 模式，只派发用户回调；切换到内置工具时仍派发已注册回调，同时执行该工具，避免两处重复实现同一笔画。鼠标 button=1/2/3，坐标转换为逻辑 Float；键名 Enter、Escape、Backspace、Space、PageUp、PageDown，其余可打印字符或 Tk keysym。注册时检查函数及固定参数数量；同类注册覆盖旧项。定时器从 show 开始计时，延迟合并，不追补积压次数。

Tk 只在主线程管理窗口，ZZY 在单一工作线程顺序处理消息和回调；不在任意 AST 指令中途重入。正常关闭可中断长回调并让 show 返回成功；原始诊断、队列溢出和执行取消不吞成成功。关闭信号独立于数据队列；清理后无存活工作线程。不能安全强杀任意阻塞 Python 调用，仍需进程隔离作为硬终止边界。

## 撤销与回放

历史保存增量字段和只读路径引用，撤销恢复相关笔/层状态；新编辑清空 redo。创建 Canvas/Pen、光标显示、视图状态不入绘图历史。分组不嵌套，空组忽略；不承诺回滚先前 I/O。填充 end 是一项，cancel 无历史。活动组/草稿禁止 undo/redo、保存/捕获/回放。

窗口支持播放/暂停/单步/定位。回放副本只应用记录，不重跑源程序、随机数或回调，不覆盖真实笔；编辑退出回放，保存针对完整文档。frame_interval 初值 40::ms，正时间向上取整毫秒，范围 (0,24h]。检查点最多 8 个且 16MiB，核心预算不够时不建立可选缓存，增量定位仍正确。clear_history 显式清除 undo/redo，几何不变；clear 因历史仍引用旧路径，不能等同于释放全部内存。

## 保存、重启与函数复用

SVG 含背景/裁剪/可见层/规范路径与文字，不含光标；XML 转义与非法字符均受检查。save_* 先完成有界生成校验，再独占创建同目录临时文件并替换；失败保留旧文件并清理临时文件，不创建父目录，不承诺断电持久化/多写者事务。

图案 schema_version=1、kind=zzy-drawing，项目 kind=zzy-project。两者严格拒绝重复键、未知字段/版本/类型、非有限数、错误引用及越界。项目保存笔/图层/几何池/历史/redo/ID 高水位与回放间隔，不保存窗口/回调/定时器/Lazy；load_project 全部校验后返回新 Canvas，坏数据不覆盖已有文档。

capture 只包含可见已完成几何；后改源文档不影响 Drawing。stamp 按缩放→逆时针旋转→平移插入 default 层的一组，保留所有笔状态。save_function 输出自包含 .zzy 模块，名字经同一 Lexer、完整源码经 prepare 验证后原子写入；空图案/坏名字为失败 Result。导出函数 name(canvas,x,y,scale,angle) 返回盖章 ID 的 Result，私有 Lazy 每个上下文首次调用解码一次。check/导入准备不解码、不画图。

```text
(use) "flower.zzy" (as) flowers;
(zno)c:=sketch.canvas(800,600,"复用图案");
io.print(flowers.draw_flower(c,0,0,1,0));
io.print(sketch.save_svg(c,"reused.svg"));
```

## 固定扩展配额

扩展配额与核心 default-v1 同时生效；当前 --limits 只能配置核心预算，不能调高下表固定阈值。逻辑载荷不等于 CPython RSS；达到某个单项上限不表示所有上限可同时组合。

| 项目 | 上限 |
|---|---|
| 画布宽/高 | 正 Int，32768 |
| 坐标/距离/半径/角度绝对值 | 1,000,000；派生坐标同样检查 |
| 线宽/直径/字号 | (0,10000] |
| 单批点/单曲线段/贝塞尔深度 | 10000 / 65536 / 24 |
| 每画布路径段/对象 | 1000000 / 100000 |
| 每画布笔/活动图层/定时器 | 各 256 |
| 历史命令/增量载荷 | 100000 / 64MiB；分组内命令也计数 |
| 输入/渲染队列 | 4096 条 / 1 条合并刷新；合计载荷 16MiB |
| Tk 文档渲染 item | 200000；拖曳预览最多另1个 |
| 回放检查点 | 8 个 / 16MiB；可选加速缓存 |

几何块基数128字节、描边48、点16，另计引用槽/草稿/临时数组；历史基数160、字段64、几何引用16、label每码点4字节，共享路径仍由 Block 计量。曲线暂存采用最多65537点的保守预留，低预算下小曲线也可能拒绝。SVG/JSON/源码生成遵守核心文本、I/O、引用槽和载荷限制。字体/图层名替换的字符串预留目前保守地保留到句柄结束，clear_history不保证这部分预留立即回收；大量反复换名/字体可能较早触发核心预算。容量超限 E211，在发布前拒绝，不自动降低精度或丢弃历史/输入。

## 复现与证据边界

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m tests --report tests/e4/results/all-tests.json
& ./.venv/Scripts/python.exe -X utf8 -m tests.gui_sketch --report tests/e4/results/gui.json
& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.run --repeats 3
& ./.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.render --all --repeats 3
```

GUI 命令必须在真实桌面运行，缺环境会失败而不跳过；headless 通过不能代替它。覆盖和原始证据见 [tests/e4](../../tests/e4/README.md)，性能方法/局限见 [测量报告](../../benchmarks/sketch/README.md)。其他 OS/Python/字体、所有最大容量组合、操作系统 ACL 和断电持久化没有本次证据，PNG 不可用。
