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

## 候选结果

两轮分别用种子 711 和 712，各 288 次运行，其中 48 次预热、240 次正式。全部匹配固定答案，失败和超时为 0。另有 16 次 A/B 预跑。单元格是同序号逐对比较的耗时变化中位数，负值表示更快，括号中为 MAD，单位为百分点。

| 夹具 | 执行第一轮 | 执行第二轮 | CLI 第一轮 | CLI 第二轮 |
| --- | ---: | ---: | ---: | ---: |
| X00 | +1.69% (27.89) | −12.83% (21.39) | +2.47% (9.54) | +0.79% (6.74) |
| X01 | −2.65% (4.29) | −7.00% (10.43) | +5.13% (7.61) | +0.07% (9.99) |
| X02 | −1.62% (12.65) | +2.25% (10.37) | −4.88% (9.16) | −7.17% (7.92) |
| X03 | −3.04% (9.74) | +2.36% (4.09) | +8.12% (10.95) | +7.36% (8.40) |

候选未达到保留门槛。正式源码与 N6 原生 CLI 继续使用原实现。候选只在独立源码目录构建，产物 SHA-256、原始样本、CPU 和内存分布见 [A/B 归档](../results/native-n7/lookup.tar.gz)。

```powershell
$py = '.\.venv\Scripts\python.exe'
& $py -X utf8 -m benchmarks.n7.experiment lookup dist/native-n7/lookup-src
cmake -S dist/native-n7/lookup-src/native_runtime -B build/native-n7-lookup -G 'Visual Studio 17 2022' -A x64 -DBUILD_TESTING=OFF -DZZY_NATIVE_BENCHMARK=ON
cmake --build build/native-n7-lookup --config Release --target zzy-native native-n7-probe
New-Item -ItemType Directory dist/native-n7/lookup-bins
Copy-Item build/native-n7-lookup/Release/zzy-native.exe dist/native-n7/lookup-bins/native.exe
Copy-Item build/native-n7-lookup/Release/native-n7-probe.exe dist/native-n7/lookup-bins/probe.exe
& $py -X utf8 -m benchmarks.n7.run run dist/native-n7/frozen dist/native-n7/lookup-replay-1 --seed 711 --candidate dist/native-n7/lookup-bins
& $py -X utf8 -m benchmarks.n7.run run dist/native-n7/frozen dist/native-n7/lookup-replay-2 --seed 712 --candidate dist/native-n7/lookup-bins
& $py -X utf8 -m benchmarks.n7.paired dist/native-n7/lookup-replay-1/raw.jsonl native candidate
```
