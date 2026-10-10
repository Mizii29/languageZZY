# ZZY 诊断格式与错误示例

更新：2026-10-11｜diagnostic schema_version：1｜状态：基础格式、词法与 P02 数据/控制流诊断已实现；函数/单位等仍为期望输出

错误码和退出码以 [syntax.md](syntax.md) 为准，资源细则见 [resources.md](../runtime/resources.md)。本文件确定人和 Agent 可依赖的定位方式；不新增语言语法。

## 1. 输出约定

默认文本首行为 `文件:行:列: 错误码 消息`，随后可显示源码片段、定位标记和修复建议。诊断写 stderr，正常程序输出写 stdout。建议不自动修改源码；修复提示不能抹掉原始错误原因。

`--diagnostic-format json` 输出 UTF-8 JSON Lines：每行一个完整 JSON 对象，不在 stderr 混入文本标题、颜色代码或 Python traceback。字段固定为 schema_version、kind、code、file、span、message、notes；kind 为 error、trace、cancelled 或 internal_error，非 error 的 code 为 null。观察 `(@_@)` 使用 trace。notes 为字符串数组；错误码/位置/结构为稳定接口，消息和建议文字可改进，普通黑盒不对所有中文措辞做精确匹配。当前接入 info/source-info/lex/run/check；lex 支持 E101/E102/E211，run 增加最小语法 E103、顶层名称 E301/E302、执行类型/调用/写入 E201/E202/E203。P02 增加 E204/E205/E206/E208 和前端 E304；构造/with 字段清单错误 E203，未知字段访问 E302。input/range/array 的单一类型实参不符指向对应值表达式，len/str 的不支持类别指向调用左括号，下标错误指向左方括号，结构字段注解不符指向值表达式。观察语句与其余阶段能力仍待实现。

CLI 明确设置标准流的 UTF-8 编解码及约定换行行为，不依赖 Windows 控制台代码页猜测；重定向到管道也保持相同协议。预算不足时裁剪可选源码片段/notes 和消息内容，保留完整合法 JSON 记录；文件名异常长仍无法容纳时使用 file=null，并在短消息中说明定位被省略，不能输出半条记录。中断/内部缺陷没有 code 时，文本格式也不硬造错误码。

span 为 `{start: {line, column}, end: {line, column}}`，从 1 开始、右端不含；列按原文 Unicode 码点，不按 UTF-8 字节、终端字形宽度或解码字符串长度。开头 BOM 不计列；CRLF 整体是一次换行，源码 span 换算必须保留与原文的映射，制表符计一个码点。EOF 错误可用起止相同的零宽 span。制表符/宽字符的屏幕下划线由渲染器另做显示换算，不改机器坐标。

file 为诊断对应文件路径：CLI 默认输出相对进程工作目录的路径，无法表示时用绝对路径；目录分隔符在 JSON 中统一为 `/`。源码/配置尚未成功读入时可有 file 而 span 为 null；无对应文件的 CLI 参数错误二者为 null。缺文件不能伪造第 1 行的源码位置。

P01 基线采用首个错误即停止：源码词法、语法、名称/静态检查均先于执行；运行错误中止当前 run。未执行分支的运行时类型错误不提前报告。将来多错误恢复另列能力，不许为了输出更多错误执行 check 中的用户表达式。

定位选择：未声明名称指向标识符；未闭合字符串/注释指向起始标记；二元类型/量纲错误指向运算符；参数/字段注解不符指向对应值表达式。跨函数错误保留最内层主位置，并在 notes 补调用位置；Lazy 缓存错误保留首次主位置并补当前 wake 位置，不复制整份源码到记录里。

P01-01 的 lex 开发入口约定：未闭合/含物理换行的字符串为 E101，主位置是起始双引号；raw 后缺字符串为 E101，主位置是完整 `(raw)`；错误转义 E102 指向完整 `[OoO]` 及存在的非法后缀，不吞掉结束引号。词法扫描失败前不输出 Token；输出阶段的资源错误可能保留此前完整 Token 记录，但退出码仍为 2。Token 输出格式见 [项目 README](../../README.md)，它不表示完成语法检查或执行。

## 2. 四个独立的非法程序

每段单独保存为所列文件。普通 run/check 的静态错误退出 2；运行错误退出 1。测试清单预期到这些错误时，该用例应通过。

### 未声明变量：name.zzy

```text
io.print(total);
```

期望 E302，主位置第 1 行第 10—14 列（span 终点为 15），run/check 均退出 2。先声明 total，例如在前面加入 `(zno) total := 0;`；不会真的打印。

对应 JSON 记录：

```json
{"schema_version":1,"kind":"error","code":"E302","file":"name.zzy","span":{"start":{"line":1,"column":10},"end":{"line":1,"column":15}},"message":"名称 total 尚未声明","notes":["请先声明该名称，再使用它。"]}
```

### 布尔值参与加法：type.zzy

```text
io.print(1 + (true));
```

期望 run 在第 1 行第 12 列的 `+` 报 E201，span 为 [12,13)，退出 1；check 不执行运算，不提前报此运行时错误。若想输出真假则直接打印 Bool，若想计数则通过分支显式使用 0 或 1。

### 缺少多行注释结束词：comment.zzy

```text
zzysayalot:
这段注释还没有结束
```

期望 E101，指向第 1 行 `zzysayalot:`，span 为 [1,12)，run/check 退出 2。补上完整词 `zzyend`，建议独占一行；不能用引号包起来试图屏蔽注释正文中的结束词。

### 时间与长度相加：unit.zzy

```text
io.print(2::s + 1::m);
```

期望 run 在第 1 行第 15 列的 `+` 报 E213，span 为 [15,16)，退出 1；check 可检查单位名，但不执行此加法。应使用相同量纲，例如 `2::s + 1::s`；若原意是速度，应明确写长度除以时间。

## 3. 边界与回归要求

资源诊断附限制键/上限，最终记录仍受预留诊断容量控制。Ctrl+C 使用 cancelled、code 为 null、CLI 退出 130；测试中的取消/超时由运行器汇总为失败。内部实现缺陷使用 internal_error、code 为 null，按发生阶段退出 2/1，提示这是解释器问题；不能把所有未知宿主异常改写为 E201 或失败 Result 来伪装用户输入错误。

P01 起收录以上 .zzy 和期望清单，尚未支持的语法示例按阶段加入，不能假装早期版本已支持 Quantity。P06 补全 CLI-02：BOM、CRLF、中文/补充平面字符、制表符、EOF 零宽、缺文件 null span、JSON Lines 可解析、trace/error 区分、跨文件调用和 Lazy 位置；两种显示格式对应同一个诊断对象。
