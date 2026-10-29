# P11 最终候选人工验收（待执行）

本轮独立记录，不修改先前人工原件。候选为 `be9eba2` 加 P11-07 的调用/查询备注故障修复；最终运行时哈希和自动验证见 [P11证据](../../../tests/p11/README.md)。真实 Tk 自动测试不代替以下两项人工操作。尚未收到操作者结果。2026-10-30用户明确要求自动验收后先勾选P11-07，人工稍后补做；本目录继续标为未验证，不记录人工通过。

## 准备

在新的 PowerShell 终端中运行下列命令。工作目录用随机后缀创建，不覆盖之前的图形、项目或日志。不要关闭其他服务。

```powershell
$ZzyRoot = 'D:\大学资料\北邮\课程\程序设计实践\程序设计实践大作业'
$ZzyPython = Join-Path $ZzyRoot '.venv\Scripts\python.exe'
$P11Cases = Join-Path $ZzyRoot 'docs\manual-tests\p11-20261030'
$P11Work = Join-Path $ZzyRoot ('dist\p11-manual-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $P11Work | Out-Null
Push-Location $P11Work
& $ZzyPython -X utf8 -m zzy check (Join-Path $P11Cases 'canvas.zzy')
$LASTEXITCODE
```

预期 check 退出 0、无 GUI 窗口、无 manual.svg/manual.zzysketch 文件。下面程序仅由 run 执行。

## M01：真实 Ctrl+C 与后续恢复（必测）

```powershell
& $ZzyPython -X utf8 -m zzy run (Join-Path $P11Cases 'cancel.zzy')
# 看到 READY 后等待约一秒，亲手按一次 Ctrl+C。
$LASTEXITCODE
& $ZzyPython -X utf8 -m zzy run (Join-Path $P11Cases 'recover.zzy')
$LASTEXITCODE
```

预期：循环退出，无 Python traceback，退出码 130；后续程序输出 2，退出 0。记录实际提示、退出码和是否及时返回提示符。自动注入 Cancelled 或脚本发送信号不能填作本项人工通过。

## M02：真实绘图、历史、导出与关闭（必测）

```powershell
& $ZzyPython -X utf8 -m zzy run (Join-Path $P11Cases 'canvas.zzy') --gui
$LASTEXITCODE
Test-Path .\manual.svg
Test-Path .\manual.zzysketch
& $ZzyPython -X utf8 -m zzy run (Join-Path $P11Cases 'reopen.zzy') --gui
$LASTEXITCODE
Pop-Location
```

第一窗口中用自由线工具拖画，再画一个矩形；点击撤销，确认最后一项消失；点击重做，确认恢复。正常关闭窗口后，预期三个成功 Result、退出 0，两个文件存在。用浏览器打开 `$P11Work\manual.svg`，确认图形与最终画面一致；第二个命令会重开保存的项目，确认两项图形及历史仍在，再正常关闭，终端应返回并退出 0，无挂起窗口或 traceback。

把实际结果填写到 [result.md](result.md)，注明时间、操作者、候选提交/哈希与工作目录。失败时保留输出、文件及重现步骤；不因重试成功删除第一次失败。未完成项保持待验证。按用户最新授权，本轮自动门禁通过后可勾选P11-07并交接P12-01；两项人工检查作为明确待补项保留，真实执行后再复核源码身份并填写结果，不能将授权视为测试通过。
