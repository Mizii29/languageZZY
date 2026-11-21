# 原生能力矩阵与延期协议（N0-02）

2026-11-19，核心原生产物版本 0.0.0-n4-03-dev，MSVC 默认构建包含 N4-03 SQLite 和独立 N4-04 Web EXE。Python 仍是默认入口。原生 check 仅做静态准备；run 已执行核心语言及 N4-01/02 核心标准库。
逐项清单见 [capabilities.json](../../native_runtime/tests/capabilities.json)：每个 AST kind、实际 Value kind、宿主函数都有独立条目。
`implemented=false` 表示当前原生后端未实现。[N3报告](../../native_runtime/tests/n3-report.md)保存核心运行验收范围；[N2报告](../../native_runtime/tests/n2-report.md)保存静态 Program 验收历史。

| 类别 | 核心/可选 | 计划阶段 | 当前状态与保证 |
|---|---|---|---|
| UTF-8/源码位置/Token | 核心 | N1 | 已实现；严格 UTF-8/Unicode15.0.0、源码快照/码点位置与固定清单已由GCC及MSVC Debug/Release验证 |
| AST/Resolver/check | 核心 | N2 | 已实现；只读 Program、绑定/捕获布局和完整模块图；check 不求值 |
| 标量、BigInt、码点 String、Array/Map/Shape、分支/循环 | 核心 | N3 | 可执行；验证大整数、身份、别名、活动遍历和浅复制 |
| 具名/匿名函数、Cell/闭包、Lazy、Result、管道 | 核心 | N3 | 可执行；显式调用帧、捕获和请求内回收 |
| Query/Machine/Quantity/模块 | 核心 | N3 | 可执行；查询分阶段，Quantity 用精确分数，模块按请求初始化 |
| spec/test | 核心 | N5 | 收集字节快照、逐例 native worker 隔离；空收集/失败/超时/输出超额/异常退出均非成功 |
| core/io/array/text/math/data/unit 全部登记函数 | 核心 | N4 核心 | N4-01/02 已接入 35 个冻结宿主签名；资源、取消、回调和错误清理见 [标准库契约](native-stdlib-contract.md) |
| 文件读写与原子提交、严格 JSON | 核心 | N4-02 | 已接入四个文件和两个 JSON 接口；编码、原子提交、严格值标签和同进程恢复见 [N4-02 报告](../../native_runtime/tests/n4-02-report.md) |
| db.transaction/db.query | 可选宿主，完整迁移必需 | N4-03 SQLite | 已接入；MSVC 默认 ON、OFF 执行 E402/1。固定系统 SQLite、参数绑定/事务/同线程连接、取消/配额归还、并发及重启持久化见 [N4-03报告](../../native_runtime/tests/n4-03-report.md) |
| Web 与 shape 合约 | 可选宿主，完整迁移必需 | N4-04 Web | 已接入独立回环 HTTP 服务；逐请求/shared、静态 OpenAPI、严格 JSON、有界执行和关闭见 [N4-04 报告](../../native_runtime/tests/n4-04-report.md)。`ZZY_NATIVE_WEB=OFF` 不构建该 EXE。 |
| Python 嵌入 API | Python 宿主接口 | P08 | 仍由现有 Python 包提供；不承诺原生等价的公开嵌入 API。 |
| Sketch 几何、图层、历史、SVG、项目 v1、对象编辑、Drawing、回放和事件登记 | 可选宿主 | N4-05 | 已接入。Headless show 和无 PNG 后端返回明确的失败 Result。[验收报告](../../native_runtime/tests/n4-05-report.md) |
| Sketch 窗口、事件派发和交互回放 | 可选宿主 | N4-06 | Windows x64 MSVC 独立原生窗口程序，需显式启用。真实窗口与安装副本均已验证。[验收报告](../../native_runtime/tests/n4-06-report.md) |
| 资源/取消/JSON 诊断/0/1/2/130 | 核心 | N0 原型；N1—N5 正式接入 | 前端和核心运行配额、协作取消与恢复已验证；进程准备缓存未建立，真实终端 Ctrl+C 未验收 |
| run/check/test 安装及无 Python 验收 | 核心 | N5 | N5 native CI 的 Debug/Release configure、CTest、安装 smoke、PE/模块/进程树和空环境证据；人工终端与缺 CRT 主机仍未验证 |
| VM/AOT/JIT/热更新/磁盘 Program 缓存 | 本项目延期/非目标 | N7 仅评估 | 不新增 build 命令、不透明选择后端；已有独立 AOT 实验不算本路线实现 |

## 未支持行为

集中错误码表新增 **E402：当前后端未实现能力**，仅用于能力门禁；JSON 仍是 schema v1。
test 收集阶段不执行用户程序；收集成功后每个 spec 使用独立 worker。spec 失败、空集合或收集错误返回 1，CLI 参数/limits 配置错误返回 2，Ctrl+C 返回 130。普通完成时 stdout 最后一行是稳定汇总；取消或汇总本身超出配额时不保证有汇总。run 遇到未移植宿主仍报带源码位置的 E402/1；check 只静态准备，成功 0。
未知命令和非法 CLI 参数仍返回 E401/2。

成功为 0；执行用户错误/测试集合失败为 1；前端或 CLI 失败为 2；取消为 130（kind=cancelled/code=null）。
内部错误 code=null 按阶段 2/1；bad_alloc 映射 E211 前必须清理；宿主预期失败的 Result 边界不改变。
N0 的 1/130 由独立生命周期探针验证，不能据此宣传 run 已实现或真实 Ctrl+C 已验收。

## 延期复核

每个条目记录 tier/phase/status，未实现统一 E402；需要现有完整能力时仍可显式调用 `python -m zzy`。`value.NativeType` 表示已有请求内类型身份、所有权和销毁协议，不表示 Sketch 或其他扩展的构造器已移植。
现有 1738 外部用例原地保留；N6 将全部映射为原生用例并单列延期数，绝不把未支持计作通过。
重评估按计划对应阶段；N8 前默认入口不变。P12/P13 独立进度不因本矩阵调整。

N1 用户顺序例外与 N2 公开边界见 [前端集中契约](native-frontend-contract.md) 与 [Program 契约](native-program-contract.md)。N3 同进程连续核心请求、N4 文件和 SQLite 错误/取消后的恢复及原生 Web 真实交错请求已验证；完整应用对照留 N6。
