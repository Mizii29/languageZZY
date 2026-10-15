# P09 校园任务管家验收

2026-10-15：应用七个ZZY模块已经实现；22项应用专项通过，覆盖160组独立校验输入以及真实菜单、文件和恢复行为。最终完整回归1791/1791、806.968秒、退出0，失败/错误/跳过/expected failure均0；[原始汇总](results/all-tests.json)、[验收环境与源码](results/acceptance.json)、[安装包隔离演示](results/installed-demo.json)均已保存。

## 实际入口

```powershell
& ./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_p09_app -q
& ./.venv/Scripts/python.exe -X utf8 -m unittest tests.test_p09_prerequisites -q
& ./.venv/Scripts/python.exe -X utf8 -m tests --report tests/p09/results/all-tests.json
& ./.venv/Scripts/python.exe -X utf8 -m tests.p09.count_lines --check
```

在仓库根目录执行，报告目录需存在。全量入口拒绝空收集、少执行、失败、跳过和expected failure；不要把`zzy test tests/`当作应用测试入口。应用测试通过真实CLI执行main.zzy或导入真实业务模块的独立.zzy驱动，固定stdin/输出和磁盘期望位于Python测试及validation-cases.json中，不依赖spec断言自身正确。

## 覆盖与证据

[coverage.json](coverage.json)将[应用矩阵](../../apps/zzy-campus/README.md)的15行映射到22个真实测试方法，无空映射。APP-01/02/03是规则类别，22是unittest方法数，160是其中一个方法覆盖的独立数据样本，不能将它们相加为独立测试总数。

| 类别 | 实际证据 |
|---|---|
| APP-01 基础流程 | 固定完整菜单输出；新增/编辑/删除/完成/筛选/搜索/稳定排序；独立JSON和TSV全部字段/字节；另启动新CLI重开；空统计、只读视图不改dirty；历史Task别名及内容比较 |
| APP-02 外部数据 | validation-cases.json的160组：根/字段/类型、Bool/Float冒充Int、ID去重/高水位、Unicode长度和全部C0/DEL控制字符；末尾错误不部分提交；坏JSON/重复键/溢出/孤立代理/编码/缺文件；10000项及4MiB边界 |
| APP-02 保存失败 | 真实ZZY session/storage在写入/关闭/替换/权限故障下返回失败，磁盘旧字节、dirty、编辑和绑定保留，临时文件/预算清理；内部非法状态保存先拒绝。权限用宿主注入，不伪称真实Windows ACL测试 |
| APP-03 恢复 | 取消不出现打开提示；保存失败停止加载/退出；重试/换路径/保留；成功加载清历史；撤销/重做与分支、ID耗尽及重启；历史99/100/101及丢最旧提示 |
| APP-03 EOF/取消 | 各输入草稿/保存/导出确认位置EOF不写盘；dirty提醒；真实独立隐藏控制台Ctrl+C发生在dirty后加载大文件期间，退出130且旧文件不变。没有以KeyboardInterrupt注入代替真实信号 |
| CHECK | main.zzy递归check不输入、不输出、不改磁盘；前置文件探针缺文件时check仍通过 |

数量边界使用默认校园策略，9999/10000项实际加载成功，10001项显式业务失败；这些较大子进程期限180秒。单独10000项探针37.406秒，仅记录功能检查，不是性能统计。其他普通请求限时30秒、4MiB解析60秒、历史压力60秒；超时立即失败并由通用ProcessTree回收，未通过提高限额或删慢用例伪造成功。

4MiB读取+JSON解析前/等边界使用合法空文档与空白填充；超过一字节仍E211。深度65触及默认JSON资源限额而终止，不转格式Result；非法但较浅的任意容器由业务字段类别/集合拒绝。不能由这些用例推断所有字段取最大值且历史满100步的组合都能同时容纳。

## P09-01前置检查（保留）

prerequisites.json精确引用23项既有P05独立CLI期望，在校园4MiB配置下重跑，另有2项info/文件相邻边界检查。空集合、重复引用和缺失引用在收集时失败。它们是语言能力前置验证，不替代上述应用用例；独立tests.blackbox默认清单仍为原1588项，不能把复测的23项当新增语言案例。

P09-01联合18项P05集成曾43/43、16.244秒通过；当时直接导入BlackboxCase导致unittest误收集，改为模块引用后完整重跑。P09应用首轮16/16、18.692秒；补充边界及菜单ID耗尽提前拒绝后最终专项22/22、109.335秒。记录各轮实际范围，不把旧报告当新执行。

## 行数与未验证范围

[count_lines.py](count_lines.py)使用真实Lexer统计应用目录中的.zzy，拒绝空收集/不足200行并核对已保存报告。有效行为含非注释Token的物理行，另列排除纯标点行数；不计Python、夹具、文档或测试驱动。[逐文件报告](../../apps/zzy-campus/line-count.json)记录504总行/493有效行/406非纯标点行及哈希；Git强制应用源码LF，便于跨平台复算。

当前宿主Windows11 26200 / CPython3.12.14 / Unicode15；其他OS/Python未运行。Ctrl+C在执行加载时实测，其他每一条宿主阻塞调用的中断时序未逐个测试。没有真实ACL、断电、并发写者合并、路径别名去重或全部默认最大实分配矩阵的证据；TSV不支持导入，不把导出成功当保存成功。GUI/Web/Python业务嵌入不属于本应用。
