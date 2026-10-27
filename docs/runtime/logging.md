# ZZY 输出与日志配置

更新：2026-10-22｜适用：当前 CLI 诊断与 CI 回归日志｜不改变语言语法或程序输出协议

## 1. 按项目特点选择的方式

ZZY 是本机 CLI/桌面解释器。正常程序结果写 stdout，诊断写 stderr；二者已经使用 UTF-8，默认各有 1 MiB 执行预算，终止诊断另有最多 4096 字节保留区，详见 [资源配置](resources.md)。这类输出供程序、用户和测试读取，保持现有格式。

本次配置管理的是 `scripts.ci regression` 持久保存的 `tests.log`：**按大小轮转、旧文件 gzip 压缩、按份数自动淘汰**。每次 CI attempt 有独立目录，起止时间和版本由 report.json 记录；错误输出突增时，大小上限比每日切一次更适合当前项目。实现使用 Python 标准库 `logging.handlers.RotatingFileHandler`，压缩使用 `gzip`。

构建/安装子命令的捕获沿用已有每流8MiB限额，超出即失败；JSON汇总报告用于保留结果结构，不作为普通文本日志截断或轮转。人工终端记录和最终验收证据按各自指南归档。

Windows 本机和 GitHub 托管 runner 使用同一入口；当前没有常驻 Linux 日志服务，所以不配置 logrotate、journald 或 SIGHUP。日志由 CI 父进程写入和重新打开，子进程只向管道输出，轮转不会要求解释器配合信号。

## 2. 真正生效的配置文件

[logging.json](logging.json) 会被 `scripts.ci static` 校验，并由 `scripts.ci regression` 在启动回归前自动读取；路径相对仓库根目录确定，与调用者 cwd 无关。不是仅供展示的样例，不需要增加命令行参数。

```json
{
  "schema_version": 1,
  "max_bytes": 1048576,
  "backup_count": 4
}
```

| 字段 | 当前值 | 含义及允许范围 |
|---|---|---|
| schema_version | 1 | 配置版本，必须为整数 1 |
| max_bytes | 1048576 | 单文件最多 1 MiB，按 UTF-8 字节计；可设整数 4096—67108864（4 KiB—64 MiB） |
| backup_count | 4 | 最多保留 4 份轮转备份；可设整数 1—10 |

修改配置后下一次运行生效，执行期间保持候选文件不变。缺字段、未知字段、重复键、布尔/浮点数伪装整数、超范围或超过 64 KiB 的配置都会失败；不允许用 0 悄悄关闭容量控制。

如果需要更大的排查窗口，可把 max_bytes 改为 8388608（8 MiB）；代价是每次运行最多保留约 40 MiB 原文。默认 1 MiB/4 份适用于当前一键回归的输出规模，异常失败风暴也有上限。

## 3. 文件命名、轮转与清理

工作流默认产生：

```text
dist/ci/regression/
  report.json       本次 CI 报告、时间、版本和日志配置
  all-tests.json    完整测试计数与结果
  tests.log         当前写入，最多 1 MiB
  tests.log.1.gz    最近一次轮转
  tests.log.2.gz
  tests.log.3.gz
  tests.log.4.gz    最旧保留备份；下一次轮转自动淘汰
```

每个 job 最多保留 **1 个活动文件和 4 个压缩备份**，原文合计最多 5 MiB；压缩文件实际大小取决于内容，轮转过程中还会短暂使用一个压缩临时文件。旧日志达到份数上限后自动删除，不会因同一轮测试持续输出而无限累积。普通成功回归通常只有数 KiB，不会触发轮转。

输出通过有界小块流式读取，不把整轮日志放进内存；UTF-8 多字节字符在文件边界保持完整，文件使用 UTF-8，非法字节以 `\xff` 等转义保留可见线索。写入端不增加平台换行转换，子进程产生的换行原样保留。原始输出不额外加时间戳/级别前缀、不补换行；一条很长的文本行或 JSON 可能跨文件，分析时按旧到新拼接。

`report.json` 的 `log` 部分记录配置、文件名、`rotations`（轮转次数）及 `older_logs_discarded`（是否已淘汰更早片段）。后者为 true 时只能把保留内容称为“最近日志”，不能声称保留了全程日志。**日志淘汰不会把失败测试改成成功**：退出码和 all-tests.json 的完整计数仍是门禁依据。

压缩先写临时文件，完成后发布备份；写盘、压缩或读取管道失败均让 CI 失败并清理本次进程树，不会静默丢日志后显示绿色。超时/取消也清理进程并保留已写内容。磁盘完全不可写时，report.json 也可能无法生成，此时保留的 CI 控制台失败与缺报告本身就是失败依据。

GitHub Actions 已配置 artifact 保留 **14 天**，包含活动日志、gzip 备份和 JSON 报告；本机实现已验证，云端上传/到期回收仍需首次实际 Actions 运行确认。本地不同 attempt 的证据目录不自动整目录删除；最终报告、人工 Transcript 和业务存档按 [最终测试计划](../development/final-test-plan.md) 归档，配置不会清理已有 `docs/manual-tests/` 资料。份数上限是每轮日志的上限，不是整个 dist 的总空间上限。

## 4. 语言与结构字段保持稳定

当前采用“**固定错误码 + 中文解释 + 结构化字段**”。本项目不根据 locale 自动改成另一套中英提示；程序/告警/Agent 应依赖错误码和字段，中文说明用于阅读。系统和外部构建工具附带的错误细节可能随 OS/版本而变，不把这些细节作为稳定匹配条件。

- 正常输出仍走 stdout，诊断仍走 stderr；轮转仅影响 CI 保存的副本。
- `--diagnostic-format json` 仍输出 JSON Lines，字段固定为 `schema_version/kind/code/file/span/message/notes`；错误码如 E302、E211、E401 不翻译。
- 定位/错误码是稳定契约；消息可按正式诊断契约改进，脚本避免依赖整段中文措辞。错误说明与独立示例见 [诊断文档](../language/diagnostics.md)，完整错误码见 [语法契约](../language/syntax.md)。
- CI 的 `started_at/finished_at` 使用带 UTC 偏移的 ISO 时间，`context` 包含 checkout/head/base SHA、run ID、attempt 和源码指纹；字段名不随语言改变。按本轮时间/身份定位目录，再读取日志。

例如从仓库根目录执行：

```powershell
$ZzyPython = (Resolve-Path './.venv/Scripts/python.exe').Path
& $ZzyPython -X utf8 -m zzy run tests/p06/inputs/diagnostic-name.zzy --diagnostic-format json
$LASTEXITCODE
```

预期退出 2，stderr 一行 JSON，code 为 E302、定位非空，无额外日志标题或 Python traceback。stdout 不会多出“日志初始化成功”等信息。

## 5. 本机运行和查看

在仓库根目录的 PowerShell 执行。证据目录必须全新；重跑更换日期/attempt，不覆盖旧报告：

```powershell
$ZzyPython = (Resolve-Path './.venv/Scripts/python.exe').Path
$LogEvidence = 'dist/logging-check/2026-10-22-attempt01'
& $ZzyPython -X utf8 -m scripts.ci regression --output "$LogEvidence/regression"
$LASTEXITCODE
Get-Content -LiteralPath "$LogEvidence/regression/tests.log" -Tail 30 -Encoding utf8
Get-Content -LiteralPath "$LogEvidence/regression/report.json" -Raw -Encoding utf8 |
    ConvertFrom-Json | Select-Object -ExpandProperty log
```

预期成功时退出 0、passed=true；当前全量收集 2002 项，计数完整且零失败/错误/跳过；普通输出量下 rotations=0、older_logs_discarded=false，配置显示 1048576/4。回归需要较长时间，实际结果以新报告为准。

运行中可以在 VS Code 另一终端用 `Get-Content -LiteralPath "$LogEvidence/regression/tests.log" -Tail 30 -Wait -Encoding utf8` 查看；新终端要先设置相同的 `$LogEvidence`。发生轮转后重新打开当前文件，已有读取句柄可能仍指向旧文件。

若已经轮转，完成后按 **.4.gz → .3.gz → .2.gz → .1.gz → tests.log** 顺序读取实际存在的文件。下面命令自动排序，解压到 stdout，不修改证据：

```powershell
@'
from pathlib import Path
import gzip, shutil, sys
folder = Path(sys.argv[1])
archives = sorted(folder.glob("tests.log.*.gz"),
                  key=lambda p: int(p.name.split(".")[-2]), reverse=True)
for path in archives:
    with gzip.open(path, "rb") as stream:
        shutil.copyfileobj(stream, sys.stdout.buffer)
with (folder / "tests.log").open("rb") as stream:
    shutil.copyfileobj(stream, sys.stdout.buffer)
'@ | & $ZzyPython -X utf8 - "$LogEvidence/regression"
```

只验证日志机制可以快速执行 `& $ZzyPython -X utf8 -m unittest tests.test_ci_logging -v`。其10项用例使用4 KiB小限额与临时目录，覆盖UTF-8/大小边界、备份淘汰、非法字节、配置拒绝、失败退出、超时、后代进程占管道、写盘及压缩故障；不向真实日志或用户数据写入故障。

实现入口：[CI 日志工具](../../scripts/ci_logging.py)、[CI 主入口](../../scripts/ci.py)、[工作流与本机完整复现](../development/ci-design.md)。正式性能测试仍独占机器执行，不从本次回归时间推导性能结论。
