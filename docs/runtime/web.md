# P08 Web 与互联集中契约

2026-10-29。P08-01—05已完成实现与自动验收，SQLite及整体验收提交为0a70825；此前提交权限阻塞已解除。本轮人工主流程已完成[证据核验](../manual-tests/p08-20261028/manual-test-review.md)，共享模式重复操作按操作者备注确认。核心语法/stdlib ABI 不变。本文件是 Web 边界唯一规则来源，不将旧设计中的 web.get/web.post/web.json/web.serve 方向示例注册为可调用语言接口。

## 决策与范围

采用 Starlette 0.52.1 / Uvicorn 0.54.0，可选安装 `.[web]`。服务面向本机课程演示，默认127.0.0.1；无认证、TLS、跨域授权或互联网部署承诺。Python只承担协议、路由和通用转换，业务在ZZY。选择固定宿主路由表而不是启动时执行ZZY注册代码：默认模式启动只准备依赖图、校验入口，不产生业务副作用；显式shared模式的初始化时机见下节。源码/路由是启动快照，修改需要重启；无热更新或自动缓存。

默认shared=False每请求重新实例化整个模块与捕获环境；显式shared=True共享经递归校验/冻结的模块数据和只读Program。模式不自动切换，拒绝规则见P08-02一节。

## 实际入口与路由

`zzy.web.create_app(module, routes, *, page=None, timeout=5.0, workers=4, shared=False)` 返回ASGI应用。module为本地ZZY文件路径；routes为 `(method, path, function_name)` 序列，只支持GET/POST、以/api/开头的固定路径，不支持模板、查询串或片段。重复项、空表、缺失入口、非单参数顶层具名函数在启动时拒绝。函数实际类型/返回注解按原解释器校验。

`python -m zzy.web MODULE --route GET /api/hello hello --route POST /api/greet greet --page PAGE [--host HOST] [--port PORT] [--shared]` 使用Uvicorn。page是可选单个UTF-8 HTML文件，启动有界读取，仅在GET /提供，不开放目录遍历。GET /自动支持HEAD；API的HEAD/OPTIONS等均405，无自动CORS。缺路由404，不重定向尾斜杠。路由校验不运行模块初始化；默认初始化在每个请求中执行；--shared在服务启动时执行一次。

## Request / Response

Request是每请求新建的Map，五个键：method(String)、path(String)、query(Array of [String,String])、headers(Array of [String,String])、body(JSON值)。query/headers保留框架提供的顺序/重复项，不隐式合并；header名称按ASGI转小写。GET body必须为空并映射Null。POST要求application/json或application/json; charset=utf-8；大小写/首尾空白归一，其他参数/媒体类型415。非identity Content-Encoding拒绝，不自动解压。

业务函数必须返回Map或普通shape，字段恰好status与body。status必须Int（非Bool），200..599，排除204/205/304这些无正文状态；body为支持的JSON值。Content-Type由适配器固定application/json，不能注入任意响应头。示例中的Response为普通ZZY shape，自行构造，不提供隐式结果转换。业务可返回422和中文数据提示；不自动解包Result。

输入复用核心严格JSON codec，拒绝重复键、尾部额外数据、NaN/Infinity、非有限Float、非法UTF-8/孤立代理字符。Request元数据与body独立解析，body不能注入其他字段。Null/Bool/Int/Float/String/Array/Map按原标签转换，结构输出为字段对象。HTTP Int双向限于±(2^53-1)，大整数必须由字段契约显式约定十进制String；不会随值大小改变类型。字符串不执行[OoO]转义。循环引用、函数、Result、Lazy、Machine、Quantity、Range、原生句柄/定义拒绝；不唤醒、不解包、不开放Python属性/eval/exec。

## 容量、错误与生命周期

固定每请求body65536字节、响应/静态页65536字节、headers原始键值字节与query_string合计16384字节。流式读取在追加前检查；框架接收单块/解析HTTP头发生在适配器之前，不承诺OS或ASGI内存硬限。JSON及ZZY运行使用default-v1，将io_payload_bytes收紧至65536，其他核心限额不变；执行输出各1MiB，仅在请求私有缓冲，不混入HTTP。JSON嵌套沿用64层限制。

固定最多workers个正在收体或运行的请求（1..16，默认4），饱和503，不建立无限任务队列。ZZY在受控线程池执行，不直接占用事件循环；CPU执行仍受GIL影响，不承诺多核加速。timeout分别约束收体阶段和执行阶段（各默认5秒，0<值<=60），不是两个阶段共享的总期限。

错误响应形状为 `{"error":{"code":"..."}}`：非法JSON/GET带body为400；读体超时408；容量输入413；媒体415；元数据431；路径404/方法405；非法业务Response500 invalid_response；语言诊断500 zzy_error；内部错误500 internal_error；运行资源503 resource_limit；执行超时504 request_timeout。输入JSON核心配额失败也413 resource_limit。状态码/资源错误不冒充业务成功。内部诊断记录服务端源码位置，响应不泄漏路径、原始异常或Python堆栈。

超时/客户端断连/ASGI任务取消触发CancellationToken；解释器检查点及支持取消的原生操作退出并释放上下文。超时响应可先返回，执行槽直到线程真正退出才释放。取消不能强制打断任意阻塞宿主文件调用；服务关闭停止接单、取消全部活动令牌并等待池结束，永久阻塞宿主可能延迟关闭。不得将线程超时称为硬进程隔离。ZZY代码必须是服务拥有者信任的代码，本层不是文件系统沙箱。

## 阶段接口索引与后续任务

P08-02的实际共享模式和拒绝策略见下一节。

P08-03接口与转换规则见下文；当前开发验收状态以todo为准。内部RequestRuntime不属于公开嵌入API。

P08-04实际db接口与生命周期见文末SQLite契约；保留校园CLI及文件格式。

P08-05：完成上述跨接口、持久化、安装与交付验收；分项通过不等于互联阶段全部完成，不以页面成功代替后续验收。


## P08-02共享模式

新增create_app(..., shared=False)与CLI --shared。默认模式保持每请求实例化；显式共享模式在ASGI lifespan启动中初始化一次，之后不重跑初始化。启动允许受信任ZZY初始化的副作用，不属于check；失败不能发布部分快照。初始化使用独立计量、空stdin与有界私有输出，在线程池中执行并受同一协作取消期限约束。

共享图校验失败使用现有模块错误E303，定位服务入口模块根节点，消息说明拒绝类别；这是模块发布条件失败，不冒充某个表达式运行出错。真正的初始化求值错误保留其原始错误码与源码位置；请求写入冻结对象仍在写表达式报E203。E214继续仅用于sketch操作状态。

共享整个模块依赖图：所有模块级可变绑定、任何可达Lazy、捕获Cell的闭包及原生句柄拒绝（E303），不隐式降级。只读闭包递归检查captures和注解；结构定义的默认值仍在请求中求值，其全局捕获绑定全部纳入共享检查。Array/Map/结构/嵌套Machine通过现有写入口递归冻结；默认新数组按请求创建，默认引用共享数组保持冻结。共享命名空间别名不支持；内置命名空间的成员缓存字典按请求复制，启动时已构造的只读成员（包括array.Stats等名义类型定义）保持身份，之后的惰性缓存写入只属于该请求。

共享数据的预留由服务拥有，所有请求结束、线程池退出后才释放；每请求独立Binding映射/模块映射/Frame/计量/输入输出。共享数组遍历不修改active计数，冻结检查仍先于写入，普通可变数组的遍历规则不变。只读Program仍为固定启动快照；没有自动缓存、热更新或VM。

## P08-03 Python嵌入

公开入口为`from zzy.embedding import load_module, LoadedModule, CallResult, ConversionError`，核心安装即可使用，不导入Web/GUI。签名：

```python
load_module(path, *, policy=None) -> LoadedModule
module.exports -> tuple[str, ...]
module.call(name, *arguments, stdin="", cancellation=None) -> CallResult
module.close() -> None
```

policy为ResourcePolicy或None；cancellation为CancellationToken或None。load_module仅prepare入口及依赖快照，不执行初始化或spec。exports按源码顺序列出入口模块顶层具名函数，不暴露变量、导入别名、结构构造器或任意Python属性。call按名称及位置参数调用，可调用零参数/多参数函数；先检查name/stdin/cancellation的宿主类型，再检查关闭状态、导出名称和参数数量。未知名称LookupError、参数数量或宿主参数类型错误TypeError，在执行初始化前拒绝。ZZY内部参数/返回注解仍走原诊断。

每次call先在独立上下文中转换参数，再执行模块初始化及导出函数，最后转换结果，finally释放全部运行值、句柄和预留；默认空stdin即EOF，输出只进本次私有缓冲。返回冻结记录CallResult(value, stdout, stderr)，value是脱离上下文的Python数据树；失败不返回部分结果，原DiagnosticError、ResourceExceeded、Cancelled保持类别及定位，不自动包装成Result。Python调用点无ZZY表达式位置，参数注解诊断定位导出函数名；函数内部错误保留真实源码及调用notes。

支持`with load_module(...) as module`；退出调用close。close幂等，释放模块持有的Program/函数索引；关闭后exports/call/重新进入with均RuntimeError。可并发调用同一模块，每次独立初始化/状态/预算；有在途调用时close明确RuntimeError且模块仍开放，不暗中等待或取消。宿主须先cancel令牌并等调用结束，再close。同步API不创建后台线程、不设置隐式超时；取消沿用协作检查点，不能强制打断任意阻塞宿主操作。宿主不得在call期间并发修改其参数树。加载源码的副作用属于受信任代码，本API不是文件系统沙箱。

参数转换仅接受精确内置类型None/bool/int/float/str/list/dict（不接受子类/tuple/自定义对象）；dict键必须精确str。映射为Null/Bool/Int/Float/String/Array/Map。Bool不作为Int；只接受有限Float和无孤立代理码点的String，不解码[OoO]。输出反向转换，普通结构变字段dict（不保留名义类型）；拒绝Result、Lazy、函数、Machine、Quantity、Range、定义、模块及原生句柄，不解包或唤醒。循环引用双向拒绝；重复非循环引用按出现次数深复制，不保留可变别名。转换失败抛ConversionError（ValueError子类）。

Python整数保持int，受integer_bits约束，不经十进制/JSON字符串中转；HTTP仍双向限制安全整数±(2^53-1)。大整数HTTP字段必须由业务明确为十进制String，不按大小偷偷改变类型。两种入口的区别是传输能力，不改变ZZY的Int语义。

转换受value_depth（根容器为1）、container_items、text_codepoints及runtime对象/槽/载荷预算约束；导出Python树构建也预留预算，避免重复别名指数展开绕过配额。stdin受io_payload_bytes限制并计入临时载荷。调用成功后返回数据和输出由Python调用者拥有，不属于活跃ZZY上下文预算；不承诺进程RSS上限。显式load不启用自动缓存、热更新、VM或shape合约生成。

## P08-04 SQLite契约

受控语言接口：db.transaction(path: String, callback: Function) -> Result，callback必须零参数并返回Result；成功提交并返回该Result，失败Result回滚。db.query(sql: String, params: Array) -> Array<Array>只允许事务内执行，按列顺序返回行，非查询返回空数组。参数使用SQLite绑定，不拼接；只接受Null/Int（有符号64位）/有限Float/String，Bool、容器、句柄拒绝。数据字段由ZZY业务校验；路径和SQL由受信任程序控制，不将客户端输入当SQL。

每次transaction新建同线程连接，BEGIN IMMEDIATE，禁止嵌套；所有退出路径finally回滚未提交事务并close。callback成功的提交发生在transaction返回之前，之后的语言/HTTP编码失败不撤销已提交事务，业务应在回调内完成校验。事务不跨请求共享，不支持手工BEGIN/COMMIT/SAVEPOINT、ATTACH/DETACH、PRAGMA或加载扩展；这些语句由SQLite authorizer拒绝。执行只支持单条SQL，参数数量由SQLite检查。SQL/I/O失败E401（客户端仍为既有zzy_error），类型E201、Int范围E208；错误不包含数据库内容或宿主堆栈。取消保持Cancelled，资源保持E211，均回滚。

每SQL执行期限1秒，进度检查每1000条SQLite指令；锁等待最多250ms。取消在SQLite检查点及取行之间检查；文件系统阻塞仍无硬终止保证。SQL及单行单元长度受io_payload_bytes/SQLite长度限额控制，结果按行转换并使用已有对象/槽/载荷预算，不fetchall。SQLite内部页缓存/RSS不属语言逻辑计量。只支持文本、整数、浮点、Null结果，Blob拒绝；Unicode和有限数沿用转换边界。SQLite使用Python自带sqlite3，核心check只解析，不打开数据库，不加载GUI/Web。
