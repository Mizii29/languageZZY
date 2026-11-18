# N1 原生源码与词法接口

2026-11-17建立，2026-11-18补齐正式构建验收。范围为 N1-01—04，遵循 [语法](../language/syntax.md)、[诊断](../language/diagnostics.md)、[资源](../runtime/resources.md)。不复制第二套语言规则。先前N0-03顺序例外为历史，最新代码已通过CMake/MSVC Debug/Release、非空CTest及安装/源码外验证，见[正式报告](../../native_runtime/tests/msvc-report.md)。

## 公开命令与阶段

`zzy-native info`、`source-info FILE`、`lex FILE`，共同支持 `--limits FILE`、`--diagnostic-format text|json`（命令前后均可，支持等号形式）；`--` 后停止选项识别。`--help`（含子命令）与 `--version` 不读取 limits。未知选项不缩写匹配，参数/配置错误为 E401/2。

`source-info` 返回 file、原始 bytes、去除单前导 BOM 后 codepoints、LF 定义的 lines、原始字节 sha256、syntax_checked=false、生效 resource_fingerprint；既不词法检查也不执行业务。`lex` 输出 schema_version=1 的 Token JSONL：kind/lexeme/value/raw/span；value 只对 STRING 为解码文本，数字不在本阶段转为值。非 EOF Token 全部扫描成功后才开始输出；首个词法失败时 stdout 空。EOF 是零宽 Token，不占 tokens_per_file。

`info` 报告 N1、Unicode15.0.0、compiler/CRT/位数、三个 supported_commands、生效 default-v1 与 SHA256。尚无 AST、Resolver、值执行或缓存；run/check/test 仍在读取源码之前 E402/2，不触发 Python fallback。N1 的 lex 成功不表示程序语法/名称/类型正确。

## 源码、Unicode 与所有权

Win32 宽字符 argv/文件接口，严格 UTF-16↔UTF-8，拒绝路径 NUL 和非标量参数。源码为不可变原字节快照，严格 UTF-8，拒绝过长编码、代理区、越界、截断及非法续字节。只移除一个前导 BOM；第二个 BOM 留在文本，lex 依语法拒绝。

每个码点含原始字节起始偏移，含 EOF；反向查询仅接受实际码点边界，BOM 内偏移不当作文本。span 半开且从1计数；补充平面字符与 Tab 各占一列，CRLF 在 LF 后换行，单独 CR 不换行。行末 LF 产生下一空行。原始 sha256 包含 BOM/CRLF，不做换行归一化。

标识符起始/后续与空白使用锁定 CPython3.12.14/Unicode15.0.0 的离线分类数据，保留原拼写，不做 NFKC 或 locale 分类。生成器、表和来源/哈希在 native_runtime 中，运行时没有 Python。数字仅 ASCII；长整数字面只检查 numeric_digits，不借助宿主 Int64 或浮点转换。

SourceLoader 按规范文件路径（含大小写、8.3、junction）复用本上下文字节快照；读取句柄 RAII 关闭。所有读取/解码/内存分配成功后才发布和计入 source_total_bytes/module_count，失败不留半快照或费用；close 幂等释放其费用。Token 使用共享的 const Source 保持快照，不持有前端计量器；不将运行时可变图放入 Program。本阶段没有模块导入解析，module_count/import_depth 的载入接口通过原生单测覆盖，不代表 use 已可执行。

## 预算、取消和诊断

limits 文件严格 UTF-8（不接受 BOM），最大64KiB；精确字段 policy_version=1 和 limits，对象重复键（含转义同名）、未知键、Bool/Float/null、0/负数、超过2^63−1的值全部 E401。只解析这个有限深度的宿主配置，未提供语言 data JSON 接口。全部22键仍在策略记录中；当前强制 source_file_bytes/source_total_bytes/module_count/import_depth/tokens_per_file/numeric_digits/text_codepoints/stdout_bytes/stderr_bytes，其他键为后续阶段保留。

源码读取按剩余配额+1有界探测；数字按每位、Token 按非EOF项、字符串按每个解码片段检查，字符串限额分别独立。host_decimal_digits=0，无 CPython 宿主十进制上限；effective_decimal_digits=numeric_digits。规范 JSON 与 SHA256 独立已知向量核验。

输出先检查完整记录的 UTF-8 字节数再写；后续输出超限可留下完整的较早 Token 行，不会半行截断。诊断 schema v1、词法 E101/转义 E102、资源 E211、源码/配置 E401；本阶段均退出2。stderr 预算耗尽时使用独立最多4096字节的最终诊断保留区，保留有效 UTF-8 和完整 JSON，不截断编码序列。

Ctrl+C/Break handler 只设置无锁原子标志；读块、UTF-8解码/行映射/哈希每至多1024源码单位、扫描循环和长注释内设协作安全点。取消退出130，kind=cancelled/code=null。不能承诺同步 Win32 文件 I/O、内存分配及系统调用可被安全点即时打断。自动测试验证扫描中的真实并发取消与后续新请求恢复；亲手 Ctrl+C 本轮未验证，不与人工验收混同。物理 RSS 不等同逻辑预算。

## 证据与非目标

固定期望来自原 tests/lex/cases.json、独立额外字节夹具、已知 SHA 向量及独立预算公式；测试不调用 Python ZZY 生成答案。原生 C++ 测试、纯 PowerShell 固定清单和源码外验收均有显式非空门禁；Python 可作为开发协调器，不属于 EXE 运行依赖。

历史GCC计数见[N1报告](../../native_runtime/tests/n1-report.md)，正式CMake/MSVC与Release安装的独立计数和CRT依赖见[正式报告](../../native_runtime/tests/msvc-report.md)。其他平台、clang-cl、Sanitizer、人工Ctrl+C/GUI、缺CRT干净主机不能由这些结果推断。本阶段不进入N2，不更改Python默认入口、requirement或P12/P13。

## N2 当前命令（2026-11-18）

N1章节描述其冻结版本。当前N2增加check/program-info并准备完整模块图，规范见[Program契约](native-program-contract.md)；run/test仍E402。N1语法/源码接口未改变，当前info stage=N2/version=0.0.0-n2、supported_commands为五项；新资源接线包含AST/语法深度、静态整数字面及Quantity。N2不求值、不创建请求对象，也没有VM/缓存。当前验收与限制见[N2报告](../../native_runtime/tests/n2-report.md)。
