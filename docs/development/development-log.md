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

## 2026-10-10：P01-03 至 P01-05，非执行检查与 P01 整体验收

- 授权与核对：用户要求按同样标准从 P01-03 连续完成整个 P01，故本轮覆盖 03/04/05 后结束，不进入 P02。重新读取项目 SKILL、todo 交接/最新日志，按索引核对 syntax/stdlib、interpreter/resources/diagnostics、roadmap 与 test-coverage。真实起点为 feature 的 8c42467，工作区干净、相对 origin/feature ahead 2；宿主仍为项目 .venv 的 CPython 3.12.14 / Windows 11 10.0.26200 / Unicode 15.0.0。没有用户未提交修改。
- P01-03：CLI 注册 check FILE，与 run 共用 SourceLoader 和 prepare；只有 run 构造 Interpreter 并切到执行阶段。check 成功时两个输出流为空、退出 0；词法/语法/名称/字面值准备及前端配额错误仍退出 2。一般运算、io.print、运行时类型/调用/可写性与执行预算不提前触发；未实现语法仍拒绝。新增 105 个外部 check 期望，其中 93 项复用 run 的独立源码但保存独立期望，另覆盖极小执行预算、后段名字错误、源码/Token 配额、诊断样例、BOM/CRLF/Tab、中文空格路径、cwd 和缺文件。两份 CRLF 源码由 .gitattributes 保留字节。
- P01-03 验证：`.venv/Scripts/python.exe -X utf8 -m unittest tests.test_check_cli -q`，105/105 通过、19.686 秒。扩展 test_cli 验证 run/check 的缺文件/非法 UTF-8、参数前后顺序、-- 后以连字符开头的中文空格路径、同一前端错误 text/JSON 一致；另在真实 prepare 路径上断言 check 从不构造 Interpreter。没有把运行时类型错误在 check 中报出当成静态检查能力。
- P01-04：新增 tests/blackbox.py 作为统一外部运行器，tests/process.py 负责新进程及有界 I/O，原 lex/run 测试适配器改为复用同一实现。三份清单显式记录 mode/stdin，旧 155 项 lex/run 的 Token、输出、诊断、限额和退出期望逐项与 HEAD 对比保持一致，没有删改已有答案。按路径稳定排序；每例新进程，stdout/stderr 并行读取，独立容量、超时、临时 stdin 和资源配置均明确。
- 运行器失败语义：坏/空清单、重复键/ID、缺字段、非法类型/模式/限额、启动失败、输出/错误位置不符、超时和输出超额均失败，整体返回 1。可选 --report 保存版本、数量、命令、原始期望、实际退出码、失败详情、生效策略和指纹；写报告失败也失败。清单是外部固定期望，不使用 spec，也不通过解释器生成答案。不是未来 zzy test 或完整语言黑盒，运行器在仓库 tests 中而非发行包内。
- 捕获器复核：原 read(4096) 可能在子进程只写少量超额数据后等待时延迟检测，改为 read1(4096)；用“写 32 字节、flush 后等待，捕获限额 16”的真实进程验证立即按超额失败。补双管道各 100000 字节与 UTF-8 stdin、stderr 独立上限、超时后进程/管道回收；当前 P01 子集不产生子进程树，派生进程/GUI 清理仍留 P06。`.venv/Scripts/python.exe -X utf8 -m unittest tests.test_blackbox_runner tests.test_cli -v`，20/20 通过、8.913 秒。故意错误的答案/清单/超时是运行器反向测试，不是跳过或掩盖语言测试失败。
- 完整回归：`.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -q`，316/316 通过、62.959 秒、无跳过；其中 260 个外部 CLI 用例和 56 个宿主/入口/运行器测试。原 P00/P01-01/02 行为未见回归，本轮没有未修复的测试失败。
- 独立总验收：`.venv/Scripts/python.exe -X utf8 -m tests.blackbox --report dist/p01-blackbox-report.json`，260/260 通过、52.020 秒、退出 0。含 lex 62、run 93、check 105；报告中每例 observed_exit_code 与外部期望一致，26 种有效资源策略/指纹。报告属于可重建产物，保持忽略、不纳入 Git。
- P01-05 发布验证：包升至 0.1.0a3，info.stage 为 P01。bundled Python 执行 `-m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist` 成功，再用其 pip 的 `--python .venv/Scripts/python.exe install --no-index --no-deps dist/zzy_language-0.1.0a3-py3-none-any.whl` 安装成功，仅修改项目虚拟环境、未联网安装依赖。`.venv/Scripts/zzy.exe --version` 输出 0.1.0a3 (P01 interpreter)。
- roadmap 完成标准实测：使用安装包的 `.venv/Scripts/python.exe -I -m zzy run <hello.zzy 绝对路径>` 输出 `5\n`、stderr 空、退出 0；同样的 check 命令双流为空、退出 0。再以 run/check 分别运行 lexical-before-effects、unclosed-string、bad-escape、missing-semicolon 四份独立错误源码，均 stdout 空/退出 2，错误码分别 E101/E101/E102/E103；半开 span 分别为第 1 行 [20,21)、[10,11)、[11,17) 和第 2 行 [13,13)。安装包也通过这些检查，没有只验证工作区导入。
- 使用说明：更新 README、SKILL/guide、导航、测试/示例说明、资源/诊断和实施文档。修正文档陈旧状态：roadmap 第 9 节原把 run/check 也称为未实现；guide 完整函数/spec 设计示例原引用 hello.zzy 却期望 15，与实际最小 hello 输出 5 混淆，现明确使用未来 total-up-to.zzy 设计示例，未改任何语言规则。文档静态验证为 28 份 Markdown、270 个有效本地链接、围栏闭合，仅作为文档检查，不能替代上述真实执行。
- 保留与交接：syntax/stdlib/sketch 正式契约本轮未改，requirement SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。只新增勾选 P01-03/04/05，P01 整体完成；70 项中完成 9 项。下一项 P02-01：数值、Bool、Null、比较及逻辑短路，仍用外部 run/check 清单，不提前依赖 spec；真实终端 Ctrl+C、其他平台及完整运行器能力未声称完成。
- Git：实现、用例、统一运行器和本记录组成一个 P01 阶段验收本地提交；提交标识以 Git 历史及本轮报告为准。提交前检查暂存清单、空白与文档/用例对应关系，不纳入 wheel、报告、缓存或虚拟环境，不推送、不改写历史。
- 暂存前保护检查补充：直接把 Git blob 字节与工作区 syntax 文件比较时，因 Git LF/工作区 CRLF 产生断言失败；随后按仓库过滤规则用 git hash-object --path 与 HEAD 对象比较，syntax/stdlib/sketch 均一致，未改这些文件。requirement 仍单独按原始字节 SHA-256 验证。最终暂存 40 个文件，git diff --cached --check 通过，无漏暂存或意外新文件。


## 2026-10-11：P02-01—05 连续实现与阶段验收（10 月 10 日接手）

- 起点与范围：按 skills/zzy/SKILL.md、todo 交接、最新日志读取 syntax/stdlib、interpreter/resources/diagnostics、roadmap/test-coverage。feature 与 origin/feature 均在 f3f11e3，工作区干净；实际 CPython 3.12.14（MSC v.1944 AMD64）、Windows 11 10.0.26200、Unicode 15.0.0，使用项目 .venv。用户授权完成全部 P02 并验收、本地提交，本轮未进入 P03、未推送。
- P02-01：Parser 扩展优先级及 Bool/Null/Float、一元/二元运算，禁止未分组比较链。运行时严格区分 Bool/Int，Int/Float 混合算术、精确数学比较、负数向下整除/取余、有限 Float 与除零诊断均接入；and/or 严格 Bool 且短路，不执行被跳过的打印、输入或数组修改。
- P02-02：增加块、if/elif/else、while/for、半开 Range、break/continue。prepare 以词法声明身份绑定名字，拒绝同块重复、初始化自引用（不回退外层）和循环外跳转；运行时每次块/每轮循环建立独立绑定，for 变量只读。Range 保留边界，长度不展开数组，String 按码点索引/遍历。完整函数/槽位/闭包留 P03，未将这些前置工作勾作 P03 完成。
- P02-03：values.Array 统一 push/pop/replace 入口；别名共享载荷，浅 copy 新建外层，替换更新内容版本，增删更新双版本。活动遍历计数覆盖嵌套遍历，最后一轮及随后即将 break 也在增删前 E206；允许替换，后续迭代读取新值，finally 在错误/取消/内存异常时清理计数。赋值先保存实际容器/下标、检查可写性，再求右侧，写入前重查，覆盖右侧 pop 导致旧下标失效。
- P02-04：顶层 shape 定义、名义注解、字段写入及浅层 with。构造先检查字段清单，再按源码顺序求显式值/检查类型，然后按声明顺序求默认值。默认表达式按定义处词法身份查绑定；数组字面每实例新建、外部数组默认共享。with 原值只求一次，不重跑默认值，未替换字段共享引用。缺/重复/额外构造字段 E203、未知访问字段 E302、类型 E201，位置与测试清单一致。
- P02-05：注册基础原生函数元数据和实际实现 io.input、len、str、range、array.copy/push/pop（保留 io.print）。输入提示先 flush，UTF-8 严格读取，原样保留 [OoO]、剥离一组 LF/CRLF，空行与 EOF 不混淆；读取失败 E401、资源失败 E211，不伪装 EOF。其他 stdlib 接口如 array.sum 仍明确 E302，不写成可用。新增 examples/grades.zzy，成绩统计/菜单业务由 ZZY 执行；姓名与 1 输入得到科目数 4、总分 344、平均分 86.0、最高分 100、及格科目 4，退出与 EOF 另有固定期望。
- 资源与隔离：Float/数组/结构/Range、块/循环绑定和原生引用纳入计量；数组增删容量检查在写入前，别名不重复计载荷，配额不足先回收不可达环，退出统一释放预留。Int 正负加减精确探测宽度；乘积上界可能误拒绝时回退分块精确探测。Int 转文字先检查数字/文本与载荷预算。调试显示有界收集、根复合值深度为 1、循环路径显示 <cycle>，不泄露对象地址；同一 Program 重跑的数组/结构/输入隔离由宿主测试验证。这是逻辑资源计量，不是进程 RSS 保证。
- 测试与失败修复：新增 tests/p02 的 279 个外部期望（139 run、140 check）和 10 项宿主测试。保留 P01 全部 260 例，迁移六类原“不支持”期望：Float/Bool/负号/数组/块现在成功；Float 注解赋 Int 的 run 改 E201、check 成功，spec 仍拒绝。首轮旧回归 12 个失败均对应这些能力变化；新增 209 例首轮有 7 处定位差异，修正运算符/下标定位并将单一类型原生实参指向值表达式，复测 209/209。581 项扩展回归发现迁移用例列号手写偏 1，按原文修正；随后 599/599 通过。验收补修 CRLF 在内容上限处的处理、value_depth 根容器计数、保守乘积预算回退、结构字段误套 Array 容量上限，以及 str(Int) 先预留后转换，并加入相应边界。
- 验证辅助失败也如实保留：初次清单生成脚本引号冲突未生成用例，修正后执行；误写 io_bytes 配置键被运行器收集校验拒绝，改用契约现有 io_payload_bytes。第一次读取隔离 Python 包路径受宿主默认编码影响而解码失败；改为 -I -X utf8 后完成比对，没有把该失败当作安装验证成功。
- 最终完整回归命令：`.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -q`，605/605 通过、131.198 秒、退出 0，无跳过（539 个真实 CLI 期望 + 66 个宿主/运行器测试）。已有 P00/P01 功能未见回归；运行器的空/坏清单、错误答案/诊断、超时、输出超额和启动失败测试仍会明确失败，不能以空收集报成功。
- 独立黑盒命令：`.venv/Scripts/python.exe -X utf8 -m tests.blackbox --report dist/p02-blackbox-report.json`，539/539 通过、109.961 秒、退出 0。实际 lex 62、run 232、check 245，报告逐项 passed 与 observed_exit_code 符合外部期望，包含 36 种有效资源策略指纹。报告保持忽略、可重建。check 专用程序含输入、无限循环、结构默认副作用、数组修改和除零，在运行预算仅 1 时仍双流为空；不构造 Interpreter 的原有宿主检查保留。
- 发布验证：版本升为 0.2.0a1，info.stage=P02。bundled Python 执行 `-m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist` 成功，再用其 pip 的 `--python .venv/Scripts/python.exe install --no-index --no-deps dist/zzy_language-0.2.0a1-py3-none-any.whl` 离线安装。`.venv/Scripts/zzy.exe --version` 输出 0.2.0a1 (P02 interpreter)。从 dist 工作目录以 `.venv/Scripts/python.exe -I -m zzy run/check <绝对路径> --diagnostic-format json` 验证 13 条成绩菜单、短路、默认新建/共享、活动遍历与零执行 check 用例，均符合固定输出/退出码；16 个安装 Python 源文件与工作区逐字节一致。
- 文档和契约：更新 README、skills 指南/SKILL、能力状态、覆盖映射、examples/tests 说明、资源与诊断实施细节。修复指南中“只有文档/数组仍不支持”等过时描述；syntax/stdlib 只修改当前实现状态与验证状态，语法、EBNF、库签名与行为不变。29 份 Markdown、275 个本地链接与围栏检查通过，静态结果不替代运行证据。requirement 原始字节 SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。
- 完成标准与边界：roadmap 的成绩/菜单运行、短路跳过副作用、shape 新数组默认与外部数组共享全部有 CLI 证据。P02-01—05 均勾选，70 项完成 14 项；没有已知未修复的本阶段失败。其他 Python/OS、真实终端 Ctrl+C、派生进程树/GUI 回收、函数/闭包/跨函数跳转、回调/数组校验缓存、完整 RESOURCE/CLI 和 P06 覆盖仍未验证或待实现，不据本阶段测试推断完成。下一项 P03-01。
- Git：实现、独立源码/期望、测试、指南和本记录组成一个本地 P02 阶段提交，标识以 Git 历史和本轮最终报告为准。提交前核对纳入文件、git diff --check、requirement 哈希；不纳入 .venv、wheel、临时生成脚本或报告，不自动推送、不改写历史。


## 2026-10-11：P03 函数、局部槽位与闭包实现及阶段验收

- 用户任务：连续完成全部 P03，并按 roadmap/todo/正式契约/test-coverage 验收；直接修复本阶段问题，补真实测试及文档，创建本地阶段提交后结束，不推送或改写历史。
- 接手核对：先读 skills/zzy/SKILL.md、交接和最新记录，再读 README、requirement、roadmap、syntax 函数/绑定/控制流、interpreter、resources、diagnostics、stdlib 及覆盖矩阵。实际工作区干净，feature 与 origin/feature 同在 `550fe5615f200914a44ed4221abb00d59935406b`；没有 AGENTS.md。实际 .venv 为 CPython 3.12.14 / MSC 1944 AMD64 / Windows 11 10.0.26200 / Unicode 15.0.0，PATH 没有 python/py，未把旧文档当作已实现 P03。
- 实现：Parser 接入固定位置参数、可选注解、具名/单表达式匿名函数、return；新增 resolver.py，按声明位置处理名称、参数可变性、遮蔽、自递归/前向引用及函数控制流边界。普通局部直接进入固定 Frame 槽位，只有可变捕获使用 Cell；不可变捕获保留原值/容器别名，多层捕获逐层传递，块/循环每次创建独立绑定。只读 Program 保存布局，运行时 Frame/Cell/闭包不进入 Program。具名函数自身引用单独连接，逃逸闭包仍可引用它。
- 调用与类型：保持先 callee、全部 args 左到右，再检查调用性/数量/注解；错误停止后续求值且不回滚此前副作用。注解按定义环境解析，函数创建时保存名义类型身份；参数重绑、捕获写入和显式/隐式返回仍校验，隐式返回 Null。未声明互递归、初始化自引用、非法 return 和跨函数 break/continue 在执行前拒绝。
- 执行与资源：继续 Python AST 树遍历，用户调用经生成器交给显式调用栈，不使用字节码或提高宿主递归限额掩盖问题。Frame/自身引用、捕获/类型引用、Cell 内容和函数对象进入既有计量。默认 63/64/65 调用层数及 syntax_depth=64 与 call_depth=64 组合有 CLI 证据，原生调用不计 ZZY 层数；退出/返回/异常清理局部、活动遍历与预留。
- 验收修复一：低配额探针发现驱动器保留已结束 CallRequest 和已丢弃返回闭包，使本应只占 4 个对象的后续数组分配请求第 5 个对象。改为及时清空请求并消费返回交接容器；新增 discarded-return-release、discarded-callee-release 与 live-return-not-released，证明死值释放且活值不提前释放。
- 验收修复二：普通函数诊断已有调用 notes，但资源中止跨函数传播缺少 notes。现 E211 也保留最内层主位置并追加调用位置，同时保留 ResourceExceeded/AbortSignal 类别，不吞成普通语言错误。新 resource-call-notes 的真实 run/check 与嵌套资源失败清理测试通过。
- 测试与独立期望：新增 tests/p03 的 118 个独立输入、cases.json 的 234 项期望（115 run、119 check），外加 examples/functions.zzy 纳入同一清单；正常用例都有 check 对照，四个 check 专用输入包含无限循环、I/O、无效运行时注解及递归。固定答案和源码位置独立维护，未从解释器导出快照，未依赖 spec。10 项宿主测试补普通槽位/实际共享 Cell、只读布局、Program/Interpreter 复用、输入隔离、闭包环回收、调用/活动遍历在诊断/取消/MemoryError/资源失败后清理、Frame 分配失败和返回范围。P02 的 unsupported-function 两项迁移为成功，原有其他 537 项期望未改变。
- 运行器验收：增加可选诊断 notes 的严格清单校验与比对。通过返回结果故障注入确认执行数不足、跳过、未产生观察结果和零收集不能报成功；真实空/坏清单、错误答案/诊断、超时、输出超额、启动失败与进程退出测试继续保留。最终报告同时要求非空、执行数量一致、无跳过、实际观察结果和 unittest 成功，不用 wasSuccessful 单独判断空运行。
- 过程与真实失败：运行时初稿把 yield from 放进列表推导，第一次导入测试报 SyntaxError，改成显式参数循环后原 16 项运行时测试通过。临时 for 捕获探针把区间误写成 0..3，按既有契约改为 0..<3；未改语法迁就探针。首轮 199 黑盒为 198 通过、1 个调用 notes 列号期望错误；首轮 10 宿主为 9 通过、1 个返回范围手算偏一列。按原文坐标核对后修正，230 项黑盒与 26 项运行时宿主通过。资源 notes 新用例也曾手算加号列号错误，改按固定源码字符位置计算后两项通过。没有删除/跳过失败用例，没有把这些初次失败记作通过。
- 完整回归：添加资源 notes 前，849 项 unittest 通过（187.185 秒），771 项独立黑盒通过（161.027 秒）。最终源码与新增用例定稿后执行 `.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -q`：851/851 通过、181.085 秒、退出 0、无跳过；其中 773 项 CLI + 78 项宿主/运行器。独立执行 `.venv/Scripts/python.exe -X utf8 -m tests.blackbox --report dist/p03-blackbox-report.json`：773/773 通过、161.782 秒、退出 0，lex 62/run 347/check 364，48 种有效资源指纹。两套入口覆盖有重合，不累加成不同用例数；最终报告逐项观察值与期望一致。
- 发布实测：版本 0.3.0a1，info.stage=P03。bundled Python 的 `-m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist` 离线构建成功，使用 `-m pip --python .venv/Scripts/python.exe install --force-reinstall --no-index --no-deps dist/zzy_language-0.3.0a1-py3-none-any.whl` 安装最终代码。`dist/verify_p03_install.py` 从 dist 工作目录用 `.venv/Scripts/python.exe -I -X utf8 -m zzy run/check <绝对源码路径> --diagnostic-format json` 验证 22 条函数/闭包、逐轮绑定、深调用、类型/前向引用错误、资源 notes 与 check 零执行用例；17 个安装 Python 源文件与工作区逐字节一致。zzy.exe --version 输出 0.3.0a1 (P03 interpreter)。报告、wheel 与临时脚本保持忽略。
- 指南与契约：更新根 README、skills/AI 入口、实现路线、诊断/资源说明、测试覆盖映射和示例入口。syntax 只更改能力/验证状态，2—10 节语法语义与父提交逐字一致，stdlib 原文不变，requirement 原始 SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。
- 阶段边界说明：roadmap P03 与 todo P03-03 提到 Lazy 捕获，而 P04-02 才引入 Lazy 语法/状态/唤醒。本轮完成可复用的传递捕获布局与共享 Cell 基础，在两处明确分工；Lazy AST 的捕获接入和运行验证保留 P04-02，当前 Lazy 仍拒绝，没有宣称可用或取消后续义务。未修改语言规则或新增公开库接口。
- 验收结论：roadmap 的递归/闭包正确、多次调用独立、跨函数跳转非法、槽位迁移后旧黑盒回归均有真实证据；P03-01—04 完成，70 项代码任务完成 18 项。无已知未修复的本阶段失败。其他 Python/OS、真实终端 Ctrl+C、模块/跨文件调用、Lazy/spec、库回调、GUI/派生进程树、完整 RESOURCE/CLI 与性能比较明确未验证或待实现，不以本阶段结果替代 P04/P05/P06。
- Git：本轮实现、独立源码/清单、宿主测试、指南和记录组成一个本地 P03 阶段提交，基于 feature 的 550fe56。提交标识以实际 Git 历史和最终报告为准；核对纳入文件、忽略产物、requirement 哈希及 git diff --check 后提交，不推送、不改写历史。下一项 P04-01，本轮到 P03 验收结束。

- 提交前静态复核：30 份 Markdown 的围栏和 281 个本地链接有效；70 个任务 ID 唯一、18 项完成。最终黑盒报告的 773 个逐项 passed/observed_exit_code 与期望一致，48 种资源指纹；git diff --check 通过。静态检查仅作一致性证据，不替代上述运行结果。

## 2026-10-13：P04 全部特色语法、隔离 spec 与阶段验收

- 用户任务：连续完成全部 P04，对照 roadmap/todo/正式契约/test-coverage 验收实现、成功/失败/边界用例和指南，创建本地阶段提交后结束；不推送、不改写历史。
- 接手核对：读取 skills/zzy/SKILL.md、todo 交接、最新日志及 syntax/stdlib/interpreter/resources/diagnostics/query/machine-units/roadmap/test-coverage。工作区初始干净，feature 与 origin/feature 均为 f1d57fadf9b6aede6a907cd1e73a94782a5f918b。实际 .venv 为 CPython 3.12.14、MSC 1944 AMD64、Windows 11 10.0.26200、Unicode 15.0.0，PATH 无 python/py；沿用 .venv/Scripts/python.exe。没有 AGENTS.md，不把历史能力说明当作当前实现证据。
- P04-01/03：Parser/Resolver/执行器接通 Result、常量/标签/兜底匹配及显式 Result 具名函数的后缀 ?。匹配目标只求一次、载荷分支局部只读、失败传播停止后续副作用；重复相等常量/标签、错误上下文和无覆盖均有诊断。管道先源、再被调用对象、再其他实参，唯一直接 @ 插槽，不自动解包或唤醒。
- P04-02：Lazy 使用已有传递捕获分析、共享 Cell 和显式调用栈。NEW 首次求值读取当时绑定，缓存值保留对象别名；普通错误缓存原诊断，FAILED 再次 wake 补当前调用位置。循环唤醒 E209；取消、ResourceExceeded 和宿主中止恢复 NEW，不永久缓存，Frame/深度/预留清理。宿主测试直接验证同一 Lazy 的失败复用与中止后重试，未伪造语言可以捕获致命诊断。
- P04-06/07：只读 Program 保存状态图和精确 Fraction 字面，运行时创建独立 Machine；只读 state、名义注解、失败固定消息与状态不变，成功先分配 Result 后提交状态。内部递归冻结覆盖 Array/Shape/Result 中实例及循环引用；公开模块/共享上下文接口未宣称完成。Quantity 原文字面精确，运行时 Float 按实际二进制值，量纲运算/相等/规范显示不降级；分母、中间乘积、交叉约分和指数相邻限额有独立 CLI 与 Fraction 对照。
- P04-08：查询 Resolver 检查条目顺序、@ 作用域、允许 AST 与真实 len/str 绑定，遮蔽/别名/动态/用户调用拒绝。执行输入一次、浅快照、take 一次、全部 keep、全部键、稳定 asc/desc、最终投影；take=0 不跳过筛选/排序错误。大 Int/Float 不先转换 Float 比较，Quantity 键检查同量纲。对象保持别名，结果是新 Array，每次调用重算，错误保留原位置及输入下标说明，结束恢复当前项。排序键在投影前清空，快照/索引/键缓冲和结果受预算。
- P04-04：断言检查 Bool，false 为 E210；trace 求值一次并向 stderr 写结构化位置和值，不隐式 wake。run 跳过 spec 执行但仍前端检查；test FILE_OR_DIR 按路径收集，全部准备成功后逐例新进程执行公共初始化及单独测试体。收集使用同批字节快照，总量受 source_total_bytes/module_count 约束；每例独立 cwd/TMP/TEMP/空 stdin 和策略。默认超时 10 秒，可设有限正数；父进程汇总 passed/failed/timed_out/collection_errors，空收集/坏源码/启动失败/坏输出/超时/输出超额非成功。复用有界进程捕获到 zzy/process.py，原测试兼容导入，保留进程回收回归。
- 阶段边界核对：todo P04-06/07 的 MACHINE-01/02、UNIT-01/02 引用的是完整覆盖类别，其中模块导出、unit.make/format、JSON 拒绝和文件库隔离依赖 P05；machine-units 第 3 节和 roadmap P05 明确其实施顺序。P04 完成核心状态/精确数量/显示及内部冻结，不提前把 unit 命名空间注册为可用；todo/覆盖映射明确本阶段子集，不修改语法/库签名或取消后续验证义务。
- 过程失败与修复：初版通配模式误按 IDENT 处理，223 项黑盒首轮发现 WILDCARD Token 不匹配，修复 Parser。测试稿另有 Lazy 注解拼写、缺失右花括号、管道 callable 未分组错误，依据既有 EBNF 修正输入；未放宽语法。spec 测试把 EOF 误预期为失败 Result、Lazy 显示误写大写，依据既有 Null 规则及显示实现修正。扩展用例三个失败来自两处原文范围标记（下标左方括号和匿名函数关键字），按固定源码坐标修正。首次完整回归 1095 项有四个失败：旧 unsupported-spec 两项及当时已加载的两个 spec 期望；没有删除或跳过失败用例。
- 测试落地：tests/p04 包含 157 个独立 .zzy 输入，连同两个 examples 共 317 项外部 run/check 期望（158 run、159 check）。正常/失败均检查 stdout、退出码及结构化诊断位置；check 专用源含输入、非法构造、无限循环和除零，双流为空。另有 12 项运行时宿主和 12 项 spec/trace/运行器测试，验证缓存/清理/顺序/别名/上下文隔离/冻结/原子性及防假成功。旧 unsupported-spec 源保留，仅将两项期望改成已支持时的成功；其余旧外部期望不变。
- 最终完整回归：`.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -q`：1192/1192 通过，338.965 秒，退出 0，无跳过；其中 1090 项外部 CLI 和 102 项宿主/运行器。定稿前新增宿主集中检查 `-m unittest tests.test_p04_runtime tests.test_p04_spec -q`：24/24，12.462 秒。外部用例已包含在 unittest 总数中，不把两入口相加为不同用例数。
- 示例实际运行：`-m zzy run examples/features.zzy` 输出 doing、两次 5::m*s^-1、[6, 4, 2]、(T_T)(invalid transition: doing -- missing)，退出 0；`-m zzy test examples/features-spec.zzy --diagnostic-format json` 汇总 tests=2/passed=2/failed=0/timed_out=0/collection_errors=0，退出 0。例子覆盖全部 P04 特色且不依赖 P05 库。
- 离线发布验证：包升级 0.4.0a1，info.stage=P04。bundled Python `-m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist` 成功，随后 `-m pip --python .venv/Scripts/python.exe install --force-reinstall --no-index --no-deps dist/zzy_language-0.4.0a1-py3-none-any.whl` 成功。`.venv/Scripts/python.exe -X utf8 dist/verify_p04_install.py` 从 dist 用 -I 隔离启动安装包：27 条 run/check 检查及两个 spec 通过，22 个 Python 文件与工作区逐字节相同；zzy.exe --version 为 0.4.0a1 (P04 interpreter)。wheel/临时脚本/报告均留忽略目录。
- 指南与契约：更新 README、skills 导航/指南/AI 入口、设计状态、诊断/资源/运行器说明、特色专题状态和覆盖映射。syntax 第 2—10 节、stdlib 第 1 节起接口正文、query 正文与阶段父提交一致；machine-units 仅更新实现状态，不改变正式规则。requirement 原文 SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。
- 未验证：其他 Python/OS、真实终端 Ctrl+C、模块/跨文件/文件库/JSON、公开共享上下文冻结、GUI/派生进程树、完整默认大容量 RESOURCE/CLI 矩阵与性能比较。P05/P06/后续扩展均保持未完成，不据本阶段核心验收推断通过。

- 最终独立黑盒：`.venv/Scripts/python.exe -X utf8 -m tests.blackbox --report dist/p04-blackbox-report.json`：1090/1090 通过、377.647 秒、退出 0。报告逐项 passed、observed_exit_code 与外部期望一致，计数为 lex 62/run 505/check 523；53 种有效资源指纹。
- 验收结论：roadmap 的特色示例可运行、失败有原文位置、副作用/边界/状态隔离有真实证据；P04 八项全部完成，70 项代码任务完成 26 项。没有已知未修复的本阶段失败，下一项 P05-01。当前版本仅完成所列 P04 核心，不扩展到 P05 实现。
- 提交前一致性：33 份 Markdown 围栏配对、285 个本地链接有效，70 个任务 ID 唯一，git diff --check 通过；静态检查只作一致性证据，不替代真实运行。确认 requirement 哈希及正式接口/语法正文不变。
- Git：将本轮实现、独立源码/期望、宿主测试、指南和真实日志纳入本地 P04 阶段提交。提交标识见实际 Git 历史和最终报告；不纳入 dist/.venv/wheel/临时生成脚本/报告，不自动推送、不改写历史。


## 2026-10-14：P05 全部标准库、模块与阶段验收

- 用户任务：连续完成 P05-01—04，并对照 roadmap/todo/正式契约/test-coverage 验收实现、失败/边界/别名/顺序/隔离、check 零执行与运行器防假成功；更新文档和本地阶段提交后结束，不推送或改写历史。
- 接手核对：读取项目 SKILL、todo 交接、P04 最新记录和 syntax/stdlib/interpreter/resources/diagnostics/query/machine-units/roadmap/test-coverage。初始工作区干净，feature 与 origin/feature 均为 b5406c94d96119875de968e2b8ac3664732d5a6d。真实环境仍为 .venv 的 CPython 3.12.14、MSC 1944 AMD64、Windows 11 10.0.26200、Unicode 15.0.0；PATH 无 python/py。没有 AGENTS.md。以当前文件和 Git 为准，未直接沿用记忆里的分支领先状态。
- P05-01：建立 native/catalog 的封闭注册表，35 个原生函数及 array.Stats 原生类型；记录 ABI、签名、外层类型、返回、直接错误、效果、固定纯性和回调/wake 的错误传播。参数数量/外层类型在工作前校验，Bool 不作为 Int；只对预期 IO/JSON 格式失败转换 Result，资源、取消和 MemoryError 不吞掉。原有调用/Cell/配额机制保持，未开放 Python 属性或新增公开接口。
- P05-02：完成整数 sum/stats、稳定 sorted、map/filter、text/math、Map/严格 JSON、data.kind、unit.make/format 和文件接口。stats 空值 min/max 为 Null，每次返回新名义结构；sorted 新数组保留引用顺序，回调经统一驱动并以 finally 清理活动计数。Map 保留插入顺序，覆盖不重排，keys 为新数组，递归冻结覆盖嵌套 Machine。JSON 区分 Int/Float/Bool，拒绝重复解码键、NaN/Infinity/溢出、孤立代理码点、循环和不支持的值；共享但无环引用可重复编码，不隐式 wake/解包。Float 单位构造保留实际二进制值，format 精确分数。
- 文件边界：UTF-8 严格读取、BOM 作为普通文本保留；字节/码点在读取过程中检查。普通 write_text 与独占同目录临时文件的 write_atomic 分开；成功值在文件修改前分配，atomic 完整写入/关闭后 os.replace。测试注入写入/关闭/替换失败和取消/资源/内存中止，旧文件不变且临时文件清理；两次交错写入同时持有不同临时文件。replace_file 使用明确源/目标，不承诺跨文件系统成功或断电落盘。
- P05-03：Parser/Resolver/prepare 接通 use/as；规范路径递归准备、依赖总字节/数量/深度限制、循环导入 E303，运行时每上下文只初始化一次，导出顶层具名函数/shape/machine 定义，变量和导入别名不自动导出。所有绑定/捕获按词法身份归本次运行，Program 只保存只读 AST/源码图。跨文件错误使用实际节点源码及调用 notes。spec 保存完整依赖图的收集字节，worker 从快照准备，每例独立模块/全局/Lazy/工作目录/TMP/TEMP/stdin；收集后依赖被删除仍执行原图，新 prepare 则读取新内容。未引入长期 Program 缓存或 VM 优化。
- P05-04 与指南：核心 stdlib 标记可用，新增 examples/library/helpers.zzy、main.zzy、spec.zzy 与 total-up-to.zzy；更新 README、skills/AI 入口、实现与资源/诊断说明、能力状态、测试映射。查询固定白名单按实际原生身份判断，分组不改变绑定身份，遮蔽、别名、动态调用和 data.kind 不能放行。正式 syntax 第 2—10 节与父提交逐字一致，stdlib 仅更正实现状态说明，保留签名与规则。
- 审计修复：统一校验一度改变 len/str 旧诊断位置，全量回归发现后恢复为调用左括号，未改旧期望掩盖回归。整数文本转换改为逐步受限累加，分配前检查位数/临时空间；JSON 字符串先验证转义/代理对并计真实解码长度，再分配，补 67/68/69 字节边界以防过于保守的缓冲估算误拒绝合法输入。排序/文本/文件及 JSON 临时空间接入预算，取消/宿主中止保持原信号。
- 测试落地：tests/p05 的 182 个独立输入和 8 个模块夹具，加 3 个真实示例，形成 369 项外部期望（184 run、185 check）；另有 18 项集成/宿主检查，文件与 spec 通过真实 CLI/worker 验证，失败注入补无法由 ZZY 捕获的宿主边界。P02 的 array.sum([]) 原“未实现”用例只迁移 run 为成功，保留源码；其余旧外部期望不变。未删除失败用例、跳过测试或用空收集冒充通过。
- 过程真实失败：初稿 array.Stats 使用错误 Token 构造参数，后续机械替换又造成一次导入错误，均修复后再执行；组合测试的字符串转义、模块夹具的函数前向引用、machine send 拼写和 spec 断言拼写均按既有语法修正，未放宽规则。模块初轮 283 项有 23 个失败，修正前向引用与原文坐标后剩 3 个夹具/坐标失败，修正后 305 项通过。第一轮全量 1491 项有 5 个失败（len/str 位置两项、sum 旧未实现期望一项、已加载的嵌套 use 旧坐标两项），逐项修复；不是最终通过结果。
- 过程中验证：早期既有 38 项运行时与 12 项 spec 测试通过；P05 专项 373 项通过（71.123 秒），P02 279 项通过（52.002 秒）。扩充 JSON 审计后 373 项专项再次通过（75.827 秒），新增 14 项 JSON 临界/非法转义用例通过（2.721 秒）。定稿前一次全量 1565 项通过（319.915 秒），最终清单新增 14 项后另做最终全量验收。各轮计数按当时真实清单记录，不相加成独立覆盖数量。
- 示例执行：`-m zzy test examples/library/spec.zzy --diagnostic-format json` 为 tests=2/passed=2；`-m zzy test examples/total-up-to.zzy --diagnostic-format json` 为 tests=1/passed=1，并打印公共初始化的 15，均退出 0。run/check 的固定 stdout 与错误另外纳入外部清单。
- 离线发布：0.5.0a1、info.stage=P05。bundled Python 的 `-m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist` 构建成功；`-m pip --python .venv/Scripts/python.exe install --force-reinstall --no-index --no-deps dist/zzy_language-0.5.0a1-py3-none-any.whl` 安装成功。`dist/verify_p05_install.py` 在 dist 下以 -I 隔离运行，39 条 CLI 检查和两个 library spec 通过，26 个安装 Python 文件与工作区逐字节一致；zzy.exe --version 输出 0.5.0a1 (P05 interpreter)。隔离验证初选清单有一个 ID 拼写错误导致只选到 37 条，补充所选 ID 集合必须全收集的断言并纠正后重跑 39 条，未把遗漏条目算通过。
- 未验证边界：其他 Python/OS、真实终端 Ctrl+C、全部指南片段、完整默认容量 RESOURCE/CLI 矩阵、长期缓存/淘汰、公开 Web 共享冻结、GUI/派生进程树和性能收益。P06 及后续任务不提前勾选。本机的逻辑资源预算与注入故障证据不等同 RSS 上界、操作系统杀进程后保证诊断或断电持久化。

- 最终全量验收：`.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -q`：1579/1579 通过，330.212 秒，退出 0，无跳过；其中 1459 项外部 CLI、120 项集成/宿主/运行器。独立 `-m tests.blackbox --report dist/p05-blackbox-report.json`：1459/1459 通过，301.240 秒，退出 0；报告逐项 passed/observed_exit_code 与期望一致，lex=62、run=689、check=708，57 种有效资源指纹。两入口覆盖重合，不累加计数。
- 验收结论：roadmap 的手写循环/库结果一致、排序不改变源和模块/测试状态隔离均有实际证据，P05-01—04 全部完成；70 项代码任务完成 30 项。没有已知未修复的本阶段失败，下一项 P06-01，本轮到 P05 结束。
- 提交核对：34 份 Markdown 围栏和 298 个本地链接有效；requirement 原始 SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B；syntax 第 2—10 节原文未变，git diff --check 通过。静态检查仅作一致性证据，不替代真实运行。
- Git：将本轮代码、独立源码/期望、集成测试、实际示例、指南和日志纳入本地 P05 阶段提交，基于 feature 的 b5406c9；提交标识见实际 Git 历史及最终报告。dist/.venv/wheel/临时生成脚本与机器相关报告保持忽略，不推送、不改写历史。


## 2026-10-14：P06 完整测试、指南、真实中断和阶段验收

- 用户任务：完成 P06-01—05，逐项对照 roadmap/todo/正式契约/test-coverage，核对成功/边界/失败、求值顺序/别名/隔离/定位、check 零执行、未实现能力与零收集误报；修复后真实回归，更新记录并创建本地阶段提交，不推送或改写历史。
- 接手：按 skills/zzy/SKILL.md 阅读交接和 P05 最新记录，核对 README、requirement、roadmap、覆盖及所需 syntax/stdlib/diagnostics/resources/interpreter 契约。初始 feature 工作区干净，HEAD 与 origin/feature 均为 f8092d4b56d5941f6c4f3dba1aeefd74073cae3b。CPython 3.12.14 / Windows 11 26200 / Unicode 15.0，入口仍为 .venv/Scripts/python.exe -X utf8；不使用文档中的能力作为运行证据。
- 代码修复：旧 run_bounded 只 kill 直接子进程，改成拥有整个进程树。Windows CREATE_SUSPENDED 后先加入带 KILL_ON_JOB_CLOSE 的 Job，再恢复初始线程；正常退出遗留后代、超时、输出超额、取消和启动设置失败均清理。TerminateJobObject 后等待 active process=0，避免后代不持有管道却仍持有临时文件。POSIX 使用独立进程组，代码存在但本机未运行验证。
- 真实中断：首次控制台探针无法中断 run、test 只能到超时；查明桌面宿主传下 ignore-Ctrl+C 标志。CLI 在附着 Windows 控制台时清除该标志。test_p06_process 在隐藏独立控制台运行真实 run/test，外部 helper 只向目标控制台生成 Ctrl+C，验证 stderr 一条 cancelled/code=null、退出 130、spec 临时目录消失；与 KeyboardInterrupt 注入/超时退出 1 明确分开。句柄重复启动稳定、故障后管道关闭、无继承管道的持文件孙进程退出均有真实检查。
- 测试交付：P06 cases.json 新增 129 项（run 64/check 65），含 diagnostics 四个原文、15 个小资源限额的三值、check 全效果毒丸和 15 个文档片段。全部外部清单合计 1588（lex 62/run 753/check 773），不依赖 spec。69 个本阶段 .zzy 夹具；coverage.json 为 33 条核心规则提供正常/边界/错误实际 ID，自动核对规则全集、引用与退出属性。既有顺序/别名/状态/跨文件/Lazy/错误回归保持，未删减原清单。
- 独立 spec 与指南：9 组变形 spec 同时比较独立固定 stdout，覆盖 sum、stats 手写循环、with/共享、JSON 往返、Quantity、Machine、query 手写稳定插入参考、pipeline 一次、sorted 幂等。syntax 的 13 段和 guide 的 2 段全部保存并逐段内容核对、check/run；另运行语法 spec、累加 spec、指南文件函数 3 个正常/失败 spec。新增 examples/agent-practice 的任务、两个模块和 spec，测试独立固定数据/业务失败/EOF/保存失败/check；真实当前 Agent 按指南完成，无第三方盲测或伪造 Agent 记录。其首次专项 3/3、4.281 秒通过（内含多子场景与 2 spec）。
- 资源验收：其余源码/依赖四键和 stderr 由生成式 CLI 用例补齐，20 个生效限额都有缩小配置相邻三值。关键默认值实测源码 2 MiB/总图16 MiB、Token250000、AST500000、module128、import32、数字4096、Int65536bit、指数64、String4Mi码点、IO16MiB、双流1MiB；默认语法/调用/值深度沿用并重跑原63/64/65。AST 探针只提高 Token 上限；IO 字节探针只提高 String 容量4码点，报告/代码明确隔离方式。缓存两键只在配置和指纹中保留，长期 Program 缓存尚未实现，命中/淘汰/宽转紧不计已验证。
- 运行器：新增 python -X utf8 -m tests 一键入口；collected 必须 >0 且等于 tests_run，不允许 skip/expected failure，并记录环境/策略指纹。原 blackbox 的空/坏清单、输出超额、少执行、错误答案、超时和报告失败回归保留。正常 spec 不与故意非法源码混收；未改为 zzy test tests/。
- 实际发现与修正：首轮新增外部清单 129 项中 5 项失败来自独立答案的手算位置/输出超限无来源定位：核对原文调用括号列、词法扫描前缀和 Output 无来源位置后修正期望，未放宽比较。默认 stderr 的初稿误以为单条 trace 可超过4KiB，改为多条完整记录累计至默认限额。1MiB 逐字符 stdin 探针在60秒超时后已回收；该性能探针未通过，不提升超时冒充成功，默认输出容量改用受限文件读取供值。大 stdin 性能留 P07，不宣称本轮测出效率。静态链接检查发现故意缺失文件样例不可作为真实文件链接，改为链接其期望清单。
- 文档一致性：纠正 README 旧“仅基础库/Map待实现”及 stdlib 的“拟议 write_atomic”过期措辞，语法/接口规则未变；同步指南/SKILL、导航、roadmap、diagnostics、resources、interpreter 和 tests/README，新增完整 P06 映射及 Agent 练习记录。语法第2节起正文与 HEAD 完全一致；requirement SHA-256 仍为 B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。
- 实测命令：-m unittest tests.test_p06_resources tests.test_p06_guides -v 的初版生成式/指南 11/11、114.064秒通过；之后新增默认文本/IO/输出、映射、诊断与进程专项分别通过。-m unittest tests.test_p06_diagnostics tests.test_p06_process tests.test_p06_guides -v：12/12、13.623秒。Job drain 补强后的 -m unittest tests.test_p06_process tests.test_blackbox_runner.CaptureTests tests.test_p04_spec -q：20/20、17.942秒通过。
- 首轮一键全量：.venv/Scripts/python.exe -X utf8 -m tests --report dist/p06-all-tests.json：1733/1733、675.402秒、退出0、无跳过/expected failure。为把最终 Job drain 代码纳入同一全量快照，已另启动最终完整回归；最终结果在下文追加，不将前一快照当成该修改的全量证据。
- 发布专项：0.6.0a1 wheel 使用宿主 pip --no-deps --no-build-isolation --no-index 离线构建，pip --python .venv/Scripts/python.exe install --force-reinstall --no-index --no-deps 安装。dist/verify_p06_install.py 以 -I -X utf8 在 dist 下运行全部129项 P06 CLI、9个变形和2个Agent spec，全部通过；27个安装Python文件集合及字节与工作区一致。初次安装探针取中文路径时遗漏 -X utf8 导致宿主解码失败，修正探针后完整重跑，未称该次失败为安装通过。zzy.exe --version 输出0.6.0a1 (P06 interpreter)。
- 额外已运行指南命令：zzy test examples/features-spec.zzy 为2/2；examples/library/spec.zzy 为2/2；examples/total-up-to.zzy 为1/1且顶层输出15。全部退出0。指南代码块一致性测试在文案修改后再次通过。Markdown围栏、本地链接、compileall和git diff --check仅作静态/打包补充，不充当语言执行证据。
- 明确未验证：其他Python/OS、最大默认 container_items/runtime_objects/runtime_slots/runtime_payload_bytes 实分配压力、1MiB逐字符stdin性能；长期Program缓存/优化、GUI/sketch、Web/嵌入、完整应用及性能收益未实现或留后续。P06 按正式资源要求完成所有缩小配置与关键默认边界，不声称完整默认最大分配矩阵或RSS上界。当前Agent练习不等于第三方盲测，也不代替P09完整应用。

- 独立全外部清单：.venv/Scripts/python.exe -X utf8 -m tests.blackbox --report dist/p06-blackbox-report.json：1588/1588、483.761秒、退出0。逐项确认 passed、observed_exit_code 和原期望一致，lex62/run753/check773，75种生效指纹。此入口与完整1733项中的1588项重合，不能相加。默认策略指纹为2e654aef52d3267bfecf0768bef9faee1eed942a329001ec455aee951c858bd2。

- 最终代码全量门禁：.venv/Scripts/python.exe -X utf8 -m tests --report dist/p06-all-tests.json：1733/1733、663.878秒、退出0；collected=tests_run=1733，failures/errors/skipped/expected_failures 均0。1588外部CLI+145集成/宿主/运行器；此轮包含最终Job drain实现。通过后不再修改执行代码或测试代码。
- 验收结论：33条核心规则无未解释空缺，全部现有黑盒通过，15个指南代码块有实际执行记录，公开能力和计划接口分开；P06-01—05全部完成，70项代码任务完成35项。未测范围已明确，未把最大默认实分配或其他平台写成通过。下一项P07-01，本轮在P06结束。
- 提交前核对：37份Markdown围栏配对、420个本地链接有效；70个任务ID唯一、35个完成；compileall与git diff --check通过；requirement原始哈希及syntax第2节起正文保持。纳入的文件为代码/配置、测试与独立期望、可运行指南/Agent练习和真实日志；构建产物、临时目录、机器报告及venv忽略。
- Git：基于feature的f8092d4创建本地阶段提交，主题为“feat: complete P06 acceptance and process cleanup”；提交标识见实际Git历史及最终报告。不推送，不改写历史。


## 2026-10-14：P07-01 配对工作量与内部测量驱动

- 接手核对：实际分支 test、HEAD d085c94，已有用户未跟踪 docs/manual-tests/ 保留；P06 全部勾选，与本地最终报告1733/1733、663.875秒和1588外部清单一致。使用 CPython 3.12.14/Unicode15.0，默认策略指纹不变。未因文档记录而声称本次重新跑过 P06 全量。
- 已按 performance 3.4/3.5 建立 B01—B09 双语言可运行源码、n=10独立答案、三档清单及生成器。内部驱动复用 prepare/Interpreter.run/drive/evaluate，计时分 read/prepare/initialize/execute/validate/cleanup 与完整 CLI；另存词法/解析/绑定探针。每次新初态，GC开启，短任务批量上限与真实次数公开，无公开嵌入 API 或长期缓存。
- 等价性：B01/B02同while加法/真实调用；B03同已有数组手写遍历；B04同非Bool Int逐项部分和及资源检查；B05同校验/稳定排序/新数组并查全序列、频数、原数组和稳定引用；B07同快照/全筛选/全键/稳定排序/截取；B08同查表/Result/状态更新；B09同精确Fraction/gcd和量纲检查。Python不模拟AST/变量槽等语言成本，检查包装边界已明确。
- 真实失败：首轮小规模验证172条中63条失败，原因是B07误写!、B08使用保留名machine，以及Python Windows CRLF期望。修正为(not)、toggle与语言各自精确换行。未修改语言规则或把失败算成功；初始报告留dist/p07-equivalence-initial。
- 验证命令：.venv/Scripts/python.exe -X utf8 -m benchmarks.run --verify-only --output dist/p07-equivalence：172条全部成功，退出0，副本保存benchmarks/results/equivalence。-m unittest tests.test_p07_benchmarks -q：6/6、7.576秒、退出0（含18个真实配对CLI和9个check，及批内小规模状态验证）；git diff --check通过。资源失败、超时、错答案、空/坏清单和MAD统计均有测试；check双流为空。
- P07-01已完成，P07-02—04保持未勾选。先建立工具本地提交固定版本，再正式采集默认策略基线；尚无优化或性能结论。运行时源码未改，保留P06版本号。下一步为三档基线后独立剖析。


## 2026-10-14：P07-02 固定默认策略基线

- 基准工具提交36e511e；新增字节证据属性时曾误覆盖旧BOM/CRLF规则，发现后以c8f615f完整补回，夹具字节未改，不改写历史。基线记录的启动修订为36e511e；采样期间只修正Git属性、补充审计/报告等工具，27个解释器Python源码的结束哈希与开始快照完全一致，均为P06执行代码。
- 正式命令：.venv/Scripts/python.exe -X utf8 -m benchmarks.run --output benchmarks/results/baseline。B01—B09各三档，默认资源指纹不变，GC开启，种子20261008交错语言/范围；3次预热、15次样本，短任务按记录批次数复位。全部原始记录、生成输入、版本/环境、顺序、资源配置和MAD统计保存于该目录，不覆盖。
- 结果：1644条记录；108个预检组合中96成功、12超时；受配对门禁影响24项明确未测量，余84项完成252条预热及1260条正式样本。正式样本1259成功、1次B04/100000 ZZY stages请求超时。运行退出1，正确保留失败；不以删样本或提高默认30秒上限冒充全通过。B02/B03/B05/B07/B08/B09的100000档ZZY两个范围均预检超时；未把整请求超时解释为纯执行超时。
- 环境：Windows11 26200、CPython3.12.14、Unicode15.0；Intel Core Ultra5 125H，18逻辑处理器，物理内存25196617728字节。CIM查询在沙箱内返回null，原环境文件保留；另存hardware-supplement.json，依据Windows注册表与GlobalMemoryStatusEx补齐。后续环境收集加入相同后备读取。
- .venv/Scripts/python.exe -X utf8 -m benchmarks.audit benchmarks/results/baseline：evidence_complete=true，records=1644，equivalence_jobs=108，measured_jobs=84，sample_records=1260，failure_records=37，all_workloads_passed=false；审计成功不改判超时。新审计检查生成字节、哈希、环境关联、索引/次数和由原始样本重算的汇总。
- -m unittest tests.test_p07_benchmarks -v：9/9、8.747秒、退出0；补快照启动器实际选中版本、缺失记录/改动输入拒绝和不对缺样本计算比值。-m benchmarks.report --baseline benchmarks/results/baseline --output docs/runtime/performance-report.md 已生成真实基线表格；尚无优化结论。
- P07-01/02完成，P07-03/04保持未勾选。先保存此基线提交，再独立运行cProfile。最大规模失败、其他平台、峰值RSS、长期Program缓存与其他查询/单位负载仍未验证；用户docs/manual-tests继续保留且不纳入。


## 2026-10-14：P07-03 路径热点、单项优化与回归

- 先以05e972b保存完整基线，再分别执行 -m benchmarks.profile --inputs benchmarks/results/baseline/inputs --case B01/B04/B09 --n 1000 --output benchmarks/results/profile-before-B01/B04/B09（实际为三次独立命令）。均完整结果校验通过；cProfile/pstats、文本和结构记录单列，不进入正式速度样本。
- 剖析观察：location累计占比B01 64.9%、B04 64.6%、B09 70.1%；调用数8013/9023/30021，主要来自display_path/Windows relpath。嵌套累计时间不能相加，也不将剖析耗时当作性能加速比。
- 只实施这一项优化：Interpreter按源码路径缓存诊断显示字符串，缓存属于单个运行器，每次检查cwd变化即失效，run结束清空；不缓存Program、用户值、错误或求值结果，不跳过任何资源/类型/取消检查。字符串键保留源码路径大小写，数量随固定源码路径而非循环次数增长。
- 新增真实行为测试：输入回调切换工作目录后仍报告正确E205文件/行列；同一Program和运行器在不同目录复用，不出现旧路径或状态残留，失败后Frame/预算释放。-m unittest tests.test_p07_locations tests.test_p07_benchmarks -v：11/11、8.983秒、退出0。
- .venv/Scripts/python.exe -X utf8 -m tests --report benchmarks/results/regression/all-tests.json：1744/1744、汇总计时579.844秒、退出0，failures/errors/skipped/expected_failures全0；其中包含原有1588条外部CLI清单。只跑一次最终完整回归，未把额外宿主/基准调用与1588相加。
- 资源配置、正式语法/库规则未改；requirement SHA-256保持B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B。运行时包版本仍0.6.0a1，用Git提交明确区分性能版本。
- 下一步固定此优化源码提交，使用before=05e972b与after实际提交的隔离快照，同一输入/启动器交错测B01/B04、n=10000，3预热/15样本；尚未宣称有速度收益，P07-03/04保持未完成。


## 2026-10-14：P07-03/04 复测、真实性能报告与阶段验收

- 优化源码先固定为03c3ea7，再实际执行 `.venv/Scripts/python.exe -X utf8 -m benchmarks.compare --before 05e972b --after 03c3ea7 --cases B01 B04 --n 10000 --output benchmarks/results/location-comparison`。两版各27个源码文件从Git提取并保存哈希，资源实现及生效配置相同，同一输入/隔离启动器，种子交错，3预热/15样本、batch=1。152条记录全部成功（8预检/24预热/120正式），退出0；顺序、完整索引、源码哈希和重新计算的统计再次核对通过。不是用优化后工作区冒充旧版本。
- 真实收益：B01 execute 中位数1319.508→390.084ms（3.383倍），B04为425.355→127.860ms（3.327倍）；CLI分别1624.206→731.050ms（2.222倍）、1806.195→790.311ms（2.285倍）。离散程度及min/max保存在原始数据/汇总；B04 prepare约慢9.1%、cleanup约慢6.8%，不声称所有阶段改善，也未对小幅变化作统计显著性检验。只测这两个任务的n=10000，不推断优化后完整九项矩阵或跨平台结果。
- 独立优化后剖析：`-m benchmarks.profile --inputs benchmarks/results/baseline/inputs --case B01 --n 1000 --output benchmarks/results/profile-after-B01`，完整答案正确。display_path调用8020→8，location累计从0.290917到0.012898秒；剖析样本不混入正式计时，不由其耗时计算速度加速比。
- 内存探针：`-m benchmarks.profile --inputs benchmarks/results/baseline/inputs --case B07 --n 1000 --memory --output benchmarks/results/memory-B07`，结果正确，tracemalloc峰值2596070字节、当前119668字节。范围为整个sample及额外前端探针，仅Python被跟踪分配，不是RSS/原生内存或默认最大容量。
- P06大stdin遗留探针：`-m benchmarks.stdio_probe --comparison benchmarks/results/location-comparison --output benchmarks/results/stdin-probe`，4096/65536/1048576字符各版各一次。旧版1MiB在30.086秒超时，优化版11.135秒完成且长度正确；另四次成功。命令退出1，真实保留旧版失败；这是单次期限/正确性探针，不给统计加速比，不延长超时伪造旧版成功。
- 正式报告：`-m benchmarks.report --baseline benchmarks/results/baseline --comparison benchmarks/results/location-comparison --output docs/runtime/performance-report.md`重建实际表格，随后追加基于剖析/回归的人工验收分析、命令和未测范围。报告区分ZZY/Python基础算法、等价库、ZZY优化前后及机制成本。完整可比较基线ZZY均较慢，不承诺比Python快。1260正式基线样本有1超时、另12预检超时及24配对未测量，未删除或填0；审计结构成功不代表这些工作量通过。
- 最终证据审计：`-m benchmarks.audit benchmarks/results/baseline`退出0，1644记录/108预检组合/84测量组合/1260正式记录/37失败或门禁记录，evidence_complete=true、all_workloads_passed=false。当前cases只补内部函数名称，原基线清单及环境保持不动，新增driver-entrypoints.json说明；硬件null原值亦保留，Windows读取的补充数据单列。
- 代码回归以此前1744/1744完整结果为准，功能逻辑自03c3ea7后未再修改；定稿只纠正zzy/__init__.py过期模块说明及清单/文档。最终 `-m unittest tests.test_p07_locations tests.test_p07_benchmarks tests.test_p06_guides -q`：16/16、12.700秒、退出0，包含真实双语言CLI/check与指南验证，不是只跑静态检查。
- 本地包同步：bundled Python `-m pip wheel . --no-deps --no-build-isolation --no-index --no-cache-dir --wheel-dir dist`、`-m pip --python .venv/Scripts/python.exe install --force-reinstall --no-index --no-deps dist/zzy_language-0.6.0a1-py3-none-any.whl`成功。wheel SHA256为b2e5301515ec801ab30b6d6740f8bc533f35584bf1663f630e3454c80b7bb3a2。之后在dist工作目录用`-I -X utf8 -m zzy`执行九个n=10程序的run/check共18/18，逐字节输出/退出码正确，27个安装源码与工作区逐字节一致；报告dist/p07-install-validation.json。保持0.6.0a1，以Git区别性能修订，不把旧wheel当新实现。
- 文档/范围：同步README、导航、roadmap、todo、test-coverage、SKILL与资源/运行时/性能说明。requirement原始SHA256不变，syntax/stdlib整个文件与P06提交一致。38份跟踪Markdown围栏配对、446个本地链接有效；70个代码任务ID唯一、39已完成。`-m compileall -q zzy benchmarks tests`和`git diff --check`通过；这些只作静态补充，不替代运行证据。
- 验收结论：P07-01—04达到roadmap标准。等价性先验、基线、热点证据、单项优化、真实回归、交错复测及有退化/超时说明的报告均已交付。其他OS/Python、优化后完整B01—B09矩阵、超时规模完整分布、查询其他参数/失败事件性能、增长分母压力、最大默认实分配和RSS未验证。长期Program缓存、VM/NumPy、公开嵌入、GUI和完整应用没有新增实现。
- Git：基于test的d085c94，本轮依次建立36e511e（工具）、c8f615f（恢复既有字节属性）、05e972b（基线）、03c3ea7（热点优化）及最终验收提交。核对纳入的配对脚本/原始证据/测试/说明；用户docs/manual-tests/保持未跟踪、不纳入，dist/.venv/构建产物保持忽略。只本地提交，不推送或改写历史；最终提交标识以Git历史及本轮报告为准。下一项P09-01，本轮在P07验收结束。

- 暂存后补充核对：字节保留的Windows原始JSON含CRLF，首次cached diff检查将CR识别为尾部空白；pstats原文另有末尾空行。仅给benchmarks/results追加cr-at-eol，并对profile.txt允许工具自带的末尾空行，仍检查真正的行尾空格；不重写原始证据字节或哈希。重新核对暂存区通过。


## 2026-10-15：P09-01 校园任务管家结构与前置验证

- 用户范围：按P09顺序，本轮只完成最早未完成项。核实P09-01尚未勾选、P05/P06/P07已完成；读取SKILL、campus-app、stdlib、syntax、resources、roadmap、todo、最新记录，核对catalog/CLI/测试真实文件。起点为main/fa6e374（已合并P07），非旧交接中的test；在codex/p09-01-campus-design开发，保留用户docs/manual-tests/。
- 设计交付：apps/zzy-campus/README.md确定中文逐行菜单、增删改/完成/筛选搜索/稳定视图排序、统计/TSV导出、模块依赖、Task/Document/Session与内容dirty、候选加载提交、ID高水位、历史100步及保存/取消/EOF流程。所有功能明确所属P09-02/03及待执行APP-01—03，未创建main.zzy或占位业务实现；没有Python专用任务管理接口。只更新campus-app状态和实现设计链接，v1字段/范围/失败规则原文保持。
- 配置：limits.json仅io_payload_bytes收紧至4194304，其余默认。v1合法结构三层，分层字段校验拒绝非法容器，通用JSON仍受默认value_depth64；不将内部Session/历史结构也误限到4层。资源超限保持E211，不能吞成可恢复格式Result。
- 真实能力核验：.venv/Scripts/python.exe -X utf8 -m zzy info --limits apps/zzy-campus/limits.json退出0，CPython3.12.14、Windows11 26200、Unicode15.0；策略指纹fd1aaefacc02ee4b7d585ad733a9fed92a01d948bcdf020b38ecea64eaa80fe5。注册表及真实CLI确认Map/data.kind/严格JSON/Result、safe_int、数组/模块/查询、文件接口可用。
- 测试：tests/p09/prerequisites.json引用23项独立既有CLI期望，应用配置下执行，不改变旧答案。另2项测试实际核对info配置、文件4194303/4194304/4194305字节读取（前两档成功，超一字节E211）、缺文件check零执行。与18项P05集成联合运行：`.venv/Scripts/python.exe -X utf8 -m unittest tests.test_p09_prerequisites tests.test_p05_integration -q`最终43/43、16.244秒、退出0、无跳过。既有集成涵盖原子写入/关闭/替换故障、保留旧文件、清理、状态/模块隔离。
- 过程真实失败：首轮直接导入BlackboxCase，被unittest当测试类收集并传入字符串case，错误报告又触发TypeError。改为模块引用，重跑完整43项通过；没有跳过或删除预期案例。引用清单空/重复/缺失会收集失败，不靠零用例成功。
- 范围与行数：apps/zzy-campus尚无业务.zzy，0总行/0有效行；通用资源探针不计应用200行。未重跑整个1744项历史全量（解释器执行代码未改），更未声称APP保存失败/坏文件/重启/200行已通过。APP-01—03、实际主菜单及所有业务仍待P09-02—06。
- 同步README、导航、SKILL、roadmap、test-coverage、todo与真实Agent记录。仅P09-01勾选，70项代码任务40项完成；下一项P09-02。本地提交主题docs: define P09 campus application and verify prerequisites，提交标识见Git历史/交付报告；不推送或改写历史，不纳入用户docs/manual-tests/及临时文件。

- 提交前一致性：41份Markdown围栏配对、459个本地链接有效（排除用户未跟踪手工测试目录）；70个任务ID唯一、40完成；语法/stdlib/requirement全文与父提交一致，campus-app第1节起正式规则逐字不变。requirement原始SHA256仍为B099C19FC339CE1DC1AAB7E9D6C8126A9C5C9ACE3D31B969A0623DF90F521D2B；git diff --check通过。项目及父目录没有AGENTS.md。静态核对不是运行成功的替代。


## 2026-10-15：P09-02—04 全部应用业务及专项验证

- 用户将本轮范围扩展为完成P09全部。接手codex/p09-01-campus-design/311d4e4，保留docs/manual-tests/；重读SKILL、交接、campus-app、stdlib、syntax和roadmap，采用原v1规则，继续使用Python AST解释器，不新增语言或任务管家宿主接口。
- 完成model/validation/tasks/views/storage/session/main七个ZZY模块：真实逐行菜单、增删改/完成、组合筛选搜索/稳定排序、统计/TSV、受限文件读写、全量校验后替换、值内容dirty、撤销/重做与ID高水位。历史数组与Task只发布后替换，不原地改旧任务；Map去重避免两两扫描；每个外部容器先检查类别和字段集合，业务错误显式Result，资源超限保持E211。
- 输入草稿确认前不修改状态；每层EOF结束并对dirty输出未保存提示，退出/加载先保存/放弃/取消，保存失败中止后续动作。初始打开失败可重试/其他路径/返回，不自动新建文件。保存校验和序列化先于write_atomic，成功才更新path/saved；保存不清历史，加载成功清历史/视图。TSV导出不更新dirty，保留P09-01的路径别名边界。
- 初稿真实check通过，随后完整菜单新增两条/设完成/统计/保存/退出实跑成功，磁盘全部字段正确。新增160组独立JSON格式/字段/类型/边界期望，经真实CLI调用ZZY校验；既有测试期望未改。首轮应用16/16、18.692秒通过；补上数量/字节/交互边界和真实中断后22/22、109.335秒通过，命令为`.venv/Scripts/python.exe -X utf8 -m unittest tests.test_p09_app -q`，退出0、无跳过。
- 专项包括9999/10000/10001任务（默认应用配置，单例限时180秒）；4MiB前/等/后文件；损坏/重复键/非有限数/代理字符/编码失败；ID最大值与重启、高水位/别名/dirty/100步历史；真实菜单固定全文和磁盘JSON/TSV；check零执行、每层草稿EOF、保存失败停止加载和取消。单独10000项探针37.406秒成功，仅为功能边界观察，不是P07性能统计。
- 宿主故障注入运行真实ZZY session/storage：写入/关闭/替换/权限失败保留旧文件、编辑、path、dirty、历史并清临时文件/预算；读取PermissionError同样保留会话。真实隐藏独立控制台Ctrl+C发生在有dirty修改后加载大文件期间，退出130、单条cancelled且旧存档不变；没有把异常注入当作真实信号。
- 审核时补上菜单ID/任务容量已耗尽的提前拒绝，避免无意义收集输入；未放宽校验。无需修改解释器。按真实Lexer统计7文件：504总行、493含非注释Token有效行、406排除纯标点行代码；`-m tests.p09.count_lines`生成文件SHA及计数，应用源码指定LF保证跨检出哈希稳定。测试、文档、Python和夹具不计200行。
- P09-02/03/04完成，P09-05/06尚待最终全量回归、指南与提交核对；不将当前专项成功冒充全量成功。先建立实现提交，再执行全量门禁；只本地提交，不推送，不纳入用户手工测试目录。


## 2026-10-15：P09-05/06 完整回归、指南与最终验收

- 固定实现提交8cfe8f1后，执行`.venv/Scripts/python.exe -X utf8 -m tests --report tests/p09/results/all-tests.json`：collected=tests_run=1791，806.968秒、退出0；failures/errors/skipped/expected_failures全0。含既有1588独立外部CLI、P07回归、P09前置25项和应用22项；160组验证矩阵是其中一个测试方法的子输入，计数不重复相加。
- P09-05逐项对照15行APP-01—03/CHECK，coverage.json引用全部22个实际方法，无空映射。正常/边界/失败、顺序/别名、状态隔离、读写失败/首错路径、check零执行、运行器防空收集等由真实测试覆盖；不将设计文本或静态检查冒充运行证据。
- 随附demo-input.txt在临时中文/空格目录实际执行，新增两条、完成一条、统计/保存后新进程重开；完整JSON及列表符合固定答案。另用`.venv/Scripts/python.exe -I -X utf8 -m zzy`隔离启动已安装解释器，check/演示/重启三项通过，命令/输入/双流/磁盘结果保存installed-demo.json。wheel只提供解释器，应用随仓库源码分发。
- 安装核验首轮逐字节比较失败，定位为lexer.py/prepare.py/tokens.py的CRLF差异，git diff确认无解释器实现变更；27文件统一换行后的文本相同、24文件逐字节一致。纠正核验口径后实际执行上述三项成功；没有把最初失败写成通过，也未必要地重建未变的解释器。
- `-m tests.p09.count_lines --check`复算504总行/493有效行/406非纯标点代码行及源码SHA；代码已统一LF并设Git属性。应用所有业务在ZZY，Python新增部分仅测试、计数与外部证据。没有添加语法或公开宿主接口，schema_version仍1。
- 更新应用指南、项目/应用/文档导航、人用指南、SKILL、coverage、roadmap/todo和真实Agent记录。人用指南已有两段示例正文保持，定稿时单独片段一致性检查1/1、0.005秒通过。最终运行代码与8cfe8f1保持一致，回归后只完善说明/证据。
- 未验证明确保留：其他OS/Python、真实文件ACL、每个阻塞宿主调用的中断时序、所有最坏长度/任务/历史组合、默认最大实分配与RSS、断电落盘、多写者合并、路径别名识别。真实Ctrl+C是在有未保存修改后加载大文件期间；权限是注入测试，不虚称操作系统ACL实测。
- 验收结论：P09-01—06全部完成，70项代码任务45完成；完整CLI流程、200行要求、独立测试、真实Agent记录和可复现启动/演示均满足roadmap。下一项E1-01；P11前置同时满足但本轮不越界实现。保留用户docs/manual-tests/，只创建本地实现与验收提交，不推送、不改写历史。

- 最终静态复核：41份Markdown的477条本地链接及围栏有效；70项任务ID唯一、45项完成；15行应用映射覆盖全部22个实际方法。正式syntax/stdlib/requirement、campus-app第1节起正文及解释器实现未改变；验收JSON与1791项实际报告一致，git diff --check通过。静态结果只证明文档/记录一致性，不代替上述执行。


## 2026-10-17：E1-01 受控类型、几何与填充实现

- 用户要求按E1→E2→E3→E4推进，但本轮只完成一个可验证任务；选择最早未完成E1-01，SVG明确留E1-02，不扩大到GUI/历史。起点codex/p09-01-campus-design/7fb645c，新建本地codex/e1-01-sketch-core；用户docs/manual-tests/保持未跟踪、不纳入。复核SKILL、todo交接、最新记录、sketch、syntax/stdlib、resources、diagnostics、roadmap及test-coverage。P05/P06已实现且有真实记录；接手回归 `-m unittest tests.test_p05_integration tests.test_p06_guides tests.test_metadata -q`：25/25、13.168秒通过。
- 新增sketch_metadata/sketch模块：29个实际函数、五种受控类型身份、冻结普通Position快照；按登记身份进行qualified注解检查，类型不可作为构造器，禁止宿主属性/方法反射。Canvas/Pen/Layer可变句柄按上下文/执行线程归属；Color按RGB相等，其余身份相等；通用JSON拒绝原生值，纯查询名单未扩充。Layer目前仅default内部实例，Drawing没有公开工厂，不冒称E2/E3能力可用。
- 实现初态/背景/样式、移动/负距离/转向、home/jump、正负圆弧/extent、整圈精确闭合、折线、受误差约束的三次贝塞尔和点。只读路径块一次准备后发布；位置、对象ID与计量均在验证/分配后提交。曲线0.25逻辑单位误差，最大展开段65536/深度24；不依赖后端平滑算法，不宣称SVG或像素输出通过。
- 填充为单画布单笔草稿：固定开始时填充色，描边样式可逐段改变；至少三个不同顶点，evenodd闭合不额外描边、不移动笔；cancel恢复完整起态。活动填充拒绝其他文档写入；运行结束/失败/取消清理草稿，不留锁、不自动保存。历史/撤销尚无接口，本轮不伪造空成功。
- 固定扩展配额e1-01-v1与核心预算同时生效，不修改default-v1及旧性能指纹。真实分配验证256画笔、65536曲线段、1000000文档段、100000对象及各自超一项拒绝；单独该边界方法1/1、2.538秒通过，仅是功能容量验收。9999/10000/10001批量点由真实CLI验证，临时点/路径/草稿都计量；逻辑预算不声称RSS上界或所有极限可同时组合。
- 外部清单首轮84项有12失败：夹具Bool误写裸true、字段诊断位置预期错误。改为契约的(true)及既有标识符定位，联合首批宿主100/100、31.122秒通过。扩展125项时原生构造拒绝的位置期望又误用了::，改按既有construct节点的类型标识符；未放宽语法或修改错误定位实现。随后108/108独立CLI、32.000秒通过并保存原始报告；这份报告在加入示例2项前，明确不冒充当前110项结果。
- 自审补齐内部freeze对跨上下文/线程句柄的拒绝，以及跨线程工厂调用拒绝。主动中断此前全量运行（退出1、不计成功），修复后17个宿主方法5.596秒通过，再对最终代码启动全量门禁。故障逐次注入路径/填充分配点，检查原状态、旧路径、ID、草稿及预算不变；曲线内部取消后恢复草稿，Program/运行器重用创建新上下文。check独立进程证明不导入几何实现、不读输入/写文件，headless也不导入Tk。
- 本轮验收范围的解释：todo E1-01引用SKETCH-01/02，而test-coverage的SKETCH-02还含文字/公开图层/对象编辑；依roadmap明确文字/公开图层在E2、对象编辑在E4，本轮只验收SKETCH-02填充子集，交接中显式注明，不把整行提前勾完。正式几何/填充规则保持，数值/容量阈值按契约2.2允许的实施固定写入使用指南。
- 打包用bundled Python执行 `-m pip wheel . --no-deps --no-build-isolation --no-index --no-cache-dir --wheel-dir dist`，生成wheel SHA256 e5fa4f8952ee4ef0d431e4c6888a1babda8534ee63c372c2e6e78631f0e21547。用项目Python `-m venv --without-pip "dist/E1 隔离安装"`，再以bundled pip的--python参数离线安装成功。独立环境-I在临时中文/空格cwd运行示例/失败程序的run/check及元数据检查共9项通过，29个安装源码与工作区文本一致，命令/双流/退出码/哈希见tests/e1/results/installed.json。
- 安装探针首轮元数据断言失败：普通Python -c print在Windows输出CRLF，原预期LF；实际退出0且模块断言均成立。仅把该宿主探针改为splitlines比较后重跑9项成功，ZZY CLI仍逐字节比较，不抹掉真实诊断。运行时版本仍0.6.0a1，扩展独立ABI e1-01-v1，未发布完整sketch1.0。
- 新增实际geometry.zzy示例与阶段指南，更新能力入口/标准库及语法状态说明、资源说明和覆盖映射。requirement原始SHA256仍b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b。最终全量尚在运行；暂不勾选E1-01。GUI、SVG、公开图层/文字、历史/回放/图案/事件/项目以及其他平台均无本轮验收结果。


## 2026-10-17：E1-01 最终验收与本地交付

- 最终代码执行`.venv/Scripts/python.exe -X utf8 -m tests --report tests/e1/results/all-tests.json`，collected=tests_run=1918，729.36秒、退出0；failures/errors/skipped/expected_failures全部0。当前外部CLI1698项（原1588+E1新增110），另有17个E1宿主方法，均包含于1918，不重复累加。P09与所有既有核心/测试运行器回归实际重跑通过。
- 验收JSON保存生效核心策略、扩展ABI/固定配额、环境及源文件字节/LF文本哈希。安装隔离9/9、29文件文本一致的报告保留；旧108项专项明确标为加示例/最终冻结修复前，不当成最终清单。验收文档生成器首轮嵌套字符串语法错误，未修改文件；改为独立脚本后重新生成，不涉及运行实现。
- 正式sketch第1—8节、核心EBNF及requirement原文保留；数值/分配阈值按契约要求固定于阶段指南。只勾选E1-01，70项代码任务46完成；E1-02及E2—E4保持未勾选。当前仍非完整sketch1.0，SVG/GUI/撤销/回放及后续接口没有占位成功。
- 下一项E1-02：复用逻辑路径生成并解析核对SVG，实施输出配额、XML转义与原子保存；其后才推进E2窗口。其他OS/Python、最大组合容量、RSS、性能、窗口/关闭及历史/回放明确未验证。
- 本地阶段提交限定解释器接入/几何模块、真实测试与证据、示例和能力说明；用户docs/manual-tests/及dist不纳入，不推送/改写历史。提交标识以Git历史及最终答复为准。

- 本地虚拟环境已用同一wheel离线force-reinstall同步；随后临时中文/空格cwd下以-I执行示例check/run 2/2，29个安装源码文本与工作区一致，追加到installed.json。定稿静态复核43份Markdown/500条本地链接及围栏、70个唯一任务/46完成、仅E1-01勾选、源码哈希与实际全量报告一致；git diff --check及compileall通过。指南原代码片段一致性单独1/1、0.003秒通过，静态结果不代替运行证据。

## 2026-10-17：E1-02 SVG 验收

- 本轮用户扩大到完成 E，继续按 E1→E2→E3→E4，不把后续未验收项标为可用。基于 ac91a27；保留未跟踪 docs/manual-tests/。
- 实现 svg_text/save_svg，复用规范路径、中心/Y坐标转换、画布裁剪、evenodd填充与原子文件发布；逐片容量/取消检查、XML转义、非法XML字符失败Result。冻结画布可导出，活动填充拒绝。ABI e1-02-v1。
- `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_sketch_svg tests.test_e1_runtime tests.test_e1_cli -q` 最终 132/132、36.640秒通过，无跳过。首次运行测试夹具漏传ResourceExceeded的phase、旧future-svg清单残留diagnostic导致失败，修复测试后重跑。解析SVG核对坐标/裁剪/背景/填充无附加描边/曲线逐点一致；替换失败、取消、限额保留旧文件及清理临时文件/预算；真实CLI验证check不导入几何、不保存，headless导出不导入Tk。
- GUI预检：受限环境Tk报缺init.tcl；同一Python在真实桌面环境创建Tk 8.6.12窗口，1536×960屏幕、mainloop/after关闭成功。此仅环境探针，不代表E2工具/线程验收。
- E1-02达到完成标准，E1完成；下一阶段E2。全量核心/P09回归将在本轮最终代码执行。没有将headless当GUI、撤销验收。

## 2026-10-17：E2 视图与线程验收

- 新增显式run --gui主线程Tk/单一ZZY工作线程桥接；show使用独立关闭控制信号，默认headless/check不加载Tk。图层、文字、多笔、缩放/平移、基础工具通过同一宿主调用修改文档，主线程不持有原生句柄或调用ZZY。无显示环境返回失败Result，真正工作线程错误保留原诊断。
- `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_sketch_layers -q` 2/2通过；与SVG/原几何22/22回归通过。新增6项独立CLI清单，覆盖LayerInfo快照/顺序、文字抬笔不移动和headless show失败。
- 桌面真实执行 `.venv/Scripts/python.exe -X utf8 -m tests.gui_sketch --report tests/e1/results/gui-e2.json`：3/3、1.500秒，无失败/跳过，线程ID实测不同，真实Tk事件生成矩形、视图缩放不改文档、两次关窗继续执行/导出、错误清理与缺显示环境故障注入。环境为Windows11/CPython3.12.14/Tk8.6.12；其他平台未验证。
- 基础GUI测试不声称已经验收E3历史或E4事件/项目/队列满载。E2完成后继续E3；仅本地提交，不推送。
- E2/既有CLI/SVG/图层/元数据联合125项首轮2项期望误加字符串引号，其余123项通过；按既有debug显示契约去掉夹具引号，独立E2黑盒6/6、1.637秒通过并保存cli.json；未改语言显示实现。

## 2026-10-17：E3-01 历史与回放

- 增量历史覆盖路径/文字/图层/样式/背景/clear，分组、undo/redo、显式clear_history；只读Block共享，正常撤销不回退ID，失败候选恢复状态。填充end记录begin前笔态，cancel不留历史。固定命令/字节上限，新增编辑按清除redo后的计数判断。
- 回放执行侧副本读取记录，最多8个/16MiB共享检查点，定位/单步不重新执行源程序；GUI编辑退出回放。frame_interval精确Quantity转向上取整毫秒，(0,24h]。
- 原几何/SVG/图层24/24、8.941秒；新增history宿主5/5、0.017秒；`.venv/Scripts/python.exe -X utf8 -m tests.blackbox tests/e3/cases.json --report tests/e3/results/history-cli.json` 6/6、1.461秒。几何极限测试增加clear_history隔离已经被撤销历史保留的旧图形，未降低既有几何限额。
- GUI首次4项有1失败：固定70ms等待未等到回放消息；同时暴露异常退出有未取消Tk after。测试改用3秒上限的状态等待，运行器清理所有after。真实桌面重跑 `.venv/Scripts/python.exe -X utf8 -m tests.gui_sketch --report tests/e3/results/history-gui.json` 4/4、1.531秒，无跳过。固定答案验证seek=1/step=2，undo编辑退出回放后实际笔位置2及对象数2。
- E3-01验收，继续E3-02图案/函数导出。完整E尚未完成；最终全量回归仍待本轮最终代码。

## 2026-10-17：E3-02 图案与函数库

- 实现Drawing共享不可变Block、visible capture、默认层整组stamp；平移/统一缩放/逆时针旋转以及字号/线宽转换，保留所有目标Pen状态，变换后边界先校验。group在SVG/Tk按叶几何渲染，文本单独旋转保持坐标一致。
- 严格schema1图案编码/解码：固定kind/字段、重复键/未知类型/版本/非有限数/Bools拒绝，填充边界与描边连续性校验，容量沿用核心与扩展限额。原生Drawing按上下文/线程归属，仅显式编解码。
- save_function验证同一Lexer的名字与真实prepare前端；JSON嵌在正确转义的ZZY字符串，私有Lazy首次wake解码、显式Result传播；原子替换前全部准备。真实临时中文/空格目录的导出模块check/run通过，连续调用ID1/2且调用者笔不变；宿主计数证明check零解码、每次执行首次解码一次、Program再次执行重新解码。
- `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_sketch_patterns tests.test_sketch_history tests.test_sketch_layers tests.test_sketch_svg tests.test_e3_cli -q` 23/23、3.043秒通过；其中patterns3项含多个坏schema/保留名/注入名、快照别名、变换/冻结/undo固定断言以及真实CLI模块。E3完整子集通过，继续E4，尚不发布完整1.0。

## 2026-10-17：E4-01 事件、对象与项目往返

- 新增鼠标/键盘/定时回调、固定参数数量校验、正时间间隔/取消、顺序show边界派发；单一工作线程调用ZZY，主线程只收发不可变Scene/事件。有界4096输入队列、单槽合并渲染、合计16MiB消息载荷，溢出E211；正常关闭独立Event可中断长回调，恢复show之后脚本，失败不吞成成功Result。
- 对象按可见层自上而下命中、整体移动/复制/删除，固定4逻辑单位容差；锁层可选不可改。文字命中使用明确的逻辑估计框（0.6×字号×码点数宽、字号高），不为headless测量字体；GUI新增选择/移动/复制/对象擦除、图层增改/显隐/锁/排序及笔归属操作。
- schema1项目记录图层/笔/共享几何池/ID高水位及增量undo/redo，严格字段/类型/引用/历史前后状态逐层校验，候选文档不注册到上下文；全部通过并预分配成功Result后发布新Canvas。保存走既有原子内核；不包含回调/定时器/Lazy。坏文件不会替换原文档或泄漏半份原生文档。PNG接口明确返回缺独立后端的失败Result。
- 修复联合运行暴露的解码暂存81个slot延迟释放：Decoded从仅依赖析构改为finally显式close，错误路径同样清理；10项联合回归由失败变为通过。项目新增4项（含真实CLI先check无文件、保存、另进程加载/undo/导出库复用），0.795秒通过。E4外部24项黑盒7.109秒通过，含回调arity、量纲、零timer、嵌套组、草稿undo、对象ID、文字/图层范围及headless PNG明确失败。
- GUI自审真正发现并修复三个问题：Tk变量/窗口残留可能在下一工作线程GC中析构导致Tcl_AsyncDelete；改为主线程显式销毁变量、当前回调结束后统一解除Tcl引用。默认Windows Tk多边形实际采用非evenodd填充；改为像素中心的奇偶扫描填充，分批渲染、200000渲染item硬上限，不使用背景擦除。队列溢出与关闭两次flag读取有竞争，曾被当成普通关闭；在SessionClosed出口重查失败和取消，保留E211。
- 上述修复过程的GUI运行均记为失败：一次原生析构退出1、过早解绑Tk引用导致5个after删除错误、2个工具等待/填充像素失败、渲染替换笔误导致2个错误、关闭竞争导致1个失败；没有用较早7/7结果覆盖这些失败。测试由固定等待改为有截止时间的状态等待，不放宽固定答案。最终真实桌面 `.venv/Scripts/python.exe -X utf8 -m tests.gui_sketch --report tests/e4/results/gui.json` 9/9、3.141秒通过，无跳过/后台异常。GDI读取窗口像素证明单轮廓中心红色、重复两圈中心白色、画布外灰色。
- 37项既有几何/SVG/图层/历史/图案/对象/项目宿主回归11.706秒通过（新增重启用例之后项目单独4/4）；核心check/headless仍不初始化Tk。E4-01完成，继续E4-02完整性能测量、隔离离线安装、完整回归和指南，尚未发布完整sketch1.0。


## 2026-10-17：E4-02 基线、最终自审与真实 GUI 回归

- `.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.run --repeats 3`实际退出0：108个新进程样本、27/27 ZZY/Python固定答案及几何SHA配对一致；同一运行时哈希在测量结束再次核对。基线本地提交a977596，包含原始样本、9个ZZY程序/通用Python对照、环境/配置/哈希。1000/10000/100000，single/batch/multi各3次，完整CLI与准备/生成/记录/undo/redo/定位/SVG/项目/函数导出/Lazy首次与缓存分开，峰值内存为Windows进程PeakWorkingSetSize。
- 所有108个进程正常完成，无进程失败或超时；部分操作阶段真实触发默认slots/文本/载荷限制，完整保留E211资源键、上限、请求量，不计作成功时间。100000批量线段为10个对象，100000单笔为100000对象，不能把差异写成语言加速。第三轮有显著系统时序变化但代码未变，保留标准差，不宣称优化收益。本轮未做额外速度优化。CIM硬件查询被沙箱拒绝，改用环境/GlobalMemoryStatusEx记录真实CPU标识、18逻辑处理器、25196617728字节物理内存；未虚构CPU商品型号。
- 审查新增回归先真实失败：两项宿主用例分别证明clear后的Replay按当前空列表预留不足、save_png未检查活动分组；真实GUI排队undo图层后再操作旧ID出现StopIteration→RuntimeError。随后修复Replay按历史最大对象数预留并在close释放暂存，PNG先执行idle检查，过期图层消息统一E203；不改公开语法/签名或默认配额。
- 图层池上限疑点经实现复核排除：目前无删除图层API，新增编辑清空redo，保留图层并集仍受256上限约束，没有放宽坏文件校验。长拖曳已有10000点硬上限，新GUI用例确认超一项E211且无部分笔画。元数据补E204及实际副作用分类；ABI候选设1.0，但仍须最终门禁通过才勾选E4-02/宣告完整版本。GUI状态栏补正式契约的抬笔/撤销趣味提示，不写stdout、不改变Result。
- 修复后 `.venv/Scripts/python.exe -X utf8 -m unittest tests.test_sketch_history tests.test_sketch_project tests.test_sketch_benchmarks -q`：12/12、1.838秒通过。测量工具新增零重复拒绝、GUI未完成真实渲染不能计成功的回归。`.venv/Scripts/python.exe -X utf8 -m tests.blackbox tests/e4/cases.json --report tests/e4/results/cli.json`：26/26、6.585秒通过；新增PNG活动分组真实run/check定位。
- 真实桌面 `.venv/Scripts/python.exe -X utf8 -m tests.gui_sketch --report tests/e4/results/gui.json`：11/11、4.188秒，无失败/错误/跳过。包含Windows GDI evenodd/裁剪像素、窗口工具/缩放/两次show、回调/定时器、长回调关闭、队列溢出竞争、历史定位与真实笔态、过期图层及拖曳容量。旧9/9报告不替代本次11项。
- 正在继续最终GUI性能、Replay相关复测、离线隔离安装与全量回归；E4-02保持未勾选。指南/能力说明已清除旧E1-01限定，明确PNG不可用和未测平台。用户docs/manual-tests/仍不纳入，requirement SHA256保持b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b。

- 最终GUI性能初轮27样本中6个batch小规模进程失败，已完整保留render-layout-failed.json。增加现场尺寸诊断后确认首次完成判定在1×1视口，后续变为704×504的Configure重绘改变item ID；属于测量同步错误。仅修正探针等待已映射/有效尺寸/渲染完成，保留严格ID断言；1000/10000两个原失败场景分别真实通过，再完整重跑27项。最终21个场景样本完成渲染/不变刷新/定位，6个100000独立对象样本因sketch.queue_bytes明确拒绝；无进程失败/超时，采集退出0，不将6个拒绝算作已渲染。
- `.venv/Scripts/python.exe -X utf8 -m benchmarks.sketch.seek --all --repeats 3`最终27样本：21成功、6因runtime_slots拒绝，退出0；检查真实文档/笔态未变、预算释放。资源修复后的统计与基线分列，无加速宣传。报告由实际JSON生成于benchmarks/sketch/README.md；基线a977596的Git LF文本哈希另存baseline-checkout.json，原执行字节哈希未覆盖。
- `.venv/Scripts/python.exe -X utf8 tests/e4/install.py --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`：离线wheel构建、新venv与当前venv安装、39个源码文本一致性、-I中文/空格cwd真实CLI/GUI/关窗保存/跨进程重启undo和函数库复用均通过，退出0。wheel SHA256 6d5b200a49b275e8c9b40a2f7d628a7abfb48477565cfffe07bfdb4416f7c0a4。新窗口实际映射704×504、Tk8.6.12、主/工作线程ID不同，显示8个对象；重启固定输出8、true、7、成功ID9、SVG保存成功。
- 正式sketch第7节原代码另在临时目录以-I真实check/run：check无双流/文件，headless run生成SVG与函数库并明确打印缺--gui；XML解析12条path。证据guide-example.json。正式规则/示例代码未改，只更新过时状态文字；studio追加了关窗后保存项目。
- 全量运行前冻结1019个代码/夹具文件哈希到tested-source.json，已启动`.venv/Scripts/python.exe -X utf8 -m tests --report tests/e4/results/all-tests.json`；等待最终计数，不以点状进度或专项通过代替完整回归。

- 全量首轮实际完成1982项、890.360秒，1失败/0错误/0跳过。唯一失败为P05注册表测试旧断言只允许array.map/filter具有callback副作用，而本阶段元数据已正确把真实派发用户回调的sketch.show登记为callback。保留原始all-tests-registry-failed.json及其源码快照。更新封闭期望为精确三个成员，并显式断言show不在PURE_CALLS，不改运行实现、不放宽查询纯性。
- 修复后针对注册表/元数据/测量工具的5项回归1.123秒通过。重新冻结时逐文件证明1019文件中仅tests/test_p05_integration.py改变，39个运行时文件及所有已测性能/GUI源码不变；正在重新执行完整1982项门禁，不把首轮1981项通过加一项重测伪称为一轮全量通过。


## 2026-10-17：E1—E4 最终验收与完整 sketch 1.0

- 最终完整命令`.venv/Scripts/python.exe -X utf8 -m tests --report tests/e4/results/all-tests.json`退出0，collected=tests_run=1982，898.39秒；failures/errors/skipped/expected_failures全0，含1738独立外部CLI。这是修正注册表期望后的完整重跑；首轮失败报告及原哈希另存。
- `.venv/Scripts/python.exe -X utf8 -m tests.e4.accept`汇总门禁通过：核对完整/GUI/安装报告、27/27基线配对、最终渲染/Replay运行时哈希、39安装源码文本、1019冻结代码/夹具与requirement SHA。汇总仅验证已执行证据，不冒充另一次测试。
- 真实GUI11/11、离线新环境窗口及重启分别通过。正式第7节原代码实际check/run，studio实际GUI闭环通过；指南、标准库/语法状态、资源口径、覆盖映射及性能报告同步。GUI性能21成功/6消息容量拒绝，Replay21成功/6slots拒绝；默认配置不偷换、失败不算速度，PNG明确不可用。
- 文档定稿脚本初轮嵌套引号语法错误，未修改文件，改用直接保存脚本后处理。静态链接检查初轮遇Git中文路径引号，改用git ls-files -z后46份Markdown/516条本地链接和围栏通过；静态结果不代替运行证据。提交前再核对最终链接/任务/差异及暂存范围。
- E4-02达到roadmap完成标准，七项E任务均勾选，52/70代码任务完成；现在才标记完整sketch1.0。下一项P11-01，本轮不提前执行。最终本地提交标识以Git和最终答复为准；不推送、不纳入docs/manual-tests/或dist。
- 未验证范围保留：其他OS/Python/字体/DPI、所有最大容量组合、实际ACL、断电/并发写事务及所有阻塞宿主取消时序。字体/层名替换预留保守保留到句柄结束，指南已说明；逻辑预算不是RSS硬上限。

- 定稿后复核通过：46份Markdown/518条本地链接、围栏成对；70个唯一任务中52完成，E七项全部完成；1019份冻结源码/夹具哈希一致。`git diff --check`退出0，仅Git换行提示；当前能力文档未检出遗留E4待验收状态。

- 最后逐行审阅纠正todo/stdlib措辞：不执行用户代码仅适用于check；headless正常执行程序和文件操作，两者均不初始化Tk。仅文档澄清，运行代码及冻结哈希未改变。

## 2026-10-20：最终完整测试与 CI 方案

- 任务摘要：了解基本完成的项目，设计提交前的自动化/人工完整测试阶段和CI，并写入docs；本次范围为方案与文档，不执行完整验收或接通CI。
- 当前核对：分支test，HEAD为b5980430273e91567488f972db69bfc179eaa9a9；CPython3.12.14、Windows11。实际仅收集一键测试1982项；12份默认黑盒清单共1738项，GUI源码有11个测试方法。旧E4报告为2026-10-17的历史结果，未改写成新通过记录。
- 新增[最终测试计划](final-test-plan.md)：F0—F5候选冻结、自动回归、真实GUI/安装、人工端到端、性能与稳定性、交付放行；列出18项人工用例、复现命令、边界/失败检查、缺陷级别及每个attempt独立证据规则。
- 新增[CI设计](ci-design.md)：推荐GitHub Actions的Windows静态检查、全量回归、无窗口wheel安装smoke及统一ci-gate；设计PR/push/手动触发、报告留存、最小权限和八步实施验收。Python3.12.14的云端供给、控制台信号行为仍需真实试跑；GUI/人工/正式性能另验收。
- 审阅安装脚本后明确其真实副作用：tests/e4/install.py会打开GUI、覆盖固定报告并重装调用Python，不能直接用作PR无窗口smoke；tests.e4.accept只汇总既有固定证据，不能替代新候选运行。CI静态脚本/独立安装smoke/workflow及远程规则均未实施。
- 核对性能驱动与既有报告：核心正式大规模基准存在已记录超时，驱动会返回1；计划区分功能门禁、小规模正确性、正式样本采集及证据审计，不将已知失败类别或完整证据冒充全工作量成功。
- 更新docs导航、test-coverage和todo的P11入口，清理导航中基准/CLI均待实现的过期描述。70项任务仍52项完成，P11五项保持未勾选；下一正式任务仍是P11-01。
- 实际验证：检查48份Markdown的本地文件链接及代码围栏，无错误；18个人工ID唯一；GUI方法数与计划一致；Git差异空白检查通过。requirement SHA256仍为b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b。上述静态检查和收集不是测试执行。
- 未运行：1982项完整回归、11项真实GUI、人工用例、离线安装、性能复测和GitHub Actions。本轮不生成对应成功记录，用户docs/manual-tests/资料保留。
- Git：本轮文档尚未提交，未推送。后续按计划准备候选版本和独立证据目录；CI按CI-01先验证精确运行时可取得，再落实脚本与工作流。

## 2026-10-20：CI 实现、本机完整验证与独立人工指南

- 用户继续要求应用 CI 设计，另写详细 VS Code 人工测试 Markdown；本轮据此新增 `.github/workflows/ci.yml`、`scripts.ci`、运行时/构建工具锁、安装探针及 CI 门禁自检，不修改语言运行实现或正式语义。未推送、未配置远程分支保护，不把本机通过写成 GitHub Actions 已通过。
- 工作流 `ZZY CI`：main/test/feature/codex/** push、目标 main/test 的 PR、手动触发；Windows 2025 上 static → regression-windows/package-smoke → ci-gate。配置只读权限、完整 Action SHA、超时、并发取消、失败产物上传及 14 天留存。汇总核对依赖状态、checkout/head/base SHA、run ID/attempt 和源码指纹。
- 精确环境供给：官方 actions/python-versions 当日清单没有 Windows 3.12.14 资产，改用 Astral 20260929 的 Windows x64 CPython 3.12.14；固定归档 SHA256 为 `28728baf30b65e263f0b25c5a85be8226e7ab0d212fbadd6a8f0f796139fa804`，先校验再解压执行。未改 requires-python、未降级到其他补丁版。pip25.2/setuptools80.9.0/wheel0.45.1 由带哈希的 requirements 固定，只安装到隔离 CI 运行时。
- 本机下载调试保留事实：最初 Invoke-WebRequest 和 curl 传输被中断，保留 dist 下失败目录；Python urllib 路径完整下载并通过哈希。缓存归档启动及正常联网 bootstrap 均实际通过，正常联网结果位于 `dist/ci-runtime-network-20261020`。此过程不证明云端供给已经试跑。
- 静态入口校验 requirement 字节 SHA、测试清单及重复次数、夹具存在性、Markdown 链接/围栏、空白和应用行数。新增基线为1992项，其中10项是CI宿主自检；独立黑盒仍为12清单1738项，P09应用策略重复23项不丢失。最初去重方案无法保留这23次执行，补反例后改用多重集合；预期缺文件的E401负例与意外丢失夹具分开处理。
- 安装入口离线构建 wheel，在源码目录外的中文/空格临时 cwd 建全新 venv，以 `-I` 验证39个源码、CLI/spec/诊断、check无副作用、headless SVG/项目/函数库、实际校园菜单保存与另一进程读取。临时新环境完成后清理，不重装项目 `.venv`。构建日志初轮遇GBK字节解码失败，保留 `dist/ci-local-precheck/package`；明确子进程UTF-8并保留异常字节后重跑通过，未改产品标准流契约。
- 锁定运行时完整实测：`python -X utf8 -m scripts.ci static/package/regression` 的最终报告位于 `dist/ci-local-final/`；完整回归 **collected=tests_run=1992、1443.14秒、退出0，failures/errors/skipped/expected_failures均0**。实际运行环境为Windows11/CPython3.12.14（Sep29 MSVC构建），不是托管Windows2025；本次非独占性能测量，不与旧回归耗时推导速度结论。
- 同轮安装 passed=true、39个源码一致、headless=true；wheel SHA256为 `edb2d37c32bae1cc5f49f2c4df7421fabcbb497eadc59422a52f6fa932a9aa9f`。`scripts.ci gate --artifacts dist/ci-local-final --output dist/ci-local-final/gate` 实际退出0，三个job证据通过。报告关联HEAD `b5980430273e91567488f972db69bfc179eaa9a9` 及未提交工作区源码指纹 `40f0093d84f18fcbb72dc27b4567bb9107f2b28f6c5e47e81f93cf341db7bec2`，执行前后相同。
- 门禁10项自检全部通过并已包含在1992项中；另实际调用CLI验证上游failure/cancelled/skipped、旧run报告、缺报告五种情况，均退出1且passed=false，证据 `dist/ci-negative-checks-20261020/summary.json`。工作流由下载后核验SHA的 actionlint v1.7.12 实际检查通过；未把本地反例说成失败PR验证。
- 新增独立 [本机 VS Code 人工测试指南](manual-test-guide.md)：显式解释器/UTF-8、独立中文工作目录、真实Ctrl+C、语言诊断、应用M05—M10逐项输入和状态、GUI工具/图层/历史/回调、项目/函数重启、安装副本、DPI、日志及M01—M18记录表。锁层非法编辑按当前E203终止语义放入独立负例，不错误要求同一个show继续；不覆盖用户人工资料。
- 指南主要命令实际复核33次，记录于 `dist/manual-guide-command-check-20261020-attempt02/commands.json`，独立报告passed=true。首轮发现“缺表达式”预期误写E101，实际为E103，修正文档后重跑；首轮记录另留。GUI程序仅做前端check；studio往返复核使用临时去除show的副本，不据此声称真实窗口或人工测试完成。
- 同步根README、docs导航、最终计划/覆盖说明及todo入口；requirement内容和用户 `docs/manual-tests/` 未改。P11五项仍未勾选，70项中52完成。待实际执行：GitHub首跑/PR失败及取消/分支必需检查、11项本轮真实GUI、18项人工验收、真实离线GUI及正式性能/交付复核。
- 文档复核：指南与CI文档共28个PowerShell代码块经本机Parser检查无语法错误，M01—M18章节完整且唯一；新增锁层负例check退出0，未开GUI。正常下载入口及完整门禁验证后没有再修改CI/测试/产品源码，源码指纹保持一致。

## 2026-10-22：输出与日志配置

- 按用户给出的日志知识点选择适合本机CLI/桌面项目的部分：对实际持久写盘的CI回归tests.log配置大小轮转、gzip压缩与保留份数；沿用CLI的UTF-8、stdout/stderr分工、固定错误码和结构化诊断，不增加用户程序输出前缀或按locale翻译机制。
- 新增实际生效的 [logging.json](../runtime/logging.json) 和 [配置说明](../runtime/logging.md)。默认max_bytes=1048576、backup_count=4；每轮最多1个活动文件和4份gzip备份，超出自动淘汰，GitHub artifact仍保留14天。本地不同attempt的结果目录及人工资料不自动整目录删除，文档明确份数上限并非dist总空间上限。
- 新增scripts/ci_logging.py，复用标准库RotatingFileHandler/gzip；按UTF-8字节校验单文件容量，管道流式读取，跨块解码保留中文，非法字节转义可见。父进程管理写入和重新打开，无需子进程接收SIGHUP。写盘/压缩失败使CI失败并清理进程树，压缩发布完成前不删除当前原文。
- scripts.ci静态入口校验配置字段/类型/范围/重复键/64KiB上限；回归入口自动读取配置，report/log新增文件名、配置、rotations和older_logs_discarded。报告明确已淘汰时只保留最近片段，完整测试结果仍由退出码和all-tests.json核对；没有用日志截断掩盖失败。
- 新增10项日志宿主检查，覆盖实际UTF-8字节上限、备份淘汰、跨块/残缺编码、可调整配置、非零退出、超时、后代进程占管道、写盘与压缩故障。最终专项命令`python -X utf8 -m unittest tests.test_ci_logging tests.test_ci -q`实测20/20、1.269秒通过，无跳过。清单从1992增至2002，原12份黑盒清单1738项未变；39个产品源码文件未修改。
- 自审将固定默认值断言替换为“自定义8KiB阈值实际不轮转6KiB输出”的用例，保证合法调参不被旧断言阻止；基线仅对应新增日志用例及该明确替换。先前attempt01全量主动中断、未形成最终报告，目录保留；随后冻结最终源码为`0014a5309105954667555b648bf98b37434e9d16610af3eccf510482ae8e439b`，启动attempt02完整重跑，最终结果见下文。
- 按正式1MiB/4份配置，实际向捕获器输入7000006字节，6次轮转后仅保留4个gzip及当前文件；每个备份原文1048576字节、当前708550字节，保留尾部4902854字节与原输入后缀完全一致，older_logs_discarded=true。证据为`dist/logging-verification/2026-10-22-rotation-smoke/report.json`；文档中的合并读取程序实际运行，重建内容逐字节一致。
- 实际CLI六次验证：在C、zh_CN.UTF-8、en_US.UTF-8三组LANG/LC_ALL设置下运行hello及JSON诊断负例，正常输出均为5/退出0，错误均为E302/退出2且七个结构字段、消息和位置一致，无新增输出；证据为`dist/logging-verification/2026-10-22-interface/cli-protocol.json`。这是环境变量组合验证，不扩展为所有OS语言环境已验收。
- 静态复核通过：50份Markdown、583条本地链接及围栏，日志文档3个PowerShell代码块语法正确；配置有效，当前收集2002。requirement字节SHA256仍为b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b。更新README、导航、CI/人工/覆盖/最终计划的当前计数和日志入口，历史通过数据不改写。
- todo仍为52/70完成、P11五项未勾选；用户docs/manual-tests/保持原状。未推送、未改变远程规则；本轮不重做GUI/人工/正式性能验收，也不把本机检查写成云端Actions已通过。
- 最终attempt02实际通过：`scripts.ci static/package/regression/gate`均退出0；完整回归collected=tests_run=2002、621.75秒，failures/errors/skipped/expected_failures均0，安装核对39个源码通过。报告位于`dist/logging-verification/2026-10-22-attempt02/`，四份报告源码指纹一致，复核时仍等于冻结值；这是本轮完整执行，未拼接旧通过项。
- 普通完整回归tests.log实际3131字节，report/log正确记录1048576/4、encoding=utf-8、compression=gzip、rotations=0、older_logs_discarded=false；产物汇总三个job均true。此次时间是功能回归耗时，不是独占性能测量或速度优化结论；大输出的6次轮转证据另列于上文。


## 2026-10-27：首次人工测试归档与云端路径兼容修复

- 用户确认第一次人工大规模测试已完成，要求推送 feature 并经 PR 合并 main。将原始人工报告 manual-test-result.doc、CI/日志入口和测试指南归档为 431e7e4；保留 docs/manual-tests/ 未跟踪图片，不纳入构建产物，不提前勾选 P11。
- 提交前重新核对本地 2002 项完整通过证据及源码指纹一致，另运行 static 与 20 项 CI/日志专项通过。随后 PR #3 首次触发云端检查：静态和隔离安装通过；Windows Server 2025 完整回归实际运行 2002 项，6 项失败，原始失败日志保留在对应 Actions 产物中，不将本地通过当作云端通过。
- 根因：Windows 当前目录可保留 8.3 短路径别名，而 Source.path 已解析成长路径，relpath 将同一目录误当作不同路径。四项诊断路径断言及两项精确 stderr 容量边界因此失败。本机 GetShortPathNameW 实际切换到短路径后复现，既有路径回归中新增同一场景，修复前明确失败。
- 修复：display_path 在计算相对路径前统一规范化源路径和当前目录，跨盘仍返回规范绝对路径；不改错误码、源码坐标、资源限额或既有外部答案。回归验证包含短路径、缺失文件和重复运行上下文；最终云端结果以该 PR 修复提交的完整重跑为准。
- 本机修复后专项：tests.test_p07_locations/test_cli/test_p04_spec/test_p06_diagnostics/test_p06_resources 共 38/38 通过、107.274 秒，无跳过；静态入口通过。此结果不替代云端完整重跑。


## 2026-10-28：P08-01 HTTP与同源网页

- 用户明确选择P08，并在提示末限定“现在完成p08-1”；因此本轮仅P08-01，不勾选P08-02—05，不提前P10。接手main/fcb9373，Git只有未跟踪docs/manual-tests/，没有已跟踪脏修改；保留人工目录和requirement原文。P05/P06/P09的完成状态与当前代码核对一致。
- 阅读项目技能、README、todo交接、最新日志、P08 roadmap、interpreter第11节、stdlib/resources/test-coverage、项目配置和CI。使用zzy、git-pushing及失败时systematic-debugging技能。brainstorming内容仅用于设计检查；用户已明确架构/任务并授权普通选择直接实施，不增加常规确认门禁。
- 设计决定：Starlette/Uvicorn可选extra；固定宿主路由表启动校验，启动只prepare不执行模块；每请求完整重建模块/捕获环境，复用只读Program，私有输入/输出/ResourceMeter。旧web.get/web.serve方向示例无现有签名，集中契约docs/runtime/web.md明确替代方案、实际Request/Response、JSON安全整数/拒绝、资源、错误、取消与后续嵌入/SQLite边界，不扩展语法。
- 新增zzy/web.py、examples/web/app.zzy和同源页面。业务问候/姓名校验由ZZY编写；Python只做适配/转换，复用既有json_codec、解释器调用栈和finally清理。每body/响应64KiB、metadata16KiB、默认4并发、每收体/执行各5秒；超时/断连/关闭取消令牌，阻塞宿主不能强制打断的边界明确记录。
- 首次依赖安装受沙箱网络WinError10013阻止；同命令授权联网安装成功：Starlette0.52.1/Uvicorn0.54.0及环境报告所列依赖。官网文档读取超时，依据本机安装源码与真实验证，不把未读网页当证据。核心dependencies仍为空。
- 实际失败修复：示例首check报E101裸!，核对syntax改为(not)/(or)；内部探针Map.set传Python字符串报AttributeError，核对Value键、CallRequest单元素返回容器及stringify返回Value后修正边界；首次HTTP业务期望200却422，核对data.kind固定标签为map而非object，修正ZZY示例，不改既有标准库或放宽测试。
- 测试命令：`.venv/Scripts/python.exe -X utf8 -m unittest tests.test_web_core -v`3/3通过；`-m tests.web_http --report tests/p08/http.json`最终8/8、2.406秒通过，零跳过，真实TCP，无TestClient替代。覆盖正常/拒绝、边界、错误恢复、12次并发独立计数、循环超时/慢body/断连释放与服务生命周期。
- 浏览器实际访问127.0.0.1:8765，GET显示language=ZZY；POST同学显示你好，同学；空姓名422显示长度要求。截图tests/p08/browser-failure.png。演示服务已停止；自动浏览器检查不冒充用户人工验收，未改人工材料。
- `.venv/Scripts/python.exe -X utf8 -m scripts.ci package --output dist/p08-package --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`通过，隔离核心wheel无第三方安装、40源码核对，保留package.json/package-probe.json。另新建dist/p08-web-installed/env安装该wheel[web]；`env/Scripts/python.exe -I -X utf8 .../probe.py`确认导入来自新环境并重跑8/8真实HTTP、2.938秒通过。保留installed-http.json和源码/依赖哈希。
- CI新增web-http独立job，安装可选wheel、执行专项并上传证据，ci-gate依赖该job结果；核心/GUI仍分离。无推送，云端新增job尚未验证。本轮GUI未重跑，HTTP通过不替代GUI。
- 完整核心回归正在运行，待最终结果才勾选P08-01。P08-02的共享冻结图与默认捕获完整矩阵、P08-03公开嵌入、P08-04 SQLite和P08-05完整交付留下一轮。

- 最终完整命令`.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression.json`退出0：2005/2005、877.547秒，失败/错误/跳过/expected failure全0；原2002项完整保留，外部CLI1738项未减。最终源码哈希与HTTP/安装实测一致。静态门禁通过53份Markdown/612条本地链接、任务/fixture/requirement核对。P08-01达到子任务标准，现勾选；P08整体未完成，下一项P08-02。

- 定稿后静态门禁再次通过；测试清单仅新增3个核心ID（2002→2005），原清单及期望未删减。todo核对53/70，P08只有01勾选。分支codex/p08-01-web，本轮仅本地提交，不推送；最终标识见Git与答复。


## 2026-10-28：P08-02共享冻结模块与并发隔离

- 接手codex/p08-01-web/1e32f97，仅docs/manual-tests/未跟踪；保留用户8000端口服务及人工材料，测试使用独立临时端口。截图证明用户P08-01 GET/POST成功，未将其视为本轮隔离验收。读取技能、集中契约、todo/日志、相关解释器捕获/默认构造/冻结/计量与CI实现，沿用既有语法。
- 先在集中契约明确显式shared=True/--shared方案：默认逐请求模式保留；共享模式ASGI lifespan启动时初始化一次，受信任初始化副作用与check分开。递归拒绝全部模块可变绑定、Lazy、Cell闭包捕获、原生句柄及命名空间别名；共享闭包/结构默认捕获/导入依赖的全部全局绑定一并检查，无静默降级。实际代码zzy/web_shared.py，采用独立服务计量和预留所有权转移，停服后释放。
- Array/Map/Shape/Machine递归冻结；捕获只读容器的闭包检查到容器。普通结构默认[]仍每请求创建；默认引用共享数组保持冻结。默认表达式引用的全局环境由整个模块绑定图检查；函数内新建值/Cell仍属于请求，不禁止请求局部修改。
- 复查发现冻结Array遍历仍写active计数，修改for与array.map/filter仅对非冻结数组记录active；冻结写入口E203不变，普通可变数组原活动遍历规则保持。内置Namespace成员惰性缓存按请求创建，防止把其缓存或资源归属共享到请求之间。
- 首轮核心专项6/6、HTTP10/10通过；补依赖/默认捕获与生命周期后核心7/7。HTTP强制两个请求在解释器入口屏障交错，8次不同输入保持各自输出和EOF输入；共享写失败后读状态保持不变；忙worker时503及时返回、原循环504；真实服务只初始化一次，关闭后预留归零。
- 生命周期审查发现ASGI启动取消可能晚收到成功快照；新增取消令牌和late-result close回调，用受控初始化屏障证明取消后快照关闭/计量归零。为最终证据一致，主动中断尚未完成的首轮全量（未形成成功报告，不计通过），修复及专项完成后重新完整运行。
- 最终`.venv/Scripts/python.exe -X utf8 -m tests.web_http --report tests/p08/http-02.json`12/12、3.875秒通过，零失败/跳过。其中启动取消为ASGI生命周期受控交错，其余HTTP场景使用真实TCP，未冒充全是网络用例。日志中的E203/E205为负例服务端原始定位，响应不含Python堆栈。
- `.venv/Scripts/python.exe -X utf8 -m scripts.ci package --output dist/p08-02-package-final --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`通过，核心无可选依赖安装41源码核对。另对dist/p08-web-installed/env离线强制重装本轮wheel，python -I探针确认导入来自隔离env并重复12/12、3.859秒通过；源码/安装证据见tests/p08。本轮没有联网新增依赖。
- 当前完整回归正在运行，源码冻结于tests/p08/source-02.json；通过后才勾选P08-02。下一项P08-03公开嵌入，未提前SQLite/P10。GUI、用户人工测试、其他平台和所有阻塞宿主取消时序未验证；本轮不推送。

- 后续名义类型验收补出真实失败：测试初稿把array.Stats写成带括号的注解，首先E103；按正式语法修正后，合法array.stats结果传入共享函数仍E201。原因是每请求重新创建了原生名义类型定义，而共享函数注解保留启动定义。修复为各请求独立命名空间缓存字典，启动已构造成员经检查后共享身份；不放宽类型匹配。核心专项8/8、0.598秒及Web12/12、3.797秒通过。再次主动中止未完成的全量，前两次均无最终报告、不得算通过；最终源码与新增5项测试清单冻结后完整重跑。
- 最终包命令改用`-m scripts.ci package --output dist/p08-02-package-accepted --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`，退出0、41源码匹配。用该wheel离线重装隔离Web环境，`dist/p08-web-installed/env/Scripts/python.exe -I -X utf8 dist/p08-web-installed/probe.py`通过12/12、3.656秒；另同环境`core_probe.py`执行5项共享核心用例通过、0.187秒，包含名义类型修复。已更新tests/p08的package-02、package-probe-02、installed-http-02为最终包证据；前述旧包耗时仅保留为开发过程记录。
- 交付前错误码交叉核对发现新共享拒绝复用了E214，与syntax.md第265行“sketch操作状态”冲突；影响启动错误码的公共含义。改用已有E303模块错误，集中契约明确这是入口模块根节点的发布条件诊断，原始求值/冻结写入定位不改，语法错误码表不扩展。核心8/8、0.757秒，Web12/12、3.813秒通过；因此中断第三次尚未完成的全量，重新冻结实现/测试哈希后从头运行。前三次中断都不是成功报告，不拼接通过项。最终打包目录为dist/p08-02-package-release，前述accepted仍是历史过程证据。
- 静态入口第一次复用既有dist/p08-02-static目录，被exist_ok=False拒绝（退出1）；保留旧产物，改用新目录dist/p08-02-static-accepted后通过。交付定稿后再检查一次。
- E303定稿后package-release无Web依赖核心安装41源码核对通过；离线重装该wheel后HTTP12/12、4.032秒，共享核心5/5、0.161秒，均退出0。另执行`.venv/Scripts/python.exe -X utf8 dist/p08-02-cli-probe.py`，由子进程实际启动`-m zzy.web ... --shared --port 62437`，真实GET/POST返回ZZY/Ada数据，保存tests/p08/cli-02.json。只终止探针自己的子进程；不把强制结束称为优雅关闭，后者由lifespan专项证明。用户8000服务不变。

- 最终完整命令`.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression-02.json`退出0：collected=tests_run=2010，960.375秒，failures/errors/skipped/expected_failures全0。原2005项及1738外部CLI没有删减；新增5项核心用例，Web12项另执行。P08-02达到本轮完成标准，勾选后54/70；P08整体未完成，下一项P08-03。本地分支codex/p08-02-shared，仅提交本轮差异，不推送。
- 定稿静态命令`-m scripts.ci static --output dist/p08-02-static-release`退出0：53份Markdown、621本地链接、fixture/清单/任务/requirement核对通过；校园源码仍504总行/493有效行。最终7个实现/测试文件哈希匹配，wheel中41份运行时源码与工作区逐份规范换行后相同。Git差异审查仅纳入本轮27个文件，docs/manual-tests/不暂存；requirement SHA256仍为b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b。

## 2026-10-28：P08-03数据转换与Python嵌入

- 用户要求完成下一项。接手codex/p08-02-shared/4815347，核实P08-02已验收、P08-03最早未完成；Git仅docs/manual-tests/未跟踪。使用项目zzy技能核对集中契约、interpreter第11节、stdlib/resources/覆盖表、CI与包配置；普通设计选择沿用用户直接实现授权。本轮仅P08-03，不提前SQLite/P10，不操作用户8000端口服务。
- 契约先落在docs/runtime/web.md：公开zzy.embedding.load_module/LoadedModule.call/exports/close及CallResult/ConversionError。加载仅prepare；每调用新上下文，先转换宿主参数，再初始化及调用，最后转换结果，finally释放；并发可调用，活动调用时close明确拒绝且不关闭模块。返回值/输出由Python拥有；无内部Value句柄泄漏、隐式结果解包、Lazy唤醒或任意Python属性/eval/exec。
- 实现精确None/bool/int/float/str/list/dict双向转换，结构返回字段dict，循环/非有限Float/孤立代理/子类/未知类型拒绝。别名按出现次数复制，输入不回写宿主，输出不保留可变别名；输出树预留预算防止重复别名展开绕过限额。Python Int直接保留到integer_bits上限，HTTP仍严格安全整数边界，不悄悄变String。使用既有诊断、资源计量与CancellationToken，无新语言错误码/语法。
- examples/web/embed.py通过同一app.zzy的greet返回业务数据，Python无业务校验副本；真实HTTP新增对照正常中文/英文、缺字段、错误类型和Null的状态码/数据。标准库注册表及校园CLI格式均不改。
- 首轮`-m unittest tests.test_embedding -v`10项中9通过、1错误：integer_bits=2在加载综合夹具时已拒绝源码数字9，未进入目标转换。按systematic-debugging核对实际Phase.FRONTEND，新增仅identity的独立embed-boundary.zzy；配额不放宽，验证等于阈值成功/超限失败。补依赖快照、初始化失败和宿主参数类型后嵌入11/11、0.975秒通过；输出别名展开的200槽限制另核实实际在to_python/retain中触发。
- 最终核心专项包含嵌入11项与原Web核心8项：19/19、1.89秒，报告tests/p08/embedding-03.json。64/65层边界、Bool/Int、超长精确Int、Array/Map/结构、无副作用load、未唤醒Lazy、失败/取消清理、并发输入输出/计数、活动close拒绝及下一次调用恢复均实际执行。CLI check夹具静默、`-m examples.web.embed`实际输出Ada业务数据，导入embedding不加载Web/GUI。
- `.venv/Scripts/python.exe -X utf8 -m tests.web_http --report tests/p08/http-03.json`13/13、4.797秒通过；真实TCP业务对照，其余原12项保留。ASGI启动取消仍单列生命周期用例，不冒充网络请求。
- `.venv/Scripts/python.exe -X utf8 -m scripts.ci package --output dist/p08-03-package --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`通过。新wheel核心无Web依赖环境核对42源码，并新增真实嵌入调用到CI安装探针。离线强制重装wheel至dist/p08-web-installed/env后，`env/Scripts/python.exe -I -X utf8 .../probe.py`HTTP13/13、4.891秒；同环境embedding_probe.py嵌入11/11、1.046秒，均验证包从env导入。报告保存在tests/p08/package-03、package-probe-03、installed-http-03、installed-embedding-03.json。
- 最终源码/测试哈希保存tests/p08/source-03.json，冻结后启动`.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression-03.json`完整回归；最终结果未出前保持P08-03未勾选。清单仅新增11项，原2010项和1738外部CLI不删减。分支codex/p08-03-embedding，本轮本地提交、不推送。GUI/用户人工测试/其他平台/云端CI未重跑，协作取消不承诺强制中止任意宿主阻塞。
- 首次静态门禁`-m scripts.ci static --output dist/p08-03-static`失败：git diff --check报告skills/guide.md末尾新增空行；未把后续Get-Content的退出0当成门禁成功。修正文档后`-m scripts.ci static --output dist/p08-03-static-fixed`通过。未改变已冻结实现或测试。

- 最终完整命令`.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression-03.json`退出0：collected=tests_run=2021，966秒，失败/错误/跳过/expected failure均0；本轮全量一次完整跑完，没有用专项拼接或跳过。现勾选P08-03，55/70，下一项P08-04 SQLite，P08整体仍未完成。
- 定稿`-m scripts.ci static --output dist/p08-03-static-final`通过：53份Markdown/635本地链接、任务/清单/requirement核对，冻结7个实现/测试文件哈希保持一致；最终wheel42份运行时源码与当前逐份规范换行匹配。审查本轮29个代码/测试/文档及报告文件后本地提交；docs/manual-tests/不暂存，requirement SHA256仍b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b。提交标识见Git历史和答复。

## 2026-10-28：P08-04 SQLite与P08-05整体验收

- 接手ec6431b，仅docs/manual-tests/未跟踪。读取项目技能、交接、契约、注册表、资源和CI；使用zzy技能及既有故障定位/提交审查流程。用户本轮要求继续完成04及05，保留原校园CLI、requirement与8000服务。
- 先补集中SQLite契约，新增db.transaction(path,callback)/db.query(sql,params)，通过原注册表调用；连接归当前执行线程/事务，成功Result提交，失败Result/异常/取消回滚，finally关闭。不暴露原生句柄；参数化执行，禁止事务控制/ATTACH/PRAGMA等，250ms锁等待与1秒SQL进度期限，逐行转换和配额检查。
- 独立examples/sqlite/app.zzy实现任务标题校验、入库与查询；Python不写业务。新增同源页面与重启/HTTP/Python说明，数据库文件单独忽略。核心无第三方新增依赖，sqlite3惰性加载；check不创建数据库。
- 初次夹具错误用了匿名块函数，E103明确要求=>；按既有语法改为嵌套具名函数，不改变语言。SQL错误路径发现ConversionError在execute之后导入，异常匹配报UnboundLocalError，移动到try前。新增回滚探针发现测试自己的sqlite连接with仅提交不关闭，改contextlib.closing；运行时所有连接关闭检查通过，不放宽期望。
- SQLite专项最终6/6、0.974秒；真实HTTP14/14、4.829秒，新增非法业务请求及服务停止/重建后持久化。原13项全部保留。CI核心安装探针新增真实SQLite check/run/参数查询；完整回归与隔离wheel正在执行。
- 尝试git switch -c codex/p08-sqlite失败：.git/refs/heads锁文件Permission denied。当前会话禁止提权，未绕过权限；继续完成不依赖Git写权限的工作，提交受阻待最终报告。人工材料未操作。

- P08-04专项验收：最终数据库6/6、0.887秒（database-04.json），HTTP14/14；另用独立CLI服务器子进程实际POST后退出，再启动新PID，GET仍返回同一任务（process-restart-04.json）。因此勾选04，继续05全量/交付；Git提交仍受权限限制。
- P08-05安装：scripts.ci package --output dist/p08-05-package通过，43源码、核心无Web依赖环境真实SQLite check/run；离线重装wheel后14/14 HTTP通过。无新增第三方依赖，现有CI自动收集新增6项核心和1项HTTP，安装探针接入SQLite。冻结哈希见source-05.json。新SQLite网页尚未浏览器人工交互，HTTP链路实测，不冒充人工验收。

- 诊断契约复核：syntax原错误码表E401只列CLI/源码I/O，而现有宿主io.print也已使用该码；本轮明确扩展说明到SQLite操作失败，同步diagnostics与集中契约。无新错误码，既有期望不改；客户端仍使用既有zzy_error响应，不泄漏数据或路径。

- 最终完整命令`.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression-05.json`退出0：2027/2027、838.109秒，失败/错误/跳过/expected failure全0。原2021项及1738外部CLI不删减，新增SQLite6项，HTTP新增1项。P08-05技术验收通过，但本地提交因.git写权限拒绝尚未完成，todo保持05未勾选（56/70）；不将受阻提交写成完成，不推送。

- 最终静态通过54份Markdown/649本地链接；实现与测试冻结哈希匹配。审查33个本轮文件，明确排除docs/manual-tests/与requirement。实际git add显式文件清单再次被.git/index.lock Permission denied阻止（退出128），未暂存、未创建提交；当前权限禁止提权，未绕过。所有代码、文档和报告留在工作区，基线仍ec6431b。

## 2026-10-28：P08提交与feature交付

- 用户要求核查并推送feature。交付复验SQLite6/6、1.104秒，真实HTTP14/14、4.984秒，静态门禁通过；输出保存在dist/p08-delivery-review。已有完整回归2027/2027、838.109秒，本次未重跑全量；source-05.json记录的7个实现/测试文件哈希与当前一致。
- 用户恢复Git写权限后，显式暂存并审查33个P08相关文件，git diff --cached --check通过；创建提交0a70825（feat(sqlite): complete P08 integration and acceptance）。人工测试目录未暂存，requirement未修改。现勾选P08-05，57/70，后续P11仍独立验收。
- 初次fetch经现有127.0.0.1:7897代理发生schannel握手失败，临时OpenSSL后端也遇到TLS EOF；临时清空本次命令代理后fetch成功。保留HTTPS证书校验及全局配置，未将连接故障误报为GitHub权限不足。
- 已拉取并核对origin/feature与本地feature一致，且是当前P08分支祖先。后续以快进方式同步feature并正常推送；远端最终提交号以Git引用和聊天报告核验，不改写历史，不更新main/test，不将推送视为云端CI通过。

## 2026-10-28：P08完成复核与人工测试统一归档

- 用户要求检查P08日志和完成情况，编写简洁人工方案，并与上次资料统一存放。当前分支test、HEAD为330cf1754fa991bd72b4f56bc89fdaa57ce8d2ff；P08-01—05已勾选，代码任务57/70，下一项仍为P11-01。本轮仅整理文档和人工证据，不修改运行时、测试实现、requirement或用户8000服务，不提交/推送。
- 核对现存tests/p08/core-regression-05.json：2027/2027、838.109秒、零失败/错误/跳过；database-04为6/6，http-04及installed-http-05均14/14。source-05记录的7个实现/测试哈希匹配当前；验收wheel SHA256为e123f539508287db8decde7f5cfe20ab175298271bd10eaf75ad6627965f9524，43份运行时源码逐份规范换行后与当前一致。以上是现存证据核对，本次未重跑全量/HTTP/GUI。
- 新增docs/manual-tests/README.md统一索引及p08-20261028/manual-test-plan.md、manual-test-result.md。W01—W07覆盖默认GET/中文POST、422及恢复、shared冒烟、Python嵌入、SQLite中文/单引号标题、空标题拒绝、Ctrl+C失联及新进程持久化恢复。提供6块PowerShell准备/启动/结束命令，明确同一终端、同一运行目录与独立测试数据库；结果表保持待执行。
- 将上次完整guide和原始manual-test-result.doc归档到docs/manual-tests/core-sketch-20261027/；原guide路径保留导航入口，新旧DOC同目录引用不变。DOC SHA256仍为3a8b6e107be09243812146a3cffcf4c2d321f4f5e2c824be3fa5dfdb1721f4ee，未改二进制内容或41张截图。另从原运行目录复制终端记录、M17安装报告及全部顶层工作文件，共24份，逐份字节相同；不复制环境/依赖，原dist目录保留。P06原始图片未改。
- 修正文档导航、测试计划/覆盖说明和Web示例中的过期“P08未实现/数据库待04/提交仍受阻”口径；开发记录历史过程不改写，P11保持未完成。上次GUI/校园全流程不强制重做，额外DPI、物理断网、手工并发及模拟断电可跳过，不冒填通过。
- 实际执行`.venv/Scripts/python.exe -X utf8 -m scripts.ci static --output dist/p08-manual-docs-review-20261028`通过。由于既有CI有意排除人工资料目录，另单独检查该目录5份Markdown、27个本地链接和围栏，全部通过；使用PowerShell Parser检查新方案6块命令语法通过，只解析、未执行人工命令。requirement SHA256仍为b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b。

## 2026-10-29：P08人工结果逐图核验

- 用户已完成测试，要求检查。接手test/330cf17，操作者将结果表改为docs/manual-tests/p08-20261028/manual-test-result.docx，并保存runs/20261029-002147-330cf17。按项目技能及文档读取流程检查DOCX结构、全部11张原始截图、transcript、候选和工作区记录；未修改原DOCX，未重新执行服务器或用户人工测试。
- W01默认GET返回200、中文POST成功；W02空姓名422后Ada恢复成功；W04嵌入输出status200及你好，Ada，退出0。W03图5证实带shared的新进程37252启动，操作者随后备注“一切正常，与上述无异，不再重复记录”；按操作者确认记录，不冒充重复请求独立截图或并发隔离证明。GET正文language字段与初始空库亦未单独截图，保留现有自动覆盖与人工主流程的区别，不要求重复补测。
- SQLite图7保留ID1人工任务一、ID2 O'Reilly；图8空标题422，未增加空记录；图9停服失联；图10旧PID45652完成shutdown，新PID24148启动并GET200后仍返回原两条；图11新进程结束及数据库Test-Path=True。只读查询实际数据库与截图一致，integrity_check=ok，读前后SHA256均12ec1577227c4d28b8d63d95f7fa2d8fcc374e3dcc4136070d5c0da26f7bfec8。四份示例副本与当前源码/页面字节相同，source-05七个冻结文件哈希仍一致。
- 未发现阻塞性功能问题，本轮人工主流程核验通过，W03证据边界如上。favicon.ico404是未提供站点图标，非业务接口失败；PowerShell5.1 transcript的Ctrl+C管道停止文字与截图中的Uvicorn正常shutdown结合判读，不误报崩溃。transcript未完整捕获原生程序输出，以DOCX截图补足。Python/浏览器完整版本未在本轮材料独立留存，不补填已核验版本。
- 新增同轮manual-test-review.md逐项记录证据、结论与原件哈希；修复结果由MD换为DOCX后的导航失效，同步人工索引、方案、todo、Web契约状态、测试说明及最终计划。原DOCX SHA256保持de847465191ec00602c115bc5a0bc344db65b0518ec8daf85daf62fbe22fd9ff，transcript保持1d11602838b515f1f9b7a20e3c41476330708f87f155fabfc155a8c92457a2a4。代码、数据库、requirement及上次人工原件未改，不提交/推送；P11任务保持未完成。
- 实际执行`.venv/Scripts/python.exe -X utf8 -m scripts.ci static --output dist/p08-manual-review-20261029/static`通过；另外检查人工目录5份Markdown、32个本地链接和围栏通过，校验原DOCX/transcript/数据库/requirement哈希不变。核验产物存dist/p08-manual-review-20261029，不将其当作新全量、HTTP、GUI或云端CI执行结果。

## 2026-10-29：人工通过后的主分支交付

- 用户确认人工测试成功，授权提交推送并合并main。本轮将人工资料迁移、原始报告、日志、测试数据库及配套导航作为同一交付提交；不改运行时代码或requirement，不将人工确认扩写为未执行的测试。
- 提交前本地静态门禁通过，输出dist/p08-main-release-static-20261029；主分支启用PR要求且对管理员生效。本轮通过test到main的PR执行云端静态、Windows完整回归、隔离安装、HTTP和ci-gate，成功后正常合并。最终运行与合并SHA以GitHub记录及聊天报告核对，不绕过保护。


## 2026-10-29：P10-01 / P10-06 shape 合约开发与验收

- 用户显式选择01/06，其余P10候选延期。先核对zzy技能、README、todo/最新日志、innovation 4.3、Web/syntax/stdlib/resources/coverage/CI契约、实现和环境。初始main/db9be8fcf135d0ef55e36129327ba0a239fff8ca工作区干净，P08已有人工资料与PR交付；第一次创建分支因会话.git只读被拒绝，未改main。用户恢复权限后创建codex/p10-shape-contracts，保留原件与用户8000服务。
- 决策：不改语法/普通shape。静态Compiler从prepare的注解绑定/模块图构建冻结Field/Shape描述，校验/Map布局转换/OpenAPI共享此描述；拒绝动态别名/默认/递归/不支持类型。请求仍Map、按请求补标量默认；响应精确状态码绑定，其他业务状态不套成功shape。生成命令不初始化模块，默认服务模式的错误请求甚至先于逐请求初始化拒绝；shared启动初始化维持P08原义。
- 集中契约在docs/runtime/web.md；新增核心公开generate_openapi和python -m zzy.contracts；create_app增加contracts及CLI --contracts，启用后提供/openapi.json。错误422 contract_input、500 contract_response包含稳定path/reason；容量/取消沿用原控制信号。超长未知字段路径限制4096字节，避免错误响应放大；Unicode组件名转换为ASCII标识，operationId按有序路由唯一化。
- 核对官方OpenAPI3.1.1和JSON Schema numeric文档，严格保留ZZY Int/Float差异，用x-zzy-type/x-zzy-rules说明。独立jsonschema4.25.1的Draft202012Validator只验证标准子集；测试明确1.0可满足标准integer但被ZZY Int拒绝，number可接受Int但ZZY Float拒绝。default由项目实际填充，不靠第三方；Array/Map不假造元素约束。
- 初次专项14项中1项失败：夹具写成(zzz) io.input，现有语法要求(zzz)(...)，修正夹具而非放宽语法。最终核心合约14/14，真实HTTP原14项+新增5项+独立Schema3项=22/22，零跳过。交错屏障验证默认/shared不同输入、Map/Array局部修改无串用；字段失败不写业务标记文件，响应失败及资源失败后正常请求成功。资源/取消测试逐项核对计量归零。
- 实际命令：.venv/Scripts/python.exe -X utf8 -m unittest tests.test_contracts -v；通过tests.__main__.execute将同一14项结果保存tests/p10/core-specialist.json（1.227秒）。.venv/Scripts/python.exe -X utf8 -m tests.web_http --report tests/p10/http.json通过22/22（7.109秒）。生成examples/contracts/openapi.json成功；源码中业务长度/非空/优先级规则仍ZZY实现。示例人工清单均待执行，不冒填人工结果。
- .venv/Scripts/python.exe -X utf8 -m benchmarks.contracts --output tests/p10/measurement.json --repeats 30通过，4/32/128字段、每字段16字符；记录环境、资源、Git基线和实际源码哈希、全部原始样本与离散程度。prepare含读取/前端；generation含IR/OpenAPI编码；validation含Map规范化分配、不含JSON解析/业务/HTTP/清理。中位校验0.0636/0.3962/1.5638ms，无等价对照不声称提速。
- .venv/Scripts/python.exe -X utf8 -m scripts.ci package --output dist/p10-package --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe通过；44运行时源码一致，核心无第三方环境新增静态合约无副作用probe，原headless/校园/SQLite/嵌入探针保留。
- 新建dist/p10-web-installed环境，安装上述wheel[web]及scripts/ci/contract-requirements.txt。安装探针第一次把位于dist下的venv误判成源码目录；检查实际zzy.__file__后改为必须位于sys.prefix且不是源码zzy目录，再逐文件比对全部44源码。修复后python -I -X utf8 scripts/ci_web_installed_probe.py --report tests/p10/installed-http.json在源码目录外运行22/22（7.5秒）。此探针接入CI Web job，不改核心运行依赖。核心runtime/专项用例在最终回归开始前已固定；其后只补文档及单独验收的CI安装包装脚本。
- scripts.ci inventory将基线2027增至2041，仅新增14个ID；原1738外部CLI不减。scripts.ci static --output dist/p10-static-first通过；完整核心命令.venv/Scripts/python.exe -X utf8 -m tests --report tests/p10/core-regression.json进行中，输出dist/p10-regression.log，最终结果后补，不提前勾选任务。
- 本轮没有执行真实Tk GUI、云端CI、其他OS或人工验收；不扩大为P10-08已完成，不推送/合并/修改保护。requirement和docs/manual-tests原件不改。

- 额外真实CLI演示：生成命令与两个独立zzy.web --contracts进程（原版/只新增note字段的副本），10次POST均符合固定期望，导出文件与服务/openapi.json逐结构相同；自动证据tests/p10/cli-demo.json，不算人工验收。仅终止本探针拥有的进程，原8000服务未动。actionlint v1.7.12与scripts.ci static --output dist/p10-static-review均通过。

- 第一轮完整核心回归2041/2041、944.750秒通过，零失败/错误/跳过，保留core-regression-initial.json。最终审查发现业务绑定422/500时OpenAPI未描述同状态码的适配错误包；新增独立Schema用例先真实失败，再为重叠状态码生成anyOf（业务shape或严格适配错误包），业务校验本身不变。23/23 HTTP/Schema专项通过（http-final.json，7.093秒）。为避免把旧生成器回归当最终代码证据，冻结代码后通过scripts.ci regression重跑，并重建安装包及执行汇总门禁；旧安装/测量/source证据保留initial或原文件，新测量另存measurement-final.json。

- 最终冻结代码门禁：scripts.ci static --output dist/p10-final/static及static-review通过；scripts.ci regression --output dist/p10-final/regression真实调用完整python -m tests，2041/2041、919.828秒，failures/errors/skipped/expected_failures全0；scripts.ci package --output dist/p10-final/package --installer（同上）通过，44源码一致；新wheel在dist/p10-web-installed --force-reinstall --no-index --no-deps安装后，用python -I运行ci_web_installed_probe，23/23、7.282秒。scripts.ci gate --artifacts dist/p10-final --output dist/p10-final/gate退出0、passed=true，static/regression/package的context一致；Web安装结果独立保存，云端仍未运行。
- 最终测量measurement-final.json保持30次/档和同一资源配置：4/32/128字段的prepare中位数3.2545/4.1582/6.6476ms，generation为0.1429/0.2981/0.8919ms，validation为0.0635/0.3887/1.6050ms。未声称优化收益；初版结果不覆盖。最终声明仅限P10-01/06，现勾选两项；P10-02—05、07、08延期，下一项P11-01。
- 将真实报告归档tests/p10；static归档保留摘要，完整ID清单仍在dist和已审查的test-inventory。归档追加证据不改运行时/用例，source.json逐文件校验一致；requirement原始SHA256未变。人工清单待操作者执行，GUI/其他平台/云端PR门禁不冒充通过。准备审查显式暂存清单并创建本地提交；不推送、不合并、不改保护。
- 归档后scripts.ci static --output dist/p10-after-archive-static及actionlint再次通过；演示README的4个PowerShell块通过Parser语法检查（非人工执行）。暂存前核对70项代码任务仅59项完成、其余P10均未勾选，requirement及人工目录无差异。

## 2026-10-29：新增P11解释器优化计划，交付阶段顺延P12

- 用户明确选择先前讨论的1—5：诊断位置按需生成、资源计量简化、小整数守卫、sum/stats工作分离、查询排序比较；本轮授权是更新设计和开发顺序，不实现运行时。接手feature/a480ecc，工作区干净；核对todo与tests/p10现存验收，P10-01/06保持完成，不将旧报告当新测试。
- 新增docs/runtime/optimization-plan.md，安排P11-01基线→02诊断位置→03资源计量→04小整数→05sum/stats→06查询排序→07累计验收；写明源码入口、保持值/诊断/配额/取消/并发隔离、边界与故障验证、同配置单项/累计测量、无收益撤回、实际证据路径和后续交接。新报告、测试映射及命令在实现时建立，不创建假通过记录。
- 原P11-01—05交付任务一一顺延P12-01—05，任务内容与未勾选状态保留；新增七项后总数77、完成59。历史日志、人工原件及验收报告中的旧P11编号不改写；todo追加最新交接覆盖旧下一项。当前下一项P11-01冻结基线，P11完成后进入P12-01。
- P10所有候选保留，innovation新增逐项收益/成本/暂缓原因/重启条件；02/03/04/05/07/08保持未勾选。03的小整数子范围移交P11-04、08的必要对照分布到P11，不代表完整VM或完整引擎/变形扩展完成，也不重复计数。
- 同步根README、文档导航、详细设计、roadmap/todo、解释器/资源/性能说明、人用与AI指南、覆盖/CI/最终测试计划及tests/benchmarks导航，避免旧P11交付路径误导。静态一致性脚本核对原70项→新77项、59项完成、所有旧任务勾选保持、新P11七项和P12五项未勾选；requirement SHA256仍b099c19fc339ce1dc1aab7e9d6c8126a9c5c9ace3d31b969a0623df90f521d2b，当前差异仅Markdown，无运行时/测试代码变更。完整文档门禁结果另记于下。
- 实际执行`.venv/Scripts/python.exe -X utf8 -m scripts.ci static --output dist/p11-planning-static-20261029`退出0、passed=true，检查58份Markdown、753个本地链接、围栏、原测试清单与应用行数及requirement。另核对P12五项正文和勾选与旧P11逐字一致、P11计划七节与P10八项取舍完整、开发记录仅追加、新取舍锚点有效。git diff --check通过；本轮未跑全量/HTTP/GUI或性能，不新增通过声明，不提交或推送。

## 2026-10-29：P11-01 冻结基线与实验驱动

- 按用户附件逐项推进，每项本地提交。从feature/a480ecc建立codex/p11-interpreter-optimization，接手19份规划修改及新optimization-plan；保留并随本项提交，原差异和哈希存tests/p11，不冒充本轮运行时实现。requirement及人工原件不变。
- 核对P10记录列出的13文件与HEAD；CRLF使原始哈希部分不同，归一LF核对确认相同。44运行时文件以HEAD独立快照冻结，环境CPython3.12.14/Windows/default-v1、CPU/GC/依赖及源码/驱动身份存environment.json。P10历史2041全量仅证实未改基线，本项未重跑全量。
- 新增benchmarks.p11/p11_worker/p11_reference，复用B01—B09算法/答案，补stats三规模、重复键/筛选/take0查询、Sketch、成功检查/超限/预留释放。临时快照比较，不改产品开关；正确性预检→独立profile→3预热/15正式，串行交错、独立状态，阶段成本/CLI分别记录，失败不填0。测量与回归未并行。
- 真实命令：python -X utf8 -m benchmarks.p11 --before HEAD --output benchmarks/results/p11/01-baseline --profile；762条记录成功/失败0，正式样本每组15。初始01-precheck的50条通过保留，正式前已补stats参考并重做预检；profile证实成功路径重复span开销，结果不预称加速。
- python -m unittest tests.test_p11_benchmarks -v：3/3，19.741秒；用tests.__main__.execute合并驱动、test_p09_app、test_embedding、test_database：42/42，126.291秒，零跳过，01-specialist.json。python -m tests.web_http --report tests/p11/01-http.json：23/23，7.156秒。校园含自动Ctrl+C检查，不声称人工Ctrl+C。scripts.ci inventory保留2041并新增3项至2044；static --output dist/p11-01-static通过。
- 方法、基线、热点和复现命令见optimization-report；此阶段不改解释器。仅勾选01，下一项02。GUI/人工/云端未重跑，后续优化不能借用本项通过。
- 暂存审查发现原始diff的上下文空格及pstats尾部空行触发diff --check；原始规划diff改为无损gzip保存，profile只去末尾空行，不改变样本或数值。

## 2026-10-29：P11-02 诊断位置按需生成（验收进行中）

- P11-01已本地提交eaa8bcc，工作区干净后实施02。Interpreter.check/reserve成功路径只调用原ResourceMeter；仅捕获ResourceExceeded时用原location+Token.span补诊断，不添加全局缓存/回调/Program字段，不改变meter取消安全点。定位普通异常含MemoryError保留原E211；无可用定位时保持file/span为空，计数和阶段保留。
- 新增5项测试，完整诊断/Unicode/BOM/CRLF/EOF、错误provider兜底、共享Program16请求、cwd、真实CLI跨模块notes/check。第一次7项中1项失败是手写列号误差：枚举源码plus在24、独立HEAD快照也报[24,25)，修正夹具而非弱化期望。随后结合旧资源及P07位置专项16/16（0.541秒），HTTP/Schema23/23（6.687秒），记录tests/p11/02-*。
- scripts.ci inventory新增5项至2049；完整命令python -X utf8 -m tests --report tests/p11/02-core.json正在执行，不提前勾选。性能会在回归结束后单独运行。
- 完整核心2049/2049、939.047秒，失败/错误/跳过/expected failure全0，02-core.json；冻结源码见02-source.json。全量结束后才启动benchmarks.p11 --before HEAD --after WORKTREE --output benchmarks/results/p11/02-locations，覆盖全部21组，计时进行中。
- 02-locations共1496记录成功/失败0；正式每组15。B01执行3.8267→2.1884ms，B04/1000 12.3229→5.9044ms，K01 8.9836→6.6997ms；CLI多数变化小，完整表及MAD见优化报告。D02真实超限6.1072→7.9971ms（+30.9%），独立profile复核新增补定位/Diagnostic复制冷路径开销，约1.89微秒/失败；明确接受而不称所有路径更快。未改变正确性代码去追计时，保留02，下一项03。

## 2026-10-29：P11-03 资源计量与登记所有权（验收进行中）

- P11-02提交02ebaa8后实施本项。先新增WeakSet登记MemoryError注入，在旧版本真实失败（runtime_slots为2而非0，dist/p11-03-fault-before.log），确认是meter已扣款而Interpreter尚未持有清理所有权。修复为登记任何BaseException时立即release后重抛，不把取消变普通错误。
- 候选：单资源预留先完成原计数校验/取消/限额/整数计算及Reservation构造，再执行一次内部原生dict赋值；多资源仍使用副本统一提交。只对内部本来就是普通dict、str键和Int计数成立，不提供用户自定义映射接口。Reservation加slots及__weakref__，保留弱引用/子类扩展；不对Value加slots、不池化、不改跨请求所有权。
- 新增5项test_p11_meter，L-1/L/L+1、未知键/Bool/取消原顺序、空预留、构造/副本/单赋值/登记MemoryError注入，保留活traceback时仍归零，重复release、alias/cycle/超限GC重试、12个独立并发计量上下文和固定种子参考账本。结合资源、解释器和P11位置共25/25、0.734秒，03-specialist.json。
- 真实HTTP/Schema执行后启动完整python -X utf8 -m tests --report tests/p11/03-core.json；清单新增5项为2054。计时待全量结束后进行，尚未勾选03。
- HTTP/Schema23/23、6.485秒；完整核心2054/2054、899.281秒，零失败/错误/跳过，03-core.json。独立tracemalloc（不与正式计时混跑）保留1000个单槽预留：跟踪current 284208→265064字节、peak 284384→265168，释放后slots=0；03-memory.json含执行代码及双方源码身份，不测RSS。随后串行启动03-meter对照（B01/B02/B03/B04三规模/B05/B06/B08/B09/K01/R01）。
- 03-meter共884记录、失败0、正式每组15；B04三规模执行中位分别−3.7%/−6.3%/−6.8%，B02/B09/R01分别+1.9%/+2.2%/+1.4%，处于本轮MAD量级，不称全面加速。没有>20%中位退化，单项表/所有阶段原始值已存。保留小范围优化及登记修复；勾选03，下一项04。完整回归用时不当性能对照，tracemalloc不当RSS。
