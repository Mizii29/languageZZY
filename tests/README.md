# ZZY 黑盒、宿主与应用回归

从项目根目录运行 `python -X utf8 -m tests`，可用 `--report dist/p06-all-tests.json` 留存汇总。该一键入口检查收集数/执行数一致、非空、无跳过或 expected failure；底层仍可用 unittest discover 调试，但阶段验收使用带保护的一键入口。只使用标准库 unittest，实际启动 CLI 子进程并检查 stdout、stderr、退出码；宿主层验证资源预留/释放、源码坐标、词法容量和异常边界。

[词法](lex/README.md)、[P01 回归](run/README.md)、[非执行检查](check/README.md) 的 260 例与 [P02](p02/README.md) 的 279 例、[P03](p03/README.md) 的 234 例，加 [P04](p04/README.md) 的 317 例，以及 [P05](p05/README.md) 的 369 例，加上 [P06](p06/README.md) 的 129 例，共 1588 个外部用例，均不依赖 spec；正常变形 spec、指南 spec、Agent 练习及宿主清理测试由一键入口额外执行。P06 已实测 Windows 真实 Ctrl+C 和进程树回收。

## 一条命令运行黑盒

```text
python -X utf8 -m tests.blackbox
python -X utf8 -m tests.blackbox tests/check/cases.json
python -X utf8 -m tests.blackbox --report dist/p06-blackbox-report.json
```

报告目录须已存在。此入口是仓库内的 Python 外部运行器，与已实现的 `zzy test`/spec 相互独立，不包含在发行 wheel 中。默认按清单路径和源码路径排序，每例新建 CLI 子进程；全部通过返回 0，收集错误、期望不符、启动失败、超时、输出超额、零收集/执行数不符/跳过或报告写入失败返回 1。正常的预期非法 ZZY 程序匹配清单后算通过。

## 清单与报告

八个 `cases.json` 均使用 schema_version 1。每例必须含 id、mode（lex/run/check）、file、cwd、stdin、timeout_seconds、exit_code。cwd 相对项目根目录，file 相对该 cwd；stdout 是精确字符串，lex 成功改用完整 Token 列表。非零退出必须有 diagnostic 的 code/span，可指定 file（包括 null）、message_contains 及精确 notes 列表。拒绝重复 JSON 键、空清单、缺字段、非法模式/类型/限额及跨清单重复 ID（mode 与 id 共同标识用例）。

可用 limits 覆盖解释器策略，用 stdout_limit/stderr_limit 分别覆盖捕获容量；默认每流 1 MiB、清单每例显式指定超时（一般 10 秒，P06 部分为 15 秒）。UTF-8 输出不做 strip 或截断后比较，额外空格/行会失败。可选 JSON 报告记录版本、数量、每例实际命令、完整期望、观察到的退出码、失败详情、生效 ResourcePolicy 及指纹；命令内的临时 limits 文件运行后删除，其内容保留在 case.limits 中。

`blackbox.py` 统一收集和比对，`zzy/process.py`（tests/process.py 兼容导入）用临时输入文件传递 stdin、并行有界读取 stdout/stderr，超时或中断终止并等待当前子进程及其后代，回收管道、读取线程及临时文件。`test_blackbox_runner.py` 实际验证错误答案、坏/空清单、超时、超额、双管道及启动失败不会通过，并验证操作系统进程退出码。P04 spec 每例有独立 worker，真实测试覆盖超时后续跑、独立 stdin/临时目录/状态及同批字节快照。语言暂无派生进程 API；P06 用受控宿主子/孙进程验证进程树、管道及目录回收，GUI 仍未实现。P05 的模块/文件库隔离与完整依赖快照测试继续回归。


[P09校园任务管家](p09/README.md)的真实CLI/磁盘测试与4MiB策略前置检查由一键入口自动收集，独立tests.blackbox的1588项语言清单保持不变。应用采用外部期望和实际模块，不用spec成功替代菜单/保存/重启验收。
