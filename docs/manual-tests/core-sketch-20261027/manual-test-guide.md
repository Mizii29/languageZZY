# ZZY 本机 VS Code 人工测试指南

归档于 2026-10-28：本页保留上次操作与结论；P08 新增人工测试见[统一索引](../README.md)。

更新：2026-10-27｜环境：Windows、VS Code、PowerShell、CPython 3.12.14｜本指南是操作手册，不是人工通过记录

目标是让操作者在本机从头验证语言、终端交互、校园任务管家、Sketch、安装与现场演示。总体阶段和放行条件见 [最终测试计划](../../development/final-test-plan.md)，CI 的实际入口见 [CI设计](../../development/ci-design.md)。以下 M01—M18 与总体计划的人工编号对应。

本版精简重复操作：不再要求单独补 spec 汇总截图、空分类筛选、锁层故意报错、无窗口 show/PNG 负例和额外 DPI 组合；相关语义由自动回归核验。M16 保留编号用于对应总体计划，不再设置独立人工步骤；已经完成的两项负例截图仍在结果文档保留。删掉重复人工步骤不表示自动回归可以省略，也不把未测环境算成通过。

### 本轮结果核对

2026-10-27 已逐张核对 [人工测试结果](manual-test-result.doc) 的 40 张原始截图，并核对后补的第41张安装截图、本轮存档、导出文件及两份安装报告。候选为 `b598043`、工作区有未提交修改；证据根目录为 `dist/manual-verification/20261027-133652-b598043/`。本页末尾的表格与结果文档统一记录本轮状态，不能再把所有行当作“未执行”模板，也不能据此宣称最终全量验收通过。

- M01—M10、M15 的已展示结果符合预期；M11—M13 保留截图及操作者的成功备注，结论限定在已记录的基础绘图、样式/图层/网格、保存重开主流程，不扩写为每个按钮都已逐项留证。
- M10 后面原来误标为 M11 的一组 EOF 截图，归为 **M10 续**。真正的 M11 从“人工绘图验收”窗口开始。
- 本轮 M07 的独立轮次使用过“阅读修正”“阅读修订”“阅读修改”等测试标题；当前有效 `tasks.json` 的 ID 2 是 **阅读修改**，ID 顺序为 **1、2、4**，`next_id=7`。不要为匹配示例文字而改写已验证存档。重做整套测试时才使用新目录和本页的初始基准。
- M14 已记录 CLICK、键名、TICK、CLOSED、退出 0 及再次开关窗；没有人工 LONG 记录。长回调精确中断转由 GUI 自动用例负责，本轮不再要求补 LONG 截图。额外 DPI 组合、逐按钮截图与 M18 独立排练可跳过，均不记作已执行。
- M16 的无窗口 show、不可用 PNG 已补测正确，退出 0、PNG 文件不存在是预期能力失败；坏项目负例仍由自动回归覆盖。
- **M17 已补测并核验通过**：图41 对应本轮 `offline-copy/tests/e4/results/installed.json`，顶层及 `probe.passed` 均为 `true`，39 个源码与当前项目、副本和已安装包一致，wheel 与六个产物哈希相符。真实 GUI 渲染 8 个对象、视口为 704×504，记录 Tk 8.6.12；关闭后保存、新进程加载/撤销/函数复用均通过。保留图40的早先 headless 结果，不用它代替图41及新报告。本轮精简后的人工清单没有继续强制补测项；物理断网、额外 DPI 等仍不冒填通过。

上述“自动覆盖”说明分工，不表示本次文档核对重新运行过全量或 GUI 自动套件；仍按第19节归档同一候选的实际报告。

**命令与输入的区别**：标为 PowerShell 的代码块只能在终端出现 `PS ...>` 后执行；菜单表里的 `→` 表示每一项输入后按 Enter，不能把箭头整行粘贴给程序。Tk 窗口打开时按正文操作窗口，关窗、返回 PowerShell 后再运行下一块命令。

## 1. 在 VS Code 打开项目并准备终端

1. 在 VS Code 选择“文件 → 打开文件夹”，打开 `D:\大学资料\北邮\课程\程序设计实践\程序设计实践大作业`。也可在 PowerShell 运行 `code 'D:\大学资料\北邮\课程\程序设计实践\程序设计实践大作业'`。
2. 选择“终端 → 新建终端”，终端配置选择 PowerShell。推荐 PowerShell 7；以下测试使用显式解释器路径，不依赖激活 venv 或 VS Code 的运行按钮。
3. 如果安装了 Python 扩展，可在命令面板执行 `Python: Select Interpreter`，选择项目 `.venv\Scripts\python.exe`。这有助于查看 Python 工具代码，实际测试仍以本页命令为准。`.zzy` 文件可用纯文本模式编辑，保存为 UTF-8，不要当 Python 文件用 F5 执行。
4. 在该终端粘贴下列准备命令。后文沿用这一个终端的变量；新开终端需重新准备。测试目录每次新建，不使用真实任务存档。

```powershell
Set-Location -LiteralPath 'D:\大学资料\北邮\课程\程序设计实践\程序设计实践大作业'
$RepoRoot = (Get-Location).Path
$ZzyPython = (Resolve-Path './.venv/Scripts/python.exe').Path
& $ZzyPython -X utf8 -c "import platform,sys; print(sys.executable); print(sys.version); assert platform.python_implementation()=='CPython'; assert sys.version_info[:3]==(3,12,14)"
if ($LASTEXITCODE -ne 0) { throw '必须使用 CPython 3.12.14' }
git status --short
$Candidate = (git rev-parse --short HEAD).Trim()
$RunName = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $Candidate
$Evidence = Join-Path $RepoRoot "dist/manual-verification/$RunName"
$Work = Join-Path $Evidence '中文 空格 工作目录'
New-Item -ItemType Directory -Path $Work -ErrorAction Stop | Out-Null
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = $Utf8NoBom
$OriginalPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $RepoRoot
Start-Transcript -Path (Join-Path $Evidence 'terminal.txt')
& $ZzyPython -X utf8 -m zzy info
```

**预期**：版本断言通过；`info` 输出一个 JSON 对象，`zzy_version=0.6.0a1`，Python 为 3.12.14，并包含平台、Unicode、资源策略和指纹。默认策略为 `default-v1`。Git 的未提交修改如实记录，不需要为测试而丢弃它们。

如果 `.venv` 不存在，先用本机已经安装的 **3.12.14** 的绝对路径运行 `& '实际的Python路径\python.exe' -m venv .venv`；不要直接用不清楚版本的 `python` 创建环境。也可先按 CI 文档取得固定运行时，再用它创建 venv。测试源码只需标准库，不要求安装 pytest 或语言插件。

定义两个仅在当前终端使用的小函数，然后进入独立工作目录：

```powershell
function Invoke-Zzy {
    & $ZzyPython -X utf8 -m zzy @args
    $script:ZzyExitCode = $LASTEXITCODE
    Write-Host "[ZZY退出码=$ZzyExitCode]"
}
function Save-ManualSource([string]$Name, [string]$Text) {
    [System.IO.File]::WriteAllText((Join-Path $Work $Name), $Text, $Utf8NoBom)
}
Set-Location -LiteralPath $Work
```

`PYTHONPATH` 只帮助当前终端在这个工作目录找到本仓库源码；安装验证会另用 `-I` 并清除它。每条命令的 `[ZZY退出码=...]` 是上述辅助函数打印的提示，不属于 ZZY 程序的 stdout。

### 从已经完成的 2026-10-27 记录继续

如果原终端仍在，且 `$Work`、`$ZzyPython` 等变量还在，直接继续后文；**不要重新创建工作目录**。只有关闭原终端、需要在新 PowerShell 终端接着测试时，才运行本块。它沿用结果文档里的存档；以后复测要将 `$RunName` 改为自己实际的目录名。

```powershell
Set-Location -LiteralPath 'D:\大学资料\北邮\课程\程序设计实践\程序设计实践大作业'
$RepoRoot = (Get-Location).Path
$ZzyPython = (Resolve-Path './.venv/Scripts/python.exe').Path
$RunName = '20261027-133652-b598043'
$Evidence = Join-Path $RepoRoot "dist/manual-verification/$RunName"
$Work = Join-Path $Evidence '中文 空格 工作目录'
if (-not (Test-Path -LiteralPath (Join-Path $Work 'tasks.json'))) { throw '没有找到本次 tasks.json，请核对 RunName' }
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = $Utf8NoBom
$OriginalPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = $RepoRoot
& $ZzyPython -X utf8 -c "import platform,sys; assert platform.python_implementation()=='CPython'; assert sys.version_info[:3]==(3,12,14); print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw '必须使用 CPython 3.12.14' }
function Invoke-Zzy {
    & $ZzyPython -X utf8 -m zzy @args
    $script:ZzyExitCode = $LASTEXITCODE
    Write-Host "[ZZY退出码=$ZzyExitCode]"
}
function Save-ManualSource([string]$Name, [string]$Text) {
    [System.IO.File]::WriteAllText((Join-Path $Work $Name), $Text, $Utf8NoBom)
}
$CampusMain = Join-Path $RepoRoot 'apps/zzy-campus/main.zzy'
$CampusLimits = Join-Path $RepoRoot 'apps/zzy-campus/limits.json'
Start-Transcript -Path (Join-Path $Evidence ('terminal-resume-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt'))
Set-Location -LiteralPath $Work
```

## 2. M01：基本语言示例

依次运行：

```powershell
Invoke-Zzy run (Join-Path $RepoRoot 'examples/hello.zzy')
Invoke-Zzy run (Join-Path $RepoRoot 'examples/functions.zzy')
Invoke-Zzy run (Join-Path $RepoRoot 'examples/features.zzy')
```

预期三条命令均退出 0；hello 输出 `5`；functions 依次输出：

```text
720
[1, 2, 11]
[0, 1, 2]
```

features 应显示状态机进入 `doing`，两次相同的精确速度值、查询结果 `[6, 4, 2]`，以及非法状态迁移的失败 Result；本例末尾故意打印失败 Result，进程仍正常退出。不要把失败 Result 和解释器崩溃混为一谈。

spec 汇总属于自动回归内容，不要求另补人工截图。

## 3. M02：错误诊断及 check/run 的区别

创建三个独立错误文件；不要把它们放进正常 spec：

```powershell
Save-ManualSource '错误 名称.zzy' 'io.print(total);'
Save-ManualSource '语法错误.zzy' '(zno) x := ;'
Save-ManualSource '类型错误.zzy' 'io.print(1 + (true));'
Save-ManualSource '量纲错误.zzy' 'io.print(2::s + 1::m);'
Invoke-Zzy run '错误 名称.zzy'
Invoke-Zzy run '错误 名称.zzy' --diagnostic-format json
Invoke-Zzy check '语法错误.zzy' --diagnostic-format json
Invoke-Zzy check '类型错误.zzy'
Invoke-Zzy run '类型错误.zzy' --diagnostic-format json
Invoke-Zzy run '量纲错误.zzy' --diagnostic-format json
```

| 命令 | 预期 |
|---|---|
| 未声明名字的文本诊断 | 退出 2；stderr 含 `E302`、文件名及第 1 行第 10 列；没有 Python traceback |
| 同一错误的 JSON 诊断 | 退出 2；`kind=error`、`code=E302`、`file=错误 名称.zzy`、span 从 `(1,10)` 到 `(1,15)`；完整 JSON 一行 |
| check 语法错误文件 | 退出 2；`E103`，span 从 `(1,12)` 到 `(1,13)`，无 traceback |
| check 类型错误文件 | 退出 0；不计算 `1 + true`，无输出 |
| run 类型错误文件 | 退出 1；`E201`，span 从 `(1,12)` 到 `(1,13)` |
| run 量纲错误文件 | 退出 1；`E213`，span 从 `(1,15)` 到 `(1,16)` |

VS Code 可能把原生 stderr 显示为红色；颜色不是判定标准。记录错误码、退出码和行列，不把预期错误记成测试失败。

## 4. M03：check 不执行用户程序，headless 会执行

```powershell
Save-ManualSource '检查副作用.zzy' @'
(zno) value := io.input("请输入> ");
io.print(value);
io.print(io.write_text("check-effect.txt", "done"));
(zno) c := sketch.canvas(200, 100, "headless");
io.print(sketch.save_svg(c, "check.svg"));
'@
Invoke-Zzy check '检查副作用.zzy'
Test-Path -LiteralPath 'check-effect.txt'
Test-Path -LiteralPath 'check.svg'
```

**预期**：check 退出 0，不出现输入提示、不弹窗；两个 `Test-Path` 都为 `False`。

然后在同一工作目录运行：

```powershell
Invoke-Zzy run '检查副作用.zzy'
```

看到 `请输入>` 后，**手动输入 `测试` 并按 Enter**。等程序退出、重新出现 PowerShell 提示符后，再执行：

```powershell
Get-Content -LiteralPath 'check-effect.txt' -Encoding utf8
Test-Path -LiteralPath 'check.svg'
Get-Content -LiteralPath 'check.svg' -Encoding utf8 -TotalCount 1
```

**预期**：显示输入内容和两个 `(^_^)(null)`，退出 0，不弹 Tk 窗口；后续命令分别显示 `done`、`True` 和 SVG 文本。这说明 headless 正常执行 I/O，不能把它误解为只检查。若要重新验证前半段 check，换全新测试目录，避免把 run 已生成的文件误当成 check 的副作用。

## 5. M04：在 VS Code 终端按真实 Ctrl+C

```powershell
Save-ManualSource '取消循环.zzy' 'io.print("READY"); (while) (true) {}'
& $ZzyPython -X utf8 -m zzy run '取消循环.zzy' --diagnostic-format json
```

看到 `READY` 后，先确保终端有焦点且没有选中文字，再按一次 Ctrl+C。不要按终端垃圾桶按钮，也不要把关闭终端算作取消成功。返回 PowerShell 提示符后立即输入：

```powershell
$LASTEXITCODE
```

**预期**：退出码 130；stderr 有 `kind=cancelled`、`code=null` 的 JSON，无 traceback；终端仍可继续执行命令。若选中了终端文字，Ctrl+C 可能只复制文本，应清除选择后重试。这个场景直接调用 Python，避免 Ctrl+C 同时中止辅助函数而留下旧的 `$ZzyExitCode`。

校园应用的取消另在 M10 测试。仅凭自动运行器的 timeout 不能算真实 Ctrl+C 通过。

## 6. M05：校园任务管家主流程

先检查并启动真实入口，始终带应用限额：

```powershell
$CampusMain = Join-Path $RepoRoot 'apps/zzy-campus/main.zzy'
$CampusLimits = Join-Path $RepoRoot 'apps/zzy-campus/limits.json'
Invoke-Zzy check $CampusMain --limits $CampusLimits
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

check 应退出 0、无输出且不询问菜单。run 显示 `ZZY 校园任务管家 v1` 和 `1新建 2打开 0退出>`。以下箭头表示“输入左边内容，按 Enter，再输入下一项”；**不要把整行箭头文本粘贴给程序**。

| 步骤 | 依次输入 | 预期 |
|---|---|---|
| 新建 | `1` | `已新建`；任务数 0、next_id 1、未保存 true |
| 新增 A | `2 → 作业 → 课程 → 3 → 1` | `已更新`；任务数 1、next_id 2 |
| 新增 B | `2 → 读书 → 生活 → 1 → 1` | 任务数 2、next_id 3 |
| 新增 C | `2 → 实验 → 课程 → 3 → 1` | 任务数 3、next_id 4 |
| 编辑 B | `3 → 2 → 阅读 → 学习 → 2 → 1` | ID 2 的标题/分类/优先级变更，任务数不变 |
| 完成 A | `5 → 1 → 1` | ID 1 的 done 为 true |
| 删除 C | `4 → 3 → 1` | ID 3 删除，next_id 仍为 4 |
| 再新增 | `2 → 新作业 → 课程 → 3 → 1` | 新任务使用 ID 4，next_id 5 |
| 列表 | `1` | ID 按原存储顺序为 1、2、4 |
| 统计 | `8` | total 3、done 1、pending 2、priority `[0,1,2]`、课程 2/学习 1 |

列表的有效内容应为：

```text
id	title	category	priority	done
1	作业	课程	3	true
2	阅读	学习	2	false
4	新作业	课程	3	false
共3项
```

上面 `\t` 表示实际 Tab 列分隔。此时保持应用运行，继续 M06、M07；未保存应一直为 true。

## 7. M06：筛选、稳定排序和 TSV

在当前校园主菜单继续：

| 操作 | 依次输入 | 预期 |
|---|---|---|
| 组合筛选 | `6 → 课程 → 3 → 0 → 作业` | 分类课程、优先级高、全部状态、标题含作业 |
| 排序 | `7 → 2` | 按优先级降序 |
| 列表 | `1` | 只剩 ID 1、4，两个相同优先级保持原顺序 |
| 导出 | `9 → report.tsv → 1` | `导出成功`，不把 TSV 当作任务存档 |
| 清筛选 | `6 → 空行 → 0 → 0 → 空行` | 分类和标题处直接回车，不输入“空行”二字 |
| 恢复原序 | `7 → 0`，再 `1` | 三条任务仍为 1、2、4；原数据不因视图操作改变 |

筛选、排序、导出都不额外改变 dirty。空筛选结果的边界由自动回归覆盖，不再要求另补人工截图。

导出文件在 `$Work\report.tsv`，预期只包含表头与 ID 1、4 两行，done 分别为 true/false；编码 UTF-8、行尾 LF。完成 M07 退出程序后可用 VS Code 打开该文件核对，不要在原生菜单运行时把 PowerShell 命令输进去。

## 8. M07：保存、重启和未保存提示

继续当前会话：输入 `10 → tasks.json → 1`。

**预期**：出现 `保存成功`；任务数 3、next_id 5、未保存 false。输入 `0`，应直接 `再见` 并退出 0。此时再在 PowerShell 检查：

```powershell
$Saved = Get-Content -LiteralPath 'tasks.json' -Raw -Encoding utf8 | ConvertFrom-Json
$Saved | ConvertTo-Json -Depth 8
Get-Content -LiteralPath 'report.tsv' -Encoding utf8
```

任务 JSON 顶层恰有 `schema_version`、`next_id`、`tasks`；版本 1、next_id 5；三条记录为 M05 的最终值。不要求 JSON 具有缩进。

在 PowerShell 重新启动：

```powershell
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

程序内输入 `2 → tasks.json → 1`。**预期**：`打开成功`，字段/顺序不变、未保存 false。

**文件名注意**：保存和打开都输入 `tasks.json`，含末尾的 `s`。如果误输 `task.json`，报 `[Errno 2] No such file or directory` 是路径不存在；在 `1重试 2其他路径 0保留当前>` 处输入 `2 → tasks.json` 改路径，随后输入 `1` 查看列表。输入 `1重试` 只会重试原来的错误路径。

在这个已打开的会话里输入 `3 → 2 → 阅读修订 → 学习 → 2 → 1`，然后：

1. 输入 `0 → 0 → 1`：取消退出，再看列表。应仍在程序内，ID 2 为“阅读修订”、未保存 true。
2. 输入 `0 → 2`：放弃修改后退出。

回到 PowerShell 再运行同一启动命令：

```powershell
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

程序内依次输入 `2 → tasks.json → 1`，ID 2 应仍为“阅读”、未保存 false；再输入 `3 → 2 → 阅读修订 → 学习 → 2 → 1 → 0 → 1 → 1`。最后三个输入分别是退出、先保存、确认写入；应保存成功并退出 0。

回到 PowerShell 再启动一次：

```powershell
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

输入 `2 → tasks.json → 1`，这次应读到“阅读修订”。确认保存的标题确实恢复后输入 `0` 退出；后续 M08—M10 只要求存档内容前后一致，不强制恢复原标题。已绑定文件时保存只需确认，不再询问路径。本轮实际使用的是“阅读修改”，也是有效基准；“放弃修改”的判断是恢复进入该轮时的磁盘标题。

## 9. M08：坏文件、加载失败与保存重试

**开始位置：PowerShell，当前校园程序已经退出。** 本节继续使用 M07 保存的 `tasks.json`；下面命令会回到它所在的 `$Work`，然后创建一个独立坏文件：

```powershell
Set-Location -LiteralPath $Work
Save-ManualSource 'bad.json' '{'
$TasksHashBefore = (Get-FileHash -LiteralPath 'tasks.json' -Algorithm SHA256).Hash
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

启动后按表输入，每个箭头处按 Enter：

| 操作 | 菜单内依次输入 | 预期 |
|---|---|---|
| 打开好文件 | `2 → tasks.json` | 打开成功，三条任务 |
| 制造未保存修改 | `3 → 2 → 内存修改 → 学习 → 2 → 1` | ID 2 改名，未保存 true |
| 尝试加载坏文件 | `11 → 2 → bad.json → 0` | 选择放弃旧修改以尝试打开；坏 JSON 打开失败后选择保留当前 |
| 检查保留状态 | `1` | 仍是 ID 1、2、4，ID 2 仍为“内存修改”，未保存 true |
| 放弃并退出 | `0 → 2` | 不写回磁盘，正常退出 |

回到 PowerShell 后运行下面命令，应为 `True`。版本、重复键、字段类型等 JSON 负例由自动回归覆盖，不再逐个手工重复。

```powershell
(Get-FileHash -LiteralPath 'tasks.json' -Algorithm SHA256).Hash -eq $TasksHashBefore
```

保存失败独立测试：保持在 `$Work`，先运行：

```powershell
if (Test-Path -LiteralPath '不存在的目录') { throw '本负例要求该目录不存在，请换一个不存在的目录名' }
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

在程序内依次输入 `1 → 2 → 保存重试 → 课程 → 2 → 1`，新建一条临时任务；再输入 `10 → 不存在的目录/tasks.json → 1`。**不要创建这个父目录**。

**预期**：保存失败、仍在会话、未保存 true、不创建父目录；随后 `10 → retry-tasks.json → 1` 应成功，才变为未保存 false。输入 `0` 退出，`[ZZY退出码=0]`。原 `tasks.json` 不应被覆盖；不通过目录“只读”属性推断实际 Windows ACL 行为。

## 10. M09：撤销/重做、分支历史与 ID 高水位

**开始位置：PowerShell，前一程序已经退出。** M08 没有改写基准 `tasks.json`，它的 next_id 仍为 5。启动：

```powershell
Set-Location -LiteralPath $Work
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

先在程序内输入 `2 → tasks.json` 打开基准，再依次操作下表。此测试只做一轮；已完成后再次执行会从更高 ID 开始，不能继续套用 5、6、7 的固定预期。

| 操作 | 依次输入 | 预期 |
|---|---|---|
| 新增临时任务 | `2 → 临时 → 课程 → 2 → 1` | 使用 ID 5，任务数 4、next_id 6 |
| 撤销 | `12` | 任务数 3、next_id 仍为 6；未保存 true |
| 重做 | `13` | ID 5 恢复，任务数 4 |
| 再撤销 | `12` | ID 5 再消失 |
| 新增分支 | `2 → 分支任务 → 课程 → 2 → 1` | 使用 ID 6，next_id 7，不能复用 5 |
| 再重做 | `13` | 空重做历史提示，不恢复旧 ID 5 |
| 删除最高 ID | `4 → 6 → 1` | 只余 1、2、4，next_id 仍为 7 |
| 保存并退出 | `10 → 1 → 0` | 保存成功，退出 0 |

回到 PowerShell 后重新启动：

```powershell
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

程序内输入 `2 → tasks.json → 1`，应仍为三条、next_id 7、未保存 false；再输入 `12`、`13`，应分别提示没有可撤销/重做的历史；输入 `0` 退出。这是合成存档的有意变更，后续应用测试以 next_id 7 为当前值，不再要求回到 5。

## 11. M10：非法输入、EOF 与应用 Ctrl+C

**开始位置：PowerShell，前一程序已经退出。** 启动：

```powershell
Set-Location -LiteralPath $Work
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

1. 在起始菜单依次输入 `abc`、直接回车、`99`：应提示十进制整数或范围问题，可继续输入，不能崩溃。
2. 输入 `1 → 2 → 三个空格 → 课程 → 2 → 1`；其中“三个空格”指按三次空格键再回车。应报告标题字段失败，任务数仍 0。再输入 `2 → 取消草稿 → 课程 → 2 → 0`，取消合法草稿后也仍为 0。
3. 用终端真实 EOF（Windows 原生终端通常 Ctrl+Z 再 Enter）结束。若 VS Code 不转发 EOF，输入 `0 → 2` 放弃退出，将真实 EOF 记为环境限制，随后用固定 stdin 验证逻辑。
4. 确认已回到 PowerShell，再执行：

```powershell
"1`n2`n未提交草稿" | & $ZzyPython -X utf8 -m zzy run $CampusMain --limits $CampusLimits
$LASTEXITCODE
```

**预期**：输入流结束时丢弃草稿，输出 `输入结束：有未保存修改，未自动保存` 和 `再见`，退出 0。它验证 EOF 路径，不证明已经测试到所有人工输入位置。

真实 Ctrl+C 另开一轮，在 PowerShell 运行下面命令。这里直接调用 Python，不用辅助函数，避免中断时留下旧退出码：

```powershell
$TasksHashBefore = (Get-FileHash -LiteralPath 'tasks.json' -Algorithm SHA256).Hash
& $ZzyPython -X utf8 -m zzy run $CampusMain --limits $CampusLimits --diagnostic-format json
```

在程序内输入 `2 → tasks.json → 3 → 2 → 中断不应保存 → 学习 → 2 → 1`。看到未保存 true 后，确保终端没有选中文字，按 Ctrl+C。回到 PowerShell 后立即执行：

```powershell
$LASTEXITCODE
(Get-FileHash -LiteralPath 'tasks.json' -Algorithm SHA256).Hash -eq $TasksHashBefore
```

**预期**：分别为 `130`、`True`；取消诊断含 `kind=cancelled`，磁盘仍是进入本轮时的任务标题（当前已有记录为“阅读修改”），未保存内容没有自动写回。

主菜单、新增、编辑、保存确认都要单独试 EOF。除手工 Ctrl+Z 外，可在程序退出后逐条运行以下固定输入；每条结束立即查看 `$LASTEXITCODE`，应均为 0：

```powershell
"1" | & $ZzyPython -X utf8 -m zzy run $CampusMain --limits $CampusLimits
$LASTEXITCODE
"2`ntasks.json`n3`n2`n未提交标题" | & $ZzyPython -X utf8 -m zzy run $CampusMain --limits $CampusLimits
$LASTEXITCODE
"1`n10`neof-never-saved.json" | & $ZzyPython -X utf8 -m zzy run $CampusMain --limits $CampusLimits
$LASTEXITCODE
Test-Path -LiteralPath 'eof-never-saved.json'
```

预期都正常结束；编辑草稿不写回 tasks.json，保存确认未输入时也不创建 eof-never-saved.json，最后为 False。主菜单 EOF 会提示有未保存修改，打开干净存档后在编辑草稿 EOF 不应把草稿变成已提交记录。

## 12. M11：真实窗口及基本绘图工具

**开始位置：PowerShell，当前没有运行中的校园程序或旧画室窗口。** 不再单独打开 Tk 演示窗口，直接验收实际画室。下面整块命令可复制执行：

```powershell
Set-Location -LiteralPath $Work
Save-ManualSource '人工画室.zzy' @'
(zno) c := sketch.canvas(800, 600, "人工绘图验收");
(zno) p := sketch.pen(c, "主画笔");
io.print(sketch.show(c));
io.print(sketch.save_project(c, "manual.zzysketch"));
io.print(sketch.save_svg(c, "manual.svg"));
'@
Invoke-Zzy run '人工画室.zzy' --gui
```

默认窗口有英文工具下拉框、笔名输入、颜色/线宽、缩放、历史条及右侧图层区。逐项选择并操作：

| 下拉项 | 操作 | 预期 |
|---|---|---|
| free | 左键按住画曲线后松开 | 一次拖曳为一条笔画；一次撤销能移除整笔 |
| line | 从一处拖到另一处 | 一条直线 |
| rectangle / circle | 分别拖动两次 | 矩形/圆可见，颜色线宽生效 |
| polygon | 按住拖动采样多个点后释放 | 闭合多边形；这里不是逐次点击顶点 |
| text | 点击并输入中文文字 | 文字显示；取消文字对话框不产生文字 |
| select / move / copy / erase | 先选择已有图形，再分别移动、复制、擦除 | 只影响命中的目标；擦除删除对象，而非用背景色涂盖 |

**窗口弹出后先不要关，也不要向终端粘贴其他命令**：继续完成 M12，以及 M13 的前四步，再点窗口右上角 X 关闭。预期终端打印三个 `(^_^)(null)`、`[ZZY退出码=0]`，没有 Tcl 异常或持续不退出的工作线程。此时回到 PowerShell 执行：

```powershell
Test-Path -LiteralPath (Join-Path $Work 'manual.zzysketch')
Test-Path -LiteralPath (Join-Path $Work 'manual.svg')
```

两行都应为 `True`。如果启动时无法导入 Tk 或没有显示环境，记为“环境阻塞”，不能算 GUI 通过。

## 13. M12：图层、样式及视图

在 M11 窗口内执行：

1. 改笔名，选颜色并调整线宽，再画一笔；应使用对应画笔和样式。
2. 右侧“新图层”输入 `前景`，选中该层，点“笔归此层”，画一个图形。
3. 对该层点“显隐”：图形隐藏/恢复；点“锁定”观察锁标记，再次点击解锁。本轮正常流程不在锁层上编辑；锁层拒绝修改的负例由自动回归覆盖。
4. 点“改名”，再通过“上移/下移”调整层序，观察重叠部分。对边界层上移/下移不应崩溃。
5. 点 `+`、`−`，切换网格，选择 `pan` 拖曳；只改变视图，图形相对关系不变，不应因此多出绘图 undo 历史。

记录工具栏是否有遮挡、按钮能否点到、文字是否可读；不能只看初始窗口成功弹出就勾选本项。

## 14. M13：撤销、重做与回放

**本节前四步都在 M11 仍然打开的同一个窗口内操作，不需要运行新命令。** 先画三笔不同图形，然后：

1. 点“撤销”两次、“重做”一次，观察图形数量与位置。
2. 点“播放”，中途“暂停”，再“单步”；拖历史滑条并释放鼠标定位到早期位置。
3. 在回放位置选择绘图工具画新图，应该退出回放；不能把回放副本误保存成真实文档的截断版本。
4. 新编辑后点重做，旧重做分支不再出现；缩放、网格不会像新增图形一样进入历史。
5. 点窗口右上角 X 关闭，等终端出现三个成功 Result 和退出码 0，按 M11 末尾确认两个文件存在。**回到 PowerShell 后**再复制下面整块命令，重新打开保存结果：

```powershell
Set-Location -LiteralPath $Work
if (-not (Test-Path -LiteralPath 'manual.zzysketch')) { throw '请先完成 M11 保存，不要在旧窗口仍打开时运行' }
Save-ManualSource '重开人工画室.zzy' @'
(?_?) sketch.load_project("manual.zzysketch") {
    (^_^)(c) => { io.print(sketch.show(c)); }
    (T_T)(m) => { io.print(m); }
}
'@
Invoke-Zzy run '重开人工画室.zzy' --gui
```

重开窗口中应有保存时的完整图层和图形，可以继续绘图；再点 X 关闭，应返回 `(^_^)(null)` 并退出 0。本项主要核对交互表现；锁层负例、精确内部笔态、缓存预算、回放不重跑 I/O 由自动回归核验，不再另做人工故意报错。

## 15. M14：鼠标、键盘、定时器与关窗重开

**开始位置：PowerShell，M13 重开的窗口也已关闭。** 创建独立事件示例并启动，复制下面整块命令：

```powershell
Set-Location -LiteralPath $Work
Save-ManualSource '人工事件.zzy' @'
(zno) c := sketch.canvas(400, 300, "事件验收：按l进入长回调");
(zno) p := sketch.pen(c, "事件笔");
(addnew) clicked(x, y, button) {
    io.print("CLICK"); io.print(button);
    sketch.jump_to(p, x, y); sketch.dot(p, 6);
}
(addnew) key(k) {
    io.print(k);
    (zif?:) k == "l" { io.print("LONG"); (while) (true) {} }
}
(addnew) tick() { io.print("TICK"); }
sketch.on_click(c, clicked);
sketch.on_key(c, key);
sketch.every(c, 1000::ms, tick);
io.print(sketch.show(c));
io.print("CLOSED");
'@
Invoke-Zzy run '人工事件.zzy' --gui
```

1. 保持默认 `callbacks` 模式，在画布上按左/右键：终端出现 CLICK 和 1/3，点击处出现圆点。
2. 点击画布使其获焦，再按 Escape、普通字符：终端显示 Escape 或对应键名。
3. 等待约两秒：至少看到一次 TICK，不要求机器调度恰好每秒一次。
4. 用窗口右上角 X 关闭。若额外探索长回调，可按小写 `l`，看到 LONG 后再点 X；本轮不要求为此单独补截图。

**预期**：show 返回 `(^_^)(null)`，随后打印 CLOSED，进程正常退出；不需要杀终端。定时器和旧回调不应在关窗后继续运行。再次执行该命令仍能正常打开，不继承上一轮计时器。若执行可选长回调，它也应能被关窗终止；没有出现 LONG 的记录只能证明常规关闭。

确认已回到 PowerShell，再执行下面命令重开一次；等看到新的 TICK，直接点 X 关闭，应再次出现 CLOSED 和退出码 0：

```powershell
Invoke-Zzy run '人工事件.zzy' --gui
```

长回调中断由 `tests.gui_sketch.GUIAcceptance.test_close_interrupts_long_callback_and_continues_script` 精确断言，队列溢出和回调诊断也由该 GUI 套件核验；本轮保留人工正常关窗、再开的记录即可。快速人工点击只能验证实际操作感受，不等同于证明触及某个内部容量阈值。自动套件仍需实际报告，不能把用例存在写成已通过。

## 16. M15：原始 studio、项目重启、SVG 与函数库

**开始位置：PowerShell，前一个事件窗口已关闭。** 本节使用全新子目录和原始 studio，窗口里不要编辑，确保固定预期可比较。复制执行：

```powershell
Set-Location -LiteralPath $Work
$StudioWork = Join-Path $Work ('原始 studio-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $StudioWork -ErrorAction Stop | Out-Null
Set-Location -LiteralPath $StudioWork
Invoke-Zzy run (Join-Path $RepoRoot 'examples/sketch/studio.zzy') --gui
```

**预期**：显示小花图案。直接关闭窗口后打印 `小花出道，图案库也保存好了。`，退出 0；目录中有 little-flower.svg、flower.zzy、little-flower.zzysketch。

看到小花后直接点 X 关闭，等 PowerShell 提示符出现。此时当前目录应仍是 `$StudioWork`。先检查生成文件并打开 SVG：

```powershell
Get-Item -LiteralPath 'little-flower.svg','flower.zzy','little-flower.zzysketch' | Select-Object Name,Length
Invoke-Item -LiteralPath (Join-Path $StudioWork 'little-flower.svg')
```

三个文件都应存在且非空。若默认打开的是文本编辑器，在资源管理器中右键 SVG，选“打开方式 → 浏览器”，检查小花、背景、裁剪与比例。关闭 SVG 预览后回到同一 PowerShell，复制执行以下整块命令，创建并运行重启程序。**这里不能用 Save-ManualSource**，因为那个辅助函数始终向 `$Work` 写文件：

```powershell
$RestartSource = @'
(use) "flower.zzy" (as) flowers;
(?_?) sketch.load_project("little-flower.zzysketch") {
    (^_^)(c) => {
        io.print(sketch.layer_info(c)[0].count);
        io.print(sketch.undo(c));
        io.print(sketch.layer_info(c)[0].count);
        io.print(flowers.draw_flower(c, 0, 0, 1, 0));
        io.print(sketch.save_svg(c, "restarted.svg"));
    }
    (T_T)(m) => { io.print(m); }
}
'@
[System.IO.File]::WriteAllText((Join-Path $StudioWork 'restart.zzy'), $RestartSource, $Utf8NoBom)
Invoke-Zzy check 'restart.zzy'
Invoke-Zzy run 'restart.zzy'
Set-Location -LiteralPath $Work
```

check 退出 0、无输出；headless run 不弹窗，固定输出：

```text
8
true
7
(^_^)(9)
(^_^)(null)
```

说明项目在另一进程中恢复了几何与历史，撤销后对象数从 8 到 7，导出的图案函数可以再导入使用，且 ID 高水位继续增长。此固定答案只适用于未编辑的 studio；M11 的自由绘图对象数量另按实际记录。

## 17. M16：负例由自动回归覆盖

本版删除无窗口 show、不可用 PNG、坏绘图项目加载的独立人工命令，由第19节自动回归核验。保留 M16 编号对应总体计划。结果文档中的已有补测不删除：切回 `$Work` 后运行两个源文件，分别得到 `GUI unavailable: run requires --gui`、`PNG unavailable: no independent PNG backend is installed`，两次退出 0，`optional.png` 为 False，符合预期。这里只确认这两个已执行负例；坏项目加载不冒填人工通过。PNG 当前仍不支持。

## 18. M17：新环境离线安装与真实窗口

**本轮状态：无窗口安装、安装后的真实 GUI 与项目往返均已核验通过，无需重跑。** 图40对应 `$Evidence/package-smoke/report.json` 的 headless smoke；新增图41对应 `$Evidence/offline-copy/tests/e4/results/installed.json`，执行时间为2026-10-27 22:05:49—22:06:06（北京时间），不是根目录里2026-10-17的历史报告。

本轮新报告两处 `passed=true`，39个源码一致，真实窗口渲染8个对象、视口704×504，Tk 8.6.12；所有记录命令退出0，重启输出为 `8 / true / 7 / (^_^)(9) / (^_^)(null)`，wheel及六个输出文件哈希复核一致。安装目标为副本内部的新环境及专用 `offline-gui-venv`，没有将项目日常 `.venv` 作为安装目标。构建/安装命令禁用下载；没有物理断网记录，不扩写为“已断网测试”。

以下步骤保留供后续复测使用。已有这次报告时无需为了补两张报告字段截图再执行一次；新一轮复测仍应新建带时间戳的副本和环境。

无窗口安装 smoke 已归入 CI，不再要求在人工章节重复执行。本节保留新的隔离安装及真实窗口探针。**开始位置：PowerShell，所有手工窗口已关闭。** 先回项目根目录并确认构建工具：

```powershell
Set-Location -LiteralPath $RepoRoot
$BuildPython = 'C:\Users\13691\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $BuildPython)) { throw '请把 BuildPython 改为本机带 pip/setuptools/wheel 的 Python 绝对路径' }
& $BuildPython -X utf8 -c "from importlib.metadata import version; print({n:version(n) for n in ('pip','setuptools','wheel')})"
if ($LASTEXITCODE -ne 0) { throw '构建工具不齐全，请先准备好后再继续' }
```

预期打印三个工具的版本，命令退出 0。这里的 `$BuildPython` 可换为自己的构建 Python；安装目标仍使用 CPython 3.12.14。工具固定版本/哈希见 `scripts/ci/build-requirements.txt`。下面驱动使用 `--no-index --no-deps --no-build-isolation`，不会下载构建依赖；先备齐工具，再按现场条件断网验证。没有实际断网时只记录“命令禁用下载”，不写“已断网测试”。

复制项目到独立验收目录，并创建专用 venv。下面整块命令可复制执行；它只在副本中更新 E4 报告，安装到两个隔离环境，不重装日常 `.venv`：

```powershell
$InstallRun = Get-Date -Format 'yyyyMMdd-HHmmss'
$OfflineCopy = Join-Path $Evidence "offline-copy-$InstallRun"
New-Item -ItemType Directory -Path $OfflineCopy -ErrorAction Stop | Out-Null
foreach ($Item in @('zzy','tests','scripts','apps','examples','benchmarks','skills','docs','pyproject.toml','README.md')) {
    Copy-Item -LiteralPath (Join-Path $RepoRoot $Item) -Destination $OfflineCopy -Recurse
}
$CopiedInstallReport = Join-Path $OfflineCopy 'tests/e4/results/installed.json'
if (Test-Path -LiteralPath $CopiedInstallReport) { Remove-Item -LiteralPath $CopiedInstallReport }
$OfflineVenv = Join-Path $Evidence "offline-gui-venv-$InstallRun"
& $ZzyPython -X utf8 -m venv --without-pip $OfflineVenv
if ($LASTEXITCODE -ne 0) { throw '专用venv创建失败' }
$OfflinePython = Join-Path $OfflineVenv 'Scripts/python.exe'
Set-Location -LiteralPath $OfflineCopy
try {
    & $OfflinePython -X utf8 tests/e4/install.py --installer $BuildPython
    $OfflineExitCode = $LASTEXITCODE
} finally {
    Set-Location -LiteralPath $RepoRoot
}
$OfflineExitCode
```

命令先清除副本带入的旧安装报告，保留原项目报告。执行期间会自动打开并关闭测试窗口，**不要手动绘图、关窗或同时运行别的 GUI 测试**。命令结束后应显示退出码 `0`。随后在 PowerShell 检查报告：

```powershell
$InstalledReport = Get-Content -LiteralPath (Join-Path $OfflineCopy 'tests/e4/results/installed.json') -Raw -Encoding utf8 | ConvertFrom-Json
$InstalledReport | Select-Object passed,wheel_sha256,isolated
$InstalledReport.probe | Select-Object passed,installed_package
$InstalledReport.source_files.Count
```

**预期**：两处 `passed` 均为 `True`、wheel 哈希非空、源码数量为 39；报告验证真实窗口映射/关窗保存、隔离重启/撤销/函数复用。失败时保留副本和控制台输出，不拿旧 E4 报告代替。本轮只记录 Windows“设置 → 系统 → 屏幕”里的当前缩放比例，不要求额外切换 125%/150%；其他 DPI 保留“未验证”。

## 19. 自动回归与本机 CI 的配合

本节是自动化验证，不要求为每一个内部断言补人工截图。前面的精简项由这里覆盖；不能因为删除了手工步骤就跳过它们。**开始位置：PowerShell，所有手工窗口已关闭。** 下面命令先切到项目根目录，自动生成新的报告名，按顺序运行：

```powershell
Set-Location -LiteralPath $RepoRoot
$AutoRun = Get-Date -Format 'yyyyMMdd-HHmmss'
& $ZzyPython -X utf8 -m tests --report (Join-Path $Evidence "all-tests-$AutoRun.json")
$LASTEXITCODE
```

全量需要较长时间。上条结束、记录退出码后，再单独运行 GUI 自动探针；期间不操作测试窗口，不同时跑正式性能测试：

```powershell
& $ZzyPython -X utf8 -m tests.gui_sketch --report (Join-Path $Evidence "gui-$AutoRun.json")
$LASTEXITCODE
```

全量当前应为 **2002 项**（原 1982 加 CI 门禁检查 10 项、日志检查 10 项），collected=tests_run，passed=true，failures/errors/skipped/expected_failures 全零。GUI 另为 11 项，同样零失败/零跳过。数量今后变化时应核对清单与基线，不沿用旧计数。GUI 命令会自己开关真实窗口，运行期间不操作那些窗口；它不能代替 M11—M14 的人工交互。

如果同一最终候选已有新的 CI 回归/安装报告，可以归档其路径，无须为补人工截图再跑一遍全量；历史版本的报告不能替代当前候选。完整 CI 包装流程见 [CI设计](../../development/ci-design.md)，本指南不再重复列出。`scripts.ci regression` 会把详细输出写入 tests.log；日志轮转方法见 [日志配置](../../runtime/logging.md)。Start-Transcript 的人工记录不受 CI 日志淘汰控制。

## 20. M18：演示排练与记录结果

**本轮可跳过独立排练。** 以下语言、校园重开、小花往返路线已分别在前项记录；本轮不再要求为了 M18 重复截图，也不填“排练通过”。答辩前如果需要练习讲解、切屏和查找材料，可按本节走一遍。

**开始位置：PowerShell，其他程序和窗口均已退出。** 排练使用本轮真实生成的文件，按下面路线操作即可，不在现场重新跑长回归或长基准。

1. 语言和诊断：复制执行，前两条应退出 0，最后一条应为 E302、退出 2（故意错误）：

```powershell
Set-Location -LiteralPath $Work
Invoke-Zzy run (Join-Path $RepoRoot 'examples/hello.zzy')
Invoke-Zzy run (Join-Path $RepoRoot 'examples/functions.zzy')
Invoke-Zzy run '错误 名称.zzy' --diagnostic-format json
```

2. 校园存档重开：运行下面命令，在程序内输入 `2 → tasks.json → 1`，应看到三条任务；M09 已完成时 next_id 为 7。说明保存/未保存状态后输入 `0` 退出。若要演示修改和保存，按 M07 流程另用演示存档，不改这份后续验收基准。

```powershell
Invoke-Zzy run $CampusMain --limits $CampusLimits
```

3. 画室和导出：运行下面整块命令，在窗口展示小花后直接点 X 关闭。程序应退出 0，生成 SVG、绘图项目和函数库；随后直接复制 M15 的 `$RestartSource = @'` 到 `Set-Location -LiteralPath $Work` 那一整块，演示函数复用：

```powershell
$DemoStudio = Join-Path $Evidence ('demo-studio-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $DemoStudio -ErrorAction Stop | Out-Null
$StudioWork = $DemoStudio
Set-Location -LiteralPath $DemoStudio
Invoke-Zzy run (Join-Path $RepoRoot 'examples/sketch/studio.zzy') --gui
```

4. 报告展示：关窗、返回 PowerShell 后运行下面命令，先列出本轮自动化报告供选择，再查看正式性能报告；在 VS Code 按 Ctrl+P 输入对应完整路径可以打开。核对报告的 passed、失败数、候选版本及测量范围，不能只展示文件存在：

```powershell
Set-Location -LiteralPath $RepoRoot
Get-ChildItem -LiteralPath $Evidence -File -Filter '*.json' | Select-Object Name,FullName
Get-Content -LiteralPath 'docs/runtime/performance-report.md' -Encoding utf8 -TotalCount 60
```

性能复现命令和耗时/失败分类见 [最终测试计划第6节](../../development/final-test-plan.md#6-性能容量与稳定性)。正式测量须回仓库根目录、独占机器、写全新目录；已有大规模超时或资源拒绝如实列出，不能把不完整样本填 0 或写成“全部更快”。人工演练主要验证能找到并解释这些证据，不要求每次现场重跑长基准。

本轮记录如下。“图”指结果文档中按出现顺序计数的41张截图，前40张保持原样，第41张为操作者补测记录。日期为 2026-10-27，操作者为本机用户；核对者只复核证据，未代替操作者补跑测试。环境为 Windows 11、CPython 3.12.14、ZZY 0.6.0a1；本轮 M17 新报告确认 Tk 8.6.12，系统缩放比例未记录，不套用历史环境值。候选 `b598043`，工作区差异未提交。

| 用例ID | 实际结果与证据 | 本轮状态与范围 |
|---|---|---|
| M01 | 图02，三组示例输出 | 已核对，符合预期；spec 汇总不另截 |
| M02 | 图03，E302/E103/E201/E213 与 check/run 退出码 | 已核对，均为预期诊断 |
| M03 | 图04—06，check 无文件，run 输入后保存成功 | 已核对，符合预期 |
| M04 | 图07，真实 Ctrl+C，cancelled、130 | 已核对，符合预期 |
| M05 | 图08，任务编辑/删除/新增与统计 | 已核对，符合预期；部分新增过程省略 |
| M06 | 图09—10、15，筛选/排序、TSV、清筛选 | 已核对，符合预期；空结果由自动回归覆盖 |
| M07 | 图11—17，保存、取消退出、放弃、保存后重开 | 已核对，符合预期；按独立轮次比较标题 |
| M08 | 图18—20，坏 JSON 保留内存、存档哈希 True、失败保存后重试 | 已核对，符合预期；其他 JSON 负例由自动回归覆盖 |
| M09 | 图21—23，ID 5/6 分支，重开 next_id 7，历史为空 | 已核对，符合预期 |
| M10 | 图24—28，非法输入、草稿 EOF、保存确认 EOF、Ctrl+C 不写盘 | 已核对，符合预期；图27—28 原来误标 M11，现归 M10 续 |
| M11 | 图29 与“基础测试成功”备注，图31—32 的关窗保存输出 | 已记录基础绘图主流程；不推断每个工具均有逐项证据 |
| M12 | 图30，笔名/红色粗线、前景图层、网格 | 已记录截图可见操作；动态显隐/锁定/层序未逐项留证，不另要求逐按钮截图 |
| M13 | 图31—32 与“成功”备注，项目重开并退出 0 | 已记录操作者结论及保存重开；精确回放内部状态由自动 GUI 核验 |
| M14 | 图33—35，键名/CLICK/TICK/CLOSED、两轮退出 0 | 常规事件、关窗重开已记录；LONG 未人工执行，转自动 GUI 核验 |
| M15 | 图36—38，小花窗口与 SVG、三个产物、重启固定输出 | 已核对，符合预期 |
| M16 | 图39，show/PNG 能力失败、退出 0、文件 False | 两项已有负例符合预期；不再补测，坏项目由自动回归覆盖 |
| M17 | 图40—41、`package-smoke/report.json` 与 `offline-copy/tests/e4/results/installed.json`；两处 passed true，39 源文件一致，真实 GUI 渲染8个对象、视口704×504 | 已核验通过：隔离安装、真实 GUI、关闭保存及项目重启；命令禁用下载，物理断网和额外 DPI 未验证 |
| M18 | 无独立排练记录，路线已分散在前项执行 | 本轮可跳过独立排练，不记通过 |

后续复测另记执行人、日期、候选及差异、环境、实际结果和证据路径；失败要保留首次现象，追加复测，不覆盖原始截图。

截图只截取相关窗口/提示；终端日志、tasks.json、TSV、SVG、项目文件及哈希放本次 `$Evidence`。准备交付时再将选定人工资料归档到 `docs/manual-tests/final-日期-短SHA/`，既有资料不覆盖，是否提交证据由操作者决定。

全部完成后，在 PowerShell 提示符下结束记录并恢复变量：

```powershell
Set-Location -LiteralPath $RepoRoot
Stop-Transcript
$env:PYTHONPATH = $OriginalPythonPath
Write-Host "本次证据目录：$Evidence"
```

本指南后半段统一使用 `Set-Location` 切换到明确目录，不需要猜测还应执行几次 `Pop-Location`。最后检查没有本轮遗留的窗口/工作进程，且没有未说明的失败项；未测内容保留“未执行/环境阻塞”，不据此勾选 P11 完整验收。
