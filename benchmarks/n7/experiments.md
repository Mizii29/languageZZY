# N7 热点与候选

先完成 [基线](baseline.md)，再生成独立源码副本并用同一 MSVC Release 配置做插桩。探针记录 AST 任务、堆查找、pin、配额检查、预留、分配和回收的调用次数与计时。嵌套插桩区间从父区间扣除。计时器本身会干扰热点，绝对时间和各项占比均不能作为正式基准。

| 夹具 | AST 任务 | 堆查找 | 配额 check | 预留 | 分配 | 回收 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| X00 | 24 | 24 | 52 | 15 | 8 | 0 |
| X01 | 200043 | 350034 | 420043 | 100013 | 40006 | 9 |
| X02 | 410046 | 580041 | 735050 | 185015 | 65008 | 15 |
| X03 | 320060 | 430067 | 390111 | 100030 | 30013 | 7 |

候选仅把本地堆句柄的 `count + at` 改为一次 `find`。保留共享堆转发和失效、跨上下文、关闭的判定顺序。候选用独立 MSVC Release CLI 和无插桩阶段探针评估。按同组同序号逐对计算候选时间 / 基线时间。提前设定保留条件为 X01、X02 的执行配对中位数在两轮各至少降低 5%，X03 执行及三组长程序的完整 CLI 在任一轮均不回退超过 5%，并通过资源、诊断、别名、取消和累计回归。

同一 MSVC 构建的 `sizeof(RuntimeNode)` 为 472 B，`RootToken` 为 32 B，`Value` 为 16 B。这些值不包含分配器、控制块、哈希表及动态字段。X03 的实际驻留与私有提交量支持优先研究值表示和存活对象布局，例如仅为常见整数评估更紧凑的表示，继续保留精确 BigInt 与标签语义。资源预留和检查同样高频，单项候选可评估避免重复策略键查询，仍须检查诊断位置、取消安全点和原子配额归还。

更大项目若立项，先用小范围字节码 VM 验证能否减少 X01、X02 的 AST 分派与临时分配。这个实验需要把宿主开销、冷启动和长期数组内存一起测，并复用 N6 固定答案。静态算术 AOT 适合作为单独的子集实验，需证明边界溢出、资源失败和可诊断性一致。JIT 的预热成本尚无可摊薄的重复执行证据。当前 10,000 次迭代的原生准备只占数毫秒，X00 又以进程启动为主，优先做磁盘缓存的证据不足。后续缓存评估应先测真实多模块重复请求，再计入失效、源码位置信息与体积成本。

```powershell
$py = '.\.venv\Scripts\python.exe'
& $py -X utf8 -m benchmarks.n7.experiment profile dist/native-n7/profile-src
cmake -S dist/native-n7/profile-src/native_runtime -B build/native-n7-profile -G 'Visual Studio 17 2022' -A x64 -DBUILD_TESTING=OFF -DZZY_NATIVE_BENCHMARK=ON
cmake --build build/native-n7-profile --config Release --target native-n7-probe
$probe = (Resolve-Path build/native-n7-profile/Release/native-n7-probe.exe).Path
Push-Location dist/native-n7/frozen
try { & $probe X01.zzy limits.json } finally { Pop-Location }
```

[剖析原始数据](../results/native-n7/profile.tar.gz) 包含四个固定答案、本体哈希和各探针计数。首次插桩拒绝了与两个 `pin` 方法匹配的锚点。确认匹配位置后收窄到堆操作，保留第一次生成的源码副本，第二次构建及 4 项输出核对通过。
