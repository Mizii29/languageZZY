# ZZY native runtime：N1 源码与词法

独立 C++17 AST 解释器路线。**已实现 info/source-info/lex；尚无 AST 解析、check 或语言执行。** Python 仍为默认入口，check/run/test 均 E402/2，无 Python fallback。

**N0-03 和 N1 的正式 CMake/MSVC 构建验收已于2026-11-18补齐**：Debug/Release 各32/32 CTest，Release安装及源码外发布副本通过。先前GCC顺序例外作为历史保留。状态见 [todo](../docs/development/todo.md)、[集中前端契约](../docs/development/native-frontend-contract.md)、[能力矩阵](../docs/development/native-runtime-capability.md)、[正式报告](tests/msvc-report.md)。下一阶段N2，本轮没有实现。

## 已有 GCC 的本地命令

从仓库根目录 PowerShell 执行，不下载工具链、不修改系统 PATH：

```powershell
& native_runtime/tools/build-direct.ps1 -Configuration Debug
& build/native-direct-debug/zzy-native.exe info
& build/native-direct-debug/zzy-native.exe source-info examples/hello.zzy
& build/native-direct-debug/zzy-native.exe lex examples/hello.zzy --diagnostic-format json
& build/native-direct-debug/zzy-native.exe check examples/hello.zzy --diagnostic-format json
# check 预期 E402/退出2，不能写成检查成功。
& build/native-direct-debug/native-frontend-tests.exe
& native_runtime/tools/test-fixed.ps1 -Executable build/native-direct-debug/zzy-native.exe -Output dist/n1-fixed-new.json
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-debug -Output dist/n1-external-new-debug
& native_runtime/tools/build-direct.ps1 -Configuration Release
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-release -Configuration Release -Output dist/n1-external-new-release
```

Output 必须为新路径。12 个原生前端用例含默认配额边界；纯 PowerShell 固定清单含87用例，不依赖 Python。N0 堆12例和协议/生命周期仍保留；能力未实现或无测试选择必须非零。

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

Visual Studio是多配置生成器：EXE分别在build/native-debug/Debug与build/native-release/Release。CTest实际收集并通过32项：协议/CLI、堆12、生命周期4、前端12和纯PowerShell固定清单（87项）；不能省略 --no-tests=error。configure/build/test/install不下载依赖、不调用Python。

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

每配置47过程场景含1项预期强杀超时（与46条正常完成记录分列），安装及发布副本各9项smoke；check/run/test必须E402/2且无用户副作用。子进程PATH为空、PYTHONPATH无效；报告保留PE导入、实际CLI模块/进程树、加载路径、版本、源码及EXE哈希。acceptance默认DirectGCC保持旧入口，MSVC须显式传BuildOrigin/Configuration/CMakeBuildDirectory/Dumpbin，不能冒用MinGW报告标签。

MSVC Debug /MDd仅开发机测试，不分发；Release /MD使用本机已有Microsoft VC runtime14.50.35719.0与系统UCRT。发布目录只含Release EXE，未私装或附带运行库。缺CRT干净机器尚未验证，不能承诺任意Windows裸机直接运行。已有MinGW辅助preset和clang-cl没有在本轮验证。

真实手动Ctrl+C、Sanitizer、其他平台/Windows10、完整Python/Web/GUI回归与性能本轮未验证。自动扫描取消、独立安全点、进程超时退出/恢复单列于[正式证据](tests/msvc-report.md)，不代替人工操作。N0/N1技术出口满足；下一项N2-01 Parser/AST，本轮停止，Python仍为默认入口。
