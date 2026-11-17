# N0 实际证据报告

日期 2026-11-17，分支 `codex/native-runtime-plan`。这份报告只覆盖 N0 原型，不把它写成完整 ZZY 后端。

## 环境

- Windows 11 `10.0.26200`，Windows x64；当前 PowerShell 工作目录含中文与空格。
- 可用编译器：`D:\software\mingw64\bin\g++.exe`，GCC 8.1.0，x86_64-win32-seh-rev0，C++17；Debug `-O0 -g`，Release `-O2 -DNDEBUG`，`-Wall -Wextra -Wpedantic -Werror`，静态 libgcc/libstdc++，系统 msvcrt。
- `cmake`、`ctest`、`cl`、`clang-cl` 在 PATH 及当前常见安装目录未找到；没有下载或安装工具链。MSVC `/MD`、`/MDd` 方案已冻结但未验证。
- 项目无第三方运行时依赖；CMake 不含 FetchContent 或联网步骤。Unicode 15.0.0、BigInt 自有 limb 方案和 default-v1 资源策略见决策文件。

## 实际命令

```powershell
& native_runtime/tools/build-direct.ps1 -Configuration Debug
& build/native-direct-debug/zzy-native.exe info
& build/native-direct-debug/native-protocol-tests.exe
& build/native-direct-debug/native-heap-tests.exe
& native_runtime/tools/build-direct.ps1 -Configuration Release
& build/native-direct-release/native-heap-tests.exe
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-debug -Output dist/native-n0-debug-contract-final
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-release -Output dist/native-n0-release-contract-final
```

Debug/Release 直接编译退出 0；协议 3/3、堆 12/12。最终 [Debug 原始报告](../../benchmarks/results/native/n0/debug.json)、[Release 原始报告](../../benchmarks/results/native/n0/release.json)保留产物 SHA、PE imports、源码指纹、固定命令、stdout/stderr 和退出码。源码与产物 SHA-256 已独立重新计算，逐项匹配。
每种构建均记录 **32 个进程用例**：info/help/version、5 个 E402 拒绝、2 个 E401 参数失败、协议、12 个单堆用例、空集合失败、资源/取消/内部错误/恢复、真实超时终止及恢复、依赖探针；全部达到固定期望。
其中一条有意超时记录 timed_out=true，保留实际强杀退出码、purpose 和 process_exited；不是语言成功样本。

脚本验证了：

- 有效 `.zzy` 副作用文件不存在；source-info/lex/check/run/test 在读取源码前 E402、空 stdout、schema v1、file/span 为 null、退出 2，不调用 Python。
- 资源失败 E211/退出 1、取消 `kind=cancelled`/code=null/退出 130、内部错误不伪装用户错误；每种失败后逻辑对象/槽/载荷为 0，下一次 success 仍成功。
- `PATH` 为空、`PYTHONPATH=unusable-python-path`、工作目录为中文空格目录；进程模块和 PE 导入中无 Python、Tk、Tcl、NumPy。Windows 控制台的系统 `conhost.exe` 被单独识别为系统辅助进程，非运行时子进程。
- 堆实验验证 5000 节点环、1000 次重复收集、别名根保留、跨请求/旧 owner/关闭句柄拒绝、事务配额失败归还和空测试集合非零。

## 修复与相关回归

- 首次验收拒绝 CRT 的 CRLF；定位原始字节后改为二进制流输出 UTF-8/LF，没有放宽输出期望。
- 依赖探针首轮把系统控制台 conhost 当作运行时子进程；补进程名证据后按 Windows 系统辅助进程分类，仍拒绝其他未登记子进程/Python。PE 导入包括 MinGW 堆目标的 USER32，允许的系统集合固定为 KERNEL32/msvcrt/USER32，不任意放行 DLL。失败原件见 [CRLF](../../benchmarks/results/native/n0/failed-crlf.json)、[PID-only](../../benchmarks/results/native/n0/failed-conhost-pid.json)、[conhost-name](../../benchmarks/results/native/n0/failed-conhost-name.json)。
- `.\.venv\Scripts\python.exe -X utf8 -m unittest native_runtime.tests.test_inventory tests.test_resources tests.test_diagnostics tests.test_p02_runtime tests.test_p03_runtime tests.test_p04_runtime -q`：51/51、1.820秒、退出0。
- 固定语言 [golden](../../benchmarks/results/native/n0/golden-python.json)：6/6 Python CLI、退出0；原生尚不执行这些程序。首次误用 --manifest，及 Map 内部标签与 data.kind 小写标签混淆，均已按正式契约纠正并留开发日志。
- `.\.venv\Scripts\python.exe -X utf8 -m scripts.ci static --output dist/native-n0-static-final`：退出0，passed=true。这是已有 Python 静态门禁；C++ 另由两种构建的警告即错误验证。没有将该门禁当作 CMake/CTest 通过。
- 本轮没有重跑完整核心、HTTP、GUI、wheel 安装或性能测量；Python 运行时代码哈希与冻结盘点保持一致。没有沿用历史数字冒充本轮结果。

- 最终[资源计费审计](../../benchmarks/results/native/n0/resource-charge-audit.txt)发现物理节点/逻辑对象混淆：按 resources.md 和现有 Cell 存储规则先把 Map 固定期望改为1对象/2槽/4载荷，旧实现实际退出1；修正 Text/Cell 不增加 runtime_objects 后 Debug/Release 各32例重跑通过。GC 仍回收相同物理节点，不放宽语言配额。

## 未验证 / 不得外推

没有 CMake/CTest/MSVC，因此 preset configure/build/CTest/install 不能执行。实际尝试 cmake/ctest 命令得到 CommandNotFoundException，记录 exit_code=null（未启动），见[工具链原始记录](../../benchmarks/results/native/n0/toolchain.json)。N0 总出口不能标记通过；直接 GCC 编译不能替代 CMake 验收。
真实 Windows Ctrl+C、Sanitizer、源码外 CMake 安装、完整原生 run/check/test、Unicode 数据表、BigInt limb 算法、RSS/性能和所有宿主迁移均未验证。[人工与安装步骤](windows-acceptance.md)没有预填通过。真实超时强杀只验证 OS 回收与随后恢复，不能声称强杀执行了 RAII。

Python 解释器、P12/P13、默认入口和所有原有测试未改变。只有 `info` 可用；原生路线仍不得称为完整 ZZY，N1 不应开始，直到工具链阻塞被解决并按计划重新验收。
