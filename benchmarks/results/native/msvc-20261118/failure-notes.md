# 本轮失败与诊断记录

首次MSVC构建的原始输出保留在build-debug-first.txt：protocol.cpp常量条件触发C4127，/WX转换为C2220；当次构建退出1。改为等价static_assert后构建和CTest通过，警告即错误未取消。

以下为实际工具输出的摘录与定位说明，不冒充另外保存的原始进程日志：

1. 首次发布目录复制误用 `Copy-Item -LiteralPath dist/native-stage/bin/*`：`Cannot find path 'dist/native-stage/bin/*' because it does not exist.` 后续Get-FileHash也找不到目标EXE。安装本身已成功；首次空目录未作为通过证据。改用Get-ChildItem枚举并新建第二个发布目录，再运行9项smoke和依赖验收通过。
2. 开发证据审计首次在 `assert records[-1]["children"] == []` 失败。原始JSON实际仅为Windows系统conhost.exe，既有acceptance规则已经将它单列；审计改为精确只允许该系统辅助进程，其他子进程仍失败。
3. 同一审计随后报 `AssertionError: tools/acceptance.ps1`。独立重算发现.NET ReadAllText已去除UTF-8 BOM，而初版Python审计保留BOM；另有install-smoke.ps1和test-fixed.ps1同类差异。Python审计改为utf-8-sig并保持CRLF→LF，未更改被测脚本、产物、原始报告或内容期望；当前42个原生文件与5个EXE逐项一致。

以上开发审计失败不计作功能通过；最终audit.json为修正后独立复核结果。N0/N1旧失败与GCC报告均原位保留，没有覆盖。
