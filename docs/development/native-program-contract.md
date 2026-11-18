# N2：静态 Program 与 check 契约

本契约只补充原生表示与观察接口，语言规则仍以 [syntax](../language/syntax.md)、[diagnostics](../language/diagnostics.md)、[resources](../runtime/resources.md)、[query](../features/query.md)、[stdlib](../language/stdlib.md) 为准。Python 默认入口不变，不实现求值，也不引入静态类型系统。

## 表示与所有权

Parser 使用仅在准备期间可变的节点表，NodeId 为从0开始的后序索引。每个节点保留 kind、Token、子索引、注解、语法数据、半开源码范围及最长子路径深度。Program 发布时移动到独立 const 分配，只通过 const 引用公开；Source 为 const 原字节、UTF-8码点及坐标快照。复制 Program 仅共享只读描述，不共享请求状态。

Program 包含 AST、Reference(global/local/self/capture)、Symbol(owner/slot/mutable/cell)、FunctionPlan(locals/有序传递捕获/各块清理槽)、注解绑定、精确数字/Quantity字面描述、Machine边表、规范路径模块图、静态导出和 use→模块根映射。cell 只是 N3 分配 Cell 的标记。这里没有 Cell、运行期 Array/Map/Shape、闭包环境、Lazy状态、模块实例、宿主句柄或请求计量器。字面量的任意精度 limbs 只用于静态准备，不表示 N3 BigInt 执行已经完成。

无字节码、磁盘 Program 序列化、隐式进程缓存。每次 prepare 从当前有界文件快照构图。program-info 是供人/测试观察的 JSONL 描述，不能读回作为 Program 或缓存。

## 名称、捕获与图

声明按源码顺序解析；初始化中的名称遮蔽外层并报 E302。具名函数解析注解后才开放自身递归；参数注解在声明环境解析。闭包逐层记录捕获来源，捕获可变绑定标记原符号 cell。块槽位按声明顺序保存；内层函数的循环控制不继承外层循环。注解只解析名称及限定字段路径，不检查绑定的运行时类型、字段存在性或参数/返回值类型。

模块按规范路径（Windows大小写、8.3和junction身份）去重；use 相对导入者目录，扩展名精确为 .zzy。先完成当前文件 Lexer/Parser/Resolver，再依源码顺序递归依赖；活动节点重复为 E303，完成节点复用同一根。整个可达图都准备，含未调用函数中的静态名称检查；不存在运行期模块初始化。静态导出仅为顶层 function/shape/machine；不提前校验运行时模块字段访问。导入读取失败（包括源码/深度预算）按既有准备契约包装为导入点 E303；依赖内部 Lexer/Parser/Resolver 错误保留依赖文件和坐标。

## 准备、资源和副作用

check 只做扫描、构树、绑定及静态描述。按现有契约准备 Int、有限 Float、精确 Quantity 和 Machine 图；检查 query 纯调用的实际预置绑定、管道直接插槽及 Result传播上下文。声明为 Bool 的值为数字、赋值只读绑定、错误调用参数、分支内类型错误等仍属于运行期，不由 check 提前拒绝。

沿用前端预算：源码、模块数/深度、每文件Token、全图AST节点、语法嵌套及AST最长路径、数字位数、整数字面位宽、Quantity量纲、文本及输出。叶子AST深度0。取消点覆盖扫描、解析、解析名称、导入及字面准备。CLI及Program测试的PE主线程栈预留8MiB（按需提交，不是固定RSS），保证未优化MSVC构建也能接受默认syntax_depth=64。额外的物理栈余量检查只防宿主栈耗尽，映射 E211，不更改默认语法预算；不保证任意调高配置都能在有限宿主内存中成功。

不得执行默认表达式、函数体、顶层表达式、Lazy、spec断言、I/O、SQLite、GUI或宿主初始化。宿主仅使用冻结的静态名称/纯性元数据，不调用库实现。check 成功不证明运行期能力、实际多请求隔离或宿主可用。

## 公开入口

`zzy-native check FILE [--limits FILE] [--diagnostic-format text|json]`：成功0且stdout/stderr空；首个前端失败退出2，沿用schema v1；协作取消130。run/test仍在读源码前 E402/2，无Python回退。

`zzy-native program-info FILE`：先完成与check相同的准备，再输出schema_version=1 JSONL，首记录program，随后module、node、reference、symbol、function、annotation、number、quantity、machine、import。NodeId只在本快照内有效；不含地址或运行期对象身份。同一文件快照/策略下顺序确定。Int/Quantity十进制字符串避免JSON安全整数丢失，Float以17位有效数字描述。成功输出前不得有半个Program；输出配额不足可保留较早完整记录，最后报E211。该观察格式不等于语言JSON/嵌入公开ABI。

info报告N2及五个实际命令。N1词法/源码格式保持。核心check不加载Python、Web或GUI。
