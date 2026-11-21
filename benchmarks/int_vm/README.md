# ZZY 整数算法字节码实验

实验执行器从既有 Lexer、Parser、Resolver 生成的 Program 降低为栈式字节码。局部变量沿用 Resolver 的槽位，整数以 64 位带标签值存储，整数数组连续保存这些值。数组引用通过编号表示，两个变量引用同一个数组时修改可见。缩小的执行器覆盖整数运算、Bool 条件、循环、直接调用已定义的函数、整数数组构建和遍历。

MSVC Release 编译后可显式指定 `vm` 或 `ast`。独立实验入口的 `auto` 会先完成前端检查，然后尝试 VM。在拒绝的情况下由 AST 从头执行，返回路径及拒绝原因。纯子集在提交结果前只有请求内的临时状态，输出集中在最后一次 `io.print`。自定义资源策略直接走 AST，超出整数表示、出现不支持的构造或达到实验容量时也可走 AST。前端诊断和取消直接退出。

实验使用有界值栈、调用、数组和步数，检查算术溢出与取消。完整 ZZY 的配额预留、共享、诊断和运行中回退协议尚待移植。将实验推广为按函数选路前，需要让两个执行器使用相同的资源策略、类型与源码位置，并统一宿主调用和容器所有权。适用类型超出内联表示时，应在准确的运算位置升级为大整数或交还同一个调用帧。

## 复现

从仓库根目录运行。准备冻结 N7 输入的方法见 [N7 测量](../n7/README.md)。已冻结的目录可以直接复用，每次指定新输出路径。

```powershell
cmake --preset native-release -S native_runtime -DZZY_NATIVE_VM_EXPERIMENT=ON
cmake --build build/native-release --config Release --target native-int-vm
$py = '.\.venv\Scripts\python.exe'
$vm = 'build/native-release/Release/native-int-vm.exe'
& $vm auto dist/native-n7/frozen/X01.zzy dist/native-n7/frozen/limits.json
& $py -X utf8 -m benchmarks.int_vm.run dist/native-n7/frozen $vm dist/native-int-vm/replay-1 --seed 731
& $py -X utf8 -m benchmarks.int_vm.run dist/native-n7/frozen $vm dist/native-int-vm/replay-2 --seed 732
```

每轮先运行 18 条固定答案和路径守卫，再随机交错五组工作量和三种后端。每个变体 3 次预热、15 次正式，逐次核对 stdout、stderr、退出码和 Windows 内存计数器。每个样本都用新进程。执行段包含用户脚本和一次输出格式化，前端准备和字节码生成分别计时。Private Bytes 和工作集均为整个测量子进程的生命周期峰值，包含各探针自身开销。

## 本机结果

Windows 11 build 26200，Core Ultra 5 125H，MSVC 19.40 Release x64，直接 CPython 3.12.14。比较的是整数 VM、N7 冻结原生 AST 探针、同算法的直接 CPython 脚本。两轮各 225 个正式样本和 45 个预热，共 540 次进程运行，失败和超时为零。两轮各通过 18 条固定答案及守卫测试。原始输出、计数器、样本分布和可执行文件哈希见 [实测归档](../results/native-int-vm.tar.gz)。各格为两轮独立中位数的范围。

| 工作负载 | 整数 VM 执行（ms） | 原生 AST 执行（ms） | 直接 CPython 执行（ms） |
| --- | ---: | ---: | ---: |
| 常量函数 | 0.0043–0.0047 | 0.076–0.086 | 0.012–0.013 |
| 1 万次平方和 | 0.341–0.396 | 117.62–119.72 | 0.453–0.516 |
| 1 万次函数调用与分支 | 0.606–0.623 | 240.01–255.04 | 0.786–0.866 |
| 1 万元素数组 | 0.545–0.559 | 144.35–145.51 | 0.687–0.704 |
| 4 万元素数组 | 2.047–2.116 | 917.88–973.14 | 2.708–2.773 |

四组算法的 VM 中位数相对 AST 快约 260–460 倍，相对直接 CPython 快约 1.14–1.51 倍。4 万元素数组的峰值 Private Bytes 分别为 VM 1.63–1.64 MiB、AST 30.14–30.16 MiB、CPython 9.36–9.46 MiB。峰值工作集分别为 6.07–6.16 MiB、34.28–34.30 MiB、15.68–15.77 MiB。

VM 使用实验性容量保护和取消安全点。其运行期资源计量与 AST 契约存在差距，性能表反映这套精简原型的完整成本。1 万次平方和的原生前端约 6.4 ms，生成字节码额外约 0.011 ms。进程墙钟包含各自测量程序的启动和 JSON 输出，纯执行表用于比较运行内核。Release 既有执行、堆、生命周期、CLI 边界及 CI 指纹专项共 23 项通过。
