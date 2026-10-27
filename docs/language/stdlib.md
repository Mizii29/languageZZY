# ZZY 标准库接口契约

更新：2026-10-14｜标准库版本：v0.6.1｜核心语法：v0.6｜状态：P05 已实现本文核心接口，证据见 tests/p05；sketch独立扩展见其验收记录，Web/db/num待各自阶段

语言规则见 [syntax.md](syntax.md)。下面集中规定 P01—P05 的公开接口，消除旧示例的裸 `print`、`push`、`safe_int` 等名称。类型标签是说明，不引入新语法；`A` 表示任意合法 ZZY 值，`Result<A>` 仅描述载荷，源码不支持泛型。

## 1. 调用与错误约定

所有宿主接口通过注册表调用，参数数量和外层类型先检查；Bool 不作为 Int。调用错误为 `E202`，类型错误为 `E201`，程序错误沿用语法契约的诊断；可预期的数据或 I/O 失败返回 `(T_T)(String)`。不能用一个 broad catch 将控制流、配额、取消和所有 Python 异常统一吞成 Result。

只暴露正式契约登记的函数；不开放任意 Python 属性、`eval`、`exec`。`io`、`array`、`text`、`math`、`data`、`unit` 命名空间与宿主函数引用只读。已选 `sketch` 的独立接口以 [sketch.md](../features/sketch.md) 为准；`web`、`db`、`num` 属于后续扩展，当前不属于核心安装依赖。原生类型/函数的签名、归属、错误和效果元数据统一登记；查询白名单不会自动接受扩展函数。

## 2. 基础与 I/O

| 接口 | 返回与行为 | 边界 |
|---|---|---|
| `len(value)` | Int，接受 Array/String/Map/Range | String 按码点，Range 按边界算长度，不展开数组；其他类型错误 |
| `str(value)` | String，基础标量转换 | 接受 Int/Float/String/Bool/Null/Quantity；Quantity 用 machine-units 的确定性基础单位格式，Bool 为 `true/false`，Null 为 `null`；容器使用 JSON 或调试显示 |
| `range(start, stop, step)` | Range，三个非 Bool Int，半开区间 | 不设默认参数；零步长 `E208`，负步长允许 |
| `wake(value)` | 缓存载荷或普通诊断 | 参数必须 Lazy；不隐式解包 Result |
| `io.print(value)` | Null，stdout 写值并换行 | 恰好一个参数；标量使用 str；容器用确定性调试格式，循环引用显示 `<cycle>`，不输出对象地址 |
| `io.input(prompt)` | String 或 Null | prompt 必须 String，stdout 输出提示并 flush；去掉一组 LF/CRLF，EOF 为 Null，空行是空 String |
| `io.read_text(path)` | Result<String> | UTF-8 严格读取，不处理 `[OoO]`；路径错误、读取失败、编码失败为失败 Result |
| `io.write_text(path, content)` | Result<Null> | 两参数均 String；UTF-8 写入并覆盖，成功载荷 Null；不自动创建父目录，写入失败为失败 Result |
| `io.write_atomic(path, content)` | Result<Null> | 两参数均 String；完整生成受限 UTF-8 后，宿主独占创建同目录临时文件，写入/关闭后替换目标；替换前失败保留原文件，不自动建目录 |

`io.write_text` 不承诺原子持久化；CLI 应用可优先使用已实现的 `io.write_atomic`，将唯一临时文件的独占创建、写入、关闭和替换封装在宿主，失败清理临时文件。不能先“检查文件不存在”再普通覆盖创建，以免竞争；并发成功保存采用最后一次替换胜出，不承诺业务级事务。

低层 `io.replace_file(source, target)` 已在 P05 实现，参数为 String，成功 Result<Null>、文件操作失败为失败 Result；调用者须先关闭完整源文件。同目录临时文件方案不承诺断电后已落盘，replace 跨文件系统不承诺成功。应用测试覆盖写入/关闭/替换失败保留旧文件、并发临时文件不互相覆盖；类型/资源错误不吞成 I/O Result。

输入/输出或源码运行资源超限为执行错误，不能假装 EOF 或正常文件失败。整数转文字受宿主长度限制时转换为明确 `E211`；不要全局关闭 Python 的资源限制来掩盖问题。

## 3. 数组与统计

| 接口 | 行为 | 空值、修改和错误 |
|---|---|---|
| `array.copy(values)` | 新 Array，元素引用浅拷贝 | 空数组得到新的空数组 |
| `array.push(values, value)` | 原地追加，返回 Null | 活动遍历期间先报 `E206`，不修改 |
| `array.pop(values)` | 原地删除并返回末元素 | 空数组 `E204`；活动遍历期间 `E206` |
| `array.sum(values)` | 全部元素必须 Int，返回任意精度 Int | 空数组为 0；Bool/Float/混合元素 `E201`；不修改源 |
| `array.stats(values)` | 全部 Int，一次遍历返回 `array.Stats` | 空数组 count=0、sum=0、min/max=Null；不修改源 |
| `array.sorted(values)` | 新 Array，稳定升序 | 非空输入必须全 Int 或全 String；混合、Bool、Float 暂拒绝；不修改源 |
| `array.map(values, callback)` | 按下标顺序逐项回调一次，返回新 Array | 回调一个实参；错误立即停止，不返回部分结果 |
| `array.filter(values, callback)` | 同样顺序逐项回调一次，保留返回 true 的元素引用 | 回调结果必须 Bool；空输入不调用回调 |

`array.Stats` 为宿主提供的固定结构：`count`、`sum` 为 Int，`min`、`max` 为 Int 或 Null，后两字段第一版无类型注解，因为没有联合类型。每次调用产生新结构，不缓存统计结果。

所有数组写入必须经过统一接口。保存 `structural_version`（增删/重排）和 `content_version`（任何元素替换、增删/重排）；别名和宿主写入也更新版本。map/filter 活动期间适用 [syntax.md](syntax.md) 的遍历限制，异常退出亦释放计数。

逐项元素赋值即使组合成交换，也按允许的替换处理；禁止的是增删和专门的原地重排操作，不声称能判断任意算法是否在重排。第一版只有返回新数组的 sorted。应用按 Task 优先级排序时可用 ZZY 手写稳定排序；不能把 Task 数组直接交给只接受 Int/String 的 sorted。

当前契约将 sum/stats 限制为 Int，便于与逐项整数加法严格等价。浮点聚合日后须另外定义算法；不能把普通左折叠、Python `sum` 和 `math.fsum` 认为结果完全一样。Python 3.12 起改变了浮点 sum 算法，见 [Python 官方 sum 说明](https://docs.python.org/3/library/functions.html#sum)。

## 4. 文本与数学

| 接口 | 行为与失败 |
|---|---|
| `text.trim(value)` | String 去掉两端空白，范围采用宿主 Unicode 空白判定并记录 Python 版本；不改内部空白 |
| `text.join(values, separator)` | Array 中全部 String，separator 为 String；空数组返回空字符串；一次拼接 |
| `text.split(value, separator)` | String 按非空 String 分隔，保留空片段；空分隔符 `E208` |
| `text.contains(value, needle)` | 两个 String，返回 Bool；空 needle 为 true |
| `text.replace(old, new, value)` | 三个 String，替换全部非重叠匹配并返回新 String；old 为空时报 `E208` |
| `text.safe_int(value)` | String 去掉两端 ASCII 空格/制表/CR/LF，接受可选 `+/-` 加至少一个 ASCII 十进制数字；成功 Result<Int> |
| `math.abs(value)` | Int/Float 对应绝对值，不接受 Bool，不改变类型 |

`text.safe_int` 拒绝小数、指数、分隔下划线、全角数字及空文本，返回失败 Result；参数不是 String 是程序类型错误。过长转换触及执行资源限制为 `E211`，不伪装成格式错误。

## 5. Map 与 JSON

| 接口 | 行为与边界 |
|---|---|
| `data.map()` | 新的空 Map；只支持 String 键 |
| `data.kind(value)` | 恰好一个任意合法 ZZY 值，返回 String 类别标签，见下文；无副作用、不解包或唤醒 |
| `data.has(map, key)` | Bool，判断 String 键是否存在 |
| `data.get(map, key)` | 已有键的值；缺键 `E204`，不以 Null 混淆缺失与显式 Null |
| `data.set(map, key, value)` | 设置或覆盖键，返回 Null，受冻结约束；新键追加到插入顺序 |
| `data.keys(map)` | 新 Array，键按插入顺序；不暴露可写宿主视图 |
| `data.parse(text)` | 标准 JSON 转 ZZY 值，成功 Result<A>，格式/数据不支持为失败 Result |
| `data.stringify(value)` | 成功 Result<String>；不可表示的值或循环引用返回失败 Result，不修改输入 |

`data.kind` 是 v0.6.1 的最小补充，用于在调用 has/get、索引或注解构造之前校验外部数据。返回值固定为 `"null"`、`"bool"`、`"int"`、`"float"`、`"string"`、`"array"`、`"map"`；其余合法值统一为 `"other"`。严格区分 Bool/Int 及 Int/Float，不遍历容器，不泄漏 Python 类型名，不执行用户回调；Function、结构、Result、Lazy、Machine、Quantity、Range、模块/定义和原生值都归 other。参数数量错误仍 E202。第一版只服务普通应用校验，不自动加入查询纯调用白名单，不引入类型反射语法。

例如解析得到根值后先比较 `data.kind(root) == "map"`，再检查必需键；检查失败由应用显式返回失败 Result。不能直接给任意 JSON 值套 Task 注解、触发不可恢复 E201，再声称应用能恢复坏数据。完整应用校验方案见 [campus-app.md](../development/campus-app.md)。

JSON 对象为 Map，数组为 Array，布尔/空值保留各自类型；无小数点/指数的数字为 Int，其他 JSON 数字为有限 Float。解析拒绝重复键、NaN/Infinity、浮点溢出和孤立代理码点；ZZY 字符串转义不应用到 JSON 数据。

序列化结构为字段对象，Map 只允许 String 键；按字段声明/Map 插入顺序输出，紧凑 UTF-8，采用标准 JSON 引号和转义。不自动解包 Result，不唤醒任何 Lazy；Function、Lazy、Result、Range、Machine、Quantity、模块与结构/状态机定义均拒绝，嵌套在结构字段中也拒绝。循环检测只检查当前递归路径，重复但不构成循环的共享引用允许分别展开。输入容量、深度和输出容量受资源上限约束。

通用 JSON 文件往返保留 Int 数字，ZZY 可读回大整数；这不保证 JavaScript 精确读到大数。HTTP 默认只允许 `[-(2^53-1), 2^53-1]` 的整数，超出范围拒绝；需要大整数的字段必须在接口契约里显式定义十进制 String，双向转换也据此执行。禁止随数值大小偷偷改变同一字段的 JSON 类型。精度边界见 [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259.html#section-6)。

Python `json` 默认接受非有限数和重复键，因此包装层须设置严格输出（如 `allow_nan=False`）、显式拒绝非标准常量和重复键，并检查解码后的 Float 是否有限；`parse_constant` 本身拦不住 `1e400` 溢出。见 [Python JSON 兼容性说明](https://docs.python.org/3/library/json.html#standard-compliance-and-interoperability)。

输入长度/层数、数字长度与容器数量在解析分配前或过程中检查，输出采用有界片段收集，不能先构造无限大结果再检查。递归检测用受限显式栈或检查后的深度，宿主 RecursionError/MemoryError 转统一资源诊断 E211；容量超限不伪装格式失败 Result。Array/Map/结构写入与 native 批量操作共用资源、冻结和版本入口。

具体默认值与生效配置按 [resources.md](../runtime/resources.md)，普通文件路径相对进程工作目录；只有 use 的模块路径相对导入文件。JSON 类型检查、数值容量和严格格式分别判定，资源错误优先保持 E211，不将“太大”改成失败 Result。

## 6. 后续扩展的发布条件

Web 需要另列 Request/Response、路由、状态码、Content-Type、JSON 校验、事务与超时契约；Python 嵌入需要列明加载与调用接口、可转换类型及上下文所有权。`web.get/web.json/web.serve` 在其他文档中仅为方向示例，不能由 Agent 推断为已支持。

新库先补接口契约、ZZY 黑盒用例和示例，再发布能力清单。NumPy 固定宽度数值不能替代核心 Int；可选库需自己的溢出、转换、依赖版本和公平基准说明。

## 7. 单位库（P05 已实现）

量纲、倍率、精确值和显示规则以 [machine-units.md](../features/machine-units.md) 为准；不自行添加复合单位字符串解析或丢精度的取值接口。

| 接口 | 行为 | 边界 |
|---|---|---|
| `unit.make(value, unit_name)` | 新 Quantity，value 为 Int/有限 Float，unit_name 为固定单位 String | Bool/其他类型 `E201`，未知单位 `E306`；Float 从实际二进制值转有理数，不推测十进制意图 |
| `unit.format(quantity, unit_name)` | String，按目标固定单位精确换算，不修改数量 | 非 Quantity/String `E201`，未知单位 `E306`，量纲不符 `E213`；整数或约分有理数加 `::单位`，不舍入 |

两接口恰好两个实参，否则 `E202`；执行资源超限 `E211`，不吞成失败 Result。比如 `unit.format(2::s + 500::ms, "ms")` 的预期文字是 `2500::ms`。目标只接受固定单位表，第一版不支持 `"m/s"`；派生量纲使用 `str` 的规范显示。format 结果是显示文字，不作为 make 的输入。

状态机发送是语言运算 `<<`，无需另外注册 machine 库。Machine 没有通用浅拷贝接口，实例状态保存须显式取 `.state`。数学 abs、整数 sum/stats、排序等原接口不自动扩展到 Quantity。

## 8. v0.6 查询的原生纯调用名单

[query.md](../features/query.md) 的条目可调用 `len`、`str`、`math.abs`、`text.trim`、`text.contains`、`unit.make`、`unit.format`，接口签名/类型/错误保持本文件既有规则；P05 已实现这些核心接口。注册表标记固定函数身份、ABI 和纯性，Resolver 依据实际绑定核对名单；遮蔽后的同名用户函数、动态函数、任意扩展的 pure 标记不能放行。

纯性只表示无用户可见修改/I/O/隐式唤醒，资源与类型错误仍传播。查询不自动批量调用这些函数，不绕过检查；新增白名单函数须另补契约和 QUERY-03 验证。

查询本身是语法，不再添加同义 query 库。可复用查询通过既有 `(addnew)` 和 `(use)` 封装/导出，输出仍为普通 Array；JSON、stats、sorted 等不会因数组来自查询就放宽类型。

## 9. 已选 sketch 扩展（独立版本）

完整接口以 [sketch.md](../features/sketch.md) 为唯一来源：固定参数、受控原生类型、绘图/历史/事件、SVG/项目/图案函数导出与失败边界。默认通用 JSON 拒绝 Canvas/Pen/Layer/Color/Drawing，普通 Position/LayerInfo 快照按结构规则处理。资源/类型/状态错误仍为诊断，不吞成文件失败；可预期 I/O、依赖与格式失败返回 Result。

原生登记与 Tk 初始化分开；check只读接口元数据、不执行用户程序，headless运行正常执行几何及文件操作，两者均不初始化Tk。GUI能力以独立真实窗口验收为准；PNG没有独立后端时明确标为不可用。

实际接口、固定限额、平台与验收见[sketch使用指南](../features/sketch-guide.md)。五种受控类型均有实际入口，Position/LayerInfo为冻结普通快照。几何、SVG、图层/文字、历史/回放、图案、事件与项目已实现；PNG明确不可用。核心v0.6.1签名不变，扩展ABI为1.0，验收见tests/e4。
