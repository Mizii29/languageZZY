# ZZY native runtime：N2 静态 Program 与 check

独立 C++17 AST 解释器路线。**已实现 info/source-info/lex、Parser、Resolver、Program、模块准备、check 和 program-info；没有运行时求值。** Python 仍为默认入口，run/test 均 E402/2，无 Python fallback。

**N0-03/N1正式验收和最新N2补跑均已完成**：N1历史为每配置32/32；最新N2 CMake/MSVC Debug、Release各44/44 CTest，每配置固定check850/850、过程58条，Release安装和源码外副本各9/9。实际产物、失败修复与限制见 [N2报告](tests/n2-report.md)、[Program契约](../docs/development/native-program-contract.md)。状态以 [todo](../docs/development/todo.md)、[能力矩阵](../docs/development/native-runtime-capability.md)为准；旧产物证据不外推到修改后的代码。

## 已有 GCC 的本地命令

从仓库根目录 PowerShell 执行，不下载工具链、不修改系统 PATH：

```powershell
& native_runtime/tools/build-direct.ps1 -Configuration Debug
& build/native-direct-debug/zzy-native.exe info
& build/native-direct-debug/zzy-native.exe source-info examples/hello.zzy
& build/native-direct-debug/zzy-native.exe lex examples/hello.zzy --diagnostic-format json
& build/native-direct-debug/zzy-native.exe check examples/hello.zzy --diagnostic-format json
& build/native-direct-debug/zzy-native.exe program-info examples/hello.zzy > dist/native-n2-program.jsonl
& build/native-direct-debug/native-frontend-tests.exe
& native_runtime/tools/test-fixed.ps1 -Executable build/native-direct-debug/zzy-native.exe -Output dist/n1-fixed-new.json
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-debug -Output dist/n1-external-new-debug
& native_runtime/tools/build-direct.ps1 -Configuration Release
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-release -Configuration Release -Output dist/n1-external-new-release
```

Output 必须为新路径。12 个原生前端用例含默认配额边界；纯 PowerShell 固定清单含87用例，N2 check 清单含848条既有固定期望并加2个静态副作用夹具，不依赖 Python。Program 原生单测10例覆盖 AST、捕获、模块图、字面量、资源和取消；能力未实现或无测试选择必须非零。

开发协调器另验证同一独立固定清单和 CLI 边界；仅协调器使用 Python，不生成运行时答案：

```powershell
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-frontend.py --exe build/native-direct-debug/zzy-native.exe --output dist/n1-fixed-python-new.json
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-cli.py --exe build/native-direct-debug/zzy-native.exe --output dist/n1-cli-new.json
& ./.venv/Scripts/python.exe -X utf8 -m unittest native_runtime.tests.test_inventory -q
```

GCC8.1.0/x64/SEH/Win32；Debug -O0 -g，Release -O2 -DNDEBUG；C++17，-Wall/-Wextra/-Wpedantic/-Werror，静态 libgcc/libstdc++、系统 msvcrt；最低编译目标 Windows10，只在当前 Windows11 实测。没有项目级第三方库。旧 GCC std::filesystem 不可用，路径用 Win32 Unicode W API；主入口 wmain/MinGW -municode。不加载 GUI、ASGI、SQLite 或 Python。

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

Visual Studio是多配置生成器：EXE分别在build/native-debug/Debug与build/native-release/Release。N2 CMake更新后的清单应为44项：N1原有32项，另加Program固定清单、10项Program单测和空选择门禁；不能省略 --no-tests=error。configure/build/test/install不下载依赖、不调用Python。

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
if ($LASTEXITCODE -ne 0) { throw 'CLI boundary tests failed' }
# 固定清单、CLI专项另对 build/native-release/Release/zzy-native.exe 执行，Output换新文件。
```

每配置的N2 acceptance包含静态 check、Program 单测和无 Python 边界；run/test仍E402/2，check成功0且无用户副作用。子进程PATH为空、PYTHONPATH无效；报告保留PE导入、实际CLI模块/进程树、加载路径、版本、源码及EXE哈希。acceptance默认DirectGCC保持旧入口，MSVC须显式传BuildOrigin/Configuration/Dumpbin；不能冒用MinGW报告标签。最新正式 CMake/CTest 已实际重跑，证据见 benchmarks/results/native/n2-msvc-20261118；后续源码变化须按影响范围重验，直接 MSVC 证据不替代正式构建。

MSVC Debug /MDd仅开发机测试，不分发；Release /MD使用本机已有Microsoft VC runtime14.50.35719.0与系统UCRT。发布目录只含Release EXE，未私装或附带运行库。缺CRT干净机器尚未验证，不能承诺任意Windows裸机直接运行。已有MinGW辅助preset和clang-cl没有在本轮验证。

真实手动Ctrl+C、Sanitizer、其他平台/Windows10、完整Python/Web/GUI回归与性能本轮未验证；实际多请求执行隔离留N3/N6。自动准备取消、独立安全点、进程超时退出/恢复单列于新证据目录，不代替人工操作。N2-01—04已完成，下一项N3值模型与运行时，Python仍为默认入口。
