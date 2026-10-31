# P11 优化后人工测试方案

更新：2026-10-31｜候选：`test / 4b4be85eaf2addd01aafb49de43a4e6a8db581d2`｜人工状态：M01/M02 已通过｜复测预计 10—15 分钟。

本轮 P11 是解释器优化；原交付阶段已改为 P12。[现存自动证据及复核](review.md)支持 P11 的实现与自动验收结论。2026-10-31 已逐张核对本轮 8 张截图、日志、SVG 和项目文件，M01/M02 人工待补项已关闭，撤销/重做按操作人确认记录；详见[结果摘要](result.md)及[原始 DOC](result.doc)。以下命令保留用于复测，旧 P08/Sketch 结果独立保存。

## 1. 准备并确认测的是当前源码

在 VS Code 打开项目，新建一个 PowerShell 终端，按顺序执行。后续始终使用这个终端和同一 `$P11Work`。准备命令显式设置 `PYTHONPATH`，否则离开仓库后可能加载 `.venv` 中的旧安装包。

```powershell
$ZzyRoot = 'D:\大学资料\北邮\课程\程序设计实践\程序设计实践大作业'
Set-Location -LiteralPath $ZzyRoot
$ZzyPython = (Resolve-Path './.venv/Scripts/python.exe').Path
$P11Cases = Join-Path $ZzyRoot 'docs/manual-tests/p11-20261030'
$P11Candidate = (git rev-parse --short HEAD).Trim()
$P11RunName = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $P11Candidate + '-' + [guid]::NewGuid().ToString('N').Substring(0,6)
$P11Work = Join-Path $P11Cases "runs/$P11RunName"
New-Item -ItemType Directory -Path $P11Work -ErrorAction Stop | Out-Null
git rev-parse HEAD | Set-Content -Encoding UTF8 (Join-Path $P11Work 'candidate.txt')
git status --short | Set-Content -Encoding UTF8 (Join-Path $P11Work 'working-tree.txt')
$P11PreviousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
$env:PYTHONPATH = $ZzyRoot
Push-Location -LiteralPath $P11Work
Start-Transcript -LiteralPath (Join-Path $P11Work 'terminal.txt')
$P11Verify = @'
from pathlib import Path
import hashlib,json,platform,sys,zzy
root=Path(sys.argv[1]).resolve()
assert platform.python_implementation()=='CPython' and sys.version_info[:3]==(3,12,14), sys.version
assert Path(zzy.__file__).resolve()==root/'zzy/__init__.py', zzy.__file__
source=json.loads((root/'tests/p11/07-source.json').read_text(encoding='utf-8'))['source_sha256_lf']
runtime={p:h for p,h in source.items() if p.startswith('zzy/')}
bad=[p for p,h in runtime.items() if hashlib.sha256((root/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=h]
assert len(runtime)==44 and not bad, bad
print(sys.version)
print(platform.platform())
print('SOURCE_OK',len(runtime),zzy.__file__)
'@
& $ZzyPython -X utf8 -c $P11Verify $ZzyRoot 2>&1 | Tee-Object -FilePath (Join-Path $P11Work 'source-check.txt')
if ($LASTEXITCODE -ne 0) { throw '版本或源码身份不符，保留输出，停止本轮测试' }
& $ZzyPython -X utf8 -m zzy check (Join-Path $P11Cases 'canvas.zzy')
Write-Host "check退出码=$LASTEXITCODE"
Test-Path -LiteralPath (Join-Path $P11Work 'manual.svg')
Test-Path -LiteralPath (Join-Path $P11Work 'manual.zzysketch')
Write-Host "本轮证据目录：$P11Work"
```

预期：`SOURCE_OK 44` 后是**项目根目录的 `zzy\__init__.py`**；check 退出 0，无绘图窗口，两个 `Test-Path` 均为 `False`。若来源含 `site-packages` 或源码哈希失败，先保留错误，不继续填人工通过。

## 2. M01 真实 Ctrl+C 与恢复（必测）

先只运行这一条：

```powershell
& $ZzyPython -X utf8 -m zzy run (Join-Path $P11Cases 'cancel.zzy')
```

看到 `READY` 后等约一秒，亲手按一次 Ctrl+C。等待返回 `PS ...>`，立即执行下面一块；中间不要运行其他外部命令，以免覆盖退出码。

```powershell
$P11CancelExit = $LASTEXITCODE
Write-Host "Ctrl+C退出码=$P11CancelExit"
& $ZzyPython -X utf8 -m zzy run (Join-Path $P11Cases 'recover.zzy')
Write-Host "恢复退出码=$LASTEXITCODE"
```

预期：及时停止循环，无 Python traceback，Ctrl+C 退出码 **130**；随后输出 **2**，恢复退出码 **0**。截图保留 READY、实际退出码及恢复输出，可分两张。脚本发信号或自动注入取消不能代替亲手操作。若结果不同，如实填失败，不手工改成 130。

## 3. M02 绘图、历史、导出和重开（必测）

```powershell
& $ZzyPython -X utf8 -m zzy run (Join-Path $P11Cases 'canvas.zzy') --gui
Write-Host "首窗退出码=$LASTEXITCODE"
Test-Path -LiteralPath (Join-Path $P11Work 'manual.svg')
Test-Path -LiteralPath (Join-Path $P11Work 'manual.zzysketch')
Write-Host (Join-Path $P11Work 'manual.svg')
```

窗口打开后先操作，关闭后终端才会继续输出：

1. 工具栏左侧下拉框选 **`free`**（自由线），旁边画笔名填 **`主画笔`**，在画布中拖出一条线，松开鼠标。
2. 下拉框选 **`rectangle`**（矩形），在另一处拖出矩形；画面应同时有线和矩形。
3. 点“撤销”：矩形消失、线保留；点“重做”：矩形恢复。留一张最终画面截图，撤销/重做过程可在结果中简短注明。
4. 点击窗口右上角关闭。预期终端打印 **三个成功 Result（含 `(^_^)`）**，首窗退出码 **0**，两个文件检查均为 **True**。
5. 浏览器按 Ctrl+O，打开终端刚输出路径的 `manual.svg`；应有同一条线和矩形，不要求工具栏或窗口尺寸相同。

确认导出图后，在原终端执行：

```powershell
& $ZzyPython -X utf8 -m zzy run (Join-Path $P11Cases 'reopen.zzy') --gui
Write-Host "重开退出码=$LASTEXITCODE"
```

第二个进程应恢复两项图形；再点一次撤销/重做，确认历史可用。正常关闭，预期一个成功 Result、重开退出码 **0**，无残留窗口、挂起或 traceback。保留重开窗口、导出图和终端退出记录，不要求每个按钮额外截一张。

## 4. 结束与记录

```powershell
Pop-Location
[Environment]::SetEnvironmentVariable('PYTHONPATH', $P11PreviousPythonPath, 'Process')
Stop-Transcript
```

复测时另存实际日期、候选、工作目录及 M01/M02 结果，更新 [result.md](result.md) 的证据索引；本次 [result.doc](result.doc) 与对应运行目录保留。截图存新的 `$P11Work`，如 `M01-cancel.png`、`M02-reopen.png`。PowerShell transcript 可能漏掉原生程序输出，退出码和关键画面须有截图；失败重试保留第一次记录。

本轮无需重跑旧校园/P08全流程、全量回归、并发压力或长性能测量。额外 DPI/物理断网可跳过。另有 [P10 合约网页的六项人工清单](../../../examples/contracts/manual-acceptance.md)仍待执行，应在 P12 最终验收前单独安排；它不作为本次两项优化后补测的完成记录。P11-07 原先预勾选的历史保留，当前 M01/M02 已有真实人工结果。
