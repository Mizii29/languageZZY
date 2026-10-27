# ZZY Sketch：梓伊小画室扩展契约

更新：2026-10-17｜设计目标：sketch 1.0｜状态：E1—E4全部验收，sketch 1.0

本文记录用户选定的完整画笔扩展。核心语法保持 v0.6，规则见 [syntax.md](../language/syntax.md)，通用宿主调用与错误约定见 [stdlib.md](../language/stdlib.md)。sketch 使用普通库调用，不增加关键字、运算符或单位；接口 ABI 与文件 schema 单独版本化。其他新增场景及动漫/游戏主题未纳入本扩展。

## 1. 目标与完整 1.0 范围

ZZY Sketch 借鉴 turtle 的移动、转向、抬落笔与填充模型，提供程序绘图和鼠标绘图。特色是把绘图文档、分组撤销、确定性回放和 ZZY 图案函数导出连成完整流程，不宣称撤销或画笔操作为独创。参考 [Python turtle 官方文档](https://docs.python.org/3/library/turtle.html)。

完整 1.0 包含：

- 多支独立画笔，直线、圆弧、折线、贝塞尔曲线、点、填充与文字。
- 交互画布：自由画笔、直线、矩形、圆、多边形、文字；选择、移动、复制和对象擦除。
- 图层、调色、线宽、缩放/平移、坐标及可选网格。
- 文档级撤销/重做、分组、逐笔回放、暂停、单步与进度定位。
- SVG、可继续编辑的项目文件、可导入的 `.zzy` 图案库；PNG 为可选组件。
- 鼠标/键盘/定时回调，无窗口导出与黑盒测试。

几何与渲染由 Python 宿主提供；画法、工具控制和图案组合可由 ZZY 编写。小画室可以成为后续 ZZY 应用，但本次只选择扩展，不自动替换 P09 默认校园任务管家，也不把 Python 窗口代码计作 200 行 ZZY 应用。

## 2. 值类型、坐标与生命周期

### 2.1 受控的原生值

通过宿主类型注册表登记 `sketch.Canvas`、`sketch.Pen`、`sketch.Layer`、`sketch.Color`、`sketch.Drawing`，复用已有 qualified 类型语法；这些名字只读，不新增括号类型 Token。不开放任意 Python 属性、方法、构造器或 `::{...}` 构造。

- Canvas/Pen/Layer 是可变句柄，归创建它们的 ExecutionContext，跨上下文、错误画布归属及冻结写入报 `E203`；所有别名经过相同写入口。
- Color 是不可变 RGB 值，按三个分量相等；Drawing 是不可变图案快照，按身份相等，内容验证使用显式序列化/逐项比较。
- Canvas/Pen/Layer 按身份相等。Program 不缓存可变句柄、窗口、回调或图案解码 Lazy；它们属于本次执行。
- 冻结 Canvas 时也禁止其 Pen/Layer 写入。冻结 Pen/Layer 不会令其他独立画笔不可写，但被锁定图层不能增删改图形。
- `data.stringify` 默认拒绝以上原生值，含嵌套情形。只通过 sketch 的显式 schema 编解码；shape 接口合约也不自动接受它们。
- 窗口关闭只关闭视图，不销毁绘图文档；上下文结束统一清理视图、回调、定时器和队列。可序列化数据不包含这些运行时引用。

### 2.2 统一几何规则

画布中心为 `(0,0)`，X 向右、Y 向上；朝右为 0 度，逆时针为正，朝向规范到 `[0,360)`。宽高为正 Int；坐标、角度、距离和样式尺寸接受非 Bool Int/有限 Float，原生边界进行受范围限制的浮点转换。三角函数是近似计算，不宣称精确有理数几何。

初始背景为白色，默认图层名为 `default`；画笔位置/朝向为原点/0，落笔、黑色描边与填充、线宽 1，光标可见。画笔和图层名字为非空 String，同一画布各自唯一。

缩放/平移是视图变换，不改文档几何，也不进入绘图撤销历史。超出逻辑画布的几何保留，显示与 SVG 按画布边界裁剪。绘图数据只存逻辑坐标；Tk/SVG 各自转换坐标系，文字另行处理方向，不能整体翻转后让字倒置。

坐标/尺寸、曲线展开点数、单批点数、文档对象数、历史字节和输出容量都有版本化配额。边界值需在实现时根据测量固定并写入指南；完整配额未落实前不发布 1.0。所有派生坐标同样检查有限性与范围。

## 3. 公开接口与行为

以下均为固定位置参数接口；表中的返回标签仅描述载荷，不引入泛型或联合类型语法。除明确列出的返回值外，写操作返回 Null。先按核心规则求实参，再检查数量、类型、归属、冻结/图层锁和状态；完成全部准备后才提交单条操作。

### 3.1 画布、画笔和样式

| 接口 | 返回/行为 |
|---|---|
| `sketch.canvas(width,height,title)` | Canvas；创建无窗口绘图文档 |
| `sketch.pen(canvas,name)` | Pen；新画笔在默认图层，使用第 2 节初态 |
| `sketch.rgb(r,g,b)` | Color；三项必须是 0—255 的 Int |
| `sketch.background(canvas,color)` | 设置背景，进入文档历史 |
| `sketch.color(pen,color)` / `sketch.fill_color(pen,color)` | 设置描边/后续填充颜色 |
| `sketch.width(pen,width)` | 正线宽，随逻辑图形一起缩放 |
| `sketch.pen_up(pen)` / `sketch.pen_down(pen)` | 修改抬落笔状态 |
| `sketch.show_cursor(pen)` / `sketch.hide_cursor(pen)` | 显示状态；光标不进入图片或图案 |
| `sketch.position(pen)` | 新的冻结普通结构 `sketch.Position`，x/y 为 Float |
| `sketch.heading(pen)` | Float，规范化后的朝向 |
| `sketch.clear(canvas)` | 清除图形，保留画笔状态与图层，可撤销 |

创建 Canvas/Pen 不进入可撤销绘图历史，避免已有变量因撤销失去句柄；后续位置/方向/样式改变进入历史。Color/Position 与窗口光标没有隐式宿主属性访问。

### 3.2 移动和路径

| 接口 | 行为 |
|---|---|
| `sketch.forward(pen,distance)` / `sketch.backward(pen,distance)` | 按当前朝向移动，允许负距离；落笔时绘制 |
| `sketch.left(pen,angle)` / `sketch.right(pen,angle)` | 转向，不移动，允许负角度 |
| `sketch.set_heading(pen,angle)` | 设置规范化朝向 |
| `sketch.move_to(pen,x,y)` | 落笔时连接到目标，朝向不变 |
| `sketch.jump_to(pen,x,y)` | 不画线，保持原抬落笔状态与朝向 |
| `sketch.home(pen)` | 按 move_to 返回原点，再朝向 0；落笔时可能画线 |
| `sketch.circle(pen,radius,extent)` | 非零半径圆弧；完整圆写 extent=360 |
| `sketch.polyline(pen,points)` | points 为 `[[x,y],...]`；从当前位置逐点移动，空数组无操作，朝向不变 |
| `sketch.bezier_to(pen,c1x,c1y,c2x,c2y,x,y)` | 当前点为起点，两个控制点和终点；结束朝向不变 |
| `sketch.dot(pen,diameter)` | 正直径圆点，使用描边颜色；不移动、不依赖抬落笔 |

圆心为当前位置加上“当前方向左侧 radius”，负半径位于右侧；转角为 `sign(radius) * extent`，沿该有向圆弧移动，结束朝向加该转角。extent 允许正负；0 不产生几何或历史，完整圈的末点/朝向直接采用规范化起态，避免累计闭合漂移。普通部分弧保留近似值。

批量 points 在调用时复制和校验，控制点、派生点、记录及历史空间全部准备成功后一次提交。参数数组之后修改不影响已画路径；错误不能留下前几个点或改变画笔位置。曲线使用统一规范路径及受误差控制的展开，不分别依赖后端默认平滑算法。

### 3.3 填充和文字

| 接口 | 行为 |
|---|---|
| `sketch.begin_fill(pen)` | 保存起态和本次填充颜色，创建单轮廓草稿；要求落笔 |
| `sketch.end_fill(pen)` | 准备并提交一个填充组，含填充和已执行描边；至少三个不同顶点，否则 E214 |
| `sketch.cancel_fill(pen)` | 丢弃草稿，恢复 begin 前的画笔状态，不写历史 |
| `sketch.font(pen,family)` / `sketch.text_align(pen,alignment)` | 字体族 String；对齐仅 left/center/right，初始 sans-serif/left |
| `sketch.text(pen,content,size)` | String、正字号；当前位置水平文字，不移动、不依赖抬落笔 |

填充是草稿而非半成品文档，窗口可预览；结束时按 evenodd 闭合填充边界，不补一条描边，也不改变闭合前笔的位置/方向。描边颜色/宽度可以在草稿内改变，本次填充颜色仍是 begin 时的值。

同一 Canvas 最多一个填充草稿。草稿内只允许该笔的连续路径、转向、描边样式操作及读取；抬笔、jump、换图层、文字/点、其他文档写入和嵌套填充为 `E214`。填充可作为外层历史分组中的一项。未结束填充不能撤销/重做、捕获、保存、回放或结束分组；先 end/cancel。取消或执行中止释放草稿，不能永久留下“正在填充”锁。

第一版使用 RGB 实色、单轮廓填充；透明度、孔洞/多轮廓、渐变和复杂画笔纹理以后另定契约。字体替代规则写入指南，不承诺不同系统逐像素一致；headless 导出不为测字体而初始化 Tk。

### 3.4 图层与对象编辑

| 接口 | 返回/行为 |
|---|---|
| `sketch.add_layer(canvas,name)` | Layer，追加最上层；同名拒绝 |
| `sketch.set_layer(pen,layer)` | 要求同一画布 |
| `sketch.layer_visible(layer,visible)` / `sketch.lock_layer(layer,locked)` | Bool；只影响文档中该层，不改画笔几何 |
| `sketch.rename_layer(layer,name)` | 非空且不与其他层重名 |
| `sketch.move_layer(layer,index)` | 非 Bool Int，0 为最底层；越界 E204 |
| `sketch.layer_info(canvas)` | 新 Array，元素是冻结普通结构 LayerInfo；name/visible/locked/count/z，类型为 String/Bool/Bool/Int/Int |
| `sketch.pick(canvas,x,y)` | 命中最上方可见图形的正 Int ID，未命中 Null；使用已登记容差，锁定图形可选不可改 |
| `sketch.translate_object(canvas,id,dx,dy)` | 移动对象或整个图案组 |
| `sketch.copy_object(canvas,id)` | 新对象的 Int ID，复制到原层，原对象不变 |
| `sketch.delete_object(canvas,id)` | 删除完整对象/笔画；对象擦除不涂背景色 |

对象 ID 在单个 Canvas 内单调分配、不复用；undo/redo 恢复原 ID，找不到 ID 报 E204。图层和对象的可观察修改进入历史；视图网格、缩放和平移除外。取消选择不修改文档。

自由画笔把一次按下至松开作为一个折线组；矩形/圆/多边形工具调用通用几何接口。图层/画笔句柄不传入查询条目，先在查询外调用 layer_info，查询仅读取普通结构快照；不扩充原生纯调用白名单。

## 4. 历史、回放与图案复用

### 4.1 分组与撤销

`sketch.begin_group(canvas,label)` / `sketch.end_group(canvas)` 把多次操作组成一条历史。label 为 String；分组不嵌套，必须配对，空组不写历史。`sketch.undo(canvas)` / `sketch.redo(canvas)` 返回 Bool，没有历史为 false；活动分组或草稿期间为 E214。

每项记录文档增量及相关 Pen/Layer 的前后状态，撤销/重做同时恢复几何、顺序、位置、方向、颜色和线宽。多画笔共用文档历史；undo 后新增编辑清空 redo。光标可见性等展示设置与几何状态分开处理，不让回放光标覆盖真实 Pen 状态。

分组不承诺事务回滚：已完成指令按顺序提交，end 组织历史；错误不撤销先前 I/O。执行中止时清理未完成填充，释放分组标志和队列，不自动保存不完整项目。捕获/保存/回放要求没有活动组或草稿。

历史使用增量及共享的只读路径块，不保存每一步整幅文档复制。达到历史配额时，按已声明策略在新操作提交前报 E211；用户可以显式 `sketch.clear_history(canvas)` 清空 undo/redo，几何不变，不默默丢历史。

### 4.2 回放

`sketch.frame_interval(canvas,duration)` 接受正时间 Quantity，初始 40::ms；按宿主计时分辨率向上取整，范围检查后换算，不能变成零间隔忙循环。窗口按钮提供播放/暂停/单步/定位；该配置不影响脚本生成几何的速度。

回放捕获当前已完成历史的一致快照；已清掉的历史不声称仍可回放。只播放保存的几何和状态记录，不重跑源码、随机数、回调或 I/O。显示进度独立于实际文档；编辑先退出回放并显示当前完整文档，保存/捕获默认针对完整文档。复用共享检查点加快定位，限额内生成，避免每帧重建全部图形。

### 4.3 不可变图案

`sketch.capture(canvas)` 返回 Drawing，只捕获可见图层已完成几何、样式和合成顺序，不含背景、光标、历史、窗口、回调或画笔句柄；空图案允许捕获，但函数导出返回说明性失败 Result。

`sketch.stamp(canvas,drawing,x,y,scale,angle)` 返回新图案组的 Int ID。scale 必须大于 0；以图案原点为锚点，先统一缩放、再逆时针旋转、最后平移。线宽和文字随图案缩放，内部绘制顺序保持，整组插入目标 Canvas 的 default 层，默认层锁定时 E203。保持目标所有 Pen 状态，不创建同名顶层图层，不递归执行原脚本；变换后坐标和容量先校验后提交。

Drawing 与源文档共享的只能是只读数据块；随后修改源文档不改变图案。跨上下文通过显式序列化重建，不传递本次上下文的原生句柄。

## 5. 窗口与事件

### 5.1 激活与执行方式

图形入口为 `python -m zzy run file.zzy --gui`。默认 run/test 与所有 check 不初始化 Tk；headless 几何、SVG、项目和函数导出无需 Tk。注册表可读类型/签名元数据，真正 GUI 依赖延迟到图形入口；缺少 Tk/显示环境或未启用 --gui 时 show 返回失败 Result，不安装依赖或假装窗口已显示。

`sketch.show(canvas)` 返回 Result<Null>，请求显示窗口并在该执行线程顺序派发事件，正常关窗返回成功；此后脚本可继续保存文档。1.0 一次只运行一个 show 会话，回调内再次 show 为 E214。关闭后取消该会话的回调和定时器；再次显示需要重新注册。

一个 Tk 根窗口由主线程管理；ZZY ExecutionContext 只有一个执行线程拥有。主线程只处理渲染/输入消息，绝不直接访问 Cell、Lazy 或调用 ZZY。两侧只交换复制后/不可变消息，Tk 操作仅在主线程；禁止用递归 update 或忙等待来维持窗口。Tk 依赖持续事件循环、长任务要分解，参考 [Tkinter 官方线程和事件模型](https://docs.python.org/3/library/tkinter.html#threading-model)。

图形线程分工不表示 ZZY 同一上下文并行或普通 Python CPU 计算自动多核加速；核心 Lazy 的顺序执行规则保持不变。

### 5.2 注册接口

| 接口 | 回调与返回 |
|---|---|
| `sketch.on_click(canvas,handler)` | handler(x,y,button)，返回 Null |
| `sketch.on_drag(canvas,handler)` | handler(x,y,button)，返回 Null；只处理按下期间移动，按下/松开分别由 click/release 处理 |
| `sketch.on_release(canvas,handler)` | handler(x,y,button)，返回 Null；与 drag 配合完成笔画 |
| `sketch.on_key(canvas,handler)` | handler(key)，返回 Null |
| `sketch.every(canvas,duration,handler)` | handler()，返回本会话 Int timer ID |
| `sketch.cancel_timer(canvas,id)` | 返回 Bool，是否取消现存定时器 |

x/y 为已转换的逻辑坐标 Float；button 为非 Bool Int（1/2/3），key 为规范化 String，键名规则在实现指南固定。同一种鼠标/键盘注册覆盖前一回调；数量/函数类型/固定实参数量在注册时检查。回调返回值忽略，但仍遵守自身返回注解；普通运行错误终止本次执行，不能吞成 show 的普通失败 Result。

回调不在任意 AST 指令中途抢占，只在 show 的派发边界顺序调用，不发生同上下文重入。定时器在 show 会话开始后启动，使用单调时钟，延迟时合并同一定时器的待触发次数，不补发积压风暴；鼠标/键盘输入保序，不默默丢几何采样点。

输入与渲染队列有界。渲染可合并冗余刷新，但文档记录不删减；输入队列溢出为 E211，记录失败并停止会话，Tk 主线程不阻塞等待队列空间。关窗/取消使用独立控制信号，不能排在满队列尾部；执行器循环/调用及耗时宿主批量操作检查取消，清理期间解除等待，避免关窗后工作线程挂住。硬终止需要进程隔离，不能声称 Python 线程可安全强杀。

### 5.3 交互外观

画布、工具栏、图层栏和历史栏形成小画室；调色、选笔、线宽、对象擦除、网格、缩放和回放都有明确状态。内置编辑动作通过同一命令提交入口，不能由 Tk 偷改文档；ZZY 可用事件 API 编写工具与快捷键。

趣味提示保留正式诊断和位置：抬笔“画笔摸鱼中”，撤销“这一笔先回去进修”，空图案导出“画布很干净，但暂时没有作品可以出道”。提示不改变错误码、Result 或 stdout 协议，不加入动漫/红温单位。

## 6. 文件与 ZZY 函数库导出

| 接口 | 返回/用途 |
|---|---|
| `sketch.svg_text(canvas)` | Result<String>，完整可见画面，含背景，不含窗口控件/光标 |
| `sketch.save_svg(canvas,path)` | Result<Null> |
| `sketch.save_project(canvas,path)` | Result<Null>；推荐扩展名 .zzysketch |
| `sketch.load_project(path)` | Result<Canvas>，成功才创建新文档，不覆盖现有文档 |
| `sketch.drawing_text(drawing)` | Result<String>，版本化图案 JSON |
| `sketch.drawing_from_json(content)` | Result<Drawing>，严格解码图案数据 |
| `sketch.save_function(drawing,path,name)` | Result<Null>，生成可导入 .zzy 库 |
| `sketch.save_png(canvas,path)` | Result<Null>，可选后端；缺依赖返回失败，能力清单注明不可用 |

项目与图案文件都采用严格 UTF-8/JSON、schema_version=1 和明确 kind，拒绝未知版本/对象类型、重复键、非有限值、未知字段、错误引用及容量/深度越界。只存显式值数据，不存可执行回调、Lazy 或宿主对象；仅回放间隔保存为声明过的整数毫秒字段，不保存定时器注册或回调，不把 Quantity 丢入通用 JSON。历史前后状态需校验一致，损坏项目不导入半份数据。

SVG 沿用规范路径与显式填充规则，文字按 XML 转义，不将用户字符串当标签/脚本。PNG 用独立渲染后端，不以窗口截图代替正式导出；记录字体/近似误差，几何一致不保证跨设备像素一致。参考 [SVG 路径](https://www.w3.org/TR/SVG2/paths.html) 与 [SVG 填充规则](https://www.w3.org/TR/SVG2/painting.html#FillRuleProperty)。

save_* 先在资源范围内生成/校验，再独占创建同目录唯一临时文件并替换发布；文本复用 io.write_atomic 的内部发布流程，PNG 复用相同字节发布内核。不自动创建父目录，替换前失败清理临时文件并保留已有目标，不承诺断电持久化或并发事务。文件/格式/缺依赖/空图案/无效函数名等可预期失败返回 (T_T)(String)；类型/状态/资源错误保持普通诊断。

函数导出采用现有具名函数与模块规则，公开函数为 `name(canvas,x,y,scale,angle) -> (Result)`：

1. 导出固定 schema 的图案数据，把名字交给同一词法/保留字规则验证。
2. 通过统一源码生成器转义双引号、[OoO]、控制字符；数字位于 JSON 字符串内，不生成核心不支持的指数数值字面量。
3. 库内私有绑定保存 `(zzz)(sketch.drawing_from_json(...))`，每个上下文首次调用 `wake` 解码，之后复用不可变 Drawing；不会自动刷新源文档。
4. 导出函数在显式 Result 上下文中解包失败、调用 stamp 并显式返回成功，保持调用者 Pen 状态。
5. 用真实 Lexer/Parser/Resolver 检查生成文件，然后原子发布；check 不解码 Lazy、不画图。错误的生成文件不得标记导出成功。

导出库自包含，首次解码/再次调用分开测量；不使用 eval/exec、字符串替换或重新执行原画图脚本。导入方式仍为 `(use) "flower.zzy" (as) flowers;`；只导出具名函数，私有图案绑定不导出。

## 7. 完整示例与语言特色

以下正式示例已实际check/run：无--gui时SVG与函数库生成，show明确返回失败；[studio.zzy](../../examples/sketch/studio.zzy)在此基础上增加关窗后项目保存，已在离线新环境真实打开窗口并完成重启复用。证据见[tests/e4](../../tests/e4/README.md)。

```text
(addnew) flower(canvas, pen, radius) {
    sketch.begin_group(canvas, "六瓣小花");
    (for) petal (in) range(0, 6, 1) {
        sketch.circle(pen, radius, 360);
        sketch.left(pen, 60);
    }
    sketch.dot(pen, 12);
    sketch.end_group(canvas);
}

(addnew) main() -> (Result) {
    (zno) canvas := sketch.canvas(800, 600, "梓伊小画室");
    (zno) pen := sketch.pen(canvas, "梓伊一号笔");
    sketch.background(canvas, sketch.rgb(248, 245, 255));
    sketch.color(pen, sketch.rgb(150, 90, 220));
    sketch.width(pen, 3);
    flower(canvas, pen, 45);

    zzysay: 捕获独立图案，再缩放旋转放到另一处
    (zno) drawing := sketch.capture(canvas);
    sketch.stamp(canvas, drawing, 180, 100, 0.6, 30);
    sketch.save_svg(canvas, "little-flower.svg")?;
    sketch.save_function(drawing, "flower.zzy", "draw_flower")?;
    sketch.show(canvas)?;
    (return) (^_^)((null));
}

(?_?) main() {
    (^_^)(value) => { io.print("小花出道，图案库也保存好了。"); }
    (T_T)(message) => { io.print(message); }
}
```

A 查询用于 layer_info 的普通快照筛选；C 状态机可用于 ZZY 工具/播放控制，不给核心 Machine 添加动作队列；D 只用于时间 Quantity，坐标仍为普通数。Lazy 可缓存不可变图案/版本对应 SVG 文本；文档更新必须新建 Lazy，不能伪装自动响应式缓存。可用管道将点数组送入 `sketch.polyline(pen,@)`，保持唯一插槽和单次求值。

## 8. 性能、稳定性与验收

- 几何模型与显示分离；headless 建图/导出不 import tkinter，普通 CLI 启动不支付 GUI 初始化。
- 折线/曲线一次批量调用；输入仅复制一次，不逐点来回调用 ZZY。
- 历史增量、共享只读路径块、按版本/误差缓存展开结果；缓存有容量/淘汰策略，不把 Drawing 身份当成全局永不释放键。
- 只更新变动对象/区域；每帧限制渲染工作，积压不拖住关闭按钮；可合并显示刷新，不合并改变错误顺序的绘图逻辑。
- 原子提交前计入几何、历史、消息及输出的预计容量；恢复/失败清理同样有用例，内存不足不能留下部分路径。
- 初始数值采用 [resources.md](../runtime/resources.md) 的扩展限额并与上下文预算共同生效；容量与关闭/取消分别验证，不能把逻辑预算宣称为进程内存硬上限。
- 分别测 1,000/10,000/100,000 笔画的生成、记录、渲染、undo、定位和导出；分别记录单笔/批量、多画笔/图层、首次/缓存成本和峰值内存，不预先承诺帧率或速度倍数。
- Python 对照采用相同几何、曲线误差、历史与序列化工作量；turtle 动画展示耗时不能直接充当解释器性能对照。

验收先使用 ZZY 黑盒核对位置/朝向、解析后的 SVG 几何和项目内容，配合固定答案与变形关系；原生层补线程归属、窗口关闭、满队列和取消清理；GUI 实测并记录字体/平台。默认一键测试覆盖 headless，声明 GUI 能力的发布另有离线 GUI 验收，不能将 GUI 未运行记为通过。类别见 [test-coverage.md](../development/test-coverage.md)。

## 9. 实施顺序与发布条件

| 阶段 | 内容 | 依赖与完成标准 |
|---|---|---|
| E1 绘图核心 | 注册类型、几何、样式、圆弧/路径/填充、SVG、配额 | P05/P06；ZZY 能 headless 生成并验证正确 SVG |
| E2 小画室视图 | 窗口、字体、多笔、图层、缩放/平移、基础工具 | E1；坐标转换/归属/关闭与缺 Tk 用例通过 |
| E3 历史和复用 | 分组撤销/重做、回放、Drawing/stamp、函数导出 | E2；撤销状态、确定回放、另一文件导入调用通过 |
| E4 交互和往返 | 事件/定时器、对象编辑、项目读写、容量和性能验证 | E3；画/改/存/重开/复用完整，指南/能力/黑盒同步 |

E1—E4 是用户已选的完整扩展实施目标；核心P05/P06已完成，E1—E4已全部验收，当前状态与后续任务见todo。E 可以在基础成熟后与 P07/P09 交错推进，不要求并行 Agent，不替代作业交付。未完成 E1—E4 不发布“完整 sketch 1.0”，延期时明确只交付设计/已有子集；PNG 缺依赖需明确标记。计划/状态分别见 [roadmap.md](../development/roadmap.md) 和 [todo.md](../development/todo.md)。

当前66个接口、固定扩展配额、曲线0.25逻辑单位近似、真实GUI平台与PNG不可用状态见[使用指南](sketch-guide.md)。SKETCH-01—06的完整映射及各项真实证据见tests/e4；历史E1子集报告不代替最终验收。
