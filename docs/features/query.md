# ZZY 集合查询契约

更新：2026-10-08｜版本：v0.6｜状态：用户已选择 A，正式设计目标；解释器尚未实现

本文细化 [syntax.md](../language/syntax.md) 的集合查询，C/D 规则见 [machine-units.md](machine-units.md)，已选 E 绘图扩展见 [sketch.md](sketch.md)。B（自动依赖刷新）未选择；其他新增场景和动漫/游戏主题未纳入。

## 1. 四步挑出想要的数据

查询按“留下 → 排序 → 取几个 → 拿出信息”组织，结果总是新 Array：

```text
(shape) Task {
    title: (String);
    done: (Bool);
    priority: (Int);
}

(zno) tasks := [
    Task::{title: "数学作业", done: (false), priority: 3},
    Task::{title: "买书", done: (true), priority: 5},
    Task::{title: "英语练习", done: (false), priority: 2},
    Task::{title: "项目报告", done: (false), priority: 5},
];

(zno) titles := tasks ?> {
    (keep): (not) @.done;         zzysay: 留下未完成的任务
    (order): @.priority (desc);   zzysay: 越紧急越靠前
    (take): 2;                   zzysay: 只取前两个
    (yield): @.title;             zzysay: 拿出任务名称
};

(o_o) len(titles) == 2;
(o_o) titles[0] == "项目报告";
(o_o) titles[1] == "数学作业";
```

这里的 `@` 是“当前这一项”。与 `~>` 管道把整份上一步结果放进某个参数不同，查询中的 `@` 会随着当前元素改变；不会变成可在外部引用的变量。

## 2. 语法、优先级与作用域

```text
query         = logic_or {"?>" query_block} ;
query_block   = "{" [keep_clause] [order_clause] [take_clause] yield_clause "}" ;
keep_clause   = "(keep)" ":" expr ";" ;
order_clause  = "(order)" ":" expr [("(asc)" | "(desc)")] ";" ;
take_clause   = "(take)" ":" expr ";" ;
yield_clause  = "(yield)" ":" expr ";" ;
```

- `keep/order/take` 各可省略，yield 恰好一次且必须最后。顺序固定，重复或未知条目为 `E103`；不把任意块或 Python 语句解释成查询。缺 keep 表示全部保留，缺 order 表示保持输入顺序，缺 take 表示不截取，缺方向默认为 `(asc)`。
- 查询是表达式，外层绑定/返回语句仍以 `;` 结束。`?>` 左结合，优先级低于逻辑比较、高于 `(with)`、`<<` 和 `~>`。整个查询结果参加比较/取下标时用分组，例如 `(items ?> {(yield): @;})[0]`。
- `@` 可出现在 keep/order/yield 表达式内部，包括字段、下标和允许的纯函数实参；take 中禁止出现。外部变量按原有词法绑定规则读取，不能以查询重新声明它们。
- 第一版查询条目内部不允许嵌套查询、管道、匿名函数、Lazy 或 Result 传播；因此 `@` 不会被闭包捕获或误当管道插槽。普通管道其他参数仍禁止出现 `@`，包括内嵌查询；需要时先绑定查询结果再送入管道。
- 多次查询可在外层链起来，例如 `items ?> {(yield): @;} ?> {(take): 2; (yield): @;}`。源码中的 `@` 由所在查询绑定，只在条目求值时有效；普通表达式中使用为 `E307`。管道直接插槽仍服从既有 PIPE 规则。

## 3. 第一版只接受可确认无副作用的条目

允许普通标量/Quantity 字面、名字读取、当前项、只读字段/下标、数组字面、普通算术/比较/逻辑，以及下列已登记宿主函数的调用：

| 范围 | 允许的纯调用 | 实施阶段 |
|---|---|---|
| 预置绑定 | `len`、`str` | 核心已有相应接口时 |
| 宿主库 | `math.abs`、`text.trim`、`text.contains`、`unit.make`、`unit.format` | P05 对应库实现后 |

纯表示不进行用户可见写入、I/O 或隐式唤醒，不表示永远成功；类型错误、缺字段、除零、资源错误等仍按原规则发生。数组字面每次实际求值创建新数组，yield 返回已有可变值时仍保留引用。

字段读取只使用 ZZY 固定结构或契约登记的无副作用值属性，不执行任意 Python property/getter。sketch.layer_info 在查询外生成普通结构快照，再查询 name/visible 等字段；不把 sketch 函数或可变句柄加进纯调用白名单。

调用必须在 Resolver 阶段确认实际被调用对象是名单里的不可变原生绑定。内层同名用户函数/变量、动态取出的函数、用户函数（即使看起来没有打印）均不能靠拼写进入白名单。P04 的核心验收不依赖尚未实现的 P05 库。

不允许赋值、Machine 发送、I/O、可变数组/Map 操作、wake、结构构造（默认表达式可能有副作用）、with、匿名函数、Lazy、后缀 `?` 或动态调用。越出允许 AST/原生绑定范围为前端 `E307`，指向对应表达式；先声明后使用和未声明名字仍适用 `E302`。不通过运行函数后观察“有没有修改”来假装静态纯性已确认。

## 4. 确定的执行顺序

1. 求输入表达式一次，要求 Array，否则 `E201`；创建有界的浅快照，保留每项原始下标。原数组不修改，不自动复制元素里的嵌套对象。
2. 若有 take，求其表达式一次（不可使用 `@`），要求非 Bool Int 且不小于零；类型为 `E201`，负数为 `E208`。没有 take 不执行任何隐含表达式。
3. 按原始下标顺序对每项求 keep 一次，结果必须 Bool；未通过的项不计算 order/yield。keep 缺省时直接保留，不调用隐藏函数。
4. 全部筛选成功后，按保留项原始顺序各求 order 键一次，并立即校验键和已建立的键类别。全部键成功后稳定排序；排序比较不重算键表达式。
5. 排序后截取前 take 项；省略或超过保留数量时取全部。按最终顺序各求 yield 一次，生成新 Array。没有 order 时仍保持筛选后的输入顺序。

空输入依然求输入、创建新结果并求/校验 take，但不求 keep/order/yield。take 为 0 仍完成全部筛选和 order 键校验/排序，yield 不执行；不能利用截取提前隐藏后面会发生的错误。发生错误即终止当前 run，不返回部分数组；诊断保留表达式原文 span，可补原始输入下标说明。

输入表达式可按普通语言规则进行 I/O 或修改对象；纯性限制只作用于查询条目。输入求值已产生的副作用不会因后续错误回滚。第一版单线程且条目纯读取，不设置原输入的活动遍历计数；语义基于开始时的浅快照。

## 5. 稳定排序的键规则

- 非空保留集的键必须统一为普通数值（允许 Int/有限 Float 混合）、String 或 Quantity；Bool、Null、Array、Map、Result、Lazy、Machine 等不接受，类别不符为 `E201`。
- 普通数值按实际数学值比较，不先把大 Int 转 Float；String 按 Unicode 码点。Quantity 键必须同量纲，不同报 `E213`，按基础单位精确值比较。
- 没有保留项时不建立键类别，不求 order 表达式，因此不能提前执行或常量折叠其潜在错误。
- `(asc)` 和 `(desc)` 均稳定：相等键保持原输入顺序。不能将稳定升序结果整体反转来实现 desc，反转会破坏相等项的顺序。
- 排序只接受一个键表达式；多键、分组、连接、去重和增量刷新以后再选择，不提前增加语法。

结果是普通 Array，外层注解不验证其元素；yield 可返回任意合法值，后续 JSON/数组库接口继续检查实际值，不能因来自查询就放行 Quantity 或 Machine。

## 6. 封装成现成函数和库

不新增一种“查询导出”语法，直接使用既有具名函数与模块导出：

```text
(addnew) urgent_titles(tasks: (Array), limit: (Int)) -> (Array) {
    (return) tasks ?> {
        (keep): (not) @.done;
        (order): @.priority (desc);
        (take): limit;
        (yield): @.title;
    };
}
```

把函数存入 `task_tools.zzy`，另一份程序按既有 `(use)` 规则导入：

```text
(use) "task_tools.zzy" (as) task_tools;
(zno) result := task_tools.urgent_titles(tasks, 2);
```

后一个片段假定调用文件已经声明 tasks，不是独立可运行文件。P04 验证函数封装，P05 再验证模块导出。查询 AST/绑定布局可复用，输入、take 值、当前项、键和结果归每次调用，不缓存上一次答案；外部可变数据变化后再次调用会重新查询，不代表自动响应式刷新。

## 7. 实施与性能义务

- P01 固定表增加 `?>` 和六个括号条目/方向 Token，裸名称按统一保留规则处理。`?>` 比 `?` 优先；字符串和注释不解析查询。Lexer 不为了匹配 `@` 去推断具体输入类型或执行表达式。
- P04-08 在 P04-05 前实现 QueryExpr/CurrentItem、条目顺序、作用域/纯调用检查、浅快照、分阶段执行与稳定键排序。`check` 检查结构/名字/纯性但不运行输入、take、keep/order/yield。
- P05 原生注册表对纯调用使用固定函数身份和 ABI 元数据，与 [stdlib.md](../language/stdlib.md) 对齐；不能仅以 `pure=True` 放行未列入名单的扩展。模块封装沿用现有规则。
- P06 将 [test-coverage.md](../development/test-coverage.md) 的 QUERY-01/02/03 转为真实黑盒，包括空数组、take=0、相等键 desc、Int/Float 大值、Quantity 键、别名、阴影绑定和错误顺序。
- P07 分开测扫描、查询准备和执行，比较等价 Python 筛选/键准备/稳定排序/截取/映射；输入快照、错误校验和状态复位计时范围相同。

基线输入 n 项、保留 k 项、输出 r 项，时间包括完整筛选、k 个键和排序、r 次投影；排序比较目标 O(k log k)，量纲/大数比较另有成本，快照空间 O(n)。键只算一次，固定条目可用简洁计划表示减少中间 AST 分派；收益必须测量。

快照/键/结果空间在分配前检查，阶段内可复用索引缓冲、及时释放不再需要的键；不能把 yield 写回仍充当输入的快照，或因缓冲复用提前求投影/改变错误位置。大数/Quantity 比较的临时分配同样受资源限制。

第一版不提前终止筛选、不自动融合带错误的条目、不将 order+take 偷换成堆选择、不把用户回调批量交给 Python。纯性不能消除错误顺序的可观察性，优化仍需对照诊断、求值次数和引用行为。源码风格、少写代码和实际速度分别报告。
