# N0 Windows 验收与未完成门禁

本文件是可复制步骤，不是人工通过记录。当前结果见 [N0 报告](n0-report.md)；未实操的项保持未验证。

## 已有编译器的自动原型

仓库根目录执行：

```powershell
& native_runtime/tools/build-direct.ps1 -Configuration Debug
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-debug -Output dist/native-n0-new-debug
& native_runtime/tools/build-direct.ps1 -Configuration Release
& native_runtime/tools/acceptance.ps1 -BuildDirectory build/native-direct-release -Output dist/native-n0-new-release
```

每个新 Output 目录必须不存在；脚本不覆盖旧证据。原生产物复制到仓库以外的系统临时目录 `ZZY N0 <GUID>/中文 路径/bin`；保留目录和报告以供审阅，不自动递归删除。
程序进程的 PATH 清空、PYTHONPATH 无效；依赖检查使用父 PowerShell 的现有 objdump，仅是测试工具，不是 exe 的依赖。
固定预期为 32 条过程记录全部通过；其中一条是有意超时探针，必须记录 timed_out=true/实际强杀退出码/process_exited=true，不将其算作语言执行成功。
超时探针只持有本进程堆、不创建语言子进程；父脚本终止该进程并验证退出，再运行 success。硬杀不会执行 C++ RAII；这与协作取消的三项计数归零测试分别记录。完整 test worker 进程树留 N5。

## 人工 Ctrl+C（本轮未执行）

在能手动输入的 PowerShell 终端从根目录运行：

```powershell
& build/native-direct-debug/native-lifecycle-probe.exe wait
# 看到 READY 后亲手按 Ctrl+C。
$LASTEXITCODE
& build/native-direct-debug/native-lifecycle-probe.exe success
$LASTEXITCODE
```

固定期望：取消 probe 输出三项零计数，stderr 一条 cancelled/code=null，退出130；随后 success 零计数、空stderr、退出0。
记录实际命令、退出码、stdout/stderr和是否留进程；不使用本指南预填“通过”。这只验收 probe，原生 run 尚不可用。

## CMake、CTest、正式安装（工具缺失，尚未运行）

使用已有 MSVC 2022 x64 开发终端/CMake >=3.21，按 [README](../README.md) 的两个 preset 配置、构建。
必须 CTest --no-tests=error，预期非空 **19 个 CTest case**，任何失败/超时/零收集均不是通过。
再执行：

```powershell
cmake --install build/native-release --config Release --prefix dist/native-stage
```

将 dist/native-stage/bin 复制到仓库以外的新建中文空格目录；从该目录运行 zzy-native.exe info、--help、run no-execute.zzy --diagnostic-format json。
成功命令0；run必须E402/2且无用户副作用。该目录不含 Python、源码、虚拟环境，子进程PATH/PYTHONPATH清空。
核对 release exe SHA、dumpbin /dependents（MSVC）或现有 objdump -p、模块枚举和进程树；记录 VC runtime 版本与缺失时的实际加载错误，不私装runtime或把 /MDd 发给用户。
当前无工具链不能填写这些结果，N0-03 仍未完成，总出口未通过；不得据原型通过进入 N1。
