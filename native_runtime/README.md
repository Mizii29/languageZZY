# ZZY native runtime：N0 原型

独立 C++17 AST 解释器路线；**当前只有 info/帮助、能力拒绝协议和堆生命周期实验，不运行 ZZY**。
默认入口仍为 `python -m zzy`。状态见 [todo](../docs/development/todo.md)、
[能力矩阵](../docs/development/native-runtime-capability.md)、[决策](../docs/development/native-runtime-decisions.md)。

## 已实测：现有 GCC 直接编译

从仓库根目录在 PowerShell 执行；只使用本机已有 `g++.exe`，不下载、不改系统 PATH：

```powershell
& native_runtime/tools/build-direct.ps1 -Configuration Debug
& build/native-direct-debug/zzy-native.exe info
& build/native-direct-debug/native-protocol-tests.exe
& build/native-direct-debug/zzy-native.exe run examples/hello.zzy --diagnostic-format json
# 最后一条预期 E402/退出 2，stdout 为空；不是执行成功。
```

本机 GCC 8.1.0、x64/SEH/Win32 线程模型、Windows 11 10.0.26200；Debug -O0 -g，Release -O2 -DNDEBUG；均启用 C++17 和警告即错误。
MinGW 原型静态链接 libgcc/libstdc++，系统 msvcrt；最低编译目标 Windows 10（只在当前 Windows 11 机器实测）。无项目级第三方库。
直接编译不是 CMake/CTest 或正式 MSVC 安装验收。

## 待工具齐备：离线 CMake/CTest 门禁

当前机器没有 CMake/CTest/MSVC/clang-cl，以下命令已提供配置，但**尚未运行成功**；没有安装工具链。
在已有 VS 2022 x64 开发终端和 CMake >=3.21 的环境中，从根目录运行：

```powershell
cmake --preset native-debug -S native_runtime
cmake --build build/native-debug --config Debug
ctest --test-dir build/native-debug -C Debug --output-on-failure --no-tests=error
cmake --preset native-release -S native_runtime
cmake --build build/native-release --config Release
ctest --test-dir build/native-release -C Release --output-on-failure --no-tests=error
cmake --install build/native-release --config Release --prefix dist/native-stage
& dist/native-stage/bin/zzy-native.exe info
```

Visual Studio 多配置生成器的 exe 在 build/native-debug/Debug 和 build/native-release/Release。
MinGW 的辅助 preset 为 native-mingw-debug/native-mingw-release，生成到 build/native-mingw-*，仍须 CMake/CTest；不能用直接编译结果替代。
所有目标/测试只使用本仓库和系统库，没有 FetchContent、联网配置或 Python 调用。
CTest 注册非空协议、CLI 与堆测试，并设超时；必须保留 --no-tests=error。

## 接口和限制

`info` 输出 schema v1、版本、stage、编译器/CRT/位数、当前命令能力和声明的 default-v1 策略/指纹。
原生 host_decimal_digits=0，effective_decimal_digits=4096；这是策略声明，完整语言资源检查尚未接入。
`--limits` 尚不可用；不忽略它或伪报已生效。`--diagnostic-format text|json` 支持放在命令前后。
source-info/lex/check/run/test 一律在读取源码前 E402/2；无 Python fallback，未知命令/参数 E401/2。
不提供 build 命令；不加载 Web、GUI 或其他 Python 宿主。

堆原型及独立 .zzy 固定期望见 tests；它们不代表 Parser/Resolver 已移植，也没有完整语言性能结论。
原生依赖/取消/安装验证只能证明当前产物，未来 N5/N8 仍需完整 run/check/test 与宿主进程树验收。

当前直接原型的逐命令、固定期望、源码外报告和未验证边界见 [N0 报告](tests/n0-report.md)。
