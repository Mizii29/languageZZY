# ZZY 持续集成（CI）设计

建立：2026-10-20｜更新：2026-10-22｜状态：工作流及本地入口已实现；云端首跑、远程必需检查尚待验证

CI 的作用是让每次候选修改自动经过相同检查，并保存结果，及时发现回归。当前仓库远程为 GitHub `Mizii29/languageZZY`，工作流已写入 [ci.yml](../../.github/workflows/ci.yml)，通用执行入口为 [scripts/ci.py](../../scripts/ci.py)。最终完整测试及人工放行见 [最终测试计划](final-test-plan.md)，本机操作与结果见 [人工测试统一目录](../manual-tests/README.md)。本次没有推送，也没有修改 GitHub 仓库规则；文件落地不等于云端已经运行。

## 1. 适用范围和前提

本项目是单机解释器与桌面/CLI 应用，运行依赖为空，测试基于标准库 unittest。CI 首期聚焦自动验证和 wheel 构建，不引入服务器部署、自动发包或复杂服务环境。

关键前提是 `pyproject.toml` 精确限定 **CPython 3.12.14**；不能直接套用多版本 Python 矩阵，也不能用 `3.12`、`latest` 或修改安装限制来伪装兼容。2026-10-20 核对官方 `actions/python-versions` 清单：该补丁版本没有 Windows 安装资产，故本实现不依赖 `setup-python` 提供它。[官方运行时清单](https://github.com/actions/python-versions/blob/main/versions-manifest.json)

采用 Astral `python-build-standalone` 的 **20260929 / CPython 3.12.14 / Windows x64 MSVC** 安装包，URL 与 SHA-256 固定在 [runtime.json](../../scripts/ci/runtime.json)。[bootstrap-python.ps1](../../scripts/ci/bootstrap-python.ps1) 下载后先核验哈希，再解压并断言 CPython/完整版本，最后加入 job 的 PATH；runner 原有 Python 仅下载字节，不执行项目测试。下载失败、哈希错误或版本不符立即失败，不切换补丁版本。[固定发布来源](https://github.com/astral-sh/python-build-standalone/releases/tag/20260929)

wheel 工具独立固定为 pip 25.2、setuptools 80.9.0、wheel 0.45.1，使用 [build-requirements.txt](../../scripts/ci/build-requirements.txt) 的 SHA-256 与 `--require-hashes --only-binary=:all:` 安装。只有准备运行时/工具联网；后续 wheel 构建与安装使用 `--no-index`。

首期验收假设：维护者负责 workflow/工具更新及失败排查；普通 PR 必须有稳定、可追溯的检查结果；不上传真实任务数据或本地私有文件。初始建议回归 job 上限 45 分钟、构建 15 分钟，首批云端运行后依据真实耗时调整。已有本地全量约 15 分钟仅供排期，不是云端完成时间保证。

## 2. 推荐方案与取舍

| 方案 | 优点 | 代价 | 决定 |
|---|---|---|---|
| GitHub 托管 Windows 上跑无窗口回归；真实桌面及正式性能单独验收 | 接近现有进程/路径行为，复用一键入口，维护量较小 | 指定 Python 可用性和 Windows 控制台信号仍需试跑 | 首期推荐 |
| Windows/Linux/macOS、多 Python 全矩阵 | 较早发现兼容差异 | 超出现有支持证据；Python 安装契约和 GUI 像素检查不匹配 | 支持范围扩展后再做 |
| 自托管 Windows 桌面上跑全部任务 | 可预装指定运行时并做交互式 GUI | 桌面会话、机器隔离、队列和运维成本较高 | 后续可信手动任务的备选 |

托管 Windows 的系统镜像不等同于现有 Windows 11 桌面证据；记录具体镜像/OS，首轮实际验证后才能说明 CI 支持情况。不要因云端缺控制台或窗口而删掉真实 Ctrl+C 用例，或跳过后标记完整回归通过。

## 3. 触发与分支关系

工作流名 `ZZY CI`，实施路径 `.github/workflows/ci.yml`。

| 事件 | 运行内容 | 目的 |
|---|---|---|
| `pull_request`，目标 `main`、`test` | 静态检查、完整 Windows 回归、安装 smoke、最终汇总门禁 | 验证拟合入代码与目标分支的组合 |
| `push` 到 `main`、`test`、`feature`、`codex/**` | 同上 | 分支提交及合并后再验证 |
| `workflow_dispatch` | 同上 | 对指定候选版本主动重跑 |
| 后续可选 `schedule` | 默认分支上的配对正确性/较长稳定性任务 | 工作量增加后再启用，无需首期每日重复全量 |

`pull_request.branches` 指目标分支；PR 运行记录 head SHA、base SHA 及实际 checkout 的合并提交 SHA，不能只贴 head SHA 却用另一份代码测试。日程工作流针对默认分支，验证 `test` 候选时使用该分支 push 或手动指定 ref。[事件与过滤语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)

同一 PR 或同一 push 分支采用 concurrency，新的提交取消旧运行；PR 与 push 使用不同组，避免互相取消必需检查。取消结果记为 cancelled，不能当通过。首期不配置文档路径跳过：文档属于课程交付，且按路径跳过必需工作流可能让检查一直等待。后续优化也必须保持稳定汇总门禁会实际执行。

## 4. 作业划分与通过标准

```text
checkout + 固定环境
          |
        static
       /      \
regression   package-smoke
       \      /
        ci-gate

本地/可信桌面：真实 GUI + 离线整体验收 + 人工验收 + 正式性能
```

`static` 成功后，两个执行 job 在不同 `windows-2025` runner 并行；每个 runner 内顺序执行，不把进程/信号回归用并行 unittest 拆散。静态/汇总上限各 10 分钟、回归 45 分钟、安装 15 分钟；回归子进程另有 40 分钟截止及进程树清理。失败时上传已产生的报告与日志。

### A. static：范围与文档检查

- 校验配置与实际 Python 完整版本，记录 OS/镜像、Unicode、资源配置及指纹、Git 版本、commit；失败不继续跑其他 job。
- 收集测试但不执行，核对清单结构、跨清单重复 ID、源码路径及清单集合；与 [test-inventory.json](../../scripts/ci/test-inventory.json) 比较，允许新增，拒绝静默减少。当前全量 **2002**（原 1982 加 CI 自检 10 项、日志自检 10 项）、12 份清单 **1738** 个独立黑盒。P09 会在应用资源策略下重复运行其中 23 项，比较测试 ID 的出现次数，不能去重后漏掉这部分。只有明确期望 E401/退出 2/无 span 的缺文件负例允许夹具不存在。
- 正式覆盖矩阵仍由审查者核对核心规则、APP-01—03、SKETCH-01—06；脚本不声称自动理解全部语义覆盖。
- 执行 `python -X utf8 -m tests.p09.count_lines --check`，验证应用行数报告与源码一致且非纯标点有效行不少于 200。
- 检查 Markdown 本地文件链接、代码围栏、`git diff --check`；按 Git 跟踪文件收集并兼容中文/空格路径，忽略未提交的用户人工资料。正式语法/要求有变化必须显式审查，不能自动改写 `requirement.md`。

执行入口为 `python -X utf8 -m scripts.ci static --output dist/ci/static`。原始 requirement 按冻结的字节 SHA-256 校验，`.gitattributes` 对该单文件关闭换行转换，保证 Windows checkout 不改变原文。未引入全仓 formatter 或新测试框架。

静态入口也校验 [日志配置JSON](../runtime/logging.json)，拒绝关闭容量控制的0值、未知/重复字段或不合法范围；完整说明见 [日志配置](../runtime/logging.md)。

### B. regression-windows：完整无窗口回归

从 checkout 根目录直接运行源码，无需先 editable 安装；使用全新报告目录：

```powershell
python -X utf8 -m scripts.ci regression --output dist/ci/regression
```

必须同时检查进程退出码和 JSON：`passed=true`，`collected=tests_run>0`，failures/errors/skipped/expected_failures 均为 0；本次收集集合与静态阶段基线一致。报告缺失、解析失败或数量异常也失败。已有入口已检查非空、完整执行及零跳过，CI 再确认产物确实来自本轮。

回归输出由父进程流式保存为tests.log，每文件最多1MiB、保留4份gzip备份，超出自动淘汰；report/log记录轮转次数及是否丢弃更早片段。读取时按旧到新拼接，不能把淘汰后的最近日志称为全程日志。写盘/压缩失败也使job失败并清理进程树，不通过忽略日志错误掩盖失败。

全量入口已包括 1738 个外部 CLI、应用专项、变形 spec、指南与宿主生命周期测试，不再另跑一遍全黑盒增加日常成本。失败时可在新 attempt 中运行专项辅助定位，但最终以修复后的完整重跑为准。收集、清理、真实 Ctrl+C 在托管环境的首轮可用性需实际验证；环境不支持时修正 runner 配置或换到合适环境，不伪造信号成功。

PowerShell 中调用外部命令后立即判断 `$LASTEXITCODE`；尤其不能把“测试→其他成功命令”串在一个步骤内而只返回最后的成功状态。日志若经 `Tee-Object` 转发也要保留原进程码。job 内不设置 `continue-on-error` 掩盖失败。

### C. package-smoke：构建与离开源码目录的安装检查

该 job 验证实际 wheel，避免只证明仓库源码可 import：

1. 备齐、固定并记录 pip/setuptools，构建 `python -m pip wheel . --no-deps --no-build-isolation --no-index --no-cache-dir --wheel-dir dist/ci/package/wheel`；构建期禁止临时下载缺失依赖。
2. 只允许找到一个匹配本项目版本的 wheel，计算 SHA-256；创建全新 venv，使用该 wheel `--no-index --no-deps` 安装。依赖准备期可联网，安装 smoke 本身离线。
3. 在 checkout 外的中文/空格临时 cwd，清除 `PYTHONPATH`，使用新 Python 的 `-I -X utf8`；核对 `zzy.__file__` 位于新 venv，包内源码与本次候选一致。
4. 复制测试用正常程序和实际示例，运行安装包的 help/info/check/run/test；覆盖固定输出、一个诊断、一个正常 spec。用副作用程序确认 check 不输入/不输出/不写文件，再验证 headless 几何/SVG/项目往返及不导入 Tk。
5. 把实际校园应用七个模块和 `limits.json` 复制到临时目录，驱动真实菜单完成保存、退出、另一进程读取；用外部固定期望核对状态/文件。不得从源码目录误导入包，也不得用 Python 重写业务。
6. 保存每个子命令、cwd、双流、退出码和安装来源；结束后清理新 venv 与进程。

步骤 2—6 已由 `scripts.ci package` 和 [ci_installed_probe.py](../../scripts/ci_installed_probe.py) 实现，输出 `report.json`、`probe.json`、wheel 与哈希。会核对全部 39 个包源码文件，正常完成后清理临时环境，不重装调用它的项目 venv。现有 `tests/e4/install.py` 会真实开窗、重装调用它的 Python 并覆盖固定历史报告，仍保留给独立桌面验收，不用于 PR 的 package job。

### D. ci-gate：唯一稳定的必需检查

汇总 job 使用 `needs: [static, regression-windows, package-smoke]` 和 `if: always()`，下载依赖 job 的本轮 artifact，核对报告标识与实际 checkout SHA/run ID/attempt 一致；仅当三个依赖结果全部为 `success` 且必要报告完整时返回成功。failure、cancelled、skipped、缺报告均返回失败；不能只因汇总步骤本身执行了就显示绿色。若后续启用矩阵，每个平台的报告与artifact须分别标识，不能相互覆盖。

建议先完成一次成功试跑，再在仓库 `main` 的分支保护或规则集中把 `ZZY CI / ci-gate` 对应的实际 check 名设为必需，并要求 PR 分支保持与目标分支同步。GitHub 的普通 required check 可以接受 skipped/neutral，因此本项目需要显式汇总逻辑，不让漏跑的测试通过合并门禁。[保护分支说明](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

`test` 可采用同样规则，但若仍承担本地受控验证分支，应先明确其推送流程；本方案不推断远程现有保护设置。CI 检查通过后由维护者按既有流程合并，不设置自动推送、自动合并或自动发布。

## 5. GUI、性能与长期任务

| 内容 | 首期执行位置 | 与 PR 门禁关系 |
|---|---|---|
| `tests.gui_sketch` 的 11 项真实 Tk/GDI 检查 | 本地 Windows 11 真实桌面；以后可接可信手动桌面 runner | 最终候选必须另行完成，PR 绿色不证明 GUI 已通过 |
| 人工 M01—M18 | 操作者实际终端/桌面 | 按最终测试计划留记录 |
| `benchmarks.run --verify-only --output <新目录>` | 本机手动；后续可接入 CI/定时 | 检查全部配对正确性，非正式速度结论 |
| 核心及 Sketch 正式性能 | 固定本机，独占资源 | 人工发布验收，保持原始数据与失败分布 |
| 离线整体验收 | 独立 Windows/Tk 环境 | 包含 GUI、应用、文档和交付材料，区别于无窗口 smoke |

如果以后接入自托管桌面 runner，必须是隔离验收机和已登录的交互式桌面；不能假设后台服务会话可以显示 Tk。只允许运行维护者已审阅的可信 commit，不让外部 PR 自动执行于个人电脑。不使用带高权限上下文的 `pull_request_target` 去 checkout 并执行不可信 PR 代码。[GitHub 安全说明](https://docs.github.com/en/actions/reference/security/secure-use)

Linux/macOS、其他 Python 版本、额外 DPI/字体以后按明确的兼容目标分期加入；首次运行不能靠预置 skip 或 `continue-on-error` 宣称支持。若要扩展 Python 范围，先单独验证并修改正式支持契约，再调整安装元数据和矩阵。

## 6. 结果保存、权限与成本

所有结果写入忽略目录 `dist/ci/`，不覆盖 `tests/e4/results` 或原始基准。每个 job 使用独立子目录，artifact 名含 job、实际 checkout SHA、run ID、attempt。失败时也用 `if: always()` 上传已产生的日志/报告；必须产物缺失应由执行/汇总逻辑报错，而不是靠“上传了一些日志”算成功。

普通 CI artifact 保留 14 天，并受仓库上限约束；最终交付证据另行长期归档，不能只依赖会过期的 Actions artifact。保存内容为环境指纹、测试/安装 JSON、双流日志、清单和 wheel/哈希，不上传整份 venv。各 job 上传 `dist/ci/`，保留 static/regression/package 子目录，汇总下载时合并，避免同名 report.json 相互覆盖。[Artifact 官方说明](https://docs.github.com/en/actions/tutorials/store-and-share-data)

工作流权限为 `contents: read`；checkout 不持久化写凭据，不需要 PAT、部署密钥或发布权限。官方 checkout v7.0.1、upload-artifact v7.0.2、download-artifact v8.0.2 均固定完整 commit SHA，注释标出发布版本；首期不缓存 venv。提交身份核对包含 checkout/head/base SHA、run ID、attempt、源码指纹，拒绝旧报告或跨 job 源码不一致。

运行成本先由“不重复全黑盒、取消同分支旧运行、安装 smoke 与全量分机并行、正式性能移出 PR”控制。连续失败排查时保留每个 attempt，修复后回到完整门禁，不把失败 job 单纯 rerun 到绿色作为充分结论。

## 7. 在 VS Code / PowerShell 本机复现

先在仓库根目录取得与 CI 相同的运行时和工具。下列目录必须不存在；重跑时更换日期/attempt，不覆盖失败记录：

```powershell
$env:PYTHONUTF8 = '1'
$DownloadPython = (Resolve-Path './.venv/Scripts/python.exe').Path
$RuntimeDirectory = Join-Path (Get-Location) 'dist/ci-python-local-attempt-01'
./scripts/ci/bootstrap-python.ps1 -Destination $RuntimeDirectory -DownloadPython $DownloadPython
if ($LASTEXITCODE -ne 0) { throw '运行时准备失败' }
$CiPython = Join-Path $RuntimeDirectory 'python/python.exe'
& $CiPython -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'ensurepip失败' }
& $CiPython -m pip install --require-hashes --only-binary=:all: -r scripts/ci/build-requirements.txt
if ($LASTEXITCODE -ne 0) { throw '构建工具准备失败' }
```

`-DownloadPython` 可以是本机已有 Python，只负责下载；CI 的测试 Python 始终为 `$CiPython`。已缓存归档时可加 `-Archive '实际归档绝对路径'`，仍核对同一 SHA-256。若本机已有精确版本及构建工具，也可以直接指定 `$CiPython`，但应记录工具差异。

按顺序运行四个入口。每个入口会自行创建输出目录，**不要预建 static/regression/package/gate 子目录**。执行期间不要修改源码/夹具/CI 文件；Markdown 文案不进入源码指纹。

```powershell
$CiEvidence = 'dist/ci-local-attempt-01'
& $CiPython -X utf8 -m scripts.ci static --output "$CiEvidence/static"
if ($LASTEXITCODE -ne 0) { throw 'static失败，查看report.json' }
& $CiPython -X utf8 -m scripts.ci regression --output "$CiEvidence/regression"
if ($LASTEXITCODE -ne 0) { throw 'regression失败，查看tests.log及报告' }
& $CiPython -X utf8 -m scripts.ci package --output "$CiEvidence/package"
if ($LASTEXITCODE -ne 0) { throw 'package失败，查看report.json中的commands' }
& $CiPython -X utf8 -m scripts.ci gate --artifacts $CiEvidence --output "$CiEvidence/gate"
if ($LASTEXITCODE -ne 0) { throw '汇总门禁失败' }
```

预期每条退出 0，并打印对应的 `{"kind":"...","passed":true}`。回归详细进度写在 regression/tests.log 及其轮转备份；JSON 中应为 2002 项完整执行、零失败/错误/跳过。安装 probe 应为 39 个源码一致、headless=true；gate/jobs 三项均为 true。各报告在同一本机候选代码上产生、身份一致；修改代码后必须使用新一轮目录重新运行，不能拿旧报告凑门禁。

新增测试时正常运行静态检查即可，不需为数量增加更新基线。确需删除/重命名用例，先审查覆盖替代关系，再执行 `python -X utf8 -m scripts.ci inventory` 更新基线并审阅差异；日常 CI 不会自动更新基线来掩盖漏收。

## 8. 实施状态与云端启用

- [x] CI-02 基础脚本：静态、清单/报告校验、进程树管理、隔离无窗口 wheel smoke，及 10 项 CI 反例自检已落地。
- [x] CI-03 工作流：事件、超时、并发取消、最小权限、检查/汇总 job、产物上传及 Action SHA 已落地；actionlint v1.7.12 检查通过。
- [ ] CI-01 云端环境可行性：固定运行时已在本机下载、校验、执行；托管 Windows 2025 的 Job Object/控制台信号等仍需首跑验证。
- [ ] CI-04 云端实际试跑：本机结果见最新开发记录；尚未 push 或创建 PR，不能报告 Actions 已通过。
- [ ] CI-05 云端反例验证：本地自检覆盖错误/空/少执行/跳过、旧身份、缺安装证明及漏收；仍需受控失败 PR 验证真实云端失败与产物。
- [ ] CI-06 云端中断验证：同 PR 新提交取消旧运行、失败日志下载、cancelled/skipped 依赖不让汇总通过。
- [ ] CI-07 仓库门禁：首轮成功后确认实际 check 名，再配置 main/test 必需检查；当前不宣称远程分支已受本工作流保护。
- [ ] CI-08 可选扩展：定时正确性、可信桌面 runner 或兼容平台；每项附实际证据。

下一次推送包含本次文件的 `test`/`main`/`feature`/`codex/**` 分支会触发工作流；PR 目标为 main/test 时也触发。进入 GitHub → Actions → ZZY CI 查看各 job，下载本轮 artifact，核对 SHA/run ID/attempt。手动 Run workflow 通常需工作流已存在于默认分支，首次接入优先用已列出的 push/PR 事件。

CI 接入完成的标准是“真实触发、真实执行、错误能阻止通过、失败证据可取、安装确实来自 wheel、门禁对应实际检查”，不只是存在一份 YAML。最终发布仍须补齐本机 GUI、人工测试与同机性能证据。


## P10-01 / P10-06 门禁增量（2026-10-29）

核心discovery新增tests/test_contracts.py的14项，原2027项及1738外部CLI保留。核心package探针增加静态合约生成且用户文件副作用不发生，不装Web/Schema依赖。Web job额外安装[schema验证依赖](../../scripts/ci/contract-requirements.txt)，执行[安装探针](../../scripts/ci_web_installed_probe.py)：核对wheel全部运行时源码，复制必要测试/夹具到源码目录外，在Python -I下运行全部23项HTTP/Schema专项。导入来源必须是当前Python安装目录；不能把checkout源码当安装成功。云端结果须推送后另验，本轮只提交本地。静态、完整回归、安装证据见tests/p10和开发记录，旧章节历史数量不作为当前测试基线。

## P11优化与P12交付的门禁安排（计划）

2026-10-29新增P11优化、原交付阶段顺延P12，具体范围见[优化计划](../runtime/optimization-plan.md)。本轮仅更新文档，不新增CI作业或预填优化结果。P11实现时维持现有核心/独立Web依赖边界及static/regression/package/gate身份校验；2041核心、23HTTP/Schema是当前核对起点，新测试按实际清单增加，禁止少收集、skip或放宽契约。

每项先做适用专项与完整回归，最终冻结保留代码后确认完整核心、真实HTTP/Schema及源码外wheel安装都对应最终运行时/用例。低层优化同样要覆盖默认/shared、合约前置拒绝、SQLite/嵌入、失败/取消恢复；需要时增加安装探针而非只测源码。单项对照可用已验收相邻修订/内部参考路径，不能在共享服务中使用进程全局可变优化开关。

正式性能测量在固定本机串行执行，与CI回归分开；保存单项与累计原始样本、失败及退化，CI绿色不证明提速或GUI/人工通过。最终P11结论与P12放行复用[最终测试计划](final-test-plan.md)；原始云端/人工报告只按其版本和范围引用，不改写历史编号。
