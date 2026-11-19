# ZZY native runtime：核心宿主与 Sketch headless 子集

独立 C++17 AST 解释器。原生 `run` 执行核心 ZZY，已接入 `io`、`array`、`text`、`math`、`data` 和 `unit` 的 35 个冻结核心接口，含 UTF-8 文件/原子保存和严格 JSON；MSVC 默认构建另支持 `db.transaction`、`db.query`。`check` 仍只静态准备。未移植的宿主能力执行时报告 E402/1；`test` 报告 E402/2，留给 N5。Python 仍为默认入口，原生进程不回退 Python。

验收范围及产物见 [N4-04报告](tests/n4-04-report.md)、[N4-03报告](tests/n4-03-report.md)、[N4-02报告](tests/n4-02-report.md)、[N4-01报告](tests/n4-01-report.md)、[N3报告](tests/n3-report.md) 与 [能力矩阵](../docs/development/native-runtime-capability.md)。前端历史保存在 [N2报告](tests/n2-report.md)；静态入口见 [Program契约](../docs/development/native-program-contract.md)。

## 在本机运行核心程序

完成下文 Release 构建后，从仓库根目录执行：

```powershell
& build/native-release/Release/zzy-native.exe info
& build/native-release/Release/zzy-native.exe check examples/hello.zzy --diagnostic-format json
& build/native-release/Release/zzy-native.exe run native_runtime/examples/core-library.zzy --diagnostic-format json
```

原生 `run` 支持 `--limits FILE`。输出和取消使用同一请求上下文，错误或取消会清理请求堆；阻塞在 stdin 上的读取不能由运行时安全点强制中断。SQLite 使用已安装 Windows 系统组件，不下载库；非 db 的核心执行不加载它。N1/N2 的 GCC 8.1.0 结果为历史证据，当前 SQLite 包只声明 MSVC 已验收。

## 正式 CMake/MSVC 命令（本机已实测）

本机已有CMake/CTest4.5.0、VS2022 Build Tools、MSVC19.40.33812.0、SDK10.0.22000.0。只为当前PowerShell会话添加CMake路径；不下载工具链、不修改系统PATH。每步检查退出码，失败立即停止：

```powershell
$env:Path = "$env:LOCALAPPDATA\Programs\CMake\4.5.0\bin;$env:Path"
cmake --preset native-debug -S native_runtime
if ($LASTEXITCODE -ne 0) { throw 'Debug configure failed' }
cmake --build build/native-debug --config Debug
if ($LASTEXITCODE -ne 0) { throw 'Debug build failed' }
ctest --test-dir build/native-debug -C Debug --output-on-failure --no-tests=error
if ($LASTEXITCODE -ne 0) { throw 'Debug CTest failed' }
cmake --preset native-release -S native_runtime
if ($LASTEXITCODE -ne 0) { throw 'Release configure failed' }
cmake --build build/native-release --config Release
if ($LASTEXITCODE -ne 0) { throw 'Release build failed' }
ctest --test-dir build/native-release -C Release --output-on-failure --no-tests=error
if ($LASTEXITCODE -ne 0) { throw 'Release CTest failed' }
cmake --install build/native-release --config Release --prefix dist/native-stage
if ($LASTEXITCODE -ne 0) { throw 'Release install failed' }
& native_runtime/tools/install-smoke.ps1 -Executable dist/native-stage/bin/zzy-native.exe -Output dist/native-installed-smoke-new.json
```

Visual Studio 是多配置生成器；EXE 在 `build/native-debug/Debug` 和 `build/native-release/Release`。当前默认 CTest 清单为 78 项，保留 N4-04 的 76 项，新增 `library-sketch-geometry` 和 `sketch-geometry-fixed`；不能省略 `--no-tests=error`。构建和安装不下载依赖；启用 Web 且启用测试时，CTest 使用 Python 3.10+ 标准库作为 HTTP 测试客户端，可用 `-DZZY_NATIVE_WEB_TEST_PYTHON=绝对路径` 指定。两个原生程序运行时都不依赖 Python。

源码外专项与发布副本复现（Output和发布目录必须新建）：

```powershell
$nativeDumpbin = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.40.33807\bin\Hostx64\x64\dumpbin.exe'
& native_runtime/tools/acceptance.ps1 -BuildOrigin CMakeMSVC -Configuration Debug -CMakeBuildDirectory build/native-debug -BuildDirectory build/native-debug/Debug -Dumpbin $nativeDumpbin -Output dist/native-msvc-debug-new
$nativePublish = Join-Path $env:TEMP ('ZZY 发布 中文 空格 '+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $nativePublish -ErrorAction Stop | Out-Null
Get-ChildItem -LiteralPath dist/native-stage/bin -File | Copy-Item -Destination $nativePublish -ErrorAction Stop
& native_runtime/tools/install-smoke.ps1 -Executable (Join-Path $nativePublish 'zzy-native.exe') -Output dist/native-published-smoke-new.json
& native_runtime/tools/acceptance.ps1 -BuildOrigin CMakeMSVC -Configuration Release -CMakeBuildDirectory build/native-release -BuildDirectory build/native-release/Release -Dumpbin $nativeDumpbin -InstalledExecutable (Join-Path $nativePublish 'zzy-native.exe') -Output dist/native-msvc-release-new
& native_runtime/tools/test-fixed.ps1 -Executable build/native-debug/Debug/zzy-native.exe -Output dist/native-msvc-fixed-debug-new.json
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-cli.py --exe build/native-debug/Debug/zzy-native.exe --output dist/native-msvc-cli-debug-new.json
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-core-existing.py --exe build/native-debug/Debug/zzy-native.exe --output dist/native-msvc-core-debug-new.json
if ($LASTEXITCODE -ne 0) { throw 'CLI boundary tests failed' }
# 固定清单、CLI专项另对 build/native-release/Release/zzy-native.exe 执行，Output换新文件。
```

每配置的验收包含静态检查、核心运行、生命周期及无 Python 检查。子进程 PATH 为空、PYTHONPATH 无效；报告保留 PE 导入、实际 CLI 模块/进程树、加载路径、版本、源码及 EXE 哈希。MSVC 需显式指定 BuildOrigin、Configuration 和 Dumpbin。Python 只协调既有固定清单，不提供原生运行时，也不生成答案。所有证据路径须为新路径。

MSVC Debug /MDd仅开发机测试，不分发；Release /MD使用本机已有Microsoft VC runtime14.50.35719.0与系统UCRT。发布目录包含 Release EXE，启用 Web 时附带 MIT 许可证。未私装或附带运行库。缺CRT干净机器尚未验证，不能承诺任意Windows裸机直接运行。已有MinGW辅助preset和clang-cl没有在本轮验证。

真实手动 Ctrl+C、Sanitizer、其他平台、完整 Python/GUI 回归与性能未验收。N4-01—04 已满足各自子任务；下一项为 N4-05 Sketch headless，N4-06 GUI 仍待实现。

## 原生 Web 演示

MSVC 默认构建并安装独立 `zzy-native-web.exe`，仅监听本机。通过 `-DZZY_NATIVE_WEB=OFF` 关闭该产物，核心入口继续可用。正式接口和限制见 [Web 集中契约](../docs/runtime/web.md#n4-04-原生-http-宿主)。

```powershell
.\build\native-release\Release\zzy-native-web.exe examples/web/app.zzy --route GET /api/hello hello --route POST /api/greet greet --page examples/web/index.html --port 8001
```

打开 [http://127.0.0.1:8001/](http://127.0.0.1:8001/) 使用同源 GET/POST 页面，或在另一终端执行：

```powershell
curl.exe http://127.0.0.1:8001/api/hello
Invoke-RestMethod http://127.0.0.1:8001/api/greet -Method Post -ContentType application/json -Body '{"name":"ZZY"}'
```

终端 Ctrl+C 关闭服务。shape 合约可静态导出，也可以在服务启动时启用：

```powershell
.\build\native-release\Release\zzy-native-web.exe examples/contracts/app.zzy --route POST /api/tasks submit --contracts examples/contracts/routes.json --openapi
.\build\native-release\Release\zzy-native-web.exe examples/contracts/app.zzy --route POST /api/tasks submit --contracts examples/contracts/routes.json --shared --port 8002
```

在另一终端向 `http://127.0.0.1:8002/api/tasks` POST `{"task":{"title":"ZZY"}}`，或 GET `/openapi.json`。POST `{"task":{}}` 会得到 HTTP 422，路径为 `body.task.title`。省略 `--shared` 即回到默认逐请求初始化。

## 原生 SQLite 演示与依赖

使用已安装 Windows SDK 的 `winsqlite/winsqlite3.h`，运行时固定从 System32 加载 `winsqlite3.dll`；不附带 DLL。本机组件为微软签名 SQLite 3.53.4，最低 API 3.29.0，来源与哈希见 N4-03 报告。系统补丁由 Windows 更新维护。info 的 `sqlite_enabled` 表示构建开关；实际打开失败时返回 E401，不声称每台 Windows 都已具备该组件。核心/check/headless 不因该构建开关初始化 SQLite、Web 或 GUI。

集中契约见 [N4 宿主接入](../docs/development/native-stdlib-contract.md#n4-03-sqlite) 和 [SQLite 语言边界](../docs/runtime/web.md#p08-04-sqlite契约)。`db.transaction(path, callback)` 使用同线程独立连接，回调成功 Result 提交、失败 Result 回滚，错误/取消先清理再传播；`db.query(sql, params)` 使用参数绑定，返回按列顺序的行数组。Bool/Blob 不自动转换，Int 只接受有符号 64 位，SQL 与锁等待分别受 1s/250ms 期限约束。路径和 SQL 来自受信任程序；业务输入由 ZZY 校验。

从仓库根目录在新工作目录演示两次重启持久化：

```powershell
$nativeExe = (Resolve-Path build/native-release/Release/zzy-native.exe).Path
$nativeSqlite = (Resolve-Path native_runtime/examples/sqlite.zzy).Path
$nativeDemo = Join-Path $env:TEMP ('ZZY SQLite 演示 '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $nativeDemo -ErrorAction Stop | Out-Null
Push-Location $nativeDemo
try {
    & $nativeExe run $nativeSqlite --diagnostic-format json
    if ($LASTEXITCODE) { throw 'first transaction failed' }
    & $nativeExe run $nativeSqlite --diagnostic-format json
    if ($LASTEXITCODE) { throw 'restart persistence failed' }
} finally { Pop-Location }
# 首次 [[1, 原生 SQLite 留言]]；第二次 [[1, 原生 SQLite 留言], [2, 原生 SQLite 留言]]，均包在成功 Result 中。
& native_runtime/tools/test-sqlite.ps1 -Executable $nativeExe -Output dist/native-sqlite-new.json
& native_runtime/tools/test-sqlite-modules.ps1 -Executable $nativeExe -Output dist/native-sqlite-modules-new.json
```

只构建不含 SQLite 的核心包时，使用独立构建目录：

```powershell
cmake -S native_runtime -B build/native-sqlite-off -G 'Visual Studio 17 2022' -A x64 -DZZY_NATIVE_SQLITE=OFF
cmake --build build/native-sqlite-off --config Release --target zzy-native
ctest --test-dir build/native-sqlite-off -C Release -R '^(cli-info|sqlite-disabled)$' --output-on-failure --no-tests=error
```

OFF 的 info 为 false，check 仍静态识别签名，运行 db 返回带源码位置的 E402/1。此命令只验证两个 OFF 专项，不等同于 OFF 全量 CTest；ON 的正式 75 项见上文。MinGW 的 SQLite 宿主当前未支持，显式 ON 在配置时拒绝。

## 文件与严格 JSON 演示

从仓库根目录运行以下命令，在新建临时目录生成 `native-state.json`，不会修改应用数据：

```powershell
$nativeExe = (Resolve-Path build/native-release/Release/zzy-native.exe).Path
$nativeExample = (Resolve-Path native_runtime/examples/file-json.zzy).Path
$nativeDemo = Join-Path $env:TEMP ('ZZY 文件演示 '+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $nativeDemo -ErrorAction Stop | Out-Null
Push-Location $nativeDemo
try {
    & $nativeExe run $nativeExample --diagnostic-format json
    if ($LASTEXITCODE -ne 0) { throw 'File/JSON demo failed' }
    Get-Content -LiteralPath native-state.json -Raw -Encoding utf8
} finally { Pop-Location }
```

固定输出为 `(^_^)(ZZY 原生文件示例😀)`，文件含相同标题、`ids:[1,9007199254740993]` 和 `version:1`。路径相对工作目录；保存不创建父目录。文件保留 BOM/CRLF，JSON 拒绝重复键、孤立代理、不支持值和环；不自动解包 Result 或唤醒 Lazy。详细资源和取消/提交边界仅维护在[标准库原生契约](../docs/development/native-stdlib-contract.md)。

专项复现（Output 必须新建）：

```powershell
& native_runtime/tools/test-library.ps1 -Executable build/native-release/Release/zzy-native.exe -FileJson -Output dist/native-json-new.json
& native_runtime/tools/test-files.ps1 -Executable build/native-release/Release/zzy-native.exe -Output dist/native-files-new.json
```

## 原生 Sketch headless

现在可绘制图形、编辑图层、分组撤销/重做，并生成 SVG。用下列命令运行固定用例（输出报告路径需新建）：

```powershell
pwsh -NoProfile -File native_runtime/tools/test-sketch.ps1 -Executable build/native-release/Release/zzy-native.exe -Output dist/native-sketch-new.json
```

原生 `check` 和绘图运行无需 GUI。项目 v1、对象编辑、Drawing、回放、事件与 GUI 未接入，详见 [N4-05 首批报告](tests/n4-05-geometry-report.md)。

在新的临时目录执行独立示例，生成可用浏览器打开的 SVG：

```powershell
$sketchExe = (Resolve-Path build/native-release/Release/zzy-native.exe).Path
$sketchSource = (Resolve-Path native_runtime/examples/sketch-geometry.zzy).Path
$sketchDemo = Join-Path $env:TEMP ("ZZY 画笔演示 " + [guid]::NewGuid())
New-Item -ItemType Directory -Path $sketchDemo | Out-Null
Push-Location $sketchDemo
try {
    & $sketchExe run $sketchSource --diagnostic-format json
    if ($LASTEXITCODE -ne 0) { throw "Sketch demo failed" }
    Get-Item native-sketch.svg
} finally { Pop-Location }
```
