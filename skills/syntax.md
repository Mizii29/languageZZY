# ZZY 语言语法规则

更新：2026-10-13｜适用设计：语法 v0.6、标准库 v0.6.1｜状态：P04 特色语法及此前子集已实现；本页完整示例未逐一运行，能力以根 README 为准

本文面向编写 ZZY 的开发者，按使用场景说明规则。完整 Token、EBNF 和语义以 [正式语法契约](../docs/language/syntax.md) 为准，函数签名见 [标准库契约](../docs/language/stdlib.md)。各代码块作为独立文件阅读；只有明确标注文件关系的模块示例需要组合。

## 1. 源文件与基本形式

文件扩展名为 `.zzy`，按 UTF-8 编码，允许开头 BOM 与 LF/CRLF 换行。名字区分大小写，支持契约规定的 Unicode 标识符，数字字面量只用 ASCII 数字。关键字使用半角括号，固定拼写内部不能加空格。

普通语句以 `;` 结束，代码块用 `{}`。函数、结构、状态机、分支、循环、匹配、spec 和独立块结束后不加分号。换行不自动结束语句。列表可有一个末尾逗号，但空列表不能只放逗号。

```zzy
(zno) greeting := "你好，ZZY！";
(zyes) count: (Int) := 1;
count <- count + 1;
io.print(greeting);
io.print(count);
```

`(shape)`、`(machine)`、`(use)`、`(spec)` 只允许文件顶层；具名函数允许嵌套。关键字、预置类型的裸名字及注释标记保留，`_` 仅作为匹配兜底。`io.print`、`wake`、`len` 等是预置绑定，不是括号关键字。

## 2. 注释与字符串

```zzy
zzysay: 单行注释到行尾或文件末尾
zzysayalot:
多行注释，不允许嵌套。
zzyend

(zno) message := "第一行[OoO]n第二行";
(zno) path := (raw)"C:\tmp\notes.txt";
(zno) literal := "[OoO][OoO]n";
io.print(message);
io.print(path);
io.print(literal);
```

注释起始词的冒号必须紧邻。多行结束词 `zzyend` 两边不能是标识符延续字符，建议独占一行；注释正文中的引号没有保护作用。字符串内不识别注释。`#` 不是注释，`//` 是整数除法。

字符串用双引号，不允许物理换行。转义只在读取源码时解码一次：

| 写法 | 含义 |
|---|---|
| `[OoO]n`、`[OoO]t`、`[OoO]r` | 换行、制表、回车 |
| `[OoO]q`、`[OoO]b` | 双引号、反斜杠 |
| `[OoO][OoO]` | 字面的 `[OoO]` |

反斜杠本身是普通字符。`(raw)` 后的字符串不解码转义，但双引号仍结束它，不能借 raw 嵌入双引号或跨物理行。JSON、文件输入及已解码文本不会再执行 ZZY 转义。

## 3. 声明、类型与相等

`(zno)` 禁止名字重新绑定，`(zyes)` 允许重新绑定；二者都用 `:=` 初始化，后续用 `<-` 赋值。`==` 只用于比较。类型注解可省略，有注解时会检查初始化、赋值、实参、字段和返回值。

核心预置类型有 Int、Float、String、Bool、Null、Array、Map、Function、Result、Lazy、Range、Machine、Quantity，类型位置写成 `(Int)` 等。自定义结构类型直接写名称，导入或原生类型可用限定名称。

- Int 任意精度但有资源限额；Float 必须有限。浮点字面需写成 `3.0`，暂不支持指数、十六进制或数字分隔符。
- Bool 使用 `(true)` / `(false)`，空值为 `(null)`；Bool 不视为 Int。Int 不自动满足 Float 注解。
- Array、Result、Lazy 注解只检查外层类型，不提供泛型或元素类型保证。
- 普通数值按实际数学值比较，`1 == 1.0` 为真，`(true) == 1` 为假。
- Array、Map、结构、Function、Lazy、Machine 等按身份相等；Result 按标签及载荷规则，Range 按起止步长，Quantity 按量纲与精确值比较。

`(zno)` 不会冻结对象：

```zzy
(zno) values := [1, 2];
(zno) alias := values;
alias[0] <- 9;
(o_o) values[0] == 9;
```

同一块不能重复声明，内层允许遮蔽。名字先声明后使用，不能在自身初始化表达式中读取自己，也不能借同名外层绕过该限制。

## 4. 表达式与优先级

下表从高到低；括号分组可改变结合方式，完整边界见正式 EBNF。

| 层级 | 写法 |
|---|---|
| 后缀 | 调用 `f(...)`、下标 `[i]`、字段 `.name`、Result `?` |
| 一元 | `+`、`-` |
| 乘法 | `*`、`/`、`//`、`%` |
| 加法 | `+`、`-` |
| 区间 | `..<` |
| 大小比较 | `<`、`<=`、`>`、`>=` |
| 相等 | `==`、`!=` |
| 逻辑非 | `(not)` |
| 逻辑与、或 | `(and)` 高于 `(or)` |
| 查询 | `?> { ... }` |
| 结构更新 | `(with) { ... }` |
| 状态发送 | `<<` |
| 管道 | `~>` |

普通 Int/Float 的 `/` 返回 Float，`//` 与 `%` 只接受 Int，整数除法向下取整；Quantity 除法另按单位规则。String 可与 String 相加，不与数字隐式拼接。数组不能直接相加或重复。

不允许比较链或连续状态发送；`a < b == c` 和 `p << x << y` 都不合法。`(not) x == y` 表示 `(not) (x == y)`。`--` 属于状态机箭头符号，双重负号写 `-(-x)`。

条件与逻辑操作只接受 Bool，and/or 短路。普通求值从左到右；调用先求被调用对象，再求实参，最后检查可调用性、数量与类型。赋值先定位并检查目标，再求右侧，提交前复查下标与类型。

## 5. 分支与循环

```zzy
(zno) score := 85;
(zif?:) score >= 90 {
    io.print("优秀");
}
(zzif?:) score >= 60 {
    io.print("通过");
}
(zzyf:) {
    io.print("继续练习");
}

(zyes) total := 0;
(for) number (in) 0..<5 {
    total <- total + number;
}
(while) total < 12 {
    total <- total + 1;
}
io.print(total);
```

`for` 只遍历 Array、String 或 Range，集合表达式只求一次；String 按码点遍历。`a..<b` 是步长 1 的半开区间，`a >= b` 时为空。`range(start, stop, step)` 三个参数必填，支持负步长，拒绝零步长。

`(break);` / `(continue);` 只作用于当前函数的最内层循环。每轮 for 有新的不可重新绑定变量，闭包保留各自那一轮的绑定。Array 遍历期间可替换元素，但不能通过任何别名增删或调用原地重排操作。

## 6. 数组、结构与浅层更新

Array/String 下标从 0 开始，只接受非 Bool 的 Int；负索引、越界和切片均不支持。数组字面每次求值新建，`array.copy` 复制外层，元素引用仍共享。

```zzy
(shape) Task {
    title: (String);
    priority: (Int) := 1;
    done: (Bool) := (false);
}

(zno) task := Task::{title: "阅读语法"};
(zno) finished := task (with) {done: (true)};
(o_o) task.done == (false);
(o_o) finished.done == (true);
```

结构字段固定，构造拒绝缺必填、重复和未知字段。先检查字段清单，再按源码顺序求显式值，最后按字段声明顺序求缺省值。默认表达式在定义环境中每实例求值：`[]` 得到新数组，引用外部数组则仍共享；不能引用正在构造的其他字段。

`(with)` 创建同结构的新实例，只替换指定字段，不重跑默认值，也不深拷贝。更新后立即取字段写 `(task (with) {done: (true)}).done`。

## 7. 函数与闭包

```zzy
(addnew) add(left: (Int), right: (Int)) -> (Int) {
    (return) left + right;
}

(zno) double := (addnew)(value: (Int)) => value * 2;
io.print(add(2, 3));
io.print(double(4));
```

函数只支持固定位置参数，参数可重新绑定；没有默认参数、关键字实参或可变参数。具名函数无显式返回时得到 Null，有返回注解仍须检查。匿名函数只有单表达式，直接返回该值。

具名函数支持自递归，不支持未预声明的相互递归。每次调用和块进入有独立绑定；闭包与 Lazy 捕获可变绑定时共享它，固定绑定捕获的容器也不会自动复制。

## 8. Result、匹配与失败传播

```zzy
(addnew) parse_nonnegative(input: (String)) -> (Result) {
    (zno) value := text.safe_int(input)?;
    (zif?:) value < 0 {
        (return) (T_T)("需要非负整数");
    }
    (return) (^_^)(value);
}

(?_?) parse_nonnegative("12") {
    (^_^)(value) => { io.print(value); }
    (T_T)(reason) => { io.print(reason); }
}
```

`(^_^)(value)` 包装成功值，`(T_T)(message)` 包装 String 失败原因。`(?_?)` 只求目标一次，按顺序选择首个匹配分支，支持标量常量、两种 Result 模式和最后的 `_` 兜底。载荷绑定为分支局部固定名字；重复结果标签/相等常量模式拒绝，无分支命中报错。

后缀 `?` 仅能直接用于显式 `-> (Result)` 的具名函数：成功解包，失败返回同一个失败 Result；成功路径仍需显式包装。顶层、匿名函数和 Lazy 直接表达式不能使用它。语言没有 try/catch，类型、下标、资源错误不能靠 Result 自动捕获。

## 9. Lazy 与管道

```zzy
(zno) scores := [80, 90, 100];
(zno) pending := (zzz)(array.sum(scores));
io.print(wake(pending));
io.print(wake(pending));
(zno) total := scores ~> array.sum(@);
io.print(total);
```

Lazy 创建时不执行表达式，首次 wake 读取捕获绑定的当前值并缓存结果；后续返回缓存值/引用，不自动跟踪数据变化。普通运行错误可以被 Lazy 记录，但当前 run 仍终止；循环唤醒报错。资源和取消中止不永久缓存。

管道左侧只求一次。每阶段必须是调用，恰好有一个直接实参 `@`；不能把它藏进嵌套表达式，也不允许在其他实参中再出现查询或管道的 `@`。阶段从左到右，不隐式解包 Result 或唤醒 Lazy。

## 10. 集合查询

```zzy
(shape) Item {
    title: (String);
    priority: (Int);
    done: (Bool);
}
(zno) tasks := [
    Item::{title: "写测试", priority: 3, done: (false)},
    Item::{title: "读文档", priority: 1, done: (true)},
];
(zno) titles := tasks ?> {
    (keep): (not) @.done;
    (order): @.priority (desc);
    (take): 2;
    (yield): @.title;
};
io.print(titles[0]);
```

源必须 Array，条目依次为可选 keep/order/take 和必需 yield，每项最多一次。`@` 是当前项，take 不可使用它。缺 order 保持输入顺序，默认方向 asc；排序是稳定的，键支持普通数值、String 或同量纲 Quantity。

查询先取浅快照与 take，再完整筛选、求键/排序、截取、投影。take=0 仍执行筛选和排序检查。条目限制纯读取 AST 与正式白名单原生函数，禁止用户函数、I/O、赋值、状态发送、结构构造/with、Lazy、嵌套查询/管道和 `?`。`data.kind` 不在白名单中。完整规则见 [query.md](../docs/features/query.md)。

## 11. 状态机与数量

```zzy
(machine) Progress {
    todo -- "start" --> doing;
    doing -- "finish" --> done;
    done -- "reopen" --> todo;
}
(zno) progress := Progress("todo");
(zno) result := progress << "start";
io.print(progress.state);

(zno) duration := 2::s + 500::ms;
io.print(unit.format(duration, "ms"));
```

machine 至少一条边，拒绝重复“源状态+事件”；构造必须指定已知初始状态。发送成功返回 Result 并更新实例，失败返回失败 Result、状态不变；state 只读，实例别名共享状态。不包含动作回调或事件队列。

Quantity 保存精确有理数和量纲。固定单位为 ms/s/min/h、mm/cm/m/km、one；不支持 px、deg、温度或自定义单位。加减/排序要求同量纲，乘除组合量纲，无量纲结果仍是 Quantity；不得当下标、Range 或整数整除/取余操作数。

数量小数字面按原文精确转换，运行时 Float 提升保留其二进制实际值。直接打印 duration 使用基础单位 `5/2::s`，format 指定 ms 才得到 `2500::ms`。完整规则见 [machine-units.md](../docs/features/machine-units.md)。

## 12. 模块、Map 与标准库

库文件 `helpers.zzy`：

```zzy
(addnew) twice(value: (Int)) -> (Int) {
    (return) value * 2;
}
```

同目录调用文件 `main.zzy`：

```zzy
(use) "helpers.zzy" (as) helpers;
io.print(helpers.twice(3));
```

use 相对导入文件解析路径，目标必须 `.zzy`；顶层具名函数、结构和状态机定义导出，普通变量不导出。同一上下文初始化一次，循环导入拒绝。普通 io 文件路径则相对进程工作目录。

没有 Map 字面量；使用 data.map/set/get/has/keys。JSON 解析得到 Map/Array/标量，以 `data.kind` 先判断类别，再访问字段；其返回 null/bool/int/float/string/array/map/other 的 String 标签，不解包 Result/Lazy。以下命名空间按正式签名使用：

| 命名空间 | 主要用途 |
|---|---|
| io | 单参数 print、带提示 input、UTF-8 文件和原子写入 |
| array | 整数 sum/stats、全 Int 或全 String 的 sorted、复制/增删、map/filter |
| text | trim/join/split/contains/replace/safe_int |
| math | 契约只有 abs，P05 待实现 |
| data | Map、严格 JSON、kind |
| unit | 精确数量 make/format |

JSON 不自动编码 Result、Lazy、Function、Range、Machine、Quantity 或原生绘图句柄。类型检查、资源限制、循环引用及安全整数边界见标准库，不能凭函数名猜测额外重载。

## 13. 断言、观察与测试

```zzy
(spec) "整数求和" {
    (zno) values := [1, 2, 3];
    (o_o) array.sum(values) == 6;
    (@_@) values[0];
}
```

`(o_o)` 要求 Bool，false 触发断言失败；`(@_@)` 只求一次并写 stderr。run 跳过 spec 执行，但仍检查语法与名字；test 每例新上下文、重新初始化公共部分。非法源码须另存文件，由外部清单比较退出码和诊断，不能塞进会一起解析的正常 spec。

check 读取源码和依赖、完成前端检查，但不执行初始化、打印、默认值、查询或窗口。成功退出 0，运行/测试失败 1，前端/CLI 错误 2，取消 130；位置与示例见 [diagnostics.md](../docs/language/diagnostics.md)，容量见 [resources.md](../docs/runtime/resources.md)。

## 14. 扩展与暂不支持内容

sketch 是普通宿主库扩展，不增加 Token；完整接口、原生类型、线程和文件规则见 [sketch.md](../docs/features/sketch.md)。普通 headless/check 不初始化 GUI。Web、数据库、NumPy、VM 仍属可选后续，不能按方向示例推断已有 API。

不支持泛型、继承、默认/关键字/可变参数、比较链、负索引/切片、字典字面量、字符串插值、任意 Python 属性调用和动态执行源码。编写程序前先核对实际实现状态，再选择本参考中的功能。
