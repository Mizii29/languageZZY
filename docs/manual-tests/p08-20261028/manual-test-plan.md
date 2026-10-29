# P08 人工测试方案（概要）

建立：2026-10-28｜核对基线：`test / 330cf17`｜2026-10-29 人工主流程已核验，见[逐项记录](manual-test-review.md)。以下保留重做时的操作步骤，预计 15—25 分钟，Windows、VS Code、PowerShell、CPython 3.12.14。

本轮只补 P08 的真实操作体验；原核心/校园应用/Sketch 记录见[上次指南](../core-sketch-20261027/manual-test-guide.md)。实现及自动报告已核对，详见[P08 证据](../../../tests/p08/README.md)；并发、取消、事务回滚和异常数据边界不重复手工穷举。

## 1. 准备：一个终端按顺序执行

在 VS Code 打开项目，新建 PowerShell 终端。以下变量沿用到结束；新终端不能直接跳到中间。复制的示例保持原目录关系，SQLite 只写本次新目录，避免上次“保存位置与运行位置不一致”的问题。

```powershell
Set-Location -LiteralPath 'D:\大学资料\北邮\课程\程序设计实践\程序设计实践大作业'
$RepoRoot = (Get-Location).Path
$ZzyPython = (Resolve-Path './.venv/Scripts/python.exe').Path
& $ZzyPython -X utf8 -c "import platform,sys,starlette,uvicorn; assert platform.python_implementation()=='CPython' and sys.version_info[:3]==(3,12,14); print(sys.version); print('Web:',starlette.__version__,uvicorn.__version__)"
if ($LASTEXITCODE -ne 0) { throw '先检查 Python 版本与 Web 可选依赖，再继续' }
$Candidate = (git rev-parse --short HEAD).Trim()
$RunName = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $Candidate
$RunRoot = Join-Path $RepoRoot "docs/manual-tests/p08-20261028/runs/$RunName"
New-Item -ItemType Directory -Path $RunRoot -ErrorAction Stop | Out-Null
Start-Transcript -LiteralPath (Join-Path $RunRoot 'terminal.txt')
git rev-parse HEAD | Set-Content -Encoding utf8 (Join-Path $RunRoot 'candidate.txt')
git status --short | Set-Content -Encoding utf8 (Join-Path $RunRoot 'working-tree.txt')
foreach ($Example in @('web', 'sqlite')) {
    $Target = Join-Path $RunRoot "examples/$Example"
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $RepoRoot "examples/$Example/app.zzy"), (Join-Path $RepoRoot "examples/$Example/index.html") -Destination $Target
}
$PreviousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
$env:PYTHONPATH = $RepoRoot
Set-Location -LiteralPath $RunRoot
Write-Host "本轮证据目录：$RunRoot"
```

若仅缺 Web 依赖，回项目根目录，使用有 pip 的 Python 执行 `python -m pip --python .venv/Scripts/python.exe install ".[web]"`，成功后重做准备。端口使用 18765/18766；若提示占用，只改为其他空闲端口并同步浏览器地址，记录实际值。

## 2. 执行清单

每项按表操作并保存一张关键截图；错误提示和成功恢复可合并截图。服务运行时在浏览器操作，终端出现 Uvicorn 启动完成后再访问。完成一组后回终端按 Ctrl+C，等待返回 `PS ...>`，再执行下一块。

先启动默认 Web 模式：

```powershell
& $ZzyPython -X utf8 -m zzy.web examples/web/app.zzy --route GET /api/hello hello --route POST /api/greet greet --page examples/web/index.html --port 18765
```

| 编号 | 操作 | 预期结果 |
|---|---|---|
| W01 / P08-01 | 打开 `http://127.0.0.1:18765/`，点“GET 问候”；姓名填“小明”点“POST 问候” | GET 为成功并有 `language: ZZY`；POST 为 `你好，小明`，中文正常 |
| W02 / P08-01 | 姓名清空点 POST，再填“Ada”重试 | 空姓名显示 HTTP 422 及中文原因；重试为 `你好，Ada`，服务继续可用 |

Ctrl+C 停止后启动共享模式，在相同地址继续：

```powershell
& $ZzyPython -X utf8 -m zzy.web examples/web/app.zzy --route GET /api/hello hello --route POST /api/greet greet --page examples/web/index.html --shared --port 18765
```

| 编号 | 操作 | 预期结果 |
|---|---|---|
| W03 / P08-02 | 刷新页面，重复 GET、中文姓名 POST 和空姓名 POST | 分别成功、成功、422；终端启动命令明确带 `--shared`。此项仅人工冒烟，共享隔离由自动测试证明 |

再次 Ctrl+C 停止，在同一终端运行 Python 嵌入：

```powershell
Set-Location -LiteralPath $RepoRoot
& $ZzyPython -X utf8 -m examples.web.embed
Write-Host "嵌入退出码=$LASTEXITCODE"
Set-Location -LiteralPath $RunRoot
```

| 编号 | 操作 | 预期结果 |
|---|---|---|
| W04 / P08-03 | 查看上面命令的输出 | `{"status": 200, "body": {"message": "你好，Ada"}}`，退出码 0；无需启动 HTTP 服务 |

最后启动 SQLite 页面：

```powershell
& $ZzyPython -X utf8 -m zzy.web examples/sqlite/app.zzy --route GET /api/tasks handle --route POST /api/tasks handle --page examples/sqlite/index.html --shared --port 18766
```

| 编号 | 操作 | 预期结果 |
|---|---|---|
| W05 / P08-04、05 | 打开 `http://127.0.0.1:18766/`；添加“人工任务一”和 `O'Reilly`，点“刷新”，再刷新浏览器 | 初始 `[]`；随后恰有两条任务，ID 为 1、2，标题完整保留，单引号正常显示 |
| W06 / P08-04、05 | 输入框清空点“添加”，再点“刷新” | 显示 `请求失败 422` 及标题长度原因；刷新仍只有原两条，没有空记录 |
| W07 / P08-04、05 | 保留页面，回终端 Ctrl+C；页面点“刷新”；再原样执行上面 SQLite 启动命令，页面点“刷新” | 停服后提示“连接失败，请确认服务已启动”；新进程启动后原两条任务恢复，ID/标题不变 |

W05—W07 连续使用同一个 `$RunRoot`，不要重新执行准备命令。W07 完成后 Ctrl+C 停止，确认无 traceback；再检查文件并结束记录：

```powershell
Test-Path -LiteralPath (Join-Path $RunRoot 'examples/sqlite/tasks.sqlite3')
Set-Location -LiteralPath $RepoRoot
[Environment]::SetEnvironmentVariable('PYTHONPATH', $PreviousPythonPath, 'Process')
Stop-Transcript
```

预期 `Test-Path` 为 `True`。数据库仅用于合成测试，保留在本轮证据目录即可。

## 3. 记录与可跳过范围

本轮操作者改用[原始 DOCX 报告](manual-test-result.docx)保存结果，11 张截图已逐项核对，见[核验记录](manual-test-review.md)。重做时记录真实候选、环境、证据目录及 W01—W07 的实际结论，截图命名如 `W05-sqlite.png`，放入本轮 `$RunRoot`。出现问题保留完整输出，不用“页面能打开”替代重启持久化结果。新目录重做才能恢复初始空库。

W01—W07 是本轮保留项；上次完整校园/Sketch 流程、额外 DPI、物理断网、手工并发压测和模拟断电可以跳过，并记录理由。核心回归、HTTP、回滚/取消、安装已有自动证据，本次不要求为了截图重跑；最终候选有相关代码变化时再按 [最终测试计划](../../development/final-test-plan.md)重新选择回归。新一轮必须记录自己的实际结果，不能沿用本轮结论冒填通过。
