# ZZY 开发记录与 Agent 交接

建立：2026-10-03。任务状态见 [todo.md](todo.md)，阶段说明见 [roadmap.md](roadmap.md)。

这里保存真实发生的操作和结果。解释器、应用和性能工作尚未开始时，不提前生成成功记录、提交标识或测量数据。后续 Agent 直接追加，不覆盖旧记录。

## 记录方式

每完成一项任务或留下交接，就记一次：用户任务或提示摘要、关联任务编号、修改文件、采取的方案、实际验证结果、Git 提交和下一步。命令失败、测试未运行、优化没有收益也要如实写明。

应用阶段继续在这里记录，并标明“应用开发”；可以引用完整日志或报告，不需要记录内部思考过程。未提交时写“未提交”，未测量时写“未测量”。

## 2026-10-03：计划文档建立

- 任务摘要：为下一个执行 Agent 建立分阶段计划、待办及独立创新说明。
- 阶段：开发准备，尚未执行 P00 的代码任务。
- 接手快照：仓库只有五份已有设计文档；Git 已初始化，没有提交，`docs/` 尚未跟踪。
- 新增文件：`process.md`、`todo.md`、`development-log.md`、`innovation.md`。
- 方案：任务按 P00—P11 编号；用单一待办清单维护状态，开发记录维护验证证据；高级创新不阻塞应用交付。
- 验证：文档一致性检查通过；四份新文档的 19 个本地链接有效，代码围栏成对，12 个阶段在计划与待办中一致，58 项任务编号唯一，未将代码任务勾选完成。这不是解释器测试或性能测试。
- Git 提交：未提交。
- 下一步：P00-01，重新核对实际仓库和开发环境。

## 后续记录模板（复制后填写）

```text
日期 / 执行者：
用户任务或提示摘要：
阶段与任务编号：
接手状态：
修改文件：
实现内容与主要选择：
验证命令和输入：
实际结果：通过 / 失败 / 未运行（写明原因）
失败、限制或性能原始数据位置：
Git 提交：真实标识 / 未提交
已更新待办：
下一项任务与未解决问题：
```

## 2026-10-03：文档修订与契约统一

- 用户任务：阅读 docs 并修正调整、补充创新；requirement 文档禁止修改，关注正确性与性能。
- 接手核验：仓库只有 9 份文档，无解释器/测试/基准/应用代码；Git 无提交，docs 未跟踪。与前条建立时的 5 份快照对应不同时间，未将旧快照当当前状态。
- 修改原有 8 份：design.md、design简版.md、interpreter实现流程.md、performance简单.md、innovation.md、process.md、todo.md、development-log.md。
- 新增 4 份：README.md（文档入口）、syntax.md（v0.4 语法语义）、stdlib.md（库契约）、test-coverage.md（覆盖计划）。
- 语义修正：统一当前括号写法，明确 Bool/Int、有限 Float、相等/索引、优先级/求值顺序、默认值引用共享、闭包/Lazy 捕获、每轮绑定、修改前遍历保护、模块/check/spec 隔离与 Lazy 致命错误的验证边界。
- 库与性能：整数 sum/stats、空统计、严格 JSON、HTTP 显式大整数字段、文件临时写入加替换发布；缓存按依赖和内容版本失效。基准区分同算法、等价库与优化前后，统一初始化/复位计时范围，记录原始样本、离散程度、命中率和退化。
- 阶段调整：P09 核心 CLI 应用依赖 P05/P06，P08 Web 在应用后可选，P11 不依赖 Web/高级优化。任务编号稳定，新增 P10-07/08；未勾选任何代码任务。
- 创新补充：数组内容版本的成功类型校验缓存、变形关系与外部固定答案、注册表生成能力清单；shape 合约补缺失/Null、默认值、Array 元素类型限制和生成一致性，均未实现。
- 静态验证：13 份文档的 73 个本地链接有效、37 个代码围栏块闭合、60 个任务编号唯一；12 阶段依赖无环，process/todo 一致，P09/P11 不被 P08 阻塞。初次辅助检查误将 JavaScript/EBNF 和标题“先于 P08”纳入旧语法/依赖判断，修正检查范围后通过。
- 语法检查：通过临时 EBNF 识别器核对 51 条语法产生式引用和 17 个无占位符的 ZZY 示例块，均符合语法骨架。该检查不验证名称、类型、控制流上下文或执行结果，不代替正式 Parser 和黑盒测试。
- 宿主核验：使用 Codex 自带 Python 3.12.14 验证 Bool 是宿主 Int 子类；[1e16, 1.0, -1e16] 左折叠为 0.0、sum 为 1.0；默认 JSON 保留重复键最后值、接受 NaN、1e400 产生 Infinity。相关限制已写入库契约，并查阅 Python 官方文档、RFC 8259 和 OpenAPI 3.1.1。该运行时不表示项目已配置完成。
- requirement 保护：修订前后 SHA-256 均为 `B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B`，文件逐字节未变。
- 验证限制：没有解释器，所以没有运行拟议 zzy CLI、真实 ZZY 黑盒或性能基准；没有测得速度提升，也未将创新标为已实现。
- Git 提交：未提交，保留当前 docs 工作。
- 下一步：P00-01 复核实际环境与骨架，P00-03 复核契约后进入 P01；后续实现严格按契约补真实测试与性能数据。

## 2026-10-08：注释语法修订，创新候选待选择

- 用户任务：将单行注释改为 zzysay:，多行改为 zzysayalot: … zzyend；更有辨识度的语言创新和扫描性能建议先在聊天中给出选项。
- 修订范围：syntax、design简版、design、interpreter实现流程、performance简单、test-coverage、process、todo、README 与本记录；requirement 和其他已有规则保持原文。
- 契约版本：语法更新为 v0.4.1；冒号紧邻起始词，只在正常源码词项边界识别。多行暂不嵌套，完整 Unicode 标识符边界的 zzyend 结束，建议独占一行；未闭合及正常源码裸结束词报 E101。普通/raw 字符串与单行正文不误触发多行结束。
- 实现规划：注释跳过正文但保留换行/span，不拼接两侧词项；完整标记分流、结束候选单向搜索，保持扫描随源码长度线性增长的目标。P01-01 和 LEX-02 加入相应实现/验证义务，仍未勾选代码任务。
- 静态验证：13 份文档，73 个本地链接有效，38 个代码围栏块闭合；检查 19 个含 ZZY 语法的文本示例块，未发现旧井号注释。requirement 的 SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。
- 限制：仓库仍无解释器，没有执行真正词法/黑盒测试或扫描性能测量；静态检查不是注释扫描器正确性的证明。
- 创新范围：其他语言机制仅作为聊天候选，未写入正式语法或标记已选；等待用户选择后再细化规则与边界。
- Git：未提交；下一项仍为 P00-01。

## 2026-10-08：采用 C/D 设计，A 继续解释

- 用户指示：A 未理解，要求简单解释；C（状态机）和 D（带单位数值）可以采用。只将 C/D 纳入设计，A/B 没有加入语法，不把聊天选项当作全部获准。
- 本轮新增：machine-units.md；修改 syntax、stdlib、design、design简版、interpreter实现流程、performance简单、innovation、process、todo、test-coverage、README 与本记录，共修改 12 份既有文档；requirement 未编辑。
- 契约版本：当前设计更新为 v0.5。machine 定义为固定标签/事件边，重复源状态/解码事件拒绝；初始状态显式指定，每构造一次独立实例，state 只读。发送成功返回 Result 并改变状态，失败固定消息且状态不变；先准备成功结果再写入，冻结/别名/模块隔离有明确规则。
- 数量规则：新增不可变 Quantity，时间/长度/无量纲固定单位，约分有理数与两维量纲；十进制字面按原文精确准备，普通 Float 不变，运行时 Float 提升保存实际二进制数值。加减/排序检查量纲，乘除合成量纲，无量纲结果仍是 Quantity；make/format 不隐式舍入。
- 词法/Parser：-->、--、<< 最长匹配；数字后的 :: 单位与限定名字后的 ::{ 构造分开，数字 Token 保留原文后按字面节点转换一次。--x 不再是连续一元负号，可写 -(-x) 或 - - x；原有注释、字符串与颜文字规则保持独立模式。<< 层位于 with 与管道之间，禁止同层连发。
- 类型/库边界：新增 Machine/Quantity 注解及 E212/E213/E305/E306；模块导出状态机定义，实例不共享到 Program，冻结覆盖嵌套 Machine；JSON 与第一版 shape schema 拒绝新类型，不偷偷删状态/单位或改变数值精度。历史记录必须保存状态快照，不能把可变实例浅拷贝当撤销。
- 实施路线：新增 P04-06/07，均在 P04-05 验收前完成；P04 数量验收不依赖 P05 unit 库，P05 再补库/导出/JSON 黑盒。新增 LEX-03、MACHINE-01/02、UNIT-01/02 与关系验证；62 个代码任务均未勾选完成。
- 性能规划：状态表/单位倍率预建，实例按上下文独立；分开测词法、准备、成功/失败发送、有理数运算和位数增长；Python 对照使用等价图校验/精确数量，不拿 Float 算法冒充同语义性能对照。尚未实测收益。
- 静态验证：14 份文档，86 个本地链接有效，41 个代码围栏块闭合，62 个代码任务编号唯一；55 条 EBNF 产生式引用完整。临时语法骨架识别器检查 16 个完整示例块、7 个正向与 6 个反向形式探针，通过；只核对语法外形，不验证名称、类型、上下文、执行结果或新机制正确性。
- requirement 的 SHA-256 保持 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B，逐字节未变。没有解释器/真实 ZZY 测试/性能测量，没有创建或提交代码实现。
- Git：未提交；下一项仍是 P00-01。聊天中继续用四步挑选任务解释 A，待用户明确选择后再设计它。

## 2026-10-08：采用 A 集合查询，场景与兴趣主题留在聊天中

- 用户任务：将 A 加入设计；再提供特定场景的小库/函数，以及画画、动漫、芙莉莲法杖攻击错误、Identity V 红温等兴趣主题设计，后者仅在聊天中供选择。
- 本轮新增 query.md；修改 syntax、stdlib、machine-units、design、design简版、interpreter实现流程、performance简单、innovation、process、todo、test-coverage、README 与本记录，共修改 13 份既有文档；requirement 未编辑。
- 当前契约 v0.6：新增 ?>、keep/order/take/yield 与 asc/desc；输入只接受 Array，结果新 Array，条目顺序固定，yield 必需；@ 在查询条目表示当前项，与管道插槽分开，take 禁止 @。
- 正确性规则：条目限制纯读取 AST 与真实原生绑定白名单，遮蔽/动态/用户调用拒绝，结构默认/I/O/发送/Lazy/内嵌查询和管道不运行。源一次浅快照、take 一次校验、完整筛选后准备所有键、稳定排序/截取后投影；take=0 不隐藏筛选/排序错误，desc 相等项保持输入顺序。
- 类型与错误：排序键支持统一普通数值（Int/有限 Float）、String 或同量纲 Quantity；不同类别 E201、不同量纲 E213；新增 E307 表示查询作用域/纯性。源、keep、take、字段和资源错误继续沿用原码，保留表达式原文位置及可选输入下标说明。
- 库化：查询封装为普通 addnew 函数并用已有模块导出，不新增 query.compile 或自动结果缓存；P04 核心验收不依赖 P05 白名单库，P05 再验证库和模块。新增 P04-08（在 P04-05 前）与 QUERY-01/02/03；全部 63 个代码任务保持未勾选。
- 性能规划：固定 Token 扫描，查询 AST/布局一次准备，当前项/快照/键/结果按调用独立；键只求一次。基线完整分阶段执行，与等价 Python 快照/检查/稳定排序范围比较，不提前停止或自动 top-k 来掩盖错误。尚无性能数据。
- 静态验证：15 份文档，101 个本地链接有效，46 个代码围栏块闭合，63 个代码任务编号唯一；61 条 EBNF 产生式引用完整，query 与 syntax 的查询产生式一致。临时识别器通过 20 个示例块和 7 个正向/7 个反向语法外形探针。初次辅助检查误把 EBNF 文法块识别为 ZZY 示例，限定示例范围后重新检查通过；这不是解释器、纯性/类型或执行结果验证。
- requirement SHA-256 保持 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B，逐字节未变。仓库仍无解释器、真实 ZZY 黑盒与性能测量，没有把 A/C/D 写为已实现。
- 范围边界：兴趣/场景库只在聊天中提出，未增加相应新关键字、单位、标准库签名或代码；B 自动依赖刷新仍未采用。
- Git：未提交；下一项仍为 P00-01。

## 2026-10-08：采用 E 画笔扩展与全量复核

- 用户指示：把已认可的完整画笔方案写入文档，再通读所有文档，针对性能/稳定性做小幅调整；requirement 禁止修改。
- 接手状态：15 份文档，无解释器/测试/基准/应用；Git main 无提交，docs 未跟踪。本轮仅编辑文档。
- 新增 [sketch.md](../features/sketch.md)：完整 sketch 1.0 目标，固定接口、受控类型、坐标/路径/填充、多笔/图层/对象工具、增量历史、确定回放、Drawing/stamp、SVG/项目/图案函数库、事件线程/队列与 E1—E4。所有功能仍待实现，其他新增兴趣场景未采用。
- 同步入口、语法/库边界、设计简版、创新、实现流程、性能、阶段、待办、覆盖与本记录；共修改 14 份既有文档，新增 1 份。核心 v0.6 的 EBNF 与 Token 不改，扩展 ABI/schema 独立；新增 E214 操作状态诊断、7 项 E 代码任务与 SKETCH-01—06，未勾选代码任务。
- 小幅性能修正：Unicode 字符固定长度判定/行索引、缓存容量及同字节依赖快照、候选折叠失败/超预算回退、查询索引缓冲与键生命周期、有理数交叉约分和中间空间限额；不宣称已测加速。
- 稳定性修正：核心分配配额不等待 P10；前端/运行资源错误区分退出 2/1；JSON/批量操作分配前检查；测试双管道有界读取、输出超额失败与子进程树清理；ARRAY-02 致命错误后清理交给原生/嵌入验证，不伪造 ZZY try/catch。
- 保存补齐：P05 增加 io.write_atomic 拟议封装，由宿主独占创建同目录临时文件，关闭后替换，避免仅凭唯一文件名猜测或先查后建的竞争；普通 write_text/replace 保留，失败保留旧目标、不承诺断电/并发事务，sketch 文本导出共用发布内核。
- 静态验证：16 份文档，本地链接 121 个有效、48 个代码围栏闭合；70 个代码任务编号唯一且全部未完成，12 个核心及 4 个 E 阶段依赖无环。61 条 EBNF 引用完整且语法骨架逐字未改；66 个 sketch 接口签名、两个新示例中的 26 次调用名称/实参数量一致。
- 检查限制：静态工具仅核对链接、围栏、任务/依赖、EBNF 引用和示例接口名/个数，未验证真实 Parser、Resolver、类型、几何、GUI、I/O 或性能。没有解释器/真实 ZZY 黑盒/GUI 测试/性能数据，没有创建实现代码或虚构完成状态。
- 操作记录：首次实现流程补丁有一处上下文未匹配，工具拒绝且未写入；按实际段落修正后应用。验证脚本和修订前字节快照位于临时目录，不加入项目。
- requirement 修订前后逐字节相同，SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。
- Git：未提交；下一项仍为 P00-01，核心执行链完成后再按依赖实施 E。

## 2026-10-08：文档分类与设计两版整理

- 用户指示：整理所有文件，按语法、创新功能、解释器/性能等分类；总结详细与自然语言简单版，并整理开发阶段；requirement 保持原文。
- 接手状态：16 份 Markdown 文档，无解释器、真实 ZZY 测试、基准或应用；Git main 无提交，docs 未跟踪。本轮只整理文档，不创建代码骨架或执行实现任务。
- 文件迁移：14 份文档移入 language/features/runtime/development 或改名为 design详细版/design简单版；README 与 requirement 保留原位置。文件总数仍为 16，原路径对照集中在 README，不保留重复旧版。所有本地 Markdown 链接按新父目录重新计算。
- 两版总览：详细版串起作业、语法/语义、Result/Lazy/管道、A/C/D/E、解释器、性能、资源、测试与交付；简单版用名字与物品、信封、取餐单、流程箭头等解释，不再是另一份大语法表。精确规则仍以原契约为准。
- 专题归类：innovation 的 21 个原章节整理为五组，performance 的 15 个原章节整理为四组；保留接口/纯性/失效/量纲/线程/测量细节，区分当前设计与条件候选。修正简介、当前版本称呼及不适合正式文档的旧聊天措辞。
- 开发整理：roadmap 划分核心主线、已选 E 与可选 P08/P10，明确 P09 在 P08 前；todo 随实际顺序重排，70 项编号任务原文及未完成状态保留，下一项仍为 P00-01。未来指南/报告/交付索引也规划到对应分类。
- 历史保留：本记录已有条目只修复 Markdown 链接，原文件名、旧快照、旧验证数字和执行事实不改写；当前迁移对照供阅读旧记录使用。
- 静态验证：16 份文档，148 个本地链接有效、42 个代码围栏闭合；70 项编号代码任务与原文一致且未完成，12 个核心/可选阶段与 4 个 E 阶段依赖无环，roadmap/sketch 的 E 依赖一致。61 条 EBNF 引用完整且骨架未改；66 个 sketch 签名与文档示例的 17 次调用名称/实参数量一致。7 份契约/参考文档除迁移链接和指定简介/标题修订外内容保留，历史日志正文保留；创新 21/21、性能 15/15 原章节细节均保留。
- 验证边界：只核对文档结构/链接/契约保留/任务与依赖，不证明 Parser、运行语义、GUI 或性能；全部示例仍待解释器实现后运行。
- 操作记录：首次 README 替换补丁把删除/新建指向同一文件，工具拒绝且未写入；改用整份文本写入完成。复核中修正详细版的无显式 return 描述，使其与语法契约一致。
- requirement 与本轮开始字节快照一致，SHA-256 为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。临时验证数据不加入项目。
- Git：未提交；没有标记任何代码任务完成。

## 2026-10-08：根层与 runtime 文档审查修正

- 用户任务：阅读根目录和 runtime 文件，直接修改不合理之处；新增建议在聊天中解释。本仓库顶层仅有 docs，实际审查对象为 docs 根层四份文档及 runtime 两份文档，并对照语言、库、特色与开发契约。
- 接手状态：16 份 Markdown 文档，无解释器、真实 ZZY 测试、基准或应用；Git main 无提交，docs 未跟踪。本次修改两版 design、runtime/interpreter、runtime/performance，以及本记录与 todo 的最近验证指向。
- 语义说明修正：check 读取源码/依赖但不执行用户 I/O，模块准备与初始化分开；区分单文件退出码和测试汇总失败；Quantity 默认显示基础单位，普通数的浮点除法不能覆盖 Quantity 规则；JSON 摘要补齐既有拒绝类型。
- 实现隐患修正：捕获分析不能遗漏多层闭包与结构默认表达式；自递归函数自身引用需要正确初始化；只读结构布局与携带定义环境的运行时结构定义分开，后者不能跨执行上下文缓存。
- 性能修正：整数求和中间值也受限，未证明资源安全前使用受限累加，不无条件转交宿主 sum；区分求和加法次数、排序比较次数及大数/字符串单次操作成本。函数结果缓存不能把每次新建的数组变成同一共享对象；仍只保留既有标量缓存候选。
- 顺序和导航修正：部件讲解顺序不当作阶段依赖，P03 槽位/P05 库/P07 测量保持一致；Web 明确在 P09 后可选。第一批库对齐 stdlib 的真实设计清单；innovation 的旧第 9 节引用改为现有第 4.3 节。
- 验证：与本轮开始的临时字节快照核对修改差异；16 份文档的 150 个本地 Markdown 链接有效，42 个代码围栏块闭合，70 项编号代码任务唯一且仍未完成。原有 6 项已勾选条目仅为文档设计状态，没有新增代码完成标记。查阅 Python 官方 sum、稳定排序及 lru_cache 文档，未运行拟议 ZZY 命令。
- requirement 与本轮开始字节一致，SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B；language/features 契约及 roadmap、覆盖计划未改。检查只证明文档结构和指定一致性，不证明运行语义、GUI 或性能。
- 验证过程：一次 rg 搜索使用了 PowerShell 不展开的通配路径，随后改为明确文件/目录搜索；最初统计所有已勾选条目包含了文档状态，已限定编号代码任务核对。没有解释器，因此没有真实黑盒或性能结果。
- Git：未提交；下一项仍为 P00-01。补充建议只在聊天给出，未新增关键字、库签名或实现任务。

## 2026-10-09：补充资源、基准、应用恢复与诊断设计

- 用户任务：将上轮提出的四项补充写进设计，并继续检查其他遗漏。本轮只完善设计和实施/验收映射，不启动解释器或应用实现。
- 接手状态：16 份设计文档，Git main 无提交，docs 未跟踪，无解释器、真实 ZZY 测试、应用或性能数据。新增 runtime/resources.md、language/diagnostics.md、development/campus-app.md；同步修改 12 份既有文档，总数变为 19。
- 资源设计：default-v1 给出源码/依赖/Token/AST/数字/调用/容器/在用载荷/输出/缓存及 sketch 初始限额，说明单位、配置、生效指纹、分配预留/释放、最终诊断预留和取消清理。数值为待验证起点，不宣称精确 RSS 硬限制；无分配无限循环由测试进程硬超时处理，P10 步数配额仍可选。
- 基准设计：performance 第 3.4/3.5 节固定 B01—B09 的配对任务、规模与校验，规定 cli_total/execute/prepare 边界、批内状态复位、清单/原始记录及失败状态。P07 内部驱动复用核心解释路径，不依赖 P08 对外嵌入 API。
- 应用设计：campus-app 定义 schema_version=1、任务字段/类型/数量/ID 规则、先全量校验后替换、保存失败保留旧文件和内存、加载/退出未保存处理、历史与 ID 高水位、APP-01—03；首次读取失败不自动当空文件或覆盖。
- 诊断设计：diagnostics 定义文本与 UTF-8 JSON Lines、schema_version=1、BOM/CRLF/Unicode/Tab/EOF 的半开 span、无文件位置的 null 值、四个非法程序期望及修复说明。取消出口为 130，内部缺陷不冒充用户类型错误；预算不足时保留完整记录，不截断半个 JSON。
- 进一步发现并补齐：ZZY 缺少安全检查任意 JSON 类型的接口，标准库 v0.6.1 增加 data.kind，七种 JSON 类别与 other，严格区分 Bool/Int/Float，不解包/唤醒，不扩展 query 白名单。另明确 Python/Unicode/平台记录、工作目录与 use 路径区别、容量配置进入准备缓存键、独立应用/绘图历史规则。
- 版本/计划：核心语法仍 v0.6，EBNF 未改；标准库、资源策略、诊断、应用文件分别版本化。补充要求进入现有 P00/P05/P06/P07/P09/P11，70 项代码任务 ID、顺序和未完成状态保持；新增 CLI-02/RESOURCE-02/JSON-02 及应用验收映射，不把文档存在算实现完成。
- 静态验证：19 份 Markdown，186 个本地链接有效，49 个围栏块闭合，3 个 JSON 示例可解析；四个诊断样例的源码列区间与 JSON 定位一致，应用 JSON 样本符合所写字段/类型/ID 约束，资源示例的键/正整数/字节单位一致。70 项编号任务唯一且全部未完成，核心 EBNF 与本轮开始快照相同。
- 数学核对：独立 Python 辅助核对 B01/B02/B03 三档累加公式、B05 重复值频数、B07 n=10 的完整 id 序列与输入未变、B09 有理数答案。这里只核对文档中的期望数据，没有执行 ZZY、计时或宣称性能提升。
- 过程记录：首次追加最后几项修订时，sketch 日期行上下文不匹配，整份补丁被拒绝；读取实际行后重新应用。辅助 Python 首次控制台输出的中文路径受默认编码影响，改用 -X utf8 输出；文件内容和静态判断未受影响。快照、验证脚本与结果保存在临时目录，不加入项目。
- requirement 逐字节保持，SHA-256 为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B；其余验证仅为设计静态检查，不证明 Parser、库、资源/恢复、GUI 或运行语义正确。
- Git：未提交；下一项仍为 P00-01。后续真正实现时校准资源值、建立配对脚本及错误样例，再将真实结果写入记录。

## 2026-10-09：建立 skills 使用文档与项目介绍

- 用户任务：在根目录建立与 docs 同级的 skills，提供语法规则、开发指南、引用 docs 的 AI 文档和项目 README。本轮只编写使用文档及同步入口，没有开始解释器实现。
- 接手快照实际为 18 份 docs 文档；此前记录中的 design简单版.md 已不在工作区，仍有若干失效引用。本轮保留该现状，将现行导航改为详细设计、语法参考或开发指南，历史开发记录不改写。
- 新增 5 份文件：根目录 README.md、skills/README.md、skills/syntax.md、skills/guide.md、skills/zzy/SKILL.md。根 README 介绍项目、状态、目录和交付；skills README 导航；语法参考覆盖常用规则与特色；指南说明编程、输入/JSON、保存、测试、实现和交付；AI SKILL 按任务查阅 docs，不复制完整 EBNF。
- 同步 9 份既有文档：README、详细设计、roadmap、todo、syntax、innovation、interpreter、performance 和本记录。后四份契约/专题仅替换一处简介中的失效链接；语言规则、库接口、版本和 requirement 原文未变。P06 从“建立指南”细化为对照实现、落实可运行示例与真实验收，70 项代码任务的编号、顺序及未完成状态保持。
- 静态检查：23 份 Markdown 的 250 个本地链接有效、63 个代码围栏闭合；15 个新增 ZZY 示例块通过词项边界和括号配对检查，并按契约人工核对写法。该辅助检查不是 Parser、Resolver、类型或执行验证，所有示例仍标记未运行。
- AI 技能检查：采用 skill-creator 的项目技能格式，name/description 元信息和相对引用已核对。尝试执行其 quick_validate.py 时缺少 PyYAML，尝试安装到临时目录也未取得可用发行包，因此未宣称官方脚本通过；另按该脚本约束检查本文件的简单前置信息、名称、长度、占位符与围栏。
- 保留核对：修订与临时字节快照比较，未触碰其余正式契约；requirement SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。临时验证脚本和快照不加入仓库，未修改全局技能目录或注册 AI 工具。
- 验证边界：无解释器可供运行，未执行拟议 ZZY CLI、黑盒、GUI 或性能测试；指南存在不表示 P06 已完成。Git 未提交，下一项仍为 P00-01。

## 2026-10-09：P00 基础设施实现与验收

- 用户任务：接手项目并仅完成 P00，保留语法、库接口、requirement 和既有修改；实际验收后建立本地提交，不推送、不改写历史。
- 接手事实：根目录已有 23 份 Markdown，尚无 Python 实现；Git main 工作区干净，已有设计提交 `58543cd46aa1ace082f23e39ce692ac7ae732daf`（docs: add initial ZZY language design and development guides），并非旧日志中的“无提交”。保留该设计提交作为本轮骨架的父提交。
- 环境：终端调用 python/py 均提示命令不存在；找到本机 bundled Python `C:\Users\13691\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。实际 CPython `3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]`，Unicode `15.0.0`，平台 `Windows-11-10.0.26200-SP0`，Git `2.50.0.windows.1`，setuptools `84.0.0`，宿主十进制数字上限 `4300`。项目配置暂限定 Python 3.12.14，不声明其他 Python/OS 已验证。
- 阅读：项目 SKILL、README、requirement、roadmap、todo、最新记录，以及 syntax/stdlib、interpreter、resources、diagnostics、sketch 的类型/接口/GUI 边界、test-coverage。核对 io.print 单参数换行、输入 EOF 为 Null、严格 Bool、普通数除法/下标、默认字段每次求值、从左到右求值及首错停止；现有契约已经说明这些行为，没有新增或改名语法/标准库。
- 文件：建立 zzy 包、pyproject.toml、忽略规则、tests、examples、benchmarks、apps。实现 CLI help/version/info/source-info、Source/SourceLoader、Diagnostic/Span、ResourcePolicy/ResourceMeter/Reservation、取消/资源中止信号、Output 和不加载 GUI 的原生元数据注册结构。没有创建占位 Lexer/Parser/AST 执行器或返回假成功的 run/check/test。
- CLI 范围：info 返回环境、完整有效资源值与 SHA-256 指纹；source-info 真实读取并计算同一字节快照摘要，明确输出 syntax_checked=false。它们是 P00 开发工具，语言 run/check/test 按 P01 后续接通；未实现命令当前报 E401/2。帮助/版本不加载配置。根 README 已给出实际 Python 路径、虚拟环境、源码运行和可选安装方法。
- 资源：采用 default-v1 的全部 22 个核心键，校验配置版本、字段、重复键、非正值、Bool、非整数、UTF-8 和 64 KiB 文件上限。实现支持的配置整数范围为 1..sys.maxsize；允许单项高于总量，二者共同生效。指纹覆盖补齐默认值和宿主十进制限制，默认有效转换限额 4096；没有关闭宿主限制。默认指纹 `2e654aef52d3267bfecf0768bef9faee1eed942a329001ec455aee951c858bd2`。
- 源码与路径：增量读取限制单文件/总量，规范路径去重，同一准备会话保持字节快照，UTF-8 开头去一个 BOM，保留 CRLF/原文码点坐标与 EOF 零宽 span。入口/配置相对进程工作目录，importer 参数相对导入文件，不 chdir；use 语句本身未实现。
- 诊断与清理：统一文本/UTF-8 JSON Lines，缺文件/坏配置位置为 null，用户错误、资源中止、取消和内部缺陷分开。预留在全部检查后原子计费，失败/退出释放；输出按 UTF-8 字节检查，最终诊断独立预留至多 4 KiB、完整 JSON、只写一次。前端/执行资源信号分别为退出 2/1，取消出口 130；内部缺陷使用 internal_error，不冒充 E201。
- 实际测试：用 bundled Python 执行 `-m unittest discover -s tests -v`，33/33 通过（4.976 秒），无跳过；再通过 `-m venv --without-pip .venv` 建立独立环境，`.venv/Scripts/python.exe -m unittest discover -s tests -v` 33/33 通过（8.447 秒）。覆盖真实 CLI 子进程、中文/空格路径、UTF-8 管道、坏参数/缺文件/配置、源码 BOM/CRLF/补充平面字符/Tab/EOF、22 项计量接口的小限额 L-1/L/L+1、失败后计数与句柄释放。执行阶段资源出口在宿主层测试，未称 ZZY 程序运行成功。
- 默认容量实测：单文件 2 MiB 的 L-1/L/L+1，源码总量 16 MiB 等于/超过上限，stdout 1 MiB 的 L-1/L/L+1；配置 64 KiB 的 L-1/L/L+1。另验最终诊断在长 Unicode 消息/路径下不超过 4 KiB，JSON 可解析、stderr 耗尽仍可报告。取消/MemoryError/RecursionError/内部缺陷通过真实 CLI 异常边界故障注入，不等同于真实终端按键验收。
- 包验证：使用 bundled Python 的 `-m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist` 离线构建成功；随后用其 pip 的 `--python .venv/Scripts/python.exe install --no-index --no-deps dist/zzy_language-0.0.1-py3-none-any.whl` 安装成功。`.venv/Scripts/python.exe -I -m zzy --help`（排除源码目录导入）与 `.venv/Scripts/zzy.exe --version` 均退出 0。源码读取样例实际输出 143 字节、68 码点、3 行、syntax_checked=false。
- 静态复核：27 份 Markdown、257 个本地链接有效，围栏闭合；70 项任务 ID 唯一，先勾选已验收的 P00-01/02/03，P00-04 等提交后再勾选。EBNF 与父提交逐字一致，stdlib/sketch 未修改；requirement 原始字节 SHA-256 仍为 `B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B`。git diff --check 通过，.venv、wheel/build/egg-info、__pycache__ 已忽略，不纳入提交。
- 过程记录：两次文档 apply_patch 因只匹配了段落中的部分文本而被拒绝，均未写入；改按完整段落或精确子串替换后成功。编码测试发现前的代码复核将 SourceLoader 对 RuntimeError 的处理收窄，避免把宿主 RecursionError 误报 E401；对应资源兜底/清理测试通过。没有失败测试或跳过项被记作成功。
- 验证边界：没有 Lexer、Parser、Resolver、执行器、标准库实现、ZZY 黑盒/性能/应用/GUI；所有运行时对象引用环、缓存、未来 AST/值分配点仍需后续阶段接入和验证。元数据注册不包含可调用 sketch 实现。真实终端 Ctrl+C、其他 Python/OS 尚未验证；不宣称完整沙箱或 P06 验收完成。
- 本轮未发现需要修改语法、公开标准库接口或交付范围的契约矛盾；修正的是旧 Git/能力快照，新增 P00 工具命令及配置实现范围已在 README/resources 明示。下一阶段为 P01-01（Token、固定符号和注释扫描），本轮到 P00 为止。
- Git 提交标识将在骨架提交建立后追加，避免预写不存在的哈希。

### P00 本地提交与交接

- 已建立骨架提交 `b9e78fe9cc023e9a95b5cffb673a11b50f6a9f34`：`feat: establish P00 CLI and interpreter foundations`；父提交为已有设计 `58543cd46aa1ace082f23e39ce692ac7ae732daf`。提交前逐项核对 34 个纳入文件，确认没有 requirement、stdlib/sketch、环境目录、构建产物或缓存，暂存差异检查通过。
- Git 操作首次受沙箱 .git 只读限制，无法创建 index.lock；按用户已授权的本地提交范围申请工具提权后正常暂存和提交，无自动审核拒绝、无推送、无历史改写。提交后工作区核对干净。
- 在真实提交成功后勾选 P00-04，P00 四项全部完成，其余 66 项保持未完成；本段与 todo 的提交证据作为单独交接记录提交。本轮到此结束，下一项 P01-01。

## 2026-10-10：P01-01 词法扫描与 CLI 黑盒

- 用户任务：选择最早依赖已满足的未完成代码任务，完成该项或可独立验证子步骤后结束；P01 起通过真实 CLI、独立 .zzy 和外部清单验收，不提前使用 spec。
- 接手核对：读取 skills/zzy/SKILL.md、todo 交接栏、最新开发记录和当前代码；实际分支为 feature，跟踪 origin/feature，HEAD 为 `62a6056b27867c6362ba82f30307f7e0fe2351d6`，工作区干净。保持该分支，不按旧日志切回 main。项目 .venv 可用，CPython 3.12.14 / Unicode 15.0.0 / Windows 11 与 P00 一致。
- 任务选择：P00 四项已经完成，最早可执行项是 P01-01。按 syntax 第 2—4 节、interpreter 第 3 节、resources、diagnostics、roadmap 与 LEX-01/02/03、STR-01 覆盖要求实现；不开展 P01-02 的 AST/执行。
- 实现：新增 tokens.py/lexer.py，按首字符分流及最长匹配登记全部固定关键字、预置类型、颜文字和运算符。Token 保存 Source/原文半开偏移，数字保留原文，字符串带解码值/raw 标记；Unicode 名字使用固定长度 isidentifier 判定，不归一化，裸保留名为 RESERVED_NAME，孤立 zzyend 为 E101。
- 注释/字符串：单行到行末/EOF，多行不嵌套，按左右 Unicode 标识符延续字符检查第一个完整 zzyend；引号和注释标记在多行正文内不改变模式。普通字符串一次解码全部 [OoO] 转义，raw 跳过空白/注释后必须接双引号字符串；字符串内不识别注释，未闭合/物理换行/raw 缺字符串为 E101，错误转义为 E102，保留原始源码位置。
- 资源：每文件非 EOF Token 生成前检查数量；逐步限制 ASCII 数字位数（含前导零）和解码字符串码点；长名字/字符串/注释内设置取消检查。前端超限 E211/2，EOF 和注释不消耗 Token 配额。AST/源码嵌套、整数实际转换/位数、运行时对象计量仍留给后续对应分配层。
- CLI 与版本：增加 `python -m zzy lex FILE`，成功输出带 schema_version/kind/lexeme/value/raw/span 的 Token JSON Lines，以 EOF 结束；完整扫描失败时 stdout 为空。输出超限可能留下此前完整记录，但必须非零退出。lex 不解析、不执行，不能替代 check；run/check/test 仍未注册。包版本变为 0.1.0a1，语言 v0.6/标准库 v0.6.1 不变。
- 测试文件：新增 tests/lex/inputs 的 62 份独立 .zzy 和 cases.json；期望按契约显式维护，没有用待测 Lexer 导出快照。成功逐项比较完整 Token/值/位置，失败比较错误码、文件、span、退出码及可选消息片段。含普通程序词法输入、正常边界探针和独立非法源码，未把故意不满足语句语法的词法探针称作可执行程序。三份 BOM/CRLF 用例通过 .gitattributes 保留原始字节。
- 辅助器：test_lexer_cli.py 启动真实子进程，并行有界捕获两条管道，默认每例 10 秒/每流 1 MiB；超额、超时、坏清单/空清单均失败。当前 lex 不执行用户代码、不产生子进程树；这不是 P01-04/P06 的完整执行/spec 运行器。另有宿主测试验证计量、取消、长输入的边界检查次数和捕获器失败行为。
- 实际命令与最终结果：`.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v`，101/101 通过，22.732 秒，无跳过；包含原有 33 项、62 个新词法 CLI 用例、5 项词法宿主测试及 1 项捕获器测试。固定符号/最长匹配、全部转义/raw、两种注释、Unicode/不归一化、BOM/CRLF/Tab/EOF、数字默认 4095/4096/4097 和 Token 默认 249999/250000/250001 均得到真实验证。
- 示例实测：`.venv/Scripts/python.exe -m zzy lex examples/lexer.zzy` 退出 0，30 个 Token（含 EOF），普通字符串得到实际换行，raw 保留字面 [OoO]n；没有执行 io.print。`.venv/Scripts/python.exe -m zzy lex tests/lex/inputs/unclosed-comment.zzy --diagnostic-format json` 退出 2、E101，span 从第 1 行第 1 列到第 12 列，stdout 为空。
- 失败与修复记录：首次准备外部清单时手写 beta 偏移不对，生成脚本断言停止，核对原文后修正；第一轮 60 项中有一项 # 列号期望少算 1（实际第 15 列），根据文件字符位置修正；新增输出预算场景后的 101 项中一项误要求源码 file，而输出预算诊断应为 CLI 的 file/span=null，清单显式注明 null 并保留其他完整校验。之后 101 项全通过，没有删用例、跳过或以静态检查冒充运行成功。首轮宿主测试输出受终端编码影响，后续测试命令加 -X utf8；CLI 自身 UTF-8 管道断言始终通过。
- 长输入测量：对已读取 Source，仅计宿主 Lexer.scan，每档 5 次中位数；标识符 10000/20000/40000 码点为 2.563/4.612/9.256 ms，多行注释 10000/20000/40000 个 zzyending 候选为 14.023/33.765/73.562 ms。另用宿主测试检查边界判定次数不超过线性上界。这是本机前端增长探针，不是 P07 等价 ZZY/Python 业务基准或性能优势结论。
- 打包实测：bundled Python 执行 `-m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist` 成功生成 0.1.0a1 wheel；使用其 pip 的 `--python .venv/Scripts/python.exe install --no-index --no-deps dist/zzy_language-0.1.0a1-py3-none-any.whl` 更新项目虚拟环境成功。安装后 `.venv/Scripts/python.exe -I -m zzy lex <examples/lexer.zzy 的绝对路径>` 退出 0、30 个 Token，`.venv/Scripts/zzy.exe --version` 输出 0.1.0a1 (P01 lexer)。仅更新项目虚拟环境，未改系统 Python。
- 文档与保留：更新 README、词法/测试说明、SKILL/guide 状态、resources/diagnostics 与开发导航；28 份 Markdown 的 263 个本地链接有效，围栏闭合。syntax/stdlib/sketch 与接手提交内容一致，requirement 原始字节 SHA-256 仍为 `B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B`；git diff --check 通过。构建/虚拟环境/缓存保持忽略。
- 完成与交接：P01-01 满足词法完成标志并勾选；70 项中仅 P00 四项及 P01-01 共 5 项完成。P01 整体尚不能输出程序结果 5 或诊断缺分号，P01-02/03/04/05 均不勾选。下一项 P01-02：建立最小 AST、声明/赋值、加法、字符串与打印，复用当前词法与位置；本轮结束，不提前实现 spec、运行器全功能或后续阶段。
- Git：本轮基于 feature 的 62a6056；实现、测试与本记录组成一个本地提交，提交标识以 Git 历史及本轮交接报告为准，不推送、不改写既有历史。
- 提交前补充检查：首次 git diff --cached --check 将三份刻意保留的 CRLF 样例中的 CR 报作行尾空白；在这三条 .gitattributes 中显式设置 cr-at-eol，同时保留 blank-at-eol/blank-at-eof/space-before-tab 检查，未改变测试输入字节。

## 2026-10-10：P01-02 最小 AST 与真实执行

- 接手核对：按项目 SKILL、todo 交接和最新开发记录读取 syntax/stdlib、interpreter/resources/diagnostics、roadmap/test-coverage。实际起点为 feature 的 6bb7dbe，工作区干净、相对 origin/feature ahead 1；CPython 3.12.14 / Windows 11 10.0.26200 / Unicode 15.0.0 与此前一致，PATH 仍无 python/py，使用 .venv/Scripts/python.exe。没有把已写设计当成已实现功能。
- 本轮实现：新增 ast_nodes.py、parser.py、prepare.py、interpreter.py。不可变 AST 保存定位 Token、完整表达式范围和深度；Parser 支持最小声明/赋值/分组/加法/普通调用，缺分号、括号和非法目标明确 E103。prepare 先完成整文件顶层名称检查及 Int 字面转换，不运行表达式；重复声明 E301、自引用/前向未知名 E302 均先于任何输出。运行时用简单绑定表树遍历，无 eval/exec、无 VM、无任意 Python 属性访问。
- 可观察语义：非负 Int 加法、String 拼接及 Lexer 的一次转义解码；zno 禁止重新绑定、zyes 允许，未注解绑定可变更类型。Int/String/Null/Function 注解在初始化/重新绑定时检查。io.print 是登记的普通一参函数，可保存函数/命名空间别名，返回 Null。调用先求 callee、再逐个实参、最后验证可调用性及个数；只读赋值在 RHS 副作用前拒绝。运行错误不回滚已有 stdout。负号/其他数值与 Bool/Null 字面量、块/控制流等仍待 P02，函数/完整作用域待 P03。
- CLI 范围决定：为按用户要求做真实 P01 黑盒，本项接入既定 run FILE 入口，没有增加临时同义命令；P01-03 的 check 未注册、不勾选。run 前端错误退出 2，执行错误退出 1，成功 0；复用 UTF-8、JSON/text 诊断和全局异常出口。包版本升为 0.1.0a2，语法/库版本不变。
- 资源：AST 节点创建前检查总数和最长父子边数，源码括号嵌套独立检查；Int 字面转换受 numeric_digits 和 integer_bits 约束。执行前检查拼接大小/整数加法精确位数；Int/String 载荷、io/print 对象、绑定/实参槽、格式化临时文本接入预留。别名共享载荷，无引用替换值及时释放；上下文退出时统一释放残留预留，异常 traceback 保持存活也不保留预算。当前仅无环标量/只读命名空间，未声称容器、闭包、引用环及缓存已验证。
- 测试：新增 tests/run/inputs 的 93 个独立 .zzy、外部 cases.json 与 test_run_cli.py，真实子进程执行，不依赖 spec；期望手写，位置按输入原文核对，不从被测实现生成输出快照。覆盖正常程序、先声明后使用、类型/调用/写入错误和副作用顺序、显式未支持语法、默认 4096 位整数输出、AST/文本/位数/输出/在用载荷/引用槽边界。6 个宿主测试覆盖 AST 范围/结合性、Program 复用、跨字节加法位数、取消及异常/超额清理。捕获器复用现有有界进程辅助器，空清单/重复 ID/超时/输出超额不能成功；当前子集不启动子进程，完整进程树回收仍属 P06。
- 真实失败与修复：第一批清单的 EOF 列号及超深 AST 主位置期望有误，按源码与节点位置核对修正后 79 项通过。复核补充 raw 表达式完整范围、整数格式化共存临时文本预算后，新增 raw 注解错误用例手写列号差 1；按文件中 (raw) 至字符串末尾原文范围修正为 [19,29)。所有用例保留，无跳过或删除失败场景。
- 回归命令与结果：`.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v` 在首次扩展后 197/197 通过（41.703 秒）；完成复核修正后 `.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -q` 最终 200/200 通过（46.971 秒），无跳过，包含原有 101 项、93 个新执行黑盒及 6 个宿主测试。没有用 compileall 或静态检查代替实际执行。
- 示例命令与结果：`.venv/Scripts/python.exe -m zzy run examples/hello.zzy` 输出 `5`、退出 0；`... -m zzy run tests/run/inputs/missing-semicolon.zzy --diagnostic-format json` stdout 空、E103/退出 2，EOF span 为第 2 行第 13 列零宽。混合加法、只读赋值和调用顺序的退出码/已有输出由外部清单逐项验证。
- 打包：bundled Python 执行 `-m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist` 成功生成 zzy_language-0.1.0a2-py3-none-any.whl；再执行其 pip 的 `--python .venv/Scripts/python.exe install --no-index --no-deps dist/zzy_language-0.1.0a2-py3-none-any.whl` 成功升级项目虚拟环境。`.venv/Scripts/python.exe -I -m zzy run <examples/hello.zzy 的绝对路径>` 输出 5，`.venv/Scripts/zzy.exe --version` 输出 0.1.0a2 (P01 interpreter)。未联网安装，未修改系统 Python。
- 文档：同步 README、SKILL/guide、导航、测试/示例说明、资源/诊断与实施文档；syntax/stdlib 只更新实现状态，不改规则或版本，sketch 未改。文档本地链接和围栏检查通过（27 份 Markdown，264 个本地链接）；requirement 原始字节 SHA-256 保持 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。git diff --check 通过，venv/build/dist/cache 保持忽略。
- 验收与下一项：只勾选 P01-02；70 项代码任务中 6 项完成。P01 完成标准中的输出 5、非法字符/未闭合串/错误转义/缺分号定位已有实际验证，但 check 零执行仍缺，P01 整体未完成。下一项 P01-03：复用 prepare 接通 check，补 run/check 的入口与无副作用黑盒；不开始 P02 或 spec。
- Git：本轮代码、93 份源程序、外部期望、宿主测试和文档一起形成有意义的本地提交；提交标识以 Git 历史及本轮报告为准。提交前核对纳入文件，不纳入构建产物，不推送、不改写历史。
- 提交前补充：首次检查暂存区时发现 4 个新增 Python 文件末尾多一个空行，已删除并重新检查；未改运行逻辑。暂存清单为 121 个文件，93 份 run 源程序与外部清单一一对应，未纳入 requirement/sketch、构建产物或虚拟环境。
