# N5 原生 CLI、spec 运行器与发布验收

本报告记录 N5-01—05 的实现与证据。Python 仅作为黑盒编排器；被测 `zzy-native.exe` 不加载 CPython。

## 固定命令

```powershell
cmake --preset native-debug -S native_runtime
cmake --build build/native-debug --config Debug
ctest --test-dir build/native-debug -C Debug --output-on-failure --no-tests=error
cmake --preset native-release -S native_runtime
cmake --build build/native-release --config Release
ctest --test-dir build/native-release -C Release --output-on-failure --no-tests=error
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/test-cli.py --exe build/native-release/Release/zzy-native.exe
.\.venv\Scripts\python.exe -X utf8 native_runtime/tools/test-spec.py --exe build/native-release/Release/zzy-native.exe
```

## 已验证

- N5 spec/进程清单 19/19：空收集、收集错误、失败、超时、输出超额、文本诊断、stdin EOF/UTF-8、模块隔离、冻结源码快照、目录稳定顺序、真实控制台 Ctrl+C、worker 异常退出、强杀父进程后的 worker 结束和下一请求恢复。
- CLI 清单 83/83：公开命令、选项位置/缺失/非法值、限制边界、固定 lex/source-info 答案、失败恢复、无副作用 check、UTF-8 输出与错误诊断。
- native CTest 采用 `--no-tests=error`，并包含 `spec-process`、`cli-boundaries` 和 `native-ci-fingerprint`；源码指纹覆盖 C++/头文件/CMake/依赖/测试夹具及独立 native workflow。
- Release 安装 smoke 从源码外中文/空格目录运行；子进程 `PATH` 为空、`PYTHONPATH` 无效并移除虚拟环境变量。PE 依赖与实际加载模块没有 Python、PyPy、Tcl 或 Tk。

## 未验证和边界

本轮未断开网卡，离线结论限于不下载依赖和受控代理；未在缺少 VC Runtime 的干净机器运行。Sanitizer、其他平台和人工终端 Ctrl+C 仍未验证。Debug `/MDd` 仅开发验证，Release `/MD` 由系统 VC Runtime 提供。
