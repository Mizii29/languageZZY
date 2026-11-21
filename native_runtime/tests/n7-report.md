# N7 性能、内存与后端评估

## 出口

N7-01—N7-04 已完成评估。测量边界、夹具、资源策略、进程指标、失败保存方式和复现命令集中在 benchmarks/n7/README.md。正式 Release 原生程序来自 N6，SHA-256 为 f697f08b0336bb34522ff036ca98cb7d72e2cf1adbb3993d940ae25e43279add。N7 阶段探针、四个配对输入、default-v1 限额和 CPython 3.12.14 哈希都写入 dist/native-n7/frozen/manifest.json，原始轮次保存在 benchmarks/results/native-n7/baseline.tar.gz。

## 环境与冻结边界

测量机为 Windows 11 家庭中文版 build 26200、Intel(R) Core(TM) Ultra 5 125H，14 核/18 线程，物理内存 25,196,617,728 字节，插电，活动电源方案为平衡。工具链为 Visual Studio Build Tools 2022、MSVC 19.40.33812.0、Windows SDK 10.0.22000.0、CMake 4.5.0。Python 两个变体使用同一锁定 CPython 3.12.14 本体。Python 版 ZZY 取当前 Git tree 8a45f5348ff664d267dbddd0e1937b261cfecd3b，原生源提交为 0ed87ff7abb1329c0b46d9ac5288d308fc0ec429。固定答案由 benchmarks/n7/cases.json 给出，测量程序不能生成答案。

四个夹具为常量函数、平方和、带奇偶分支的函数调用、数组追加后遍历。X01—X03 使用 n=10000，ZZY 与 Python 文件分别来自同一 P12 算法定义，直接 Python 使用对应的语言实现。输入、结果、输出和工作目录逐样本检查。没有加入手写 C，也没有用 P12 旧样本替代本轮数据。

## 正式样本

三种变体分别是原生 ZZY、Python 版 ZZY 和直接 Python。两轮各 3 次预热、15 次正式样本，每一轮 432 次进程运行，其中 360 次正式样本，两轮正式合计 720 次。每次运行完整 CLI 和阶段探针各有记录。两轮全部 432/432 correct，失败、错误答案、超时和缺失 Windows 进程计数器均为 0。另有 24 次探针 smoke 和 12 次逻辑配额采集，全部正确。

Windows 子进程句柄在退出前后读取 GetProcessTimes、K32GetProcessMemoryInfo。报告保留 CPU user/kernel、峰值工作集和峰值 Private Bytes，逻辑对象/槽位/负载另表。四个夹具的详细中位数、MAD、四分位数、原始输出和环境在两份 summary.json / raw.jsonl 中。

原生 ZZY 的纯执行中位数为 X01 114–124 ms、X02 231–232 ms、X03 134–141 ms。Python 版 ZZY 为 291–306 ms、711–746 ms、405–419 ms。直接 Python 为 0.46–0.47 ms、0.73–0.75 ms、0.62–0.66 ms。原生执行比 Python 版 ZZY 快约 2.5–3.2 倍，直接 Python 在纯算法执行中快于原生许多。完整 CLI 包含进程、解释器/解析准备与输出。原生 X01—X03 为约 142–175 ms，Python 版 ZZY 为约 525–652 ms，直接 Python 为约 42–47 ms，故不能把原生较快外推到直接 Python 或所有边界。

完整 CLI 峰值工作集方面，原生 X00/X01/X02/X03 为约 6.2/8.3/8.4/14.7 MiB，直接 Python 为约 11.0/11.0/11.0/11.4 MiB，Python 版 ZZY 为约 27.0/27.1/27.0/35.5 MiB。原生数组样本因为运行时节点、容器和解释器对象布局，实际工作集超过直接 Python。逻辑采集中 X03 原生为 8 个对象、10016 个槽位、34911 字节，Python 版 ZZY 为 8、10016、19755，且每次请求结束后计量归零。逻辑配额不是操作系统内存的替代指标。

## 热点与候选

插桩副本不参与正式表。四个夹具分别记录 AST 任务、堆查找、配额检查、预留、分配和回收调用数，剖析原件在 benchmarks/results/native-n7/profile.tar.gz。长程序最频繁的操作是 AST 任务、句柄查找和配额检查，X02 最高达到 580041 次查找和 735050 次检查。sizeof(RuntimeNode)=472、sizeof(RootToken)=32、sizeof(Value)=16，动态字段、分配器和哈希表另计。

只评估一个候选，把本地句柄的 nodes.count(h.id) 与 nodes.at(h.id) 合并为一次 find。共享堆转发、失效句柄、关闭和所有权判断保持原顺序。候选在独立 MSVC Release 副本构建，使用种子 711、712 各 3 次预热/15 次正式。两轮共 576 次 A/B 运行，均匹配答案且 0 失败/超时。X01/X02 的阶段执行变化分别为 -2.65%/-7.00% 与 -1.62%/+2.25%，X03 为 -3.04%/+2.36%；完整 CLI 的 X03 两轮为 +8.12%/+7.36%。受噪声、夹具间方向相反及 X03 回退影响，未达到预先写明的两轮稳定 5% 门槛，候选撤回，生产源码没有改变。完整 A/B 原始证据在 benchmarks/results/native-n7/lookup.tar.gz。

## 适用回归与限制

候选撤回后，原生 Release 重新配置并构建阶段探针，运行排除两个已独立执行的长 parity 测试的 84 项 CTest，结果 84/84，总耗时 145.27 秒。固定原生清单重新运行 native_runtime/tools/test-parity.py，结果 1738/1738，失败和超时为 0。N6 已有校园、SQLite、Web、Sketch、GUI 和持久化证据保持有效，本轮没有改动这些宿主。

没有实施 VM、AOT、JIT、磁盘缓存或新的 build 命令。依据当前证据，优先级是先评估字节码 VM 是否能降低 X01/X02 的 AST 分派和临时分配，再用静态算术子集单独验证 AOT 的边界溢出、资源失败、诊断位置和取消语义。JIT 还没有足够重复请求证据覆盖预热成本，磁盘缓存还没有真实多模块重复请求证据。手写 C、Lua、Web/GUI/SQLite 主导负载、其他机器、物理断网、Sanitizer、人工 Ctrl+C、缺少 VC Runtime 的干净主机尚未在 N7 测量中验证。

复现入口见 benchmarks/n7/README.md。上述命令要求新建输出目录，不会覆盖已有轮次。N7 没有改变默认入口，N6 的解释器和测试保持可用。
