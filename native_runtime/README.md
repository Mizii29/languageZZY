# ZZY native runtime：N4-01 核心标准库

独立 C++17 AST 解释器。原生 `run` 执行核心 ZZY，并在 N4-01 接入 `io`、`array`、`text`、`math`、`data` 和 `unit` 的冻结核心接口。`check` 仍只静态准备。未移植的宿主能力执行时报告 E402/1；`test` 报告 E402/2，留给 N5。Python 仍为默认入口，原生进程不回退 Python。

验收范围及产物见 [N4-01报告](tests/n4-01-report.md)、[N3报告](tests/n3-report.md) 与 [能力矩阵](../docs/development/native-runtime-capability.md)。前端历史保存在 [N2报告](tests/n2-report.md)；静态入口见 [Program契约](../docs/development/native-program-contract.md)。

## 在本机运行核心程序

完成下文 Release 构建后，从仓库根目录执行：

```powershell
& build/native-release/Release/zzy-native.exe info
& build/native-release/Release/zzy-native.exe check examples/hello.zzy --diagnostic-format json
& build/native-release/Release/zzy-native.exe run native_runtime/examples/core-library.zzy --diagnostic-format json
```

原生 `run` 支持 `--limits FILE`。输出和取消使用同一请求上下文，错误或取消会清理请求堆；阻塞在 stdin 上的读取不能由运行时安全点强制中断。当前构建不使用第三方运行时库。N1/N2 的 GCC 8.1.0 结果为历史证据，N3 不声明该工具链已验收。

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

Visual Studio 是多配置生成器；EXE 在 `build/native-debug/Debug` 和 `build/native-release/Release`。N4-01 CTest 清单为 64 项，包含 N3 的 57 项、5 个库探针、空选择检查和 126 项独立固定库清单；不能省略 `--no-tests=error`。配置、构建、CTest 和安装不下载依赖、不调用 Python。

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

MSVC Debug /MDd仅开发机测试，不分发；Release /MD使用本机已有Microsoft VC runtime14.50.35719.0与系统UCRT。发布目录只含Release EXE，未私装或附带运行库。缺CRT干净机器尚未验证，不能承诺任意Windows裸机直接运行。已有MinGW辅助preset和clang-cl没有在本轮验证。

真实手动 Ctrl+C、Sanitizer、其他平台、完整 Python/Web/GUI 回归与性能未验收。文件/严格 JSON、SQLite、Web、Sketch headless/GUI 仍按 E402 延期；N4-01 不宣称完整 N4。N3 同进程连续请求探针和 N4-01 库探针覆盖错误、协作取消后恢复。下一项为 N4-02 文件与严格 JSON。
