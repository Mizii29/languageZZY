# ZZY 语法与语义契约

作者：赵梓伊｜更新：2026-10-09｜语法契约版本：v0.6｜状态：待实现；本文不是运行成功的证明

本文是解释器、测试、示例和 Agent 使用的统一规则来源。[语法参考](../../skills/syntax.md) 按编程场景解释规则，[design详细版.md](../design详细版.md) 归纳完整设计，[stdlib.md](stdlib.md) 定义库接口；[machine-units.md](../features/machine-units.md) 细化已选状态机和数量机制，[query.md](../features/query.md) 细化已选集合查询，[sketch.md](../features/sketch.md) 定义已选画笔扩展。作业约束始终以只读的 [requirement.md](../requirement.md) 为准。实现不足时标注未支持，不能通过修改契约伪装测试通过。

## 1. 功能边界与状态

| 范围 | 内容 | 落地阶段 | 当前状态 |
|---|---|---|---|
| 核心语言 | 基本值、声明赋值、数组结构、I/O、分支循环、函数 | P01—P03 | 未实现 |
| ZZY 特色 | Result、匹配、`?`、Lazy、管道、断言、观察、spec、状态机、带单位数值、集合查询 | P04 | 未实现 |
| 库与模块 | 批量库、文件/JSON/Map、模块 | P05 | 未实现 |
| 画笔扩展（E，已选） | sketch 原生类型、绘图/图层、撤销/回放、项目和函数导出 | P05/P06 后 E1—E4 | 未实现 |
| 后端扩展 | HTTP/JSON、Python 嵌入、数据库、请求隔离 | P08，可选 | 未实现 |
| 深入创新 | 校验缓存、接口合约、配额、VM 等 | P10，按证据选择 | 未实现 |

核心解释器先使用 Python 标准库。Web、NumPy、VM 都不作为完成基本作业的前置条件。暂不支持泛型、类继承、隐式类型转换、任意 Python 属性访问、动态执行源码、比较链、字典字面量、字符串插值和用户新增词法符号。

## 2. 词法和源码位置

- `.zzy` 文件按 UTF-8 严格读取，允许文件开头一个 UTF-8 BOM。支持 LF/CRLF；空白和注释不结束语句。
- 单行注释以完整裸串 `zzysay:` 开始，到 LF/CRLF 或文件末尾结束；多行注释以 `zzysayalot:` 开始，以完整结束词 `zzyend` 结束。起始串的冒号必须紧邻，不加括号。`#` 不再是 ZZY 注释标记，在字符串/注释外为非法字符；`//` 仍是整数除法。
- 标识符区分大小写，采用 Python `str.isidentifier()` 对应的 Unicode 标识符范围，保留输入拼写，不做 Unicode 归一化。数字字面量只使用 ASCII 数字。
- 行列从 1 开始，列按源码 Unicode 码点计数，制表符计一个码点；内部 span 为原文半开区间。不要用 UTF-8 字节数或字符串解码后的长度算列号。
- 复合符号按最长匹配处理：`:=`、`<-`、`::`、`=>`、`-->`、`--`、`->`、`<<`、`..<`、`~>`、`?>`、`//`、`<=`、`>=`、`==`、`!=`。`-->` 优先于 `--`/`->`/`-`，`<<` 优先于 `<`，`?>` 优先于 `?`；紧邻 `--x` 不再表示双重负号，改写为 `-(-x)` 或 `- - x`。
- `(` 开头时先匹配下列完整固定符号，否则是表达式左括号。固定符号内不允许空格或全角括号；字符串和注释只按各自规则扫描。

| 类别 | 固定写法 |
|---|---|
| 绑定与函数 | `(zno)`、`(zyes)`、`(addnew)`、`(return)` |
| 分支与循环 | `(zif?:)`、`(zzif?:)`、`(zzyf:)`、`(for)`、`(in)`、`(while)`、`(break)`、`(continue)` |
| 结构与逻辑 | `(shape)`、`(machine)`、`(with)`、`(and)`、`(or)`、`(not)` |
| 字面量与特殊形式 | `(true)`、`(false)`、`(null)`、`(raw)`、`(zzz)`、`(spec)` |
| 模块 | `(use)`、`(as)` |
| 查询条目与方向 | `(keep)`、`(order)`、`(take)`、`(yield)`、`(asc)`、`(desc)` |
| 预置类型 | `(Int)`、`(Float)`、`(String)`、`(Bool)`、`(Null)`、`(Array)`、`(Map)`、`(Function)`、`(Result)`、`(Lazy)`、`(Range)`、`(Machine)`、`(Quantity)` |
| 颜文字 | `(^_^)`、`(T_T)`、`(?_?)`、`(o_o)`、`(@_@)` |

上表关键字及预置类型的裸名称保留；`_` 只作匹配通配符。`wake`、`len`、`str`、`range` 和库函数是普通预置绑定。预置绑定不可重新赋值，同一顶层不能重声明；内层可遮蔽，优化必须识别实际绑定。旧版短关键字不作为别名。

注释标记属于词法规则，保留用户指定的裸串，不遵循控制关键字的括号形式；裸名称 `zzysay`、`zzysayalot`、`zzyend` 同样保留。起始标记只在正常源码的词项边界识别，不能从其他标识符中间截出注释，例如 `myzzysay:` 不是注释。两个起始串按完整拼写区分，不仅比较共同的 `zzysay` 前缀。

多行注释不嵌套；其中的引号、颜文字、`zzysay:`、`zzysayalot:` 都作为注释正文，不开启其他扫描模式。第一个左右均不是标识符延续字符的 `zzyend` 结束注释；延续字符采用同一 Unicode 标识符规则。例如 `zzyending`、`my_zzyend`、`zzyend中文` 不结束注释，正文中的 `"zzyend"` 会结束，因为注释内引号没有字符串含义。建议结束词独占一行，但允许行内结束。

单行注释内的 `zzyend` 不结束该行注释；普通/raw 字符串内的所有注释标记都是文本。多行注释到 EOF 仍未闭合报 `E101`，位置指向 `zzysayalot:`；正常源码中的裸 `zzyend` 报 `E101`。注释作为词项间空白跳过，不生成 AST 或运行指令，不能删掉后把两侧名字拼成一个；保留换行及原文位置用于诊断。

```text
zzysay: 统计三项成绩
(zno) scores := [80, 90, 100]; zzysay: 行尾注释

zzysayalot:
这里可写多行说明，(zif?:) 和 [OoO]n 都不作为语法执行。
zzyend

io.print(array.sum(scores));
```

整数为一个或多个十进制数字，前导零允许；负号是一元运算。浮点字面量必须有小数点且两侧均有数字，例如 `3.0`，暂不接受指数、十六进制和数字分隔符。`0..<5` 必须识别为整数、区间符、整数。

## 3. 字符串：只解码一次

普通字符串使用双引号，不允许物理换行。反斜杠是普通字符，不沿用反斜杠转义。

| 源码内容 | 解码结果 |
|---|---|
| `[OoO]n` / `[OoO]t` / `[OoO]r` | 换行 / 制表 / 回车 |
| `[OoO]q` | 双引号 |
| `[OoO]b` | 反斜杠 |
| `[OoO][OoO]` | 字面上的 `[OoO]` |

完整 `[OoO]` 后遇未知后缀或直接到结尾，报 `E102`；不完整的类似文本如 `[Oo` 是普通内容。解码后不再递归解释，例如 `"[OoO][OoO]n"` 得到字面 `[OoO]n`。Lexer 应直接消费原始转义序列，不能先全局替换再寻找引号。

`(raw)` 后下一个非空白、非注释词项必须是双引号字符串，完全跳过转义；其中双引号仍结束字符串。`(raw)"C:\tmp\log.txt"` 合法，但第一版没有在 raw 字符串中嵌入双引号的机制。`/` 保留为除法和 URL 中的普通字符。

运行时输入和 JSON 字符串均为数据，不再解码 `[OoO]`。JSON 使用标准 JSON 转义。

## 4. 核心语法骨架

下面的 EBNF 定义合法形式，字符串中的标点是 ZZY Token，`{...}` / `[...]` 在 EBNF 中分别表示重复 / 可选。`IDENT`、`INTEGER`、`FLOAT`、`STRING` 是词法终结符；`STRING` 的扫描模式由前置 `(raw)` 决定。列表允许一个末尾逗号，空列表不允许只写逗号。

```text
program       = { statement } ;
block         = "{" { statement } "}" ;
statement     = binding | assignment | function | shape | machine | if_stmt
              | while_stmt | for_stmt | match_stmt | spec_stmt | use_stmt
              | return_stmt | break_stmt | continue_stmt | assert_stmt
              | trace_stmt | block | expr ";" ;
binding       = ("(zno)" | "(zyes)") IDENT [":" type] ":=" expr ";" ;
assignment    = target "<-" expr ";" ;
target        = IDENT { "." IDENT | "[" expr "]" } ;
type          = BUILTIN_TYPE | qualified ;
qualified     = IDENT { "." IDENT } ;
function      = "(addnew)" IDENT "(" [parameters] ")" ["->" type] block ;
parameter     = IDENT [":" type] ;
parameters    = parameter {"," parameter} [","] ;
lambda        = "(addnew)" "(" [parameters] ")" "=>" expr ;
shape         = "(shape)" IDENT "{" {field} "}" ;
field         = IDENT [":" type] [":=" expr] ";" ;
machine       = "(machine)" IDENT "{" edge {edge} "}" ;
edge          = IDENT "--" STRING "-->" IDENT ";" ;
quantity      = (INTEGER | FLOAT) "::" IDENT ;
construct     = qualified "::" "{" [initializers] "}" ;
initializers  = initializer {"," initializer} [","] ;
initializer   = IDENT ":" expr ;
if_stmt       = "(zif?:)" expr block {"(zzif?:)" expr block}
                ["(zzyf:)" block] ;
while_stmt    = "(while)" expr block ;
for_stmt      = "(for)" IDENT "(in)" expr block ;
return_stmt   = "(return)" [expr] ";" ;
break_stmt    = "(break)" ";" ;
continue_stmt = "(continue)" ";" ;
match_stmt    = "(?_?)" expr "{" arm {arm} "}" ;
arm           = pattern "=>" block ;
pattern       = scalar_pattern | "_" | "(^_^)" "(" IDENT ")"
              | "(T_T)" "(" IDENT ")" ;
scalar_pattern = ["+" | "-"] (INTEGER | FLOAT) | STRING | raw_string
              | "(true)" | "(false)" | "(null)" ;
assert_stmt   = "(o_o)" expr ";" ;
trace_stmt    = "(@_@)" expr ";" ;
spec_stmt     = "(spec)" STRING block ;
use_stmt      = "(use)" STRING "(as)" IDENT ";" ;

expr          = pipeline ;
pipeline      = transition {"~>" stage} ;
transition    = update ["<<" update] ;
stage         = callable "(" stage_args ")" ;
callable      = primary {"." IDENT | "[" expr "]"} ;
stage_args    = stage_arg {"," stage_arg} [","] ;
stage_arg     = "@" | expr ;
update        = query {"(with)" "{" [initializers] "}"} ;
query         = logic_or {"?>" query_block} ;
query_block   = "{" [keep_clause] [order_clause] [take_clause] yield_clause "}" ;
keep_clause   = "(keep)" ":" expr ";" ;
order_clause  = "(order)" ":" expr [("(asc)" | "(desc)")] ";" ;
take_clause   = "(take)" ":" expr ";" ;
yield_clause  = "(yield)" ":" expr ";" ;
logic_or      = logic_and {"(or)" logic_and} ;
logic_and     = logic_not {"(and)" logic_not} ;
logic_not     = "(not)" logic_not | equality ;
equality      = comparison [("==" | "!=") comparison] ;
comparison    = interval [("<" | "<=" | ">" | ">=") interval] ;
interval      = sum ["..<" sum] ;
sum           = product {("+" | "-") product} ;
product       = unary {("*" | "/" | "//" | "%") unary} ;
unary         = ("+" | "-") unary | postfix ;
postfix       = primary {"(" [args] ")" | "[" expr "]" | "." IDENT | "?"} ;
args          = expr {"," expr} [","] ;
primary       = quantity | INTEGER | FLOAT | STRING | raw_string | IDENT
              | "(true)" | "(false)" | "(null)" | "@" | "(" expr ")"
              | "[" [args] "]" | construct | lambda
              | "(^_^)" "(" expr ")" | "(T_T)" "(" expr ")"
              | "(zzz)" "(" expr ")" ;
raw_string    = "(raw)" STRING ;
```

`BUILTIN_TYPE` 对应第 2 节预置类型 Token，仅出现在类型位置。数字后接 `:: IDENT` 是数量字面量，限定名字后接 `::{` 是结构构造；单位位置只查固定单位表，不查同名变量。数字 Token 保存原文，准备阶段按对应字面节点转换一次；Quantity 十进制小数不先转 Float。赋值按表达式目标后是否出现 `<-` 区分。Parser 还必须拒绝同一不带分组的比较链，包括 `a < b == c`；显式 `(a < b) == (true)` 合法。

管道阶段恰好一个直接参数为 `@`；其他参数中不可出现 `@`（包括内嵌查询的当前项），第一版连含独立插槽的嵌套管道也拒绝，可先将内层管道结果绑定为变量。调用结果作为阶段的函数时必须括起来，如 `x ~> (factory())(@)`。`(with)`、管道左结合，`(not)` 位于比较之下；所以 `(not) x == y` 是 `(not) (x == y)`。更新后取字段写 `(task (with) {done: (true)}).done`。

`(shape)`、`(machine)`、`(use)`、`(spec)` 仅允许文件顶层；具名函数允许嵌套。结构、状态机定义、函数、分支、循环、匹配、测试和独立块结束后不加 `;`，其他语句必须加 `;`。空结构合法，空匹配非法。

## 5. 类型、数值、相等与下标

| 规则 | 约定 |
|---|---|
| Int | 任意精度整数；Bool 不是 Int |
| Float | 有限双精度浮点数；字面量、运算或宿主返回的 NaN/Infinity 均拒绝 |
| 注解 | 可选，初始化、重新绑定、字段写入、实参和返回时检查实际类型；Int 不隐式满足 Float 注解 |
| Array/Result/Lazy 注解 | 只检查外层类型，不意味着检查元素或载荷 |
| 自定义结构/状态机注解 | 按定义身份检查，字段或图相同的另一种定义不自动兼容 |
| 登记的原生类型注解 | sketch.Canvas/Pen/Layer/Color/Drawing 使用已有 qualified 形式，按登记类型身份检查；仅工厂创建，不开放任意宿主属性或结构构造 |
| Machine | 可变状态机实例；定义可调用，构造恰好一个初始状态 String；`.state` 只读 |
| Quantity | 不可变数量，保存精确有理数与量纲；注解只检查外层类型，具体规则见第 12 节 |
| `+ - * /` | 两个普通数接受 Int/Float 混合，普通数 `/` 始终返回 Float；两个 String 可用 `+` 拼接；Quantity 另按第 12 节 |
| `// %` | 只接受两个 Int；向下取整，满足 `a == (a // b) * b + a % b` |
| 数值失败 | 除零为 `E205`；浮点非有限、必要提升超范围为 `E208`；不能静默截断大整数 |
| `and/or/not` 与条件 | 只接受 Bool；前两者短路，不能套用 Python 对象真值 |
| `== !=` | 总能比较合法值；不同非数值类型不相等，`(true) == 1` 为 false，`1 == 1.0` 为 true |
| 数值相等及排序比较 | 比较实际数学值，不先把大 Int 强制转 Float；String 排序按 Unicode 码点字典序 |
| Array/Map/结构/Function/Lazy/Machine/模块/结构或状态机定义相等 | 按对象身份；Quantity 按量纲及精确数值；Result 按标签及载荷的这些相等规则比较；Range 按起止步长比较 |
| 下标 | Array/String 仅接受非 Bool 的 Int，`0 <= index < len`；无负索引与切片，越界 `E204` |
| String 长度与遍历 | 按 Unicode 码点，索引结果为单码点 String，不宣称按字形计算 |

不支持字符串与数字隐式相加，也不允许数组相加或重复。数值转换、容器操作见 [stdlib.md](stdlib.md)。任意精度不表示无限资源；过深调用、过大文本转换或分配失败应给资源诊断，不泄漏 Python 异常。

## 6. 绑定、闭包和求值顺序

`(zno)` 禁止重新绑定，`(zyes)` 允许重新绑定；两者对数组、Map、结构、Machine 默认共享引用，不自动深度冻结；Quantity 自身不可变。同一块重复声明为 `E301`，内层可以遮蔽；声明初始化期间该名字不可读，不能借同名外层绕过自引用检查。名字按词法位置先声明后使用。

具名函数在解析其函数体前登记自身，支持自递归；未预声明的相互递归不支持。每次调用、每次块执行和每轮循环都有独立绑定实例。`for` 变量为该轮不可重新绑定的新绑定，闭包不会全部捕获最后一轮的值。

被函数或 Lazy 捕获的可变绑定通过共享 Cell 保存；不可变捕获可保存值，但其容器对象仍共享。Cell 由实际捕获者持有，离开栈帧后仍有效。Lazy 捕获也必须参与 Resolver 的捕获分析，不能只分析匿名函数。

普通运算从左到右，调用先求被调用对象，再从左到右求实参，然后检查可调用性、数量与注解并进入函数；前一求值报错则停止剩余求值。短路、Lazy 和 `?` 是明确的例外。

赋值先定位目标：保存实际容器和下标，各子表达式只求值一次；检查可写性，再求右侧，最终写入前重新检查下标和类型。若右侧改变了容器长度，不能用过期位置写入。程序错误不会回滚已经发生的输出或其他副作用。

## 7. 数组、结构与循环

数组字面量每次执行创建新数组。数组别名指向同一对象；元素修改与追加分别遵循第 5 节和库契约。

遍历 Array 时设置该对象的活动遍历计数；`for`、`array.map/filter` 等结束或异常退出时都释放。期间允许替换现有元素，尚未访问的位置读取当时的值；禁止通过任何别名或宿主接口增删，以及调用原地重排操作，必须在禁止动作发生前报 `E206`，原数组保持不变。逐项赋值按允许的替换规则处理，不试图判断它是否组成了“交换”；第一版 sorted 始终返回新数组。单靠长度或事后版本检查不能保证这个语义。

`a..<b` 为步长 1 的半开 Range；`a >= b` 时为空。`range(start, stop, step)` 支持负步长，零步长报错；区间只保存边界，不提前构造数组。`for` 只接受 Array/String/Range，并只求集合表达式一次。

`break/continue` 作用于当前函数内最内层循环；进入函数要重置循环上下文，不能跳出调用者的循环。`while` 每轮重新求 Bool 条件。

结构字段集合和顺序在定义时固定。`Type::{...}` 拒绝缺必填、未知、重复字段；先检查字段清单，再按源码顺序求显式值并检查类型，然后按字段声明顺序求缺省值。默认表达式在结构定义处的词法环境中每次构造求值，不可引用正在构造的其他字段。

**每次求值不等于深拷贝。** 默认值 `[]` 每实例新建；默认值为外部数组名字时，得到的仍是外部数组引用。需要独立数据应写新建表达式或显式复制，不许解释器暗中改变引用语义。

`value (with) {field: expr}` 求原值一次，检查字段后按源码顺序求更新值，创建同结构的新实例；不重跑默认表达式。未替换字段仍共享引用。字段写入允许，但类型约束、冻结状态和字段存在性均需检查。

## 8. 函数、Result 与匹配

函数参数固定位置，不支持默认参数、变长参数、命名实参。参数本身允许重新绑定；有注解时仍检查类型。匿名函数为单表达式并返回其值。普通具名函数无显式返回则得到 `(null)`；`-> (Int)` 等函数此时必须报告返回类型错误。

`(^_^)(value)` 与 `(T_T)(message)` 恰好一个参数；失败消息必须 String。格式错误的输入、文件不存在等可预期失败由库返回 Result；未声明名字、类型错误、越界等程序错误仍是解释器诊断。

后缀 `?` 只允许位于显式 `-> (Result)` 的具名函数：成功解包，失败立即返回同一个失败 Result。成功路径仍需显式返回 `(^_^)(value)`。顶层、匿名函数和 Lazy 的直接表达式禁止 `?`；Lazy 内调用另一个合法 Result 函数不受此限制。

匹配只求目标一次，从上到下选第一个匹配分支；结果模式将载荷绑定为分支局部不可重新绑定名字。常量模式按第 5 节相等规则；`_` 必须最后且只能一次；重复结果标签/相等常量模式在检查阶段拒绝。无分支命中为 `E207`，第一版没有完整静态穷尽检查。

## 9. Lazy 与管道

`(zzz)(expr)` 是特殊 AST 节点，创建时不求 expr。首次 `wake` 读取捕获绑定当时的值，之后缓存该值或普通运行时诊断；Result 失败是普通值。缓存数组等对象的引用，不复制，不随数据变化刷新。

| 状态 | wake 行为 | 下一状态 |
|---|---|---|
| NEW | 标记求值中并执行表达式 | RUNNING |
| RUNNING | 循环唤醒错误 `E209` | 由外层求值记录为 FAILED |
| READY | 返回缓存值，不执行副作用 | READY |
| FAILED | 报缓存诊断，保留原失败位置并补本次 wake 位置 | FAILED |

RUNNING 成功变 READY，普通错误变 FAILED。执行配额、取消和宿主级中止是执行上下文失败，不能永久缓存成用户值；清理正在求值标志后中止本次执行。第一版单线程执行，不共享同一可变 Lazy 给并发请求。

普通运行时错误终止当前 run，语言没有 try/catch；同一 Lazy 再次报告缓存诊断的验证需通过后续公开嵌入 API 多次调用同一上下文完成，不能伪造普通脚本可在致命错误后继续。第一版 ZZY 黑盒验证首次错误与 Result 失败值缓存，宿主层另外验证 FAILED 状态。

管道 `source ~> function(@, other)` 先求 source 一次，再求右侧函数及其余参数，按参数位置放入已保存值，最后调用；各阶段从左到右。不自动解包 Result、wake Lazy 或合并回调，不能改变错误、输出、数据库访问顺序。

## 10. 模块、测试和诊断

`(use) "campus.zzy" (as) campus;` 以导入文件所在目录解析路径，使用规范绝对路径标识模块，扩展名必须 `.zzy`。顶层具名函数、结构和状态机定义导出；其他绑定不导出，别名和导出表只读。模块在每个执行上下文第一次导入时初始化一次，循环导入为 `E303`。

`check` 递归读入依赖并解析、检查名字和控制流，**不执行导入初始化、结构默认值、状态机实例构造/转换、函数、I/O、Web 注册或 sketch 绘图/窗口/事件**。状态图校验、单位名查表与字面值准备可静态进行，原生扩展仅读取类型/签名元数据，不执行一般运算表达式。这里只检查可判定的规则，不能承诺排除所有运行时类型错误。

可共享的是只读 Program/AST/绑定布局；运行中的模块实例、Cell、数组、函数捕获环境、Lazy、Machine 实例均归本次 ExecutionContext。程序缓存键包含规范源码路径、源码哈希、语言版本、编译选项（含有效资源策略指纹）、宿主 ABI 和依赖版本；只凭文件名、mtime 或主文件哈希不足以避免陈旧依赖。

缓存以同一批已读取字节的内容哈希和依赖图建立快照，不先哈希后重新读取另一版本。缓存有条目/字节上限与淘汰策略；淘汰不影响仍被执行上下文持有的 Program。源码/数字长度、Token 数、语法嵌套和依赖深度/总量在相应分配或递归前受限，核心阶段就落实资源诊断，不等待可选 P10 请求配额。资源、取消、用户诊断和内部控制信号使用统一边界区分。

`(o_o)` 必须 Bool，false 为 `E210`；断言不展开重算子表达式。`(@_@)` 只求值一次，把源码位置和确定性值显示写 stderr，不改变正常 stdout。

`run` 跳过顶层 spec 的执行，但仍检查语法和名字。`test` 对每个 spec 建立全新执行上下文、重新执行公共初始化，仅执行所选 spec；导入模块、全局容器、Lazy、临时目录及 stdin 也隔离。公共初始化应避免启动服务或要求交互。普通 `.zzy` 输出脚本和非法源码由测试清单走真实 CLI，不能只依赖断言自身。

测试运行器汇总通过、失败、超时和收集错误；空集合、清单损坏、子进程异常或超时均非成功。全部用例执行以 ZZY 源码为对象，Python 只负责进程和期望比对。

| CLI 情况 | 退出码 |
|---|---|
| run/check 成功或全部测试通过 | 0 |
| 运行时错误、断言失败、测试失败/超时/收集失败 | 1 |
| 单文件词法/语法/解析错误、CLI 参数或源码读取错误 | 2 |
| 用户 Ctrl+C 中断单次 CLI 执行，完成取消清理 | 130 |

集中维护错误码：`E101` 词法、`E102` 转义、`E103` 语法；`E201` 类型、`E202` 调用、`E203` 写入、`E204` 下标、`E205` 除零、`E206` 遍历修改、`E207` 匹配未覆盖、`E208` 数值范围、`E209` Lazy 循环、`E210` 断言、`E211` 资源、`E212` 状态机初始状态、`E213` 量纲不兼容、`E214` sketch 操作状态（扩展启用时）；`E301` 声明、`E302` 名称、`E303` 模块、`E304` 控制流、`E305` 状态机定义、`E306` 单位名称、`E307` 查询作用域/纯性；`E401` CLI/源码 I/O。资源限额在前端触发退出 2，在执行阶段触发退出 1；测试汇总失败仍退出 1。错误码必须与覆盖表一致，不直接显示 Python traceback。

拟议 `--diagnostic-format json` 输出带 `schema_version`、`kind`、`code`、`file`、`span`、`message`、`notes` 的 stderr 记录。span 使用原文位置；调试值不得出现随机对象地址。观察记录用不同 kind，不能和错误混淆。该选项已用于 P00 基础 CLI；语言诊断待后续阶段接入。

具体格式、首错停止、BOM/CRLF 坐标、无源码的 null span 和四类错误样例见 [diagnostics.md](diagnostics.md)。取消不冒充 E211；未分类的内部实现缺陷使用 internal_error 记录，按发生阶段退出 2/1，不吞成普通 Result。默认资源数值、配置指纹、容量/取消清理和测试超时见 [resources.md](../runtime/resources.md)。以上补充不改变 EBNF；标准库 v0.6.1 增加 data.kind 供应用检查外部数据，不改变查询白名单。

## 11. 验证义务

每条公开规则在 [test-coverage.md](../development/test-coverage.md) 中对应正常、边界和错误场景。优化前后检查结果、stdout/stderr、错误码、发生位置、求值次数及共享引用语义；新引擎不能仅凭“最终数值一样”通过。

当前已有 P00 基础设施测试，但没有语言执行器测试、性能数据或已实现的语言创新。文档静态检查只能说明文档格式和交叉引用有效。

## 12. 已选核心机制：状态机与数量

完整规则、固定单位表、显示格式、资源和性能义务见 [machine-units.md](../features/machine-units.md)，该文件是本契约的细化部分。

- 状态机边为 `todo -- "start" --> doing;`；至少一条边，同一源状态/解码事件重复报 `E305`。`Progress("todo")` 每次新建实例；未知初始状态为 `E212`。`p << event` 成功先准备 Result 再写入并返回 `(^_^)(新状态 String)`；找不到边返回固定格式失败 Result，状态不变。冻结发送为 `E203`，别名共享当前状态，`.state` 不允许直接写。
- `<<` 从左到右各求值一次，低于 `(with)`、高于 `~>`；连续发送不隐式串联，`p << a << b` 拒绝。`(p << event)?` 服从既有 Result 传播规则。
- 数量字面量如 `2::s`、`0.1::s`。固定支持时间 `ms/s/min/h`、长度 `mm/cm/m/km` 和无量纲 `one`，名称区分大小写，其他名称为 `E306`。单位名不是全局保留词，也不是可替换的变量值。
- 数量十进制字面按原文生成精确有理数，基础单位为米/秒；普通 Float 不变。数量同量纲才能加减或排序，不同为 `E213`；乘除合成量纲，标量参与乘除只接受 Int/有限 Float，Float 按实际二进制值提升。Quantity 的除法即使无量纲也返回 Quantity，零除数为 `E205`。
- 数量相等比较量纲和精确数值，与普通数字不隐式相等；`// %`、索引、Range 和数量常量匹配不支持。`unit.make`/`unit.format` 接口见 stdlib；显示不承诺可重新作为源码或无损 JSON 解析。
- JSON 拒绝 Machine、状态机定义和 Quantity；结构字段中含这些值也拒绝。共享冻结递归覆盖 Machine，实例不放入共享 Program；不可变状态图和 Quantity 字面值可准备一次复用。

A/C/D 已纳入 P04 的实施目标，仍未实现；B 未采纳，不属于语法表。

## 13. v0.6 已选 A：集合查询

完整规则与函数封装见 [query.md](../features/query.md)，该文件是本契约的细化部分。

- `source ?> {...}` 输入仅接受 Array，输出新 Array；条目顺序固定为可选 keep/order/take 与必需 yield，每项最多一次。keep 为 Bool，order 单键稳定排序，take 为非 Bool 非负 Int，yield 提取每项结果。
- `?>` 左结合，低于逻辑比较、高于 with/发送/管道；整体查询参加比较/取下标需分组。`@` 在 keep/order/yield 内是当前元素，take 禁止；与管道唯一直接插槽区分，其他位置使用或捕获为 `E307`。
- 条目仅接受规定的纯读取 AST 和按实际绑定确认的原生白名单调用，不允许发送事件、I/O、写入、结构默认求值、动态/用户函数、Lazy、匿名函数、传播、内嵌查询/管道。query 文档列出完整边界；未知名字仍 `E302`，违反查询作用域/纯性为 `E307`。
- 先求输入一次并浅快照，再求 take 一次；完整 keep 阶段后才计算所有保留项的 order 键，随后稳定排序/截取，最后按输出顺序 yield。任何错误即停止，不返回部分结果；take=0 仍校验全部筛选和排序，不隐藏潜在错误。
- order 键统一为 Int/有限 Float 数值、String 或同量纲 Quantity；Bool/其他类型拒绝，混合类别 `E201`、不同量纲 `E213`。desc 相等键也保持输入顺序；排序不重算键，不强制把大 Int 转 Float。
- 查询条目/绑定布局可解析一次复用，当前项、快照、键和结果每次独立；check 不执行查询。封装为普通导出函数，不提供未经选择的自动依赖刷新或新的 query.compile 接口。

## 14. 已选 E：sketch 画笔扩展

[sketch.md](../features/sketch.md) 是独立扩展契约，核心 EBNF 不变。sketch 命名空间/原生类型由注册表提供，只开放固定接口；不可变图案可以导出普通 ZZY 函数，可变文档、回调和窗口不进入共享 Program 或通用 JSON。GUI 的线程分工不允许同一 ExecutionContext/Lazy 并行求值；默认 headless，check 不初始化 Tk。E1—E4 均待实现；其他新增场景及动漫/游戏主题未纳入。
