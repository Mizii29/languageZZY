# P00—P02 黑盒与宿主回归

从项目根目录运行 `python -X utf8 -m unittest discover -s tests -v`。只使用标准库 unittest，实际启动 CLI 子进程并检查 stdout、stderr、退出码；宿主层验证资源预留/释放、源码坐标、词法容量和异常边界。

[词法](lex/README.md)、[P01 回归](run/README.md)、[非执行检查](check/README.md) 的 260 例与 [P02](p02/README.md) 的 279 例，共 539 个外部用例，均不依赖 spec。完整语言覆盖待 P06；取消出口与清理由宿主注入验证，真实终端 Ctrl+C 尚未验收。

## 一条命令运行黑盒

```text
python -X utf8 -m tests.blackbox
python -X utf8 -m tests.blackbox tests/check/cases.json
python -X utf8 -m tests.blackbox --report dist/p02-blackbox-report.json
```

报告目录须已存在。此入口是仓库内的 Python 外部运行器，不是未来的 `zzy test`/spec 实现，不包含在发行 wheel 中。默认按清单路径和源码路径排序，每例新建 CLI 子进程；全部通过返回 0，收集错误、期望不符、启动失败、超时、输出超额或报告写入失败返回 1。正常的预期非法 ZZY 程序匹配清单后算通过。

## 清单与报告

四个 `cases.json` 均使用 schema_version 1。每例必须含 id、mode（lex/run/check）、file、cwd、stdin、timeout_seconds、exit_code。cwd 相对项目根目录，file 相对该 cwd；stdout 是精确字符串，lex 成功改用完整 Token 列表。非零退出必须有 diagnostic 的 code/span，可指定 file（包括 null）及 message_contains。拒绝重复 JSON 键、空清单、缺字段、非法模式/类型/限额及跨清单重复 ID（mode 与 id 共同标识用例）。

可用 limits 覆盖解释器策略，用 stdout_limit/stderr_limit 分别覆盖捕获容量；默认每流 1 MiB、当前清单每例 10 秒。UTF-8 输出不做 strip 或截断后比较，额外空格/行会失败。可选 JSON 报告记录版本、数量、每例实际命令、完整期望、观察到的退出码、失败详情、生效 ResourcePolicy 及指纹；命令内的临时 limits 文件运行后删除，其内容保留在 case.limits 中。

`blackbox.py` 统一收集和比对，`process.py` 用临时输入文件传递 stdin、并行有界读取 stdout/stderr，超时或中断终止并等待当前子进程，回收管道、读取线程及临时文件。`test_blackbox_runner.py` 实际验证错误答案、坏/空清单、超时、超额、双管道及启动失败不会通过，并验证操作系统进程退出码。P02 子集不会产生派生进程；进程树/GUI 清理与完整 spec 隔离仍留 P06，不能用当前测试冒充这些能力已验收。
