# 原生能力矩阵与延期协议（N0-02）

2026-11-17，原生版本 0.0.0-n0。Python v0.6 继续提供现有能力。
逐项清单见 [capabilities.json](../../native_runtime/tests/capabilities.json)：每个 AST kind、实际 Value kind、宿主函数都有独立条目。
`implemented=false` 表示没有实现，不代表测试跳过后通过。N0 只有 info/帮助/拒绝协议与独立堆原型；不能运行 ZZY。

| 类别 | 核心/可选 | 计划阶段 | N0 状态与保证 |
|---|---|---|---|
| UTF-8/源码位置/Token | 核心 | N1 | 未实现；source-info/lex 拒绝 |
| AST/Resolver/check | 核心 | N2 | 未实现；check 拒绝且不执行初始化 |
| 标量、BigInt、Array/Map/Shape、分支/循环 | 核心 | N3 | 未实现；堆图原型不等于语言容器执行 |
| 具名/匿名函数、Cell/闭包、Lazy、Result、管道 | 核心 | N3 | 未实现；原型只验证其环所有权 |
| Query/Machine/Quantity/模块/spec | 核心 | N3—N5 | 未实现；不退化为普通 Float/Map，不假装测试集合为空即成功 |
| core/io/array/text/math/data/unit 全部登记函数 | 核心 | N4 核心 | 未实现；逐签名列入 JSON，文件 I/O 权限/Result/配额沿用正式契约 |
| db.transaction/db.query | 可选宿主，完整迁移必需 | N4 SQLite | 延期；保留参数绑定/事务/每请求连接，不影响 Python 示例 |
| Web/Python 嵌入/shape 合约 | 可选宿主，完整迁移必需 | N4 Web | 延期；不声称 Python embedding API 已原生化；ASGI 替代协议需该阶段决策 |
| 所有 sketch 类型/函数、几何/SVG/历史/事件/GUI | 可选宿主，完整迁移必需 | N4 Sketch | 延期；headless 不加载 GUI；PNG 原本未支持，不算迁移退化 |
| 资源/取消/JSON 诊断/0/1/2/130 | 核心 | N0 原型；N1—N5 正式接入 | info/拒绝协议先实现；完整源码定位、动态策略、解释执行、真实 CLI Ctrl+C 尚无能力 |
| run/check/test 安装及无 Python 验收 | 核心 | N5—N8 | N0 只检验已构建的 info/原型，不外推未来进程树 |
| VM/AOT/JIT/热更新/磁盘 Program 缓存 | 本项目延期/非目标 | N7 仅评估 | 不新增 build 命令、不透明选择后端；已有独立 AOT 实验不算本路线实现 |

## 未支持行为

集中错误码表新增 **E402：当前后端未实现能力**，仅用于能力门禁；JSON 仍是 schema v1。
N0 对已知但未实现的 source-info/lex/check/run/test 在读源码之前返回：stdout 空，stderr 一条 error/E402，file/span=null，notes 含 `capability=<command>`，退出 **2**。
因此有效 ZZY 不会被误报 E103，也不会触发 Python 或 I/O。未知命令/非法 CLI 参数仍 E401/2。
未实现能力在后续前端可识别时须在准备阶段拒绝；不得运行一半再回退。未来精确源码定位按 diagnostics 契约补齐。

成功为 0；执行用户错误/测试集合失败为 1；前端或 CLI 失败为 2；取消为 130（kind=cancelled/code=null）。
内部错误 code=null 按阶段 2/1；bad_alloc 映射 E211 前必须清理；宿主预期失败的 Result 边界不改变。
N0 的 1/130 由独立生命周期探针验证，不能据此宣传 run 已实现或真实 Ctrl+C 已验收。

## 延期复核

每个条目记录 tier/phase/status，未实现统一 E402，替代入口仍为显式 `python -m zzy`。
现有 1738 外部用例原地保留；N6 将全部映射为原生用例并单列延期数，绝不把未支持计作通过。
重评估按计划对应阶段；N8 前默认入口不变。P12/P13 独立进度不因本矩阵调整。
