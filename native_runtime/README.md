# ZZY native runtime：N1 源码与词法

独立 C++17 AST 解释器路线。**已实现 info/source-info/lex；尚无 AST 解析、check 或语言执行。** Python 仍为默认入口，check/run/test 均 E402/2，无 Python fallback。

用户授权先用已有 GCC 完成 N1，暂缓 N0-03；**N1 实现与 GCC 验证完成，正式 CMake/CTest 验收待补**。N0 总出口未通过，不进入 N2。状态见 [todo](../docs/development/todo.md)、[集中前端契约](../docs/development/native-frontend-contract.md)、[能力矩阵](../docs/development/native-runtime-capability.md)、[N1证据](tests/n1-report.md)。

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
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-release -Output dist/n1-external-new-release
```

Output 必须为新路径。12 个原生前端用例含默认配额边界；纯 PowerShell 固定清单含87用例，不依赖 Python。N0 堆12例和协议/生命周期仍保留；能力未实现或无测试选择必须非零。

开发协调器另验证同一独立固定清单和 CLI 边界；仅协调器使用 Python，不生成运行时答案：

```powershell
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-frontend.py --exe build/native-direct-debug/zzy-native.exe --output dist/n1-fixed-python-new.json
& ./.venv/Scripts/python.exe -X utf8 native_runtime/tools/test-cli.py --exe build/native-direct-debug/zzy-native.exe --output dist/n1-cli-new.json
& ./.venv/Scripts/python.exe -X utf8 -m unittest native_runtime.tests.test_inventory -q
```

GCC8.1.0/x64/SEH/Win32；Debug -O0 -g，Release -O2 -DNDEBUG；C++17，-Wall/-Wextra/-Wpedantic/-Werror，静态 libgcc/libstdc++、系统 msvcrt；最低编译目标 Windows10，只在当前 Windows11 实测。没有项目级第三方库。旧 GCC std::filesystem 不可用，路径用 Win32 Unicode W API；主入口 wmain/MinGW -municode。不加载 GUI、ASGI、SQLite 或 Python。

## 以后必须对最新代码补跑的正式门禁

本机仍缺 CMake/CTest/MSVC/clang-cl，没有安装工具链。以下只提供复现命令，**尚未通过**；在已有 VS2022 x64 开发终端、CMake>=3.21 和 PowerShell 环境执行：

```powershell
cmake --preset native-debug -S native_runtime
cmake --build build/native-debug --config Debug
ctest --test-dir build/native-debug -C Debug --output-on-failure --no-tests=error
cmake --preset native-release -S native_runtime
cmake --build build/native-release --config Release
ctest --test-dir build/native-release -C Release --output-on-failure --no-tests=error
cmake --install build/native-release --config Release --prefix dist/native-stage
& native_runtime/tools/install-smoke.ps1 -Executable dist/native-stage/bin/zzy-native.exe -Output dist/native-installed-smoke-new.json
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-release/Release -Output dist/native-cmake-external-new
```

CTest 注册32项：协议/CLI、堆12、生命周期4、前端12和纯PowerShell固定清单；不能省略 --no-tests=error。configure/build/test/install 都不联网、不调用 Python。MSVC Debug /MDd，不分发；Release /MD 的 CRT 分发/缺失诊断尚待正式验收。

已有 MinGW 可选配置 native-mingw-debug/native-mingw-release 也必须经 CMake/CTest/install，不能用 direct 构建代替。源码外 smoke 脚本本轮仅针对直接 GCC EXE 测试，**不算 cmake --install 成功**。

真实手动 Ctrl+C、MSVC/clang-cl、安装、其他平台和 GUI 本轮未验证。自动扫描线程取消、独立安全点、进程超时退出/恢复单列于证据；没有相对 Python/C 的性能或内存结论。N2 为后续新授权范围，先补 N0-03 正式门禁。
