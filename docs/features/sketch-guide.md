# Sketch E1 使用与验证指南

更新：2026-10-17｜已实现子集：E1｜ABI：e1-02-v1｜完整 sketch 1.0 尚未发布

规则以 [sketch.md](sketch.md) 为准。本轮实现内存几何模型、受控类型、样式、路径和填充，阶段验收结果见 [tests/e1](../../tests/e1/README.md)。E1-02 的 SVG 已实现；E2 的窗口/图层工具/文字、E3 的历史/回放/图案、E4 的事件/项目文件仍待推进。没有占位成功接口，调用未实现成员得到 E302。

## 运行已有示例

在仓库根目录执行：

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m zzy check examples/sketch/geometry.zzy
& ./.venv/Scripts/python.exe -X utf8 -m zzy run examples/sketch/geometry.zzy
```

实际 [geometry.zzy](../../examples/sketch/geometry.zzy) 创建矩形填充和一个闭合圆，输出：

```text
sketch.Position::{x: 0.0, y: 30.0}
0.0
```

本例不显示窗口或生成图片。当前可通过 position/heading 观察几何状态；内部路径的独立固定答案、曲线误差、样式和填充组合由宿主测试核验。SVG 的外部几何验收见 tests/test_sketch_svg.py，解析导出 XML 后核对几何。

## 可用接口

全部是正式契约的固定位置参数调用，写操作返回 Null。参数先从左到右求值，再检查数量和外层类型，随后检查上下文/线程、冻结、活动填充及数值约束。

| 能力 | 已登记成员 |
|---|---|
| 创建/背景/清除 | canvas、pen、rgb、background、clear |
| 样式与位置快照 | color、fill_color、width、pen_up、pen_down、show_cursor、hide_cursor、position、heading |
| 移动/路径 | forward、backward、left、right、set_heading、move_to、jump_to、home、circle、polyline、bezier_to、dot |
| 填充草稿 | begin_fill、end_fill、cancel_fill |

Canvas、Pen、Layer、Color、Drawing 的类型身份已经登记，可用于 qualified 注解，不能直接调用类型或用 `::{}` 构造。当前只有 Canvas/Pen/Color 的公开工厂；Layer 只用于内部 default 图层，Drawing 尚无实例工厂。登记身份不等于图层编辑或图案能力已实现。

position 返回新的冻结普通 sketch.Position 结构，x/y 是 Float；它可按结构规则序列化，查询只能读取预先取得的普通快照。原生句柄不开放 Python 属性或方法；Canvas/Pen/Layer/Drawing 为身份相等，Color 为 RGB 分量相等。通用 JSON 对原生值返回失败，包括嵌套值。扩展函数未加入查询纯调用白名单。

每次执行独立创建文档；原生句柄不能跨上下文、跨执行线程或在执行结束后使用。Canvas 冻结会阻止其画笔/图层写入；独立画笔冻结不影响其他笔。冻结入口同样检查归属，无法借内部冻结绕过边界。图层锁的内部写入口已有测试，公开图层 API 待 E2。

clear 清空已提交几何并释放其逻辑预算，保留画笔、背景和 default 图层，ID 高水位不回退。本轮尚无 undo/redo，不能把契约中未来的可撤销行为当作已经交付。

## 坐标、曲线与提交

中心原点，X 向右、Y 向上；角度逆时针为正，朝向归一到 [0,360)。初态为原点/0 度、落笔、黑色描边与填充、线宽 1、光标可见、白背景。画笔名非空且同画布唯一。光标标志只存状态，E1-01 不显示光标。

圆弧按正式契约的有向圆心/转角计算；负半径、负 extent 均可用。非零整圈直接恢复起点和规范朝向，不累计闭合漂移。extent=0、空 polyline 不分配曲线缓冲、不改文档；半径 0 仍为 E208。

所有后端将复用同一只读折线路径。本版圆弧按弓高不超过 **0.25 个逻辑单位**分段，单段转角不超过 90 度；三次贝塞尔用 de Casteljau 二分，两个控制点到端点线段的距离均不超过 0.25 时接受该段，最大展开深度 24。这里固定模型近似误差，不声称像素精确或已经实现 SVG/Tk 渲染。

polyline 一次复制并验证全部点；后改输入数组不影响已发布路径。曲线/批量操作在准备后一次提交，坏点、越界、取消或分配失败不保留前半条路径，不提前改变位置/ID。路径由有预算所有者的只读块承载，为后续渲染和增量历史共享提供基础，尚无历史记录/回放实现。

## 填充

begin_fill 要求落笔且同画布无其他草稿，保存完整笔状态与开始时的填充颜色。草稿只能由该笔执行连续路径、转向、描边颜色/线宽操作或读取；抬笔、jump、点、换填充色、光标设置、其他笔写入、清画布、创建笔、改背景及嵌套 begin 均为 E214。

end_fill 要求至少三个不同顶点，发布一个 evenodd 填充组及已执行描边；闭合不新增描边、不移动笔。草稿未结束时，正式文档没有其半成品。失败保留草稿供宿主检查；语言运行错误仍终止执行，由统一清理撤销未提交草稿。cancel_fill 恢复 begin 前完整状态并释放草稿；执行中止也解除草稿锁，不自动保存。

## 配额 e1-01-v1

这些固定扩展限额与核心 default-v1 预算共同生效；不修改旧核心配置或指纹。扩展限额当前不可通过 `--limits` 调高，核心预算仍可收紧。后续若增加可配置扩展策略，需要版本化和相应验证。

| 项目 | 当前上限/规则 | 诊断 |
|---|---|---|
| 画布宽高 | 非 Bool 正 Int，1—32768 | E201/E208 |
| 坐标、距离、半径绝对值 | 1,000,000；所有派生坐标也检查有限性和范围 | E208 |
| 角度、extent 绝对值 | 1,000,000 度 | E208 |
| 线宽、点直径 | 大于 0，最多 10,000 | E208 |
| 单次 polyline 输入点 | 10,000 | E211 |
| 单曲线展开段 | 65,536，贝塞尔深度 24 | E211 |
| 每画布已提交路径段 | 1,000,000；活动草稿预占剩余额度；点计一段 | E211 |
| 每画布对象 | 100,000；整条 polyline、整条曲线或一个填充组各为一个对象 | E211 |
| 每画布画笔 | 256 | E211 |

所有文档对象、引用槽和逻辑载荷都使用现有 ResourceMeter，提交前检查。绘图块按 128 字节固定载荷、每描边 48 字节、每坐标点 16 字节及引用槽计量；这不是 CPython RSS 估计。笔状态和草稿另计固定载荷，临时点数组/递归工作栈计 scratch。当前曲线采用最多 65,537 点的保守预留，圆弧生成另有按实际段数的暂存，因此很低的核心预算可能在小曲线处拒绝；不会偷偷使用无界缓冲或降低误差。

真实测试到达了 256 笔、65,536 曲线段、1,000,000 文档段和 100,000 对象，并验证各自再增加一项失败。9999/10000/10001 个 polyline 点通过真实 CLI 验证。默认极限逐项通过不等于所有极限同时组合可容纳，也不构成性能或最大 RSS 承诺。历史、队列、输出等后续配额沿用正式契约，尚未宣称落实。

## 验证和下一项

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_e1_cli tests.test_e1_runtime -q
& ./.venv/Scripts/python.exe -X utf8 -m tests.blackbox tests/e1/cases.json
& ./.venv/Scripts/python.exe -X utf8 -m tests --report dist/e1-all-tests.json
```

check 只加载类型/签名元数据；测试用禁止 GUI 导入的独立进程确认 check 不导入几何实现、不执行输入/写文件，headless run 也不导入 tkinter/turtle。线程测试是原生句柄归属验证，**没有 GUI 验收结果**。E1 完成后按 E2→E3→E4 推进。

## E1-02：无窗口 SVG

`sketch.svg_text(canvas)` 返回 Result<String>；`sketch.save_svg(canvas,path)` 返回 Result<Null>，复用 io.write_atomic。可读取冻结画布；活动填充 E214。输出包括背景、裁剪区和规范折线路径，不包含光标。Y 坐标反转，中心平移到画布中心；填充边界单独闭合为 evenodd，不补描边。SVG 数值保留模型浮点值，允许 SVG 自身的指数记法，不改变 ZZY 数字语法。

标题按 XML 1.0 转义；非法 XML 字符返回失败 Result。逐片检查 text_codepoints/io_payload_bytes，累积文本与引用槽计入运行时预算；容量/取消仍为诊断/中止，不吞成失败 Result。先完整生成，之后同目录临时文件替换；父目录不存在不自动创建。普通 run、check 和导出不导入 Tk。

```zzy
(zno)c:=sketch.canvas(400,300,"SVG 示例");
(zno)p:=sketch.pen(c,"pen");
sketch.circle(p,50,360);
io.print(sketch.save_svg(c,"picture.svg"));
```

专项命令：`.venv/Scripts/python.exe -X utf8 -m unittest tests.test_sketch_svg tests.test_e1_runtime tests.test_e1_cli -q`。SVG 成功不构成 GUI/撤销验收。

## E2：真实 Tk 视图

显式 `python -m zzy run file.zzy --gui` 才加载 Tk。`sketch.show(c)` 正常关窗返回成功，之后可继续保存；不加 --gui 或缺 Tk/显示环境返回说明性失败 Result。默认 check/run/test 不初始化 GUI。

已新增 add_layer/set_layer/layer_visible/lock_layer/rename_layer/move_layer/layer_info、font/text_align/text、show。图层最多256，0为底层；LayerInfo是冻结普通结构快照。SVG按可见图层顺序输出文字，字体族/内容均XML转义；文字水平、字号为逻辑单位。GUI缺字体由系统Tk替代，默认sans-serif映射Arial，不保证设备像素一致。

窗口工具栏提供自由线、直线、矩形、圆、拖曳多边形、文字、平移，笔名/颜色/线宽、缩放/网格/坐标和图层状态栏。多边形以拖曳采样点形成闭合折线。Tk只操作不可变Scene与事件消息；通用绘图调用在单一ZZY执行线程执行。关闭使用独立Event，正常关闭不销毁文档。历史/回放尚待E3；公开回调、对象编辑和项目文件待E4。

真实GUI验收独立命令：`.venv/Scripts/python.exe -X utf8 -m tests.gui_sketch --report tests/e2/results/gui.json`，需桌面环境，失败不跳过。当前Windows/Tk8.6.12真实窗口3/3通过；受限执行环境会报init.tcl不可用，不能把该结果冒充GUI成功。

## E3-01：增量历史与回放

新增 begin_group/end_group、undo/redo、clear_history、frame_interval。历史保存变动字段与几何块引用；共享只读路径，不保存每步整张画布。单次失败恢复本次候选几何/位置/ID，先前成功操作不回滚。正常undo/redo保留对象ID高水位；新编辑丢弃redo。空组不入历史；填充在end时作为单项，cancel无历史。活动组/草稿不能undo/redo、导出或show。

固定上限100000条实际修改命令（分组内也计数），历史增量载荷64MiB（160字节基数、每字段64、每几何引用16；共享路径另由原Block预算拥有），不静默丢历史。达到上限可显式clear_history，几何不变。旧路径因undo而仍被保留会继续占核心预算，clear不再等于释放全部路径；容量验收用clear_history分开测几何上限。

窗口新增撤销/重做、播放/暂停/单步/进度定位。回放副本应用记录，不执行源码，不覆盖真实画笔；编辑先回到真实文档。最多8个共享路径检查点、16MiB缓存预算，预算不足仅不创建加速缓存，仍准确应用增量。frame_interval接受(0,24h]时间Quantity，向上取整毫秒，默认40ms。

宿主历史5项、独立CLI6项、真实GUI4项通过；GUI定位/单步/编辑退出以及正常关窗分别有证据。图案和项目仍待下一任务，完整1.0未发布。

## E3-02：图案与函数库

capture取得可见图层的只读路径快照；后改源文档不影响Drawing。stamp按缩放→逆时针旋转→平移，线宽/字号同步缩放，目标笔状态不变，整组放default层，undo作为一项。Drawing按身份相等，通用JSON不接受；显式drawing_text/drawing_from_json采用schema_version=1、kind=zzy-drawing和objects有序数组。对象type为path/fill/dot/text/group，固定字段、严格重复键/数值/容量检查；组只含叶对象，不允许嵌套组。错误格式返回失败Result，资源中止保留E211。

save_function(drawing,path,name)生成私有Lazy解码绑定和具名Result函数，名字经Lexer、整个文件经真实prepare（Lexer/Parser/Resolver）验证后原子写入。导入/check不解码、不绘图；首次调用wake一次解码，同一上下文后续调用复用Drawing；重新执行Program重新解码。空Drawing函数导出返回失败。引用方式仍为 `(use) "pattern.zzy" (as) patterns;`，调用 `patterns.flower(canvas,x,y,scale,angle)` 返回盖章ID的Result。

当前E3已实现，仍非完整sketch1.0；公开事件/对象工具/项目文件及完整性能测量属于E4。
