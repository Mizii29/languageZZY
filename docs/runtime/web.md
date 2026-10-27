# P08 Web 与互联集中契约

2026-10-28。P08 已选，本轮仅实现 P08-01；P08-02—05 尚未完成。核心语法/stdlib ABI 不变。本文件是 Web 边界唯一规则来源，不将旧设计中的 web.get/web.post/web.json/web.serve 方向示例注册为可调用语言接口。

## 决策与范围

采用 Starlette 0.52.1 / Uvicorn 0.54.0，可选安装 `.[web]`。服务面向本机课程演示，默认127.0.0.1；无认证、TLS、跨域授权或互联网部署承诺。Python只承担协议、路由和通用转换，业务在ZZY。选择固定宿主路由表而不是启动时执行ZZY注册代码：启动只准备依赖图、校验入口，不产生业务副作用。源码/路由是启动快照，修改需要重启；无热更新或自动缓存。

每请求重新实例化整个模块与捕获环境，绝不共享执行值、Lazy、闭包、结构定义或Machine。只复用prepare的只读Program。P08-02仍需完成共享冻结模块及更全面的捕获/并发验收，本轮不宣称该任务完成。

## 实际入口与路由

`zzy.web.create_app(module, routes, *, page=None, timeout=5.0, workers=4)` 返回ASGI应用。module为本地ZZY文件路径；routes为 `(method, path, function_name)` 序列，只支持GET/POST、以/api/开头的固定路径，不支持模板、查询串或片段。重复项、空表、缺失入口、非单参数顶层具名函数在启动时拒绝。函数实际类型/返回注解按原解释器校验。

`python -m zzy.web MODULE --route GET /api/hello hello --route POST /api/greet greet --page PAGE [--host HOST] [--port PORT]` 使用Uvicorn。page是可选单个UTF-8 HTML文件，启动有界读取，仅在GET /提供，不开放目录遍历。GET /自动支持HEAD；API的HEAD/OPTIONS等均405，无自动CORS。缺路由404，不重定向尾斜杠。路由校验不运行模块初始化；初始化在每个请求中执行。

## Request / Response

Request是每请求新建的Map，五个键：method(String)、path(String)、query(Array of [String,String])、headers(Array of [String,String])、body(JSON值)。query/headers保留框架提供的顺序/重复项，不隐式合并；header名称按ASGI转小写。GET body必须为空并映射Null。POST要求application/json或application/json; charset=utf-8；大小写/首尾空白归一，其他参数/媒体类型415。非identity Content-Encoding拒绝，不自动解压。

业务函数必须返回Map或普通shape，字段恰好status与body。status必须Int（非Bool），200..599，排除204/205/304这些无正文状态；body为支持的JSON值。Content-Type由适配器固定application/json，不能注入任意响应头。示例中的Response为普通ZZY shape，自行构造，不提供隐式结果转换。业务可返回422和中文数据提示；不自动解包Result。

输入复用核心严格JSON codec，拒绝重复键、尾部额外数据、NaN/Infinity、非有限Float、非法UTF-8/孤立代理字符。Request元数据与body独立解析，body不能注入其他字段。Null/Bool/Int/Float/String/Array/Map按原标签转换，结构输出为字段对象。HTTP Int双向限于±(2^53-1)，大整数必须由字段契约显式约定十进制String；不会随值大小改变类型。字符串不执行[OoO]转义。循环引用、函数、Result、Lazy、Machine、Quantity、Range、原生句柄/定义拒绝；不唤醒、不解包、不开放Python属性/eval/exec。

## 容量、错误与生命周期

固定每请求body65536字节、响应/静态页65536字节、headers原始键值字节与query_string合计16384字节。流式读取在追加前检查；框架接收单块/解析HTTP头发生在适配器之前，不承诺OS或ASGI内存硬限。JSON及ZZY运行使用default-v1，将io_payload_bytes收紧至65536，其他核心限额不变；执行输出各1MiB，仅在请求私有缓冲，不混入HTTP。JSON嵌套沿用64层限制。

固定最多workers个正在收体或运行的请求（1..16，默认4），饱和503，不建立无限任务队列。ZZY在受控线程池执行，不直接占用事件循环；CPU执行仍受GIL影响，不承诺多核加速。timeout分别约束收体阶段和执行阶段（各默认5秒，0<值<=60），不是两个阶段共享的总期限。

错误响应形状为 `{"error":{"code":"..."}}`：非法JSON/GET带body为400；读体超时408；容量输入413；媒体415；元数据431；路径404/方法405；非法业务Response500 invalid_response；语言诊断500 zzy_error；内部错误500 internal_error；运行资源503 resource_limit；执行超时504 request_timeout。输入JSON核心配额失败也413 resource_limit。状态码/资源错误不冒充业务成功。内部诊断记录服务端源码位置，响应不泄漏路径、原始异常或Python堆栈。

超时/客户端断连/ASGI任务取消触发CancellationToken；解释器检查点及支持取消的原生操作退出并释放上下文。超时响应可先返回，执行槽直到线程真正退出才释放。取消不能强制打断任意阻塞宿主文件调用；服务关闭停止接单、取消全部活动令牌并等待池结束，永久阻塞宿主可能延迟关闭。不得将线程超时称为硬进程隔离。ZZY代码必须是服务拥有者信任的代码，本层不是文件系统沙箱。

## 后续任务的边界（未实现接口）

P08-02：共享模块数据必须递归冻结，覆盖Array/Map/shape、嵌套Machine、默认表达式捕获；共享模块级Lazy和可变闭包拒绝或每请求实例化，并做实际交错验证。

P08-03：公开load/call/conversion/close API将在本文件补充具体签名；必须显式拥有和释放上下文，宿主传入值深拷贝并计量，Bool/Int严格区分，错误及不支持类型拒绝，不把本轮内部RequestRuntime发布为嵌入API。

P08-04：SQLite待受控注册表接口；必须只用参数绑定、连接按请求拥有、事务成功commit/异常或取消rollback/finally close，不共享连接跨线程。具体签名、锁等待和SQL约束在实现时同文件补充，当前无db接口。保留校园CLI及文件格式。

P08-05：完成上述跨接口、持久化、安装与交付验收；本轮只交付HTTP子集，不以页面成功代替后续完成。
