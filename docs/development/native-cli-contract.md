# N5 原生 CLI 与 spec 运行契约

本文件细化现有语言、[资源策略](../runtime/resources.md)和[诊断](../language/diagnostics.md)，不改变 Python 默认入口或 ZZY 语法。Windows x64 的公开命令为 `info`、`source-info FILE`、`lex FILE`、`program-info FILE`、`check FILE`、`run FILE` 和 `test FILE|DIR`；`--help`、`--version` 无需读取 limits。其他后端/宿主入口参照原生 README，不自动初始化。

`--limits FILE`、`--diagnostic-format text|json` 可在命令前后出现，也支持 `--name=value`。`--` 终止选项解析，允许以 `--help` 命名的文件。缺失/多余位置参数、未知选项、非法配置返回 E401/2。`test --timeout SECONDS` 默认为 10，必须是有限正数，只适用于 test。重复选项取最后一个值。

stdout/stderr 重定向均使用 UTF-8 字节；文件路径通过 Windows Unicode 参数处理，源码坐标是码点坐标。`run` 的 stdin 解码严格 UTF-8，非法输入为运行错误；`check`、`lex`、`source-info` 不执行用户代码。输出普通文本时保持 LF，JSON 诊断按 schema v1 每行一个记录。配置、前端与执行配额沿用资源键，不创建第二份默认 limits。

| 情况 | 退出码 |
|---|---|
| 命令/执行成功，或所有已收集 spec 通过 | 0 |
| run 运行错误；spec 失败、超时、输出超额、异常、空集合、收集错误 | 1 |
| CLI 参数/limits/普通前端准备错误、未处理的内部前端错误 | 2 |
| 控制台 Ctrl+C/Break，经协作点取消 | 130 |

## 原生 run 执行方式

核心 `zzy-native run` 接受 `--engine auto|ast` 或 `--engine=auto|ast`。默认 `auto`。缺失选项值、未知值或将其用于其他命令均为 E401/2。独立 GUI 和 Web 宿主以及 spec worker 使用其通用 AST 路径。

`auto` 在单模块且使用默认限额时，为已解析的顶层纯整数函数建立一次性字节码表。包含循环的函数及其直接调用图可以进入 VM。AST 按原顺序求值实参并检查调用深度，VM 使用有界整数和一次预留的活动帧预算。宽整数、类型不符、不支持的指令、达到内部容量或资源上界不足时，使用已求值的实参在原调用点继续 AST。VM 不包含用户 I/O、容器修改或其他宿主调用。取消直接返回现有退出码，不重放 AST 调用。自定义限额及多模块程序使用 AST。

`--engine ast` 便于同版本复现诊断和比较性能。两种方式沿用同一 ZZY 语义、标准输出、诊断和语言资源配置。字节码只在当前运行请求中保留，不扩展 Program 格式或缓存 ABI。[设计与对照数据](../../benchmarks/int_vm/README.md)

## 收集与快照

目录递归收集 `.zzy` 普通文件并按路径排序。先准备所有入口及其完整依赖图，不进行模块业务初始化。任一收集错误则全部不执行；空集合返回 E401，不能当成功。只收集入口顶层 spec，不将依赖模块的 spec 作为入口用例。

每个入口记录完整源码字节及规范路径/导入别名；worker 从记录重新准备 Program，不重新读用户源码。收集后修改或删除依赖文件，不影响本次执行。收集期累计源码/module 资源预算与每个 worker 请求预算分开计量；不引入隐式缓存或共享请求实例。

## 隔离、输出和生命周期

逐 spec 启动相同原生 EXE 的内部 worker，运行公共初始化与唯一选定 spec。独立进程、模块实例、资源计数器、临时 cwd、stdin=NUL；父进程不转发用户 stdin。快照位于另一临时目录，长度前缀逐字段受源文件/总字节等策略限制，并锁定为只读；内部入口和内部退出状态不属于公开 CLI ABI。

仅允许继承 stdin/stdout/stderr 句柄；启动时原子加入 Windows Job Object，设置 kill-on-close，防止启动间隙出现孤儿进程。每个 spec 截止时间覆盖进程启动后的准备/初始化/执行；父进程有界捕获输出，超时、取消或结束时终止整个 Job 并等待活跃进程归零。原生 CLI 不向 ZZY 开放任意进程启动接口。

正常、失败、超时和协作取消会关闭句柄并清理临时目录；Windows 进程退出后 cwd/文件锁释放有短暂延迟，目录清理进行有界重试，正常路径清理失败报告 E401。父进程被外部强杀时 Job 仍清理 worker，但不能执行 C++ 目录析构，此时临时目录可能遗留。这不等于资源已由 RAII 清理，也不是正常取消保证。

父进程将用户 stdout 计入总 stdout 配额，并为最后一行汇总预留空间；超额为失败。诊断受总 stderr 配额限制，耗尽时只使用既有最终 E211 保留区，不能把诊断丢弃当作成功。

普通完成的 stdout 最后一行固定包含 `schema_version:1`、`tests`、`passed`、`failed`、`timed_out`、`collection_errors`，均为非负整数。`tests` 是全部已收集用例数；收集错误时可能非零但没有执行。无错误且非空且 passed==tests 才返回 0。text/JSON 选项只改变诊断；汇总总是 JSON。取消不输出成功汇总；stdout 配额小到装不下汇总时，返回 1/E211，不能要求仍有完整汇总。

## 构建与发布门禁

正式 preset 固定 VS2022 x64/C++17，Debug `/MDd` 仅验证，Release `/MD` 可发布。依赖使用仓库自带代码和 Windows 系统组件，CMake 禁止 FetchContent 下载；不安装编译器。独立 native CI 执行 configure→build→非空 CTest→install→源码外 smoke，保留现有 Python CI。

源码指纹枚举 C++/头文件、CMake、依赖清单、测试程序/固定夹具、native workflow 及测试客户端依赖。代码文本 CRLF 规范化为 LF；ZZY/JSON 字节夹具保持原样。验收报告等不影响构建的 Markdown 不参与代码指纹，避免结果写入反过来改变被测代码。门禁开始/结束指纹不一致则失败，不能复用被修改前的验收结论。

PE 导入、实际加载模块和 worker 进程树共同检查无 Python；空 PATH、无效 PYTHONPATH、移除虚拟环境变量和中文/空格源码外目录是独立验收点。代理不可用和无下载不等于物理断网；缺 CRT 干净机器、其他平台、人工控制台和 Sanitizer 没执行时必须单列。
