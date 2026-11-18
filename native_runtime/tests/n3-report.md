# N3 核心执行：逐批交接

2026-11-18。基线 156a85b（N2 正式 MSVC 验收）。N3 开发中，尚未达到总体出口；不将下述组件结果冒充完整 run 或所有资源键验收。

## 批次 A：核心数值、追踪堆和原子配额

已实现 `bigint.hpp`：带符号 32 位 limb、任意精度加减乘、负无穷取整除法/余数、十进制转换、有限 binary64 的精确有理表示及 Int/Float 比较。固定答案写在 `runtime_values.cpp`，不是由 Python/被测后端生成；除固定大数外，穷举 -300…300 与 -17…17 的非零除数，与独立宿主整数公式核对。

`runtime_heap.hpp` 是真实运行时的类型节点和非拥有边，外部 Value 通过 RootToken 保根；节点不持有 RootToken。可在同一请求中回收 Array→Function→Cell→Map→Array 环，归还对象/槽位/载荷。跨请求句柄拒绝。三键预留全有或全无，分配失败回滚，配额不足先收集再判定。取消/关闭路径幂等释放，不依赖进程退出。

实际 MSVC Debug/Release 组件 CTest 均 6/6，分别 0.63s / 0.23s。命令：

```powershell
cmake --preset native-debug -S native_runtime
cmake --build build/native-debug --config Debug --target native-runtime-values-tests
ctest --test-dir build/native-debug -C Debug -R '^runtime-values-' --output-on-failure --no-tests=error
cmake --preset native-release -S native_runtime
cmake --build build/native-release --config Release --target native-runtime-values-tests
ctest --test-dir build/native-release -C Release -R '^runtime-values-' --output-on-failure --no-tests=error
```

首次 5/6：误复用 N2 Program 专属空选择文案检查。新增独立运行时选择门禁后 6/6；没有放宽 N2 断言。尚未验证整套既有 CTest、CLI run、求值语义、运行期中间空间、完整 Quantity、真实手动 Ctrl+C、Sanitizer 或性能。

下一批：最小执行器和 io.print；再接控制流/函数、闭包/特色、累计验收。N3-01—05 继续未勾选。

## 批次 B：最小 run 与输出

MSVC Debug/Release 各 18/18 CLI 固定用例通过，独立程序/期望为 tests/runtime。无 Python PATH 下运行；新增 PowerShell runner 接入 CTest，拒绝空清单/重复 ID，保留退出码和完整流。run 在准备失败时仍退出 2，执行错误退出 1；test 仍 E402。io.print/len/str/range 为本批最小垂直链，不宣称 N4 库已完成。info 阶段为 N3-dev。

首次 E302 来自将 Resolver 的 builtin 属性误当独立 reference.kind；核对 Program 实际布局后修复。另有 Float 指数夹具不属正式语法，改为等值十进制字面量，保持溢出期望 E208。剩余控制流/函数/特色/完整资源测试尚未验证。

## 批次 C：控制流、函数与捕获基础

MSVC Debug/Release 各 37/37 固定 CLI 用例通过（含批次B18项）。新增块/分支/循环/赋值、用户函数与返回检查，Frame 和求值续体由显式任务栈驱动；call_depth=1600 下实际执行 1500 层调用并返回固定 1500，未使用宿主递归执行 ZZY 调用。新增 Cell 的注解/定义身份边；每轮不可变捕获分离，离开帧的可变捕获仍共享 Cell。

活动 Array 遍历计数经增删、替换、break/continue验证；右侧缩短数组后重新检查位置，错误不回滚已有副作用。Map最小受控操作用于N3顺序/环验证，库全集仍留N4；未知成员与已知但未移植的能力分别 E302/E402。新增固定37项全部在清空PATH/无效PYTHONPATH的独立原生进程运行。夹具首次误用单等号，按正式赋值符号 <- 修正，不改变语法规则或期望。下一批完整特色语义、模块和查询，累计资源验收仍未完成。

## 批次 D：结构、Result、Lazy、Machine、Quantity、模块与查询

MSVC Debug/Release 各 63/63 固定 CLI 用例通过。结构显式字段先于声明顺序默认值求值，with 保留未替换对象引用；失败 Result 从当前函数直接退出，同时释放活动遍历；Lazy 保留捕获引用并缓存结果或诊断；Machine 先分配结果再更新状态；Quantity 采用约分整数分数；模块只在请求中初始化一次；查询先校验 take、再 keep/键/稳定排序/投影，错误保留输入下标。跨文件夹具首轮将除号手算错两列，核对源码实际第 46 列后修正固定期望。

现有独立清单的对照还发现运行期定位与误传限额等问题，实际核心累计出口待资源与同进程测试。批次 D 不作为完整资源一致性的证明。

## 批次 E：N3-01—05 累计验收（2026-11-18）

前置 N2 以提交 `156a85b` 及其正式双配置验收为准；N3 不改变 Python 默认入口或既有期望。前四批本地提交：`211712f`、`6400632`、`2b04357`、`a517114`。本批实测环境为 Windows 11 x64、CMake/CTest 4.5.0、VS 2022 Build Tools、MSVC 19.40.33812、SDK 10.0.22000.0。Debug /MDd 仅用于开发。Release /MD 实际加载 System32 的 Microsoft VC runtime 14.50.35719.0 与 UCRT 10.0.26100.9711；未安装或分发 CRT。

| 门禁 | Debug | Release |
|---|---:|---:|
| CMake configure/build 及非空 CTest | 57/57（159.04 s） | 57/57（67.84 s） |
| CTest 内固定运行 / 词法 / 静态 check 清单 | 63 / 87 / 850 | 63 / 87 / 850 |
| 新旧 CLI 配置、输入输出、准备边界 | 72/72 | 72/72 |
| 未修改的核心 CLI 用例 | 549/549 | 549/549 |
| 单列延期的 `array.sum` 用例 | E402/1 | E402/1 |
| 源码外过程与 PE/加载模块验收 | 70 条，含 1 条预期强杀 | 70 条，含 1 条预期强杀 |
| 安装与仓库外发布副本 smoke | 不发布 | 各 9/9 |

Debug CLI SHA-256：`8453b2d59757ba8c315f5540b7de43d4b2d39330e31a388585e742aad1a09d41`。Release、安装产物和发布副本 SHA-256：`05995767f684a998d940f72f49a23050aa9b5cf74646dc3c0db0ec16591bf271`。

固定回归读取原有 run/P02/P03/P04 及 P06 的资源 run 期望，比较 stdout、退出码、诊断码与固定坐标；有固定文件、notes、消息子串时也逐项核对。没有调用 Python 后端生成答案。实际选中总数为 550（549 核心 + 1 显式延期）。

- **值与资源**：有符号整除和余数、BigInt 精确宽度及混合比较、Float 最近偶数舍入、次正规值的精确二进制比值、非有限值拒绝；Quantity 分子、分母、维度与约分工作空间有限额。容器引用和临时值计量走原子预留，超限不部分发布。有效载荷为逻辑预算，不能用来推导 RSS。
- **相邻边界**：保留 P06 的 15 项资源限制用例，另测源码文件/总量、模块数、导入深度及 stderr。默认大小另有前端及既有清单覆盖；`program_cache_*` 验证可解析、保存在策略并影响指纹，N3 未建立进程缓存，因此不声称经过淘汰验收。N4 仍需验证文件和其他宿主 I/O 的单次预算。
- **同进程请求**：复用同一只读 Program，40 轮每轮依次取消 Lazy 中的真实用户调用、让另一个请求在循环中失败、再以新的取消标记成功执行。断言调用栈、任务、模块、根引用、节点和各项用量清空；已输出行保留。另测 Lazy RUNNING/FAILED/READY、缓存诊断及唤醒位置，活动 Array 遍历，紧配额下 150 次 Array→Map→闭包→Cell 环创建后继续执行。强杀仅验证进程退出，不用于证明请求清理。

复现命令见 [原生 README](../README.md)，核心协调器为 `test-core-existing.py`，固定运行清单为 `tools/test-runtime.ps1`，同进程断言在 `tests/native/execution.cpp`。Python 3.12.14 的相关基础回归 104/104，能力清单另 4/4。`python -m scripts.ci static --output dist/native-n3-work/ci-static-final` 返回 0，核对收集数 2083 和固定黑盒数 1738；这是静态检查，没有运行全量。工作区与暂存差异的 `git diff --check` 均通过。归档 [正式构建、原始输出与 PE 证据](../../benchmarks/results/native/n3-msvc-20261118/README.md)。

过程中修复了原有固定用例发现的输出错误位置、shape 字段不受 Array 单体上限误限、整除临时预算及 stderr 保留区；随后对最后的修订重跑两套门禁。进程脚本首次失败因为 Windows 测试进程的 CRLF 与断言里的 LF 不同；只归一化测试程序的换行，仍逐项检查绝对输出、状态、依赖与空标准错误。

N3 核心出口已满足。真实终端 Ctrl+C、阻塞 stdin 强制中断、Sanitizer、旧 GCC/clang-cl、缺 CRT 干净主机、全量 Python/Web/GUI 及性能对比未验收。N4 完整标准库、文件/JSON 与可选宿主、N5 spec/test 和正式 CLI 门禁、N6 全清单及应用迁移均留在对应阶段。本轮在 N3 停止。
