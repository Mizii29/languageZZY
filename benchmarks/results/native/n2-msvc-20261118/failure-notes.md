# N2 正式补跑：失败与原件

本目录只保存2026-11-18的CMake/MSVC补跑。旧GCC/直接MSVC及权限失败在相邻n2-20261118，不覆盖或改写旧退出码。

- ctest-debug.txt：首轮42/44。program-fixed测试协调器使用进程cwd解析相对路径，错误地把正确诊断文件定位到build目录；frontend-default-boundaries超过60秒等待。
- program-fixed-verbose.txt、program-fixed-detailed.txt、program-fixed-codexpwsh.json：定位相对路径问题的失败原件。实际原生诊断为tests/run/inputs/duplicate.zzy；test-fixed.ps1改为先用用例cwd解析，保留期望和首错/文件/坐标断言。debug-program-fixed-rerun是从仓库根运行850条成功的定位记录；program-fixed-cwd-rerun是从构建目录复现的失败。
- ctest-debug-rerun.txt：修复路径后，大边界仍超过旧60秒；没有算作通过。default-boundaries-debug-isolated.txt及default-boundaries-timing.json实际独立运行72.2181479秒、退出0。仅延长此用例的等待到180秒；不更改/RTC1、输入、资源上限或断言。最终ctest-debug-final.txt为44/44，Release ctest-release.txt为44/44。
- collection-debug.json是修复等待上限前的真实收集；collection-debug-final.json、collection-release.json对应最终44项。带.raw.gz的文件保存去除行尾空格/多余空白尾行前的原始字节；正文仅清理展示空白，JSON结构相等。audit.py核对最终收集名称及等待上限，不能拿旧60秒清单当最终配置。
- Git权限恢复后，先用历史N1暂存补丁创建3bfc26d。随后逐JSON解析发现7个无末尾换行文件被旧补丁拼接污染，并有CRLF变化；对照dist/native-msvc-work/intended-index和实际原件恢复全部证据字节，解析通过，独立修复提交d537ce2。未改写历史或把错误中间提交当成有效证据。N1 collection空白原件也单独压缩保留。N2共享文档采用直接构造审查后的索引版本，保留未提交用户段落，不复用该旧补丁拼接方式。

Debug/Release acceptance各58条中各1条是故意200ms强杀的清理探针，保留timed_out=true和真实退出码，独立于57条正常完成记录；不称为语言执行成功。手动Ctrl+C、Sanitizer和完整Python/Web/GUI未执行，详见N2报告。所有新报告对应自己的真实EXE SHA，未将旧失败产物哈希替换为最终值。

开发用索引准备/保留审计另有两次前置失败：HEAD计划标题与工作区不同导致精确匹配断言退出；N1压缩原件命名为collection-debug.raw.json.gz，首版审计只识别.json.raw.gz。核对现有文件后修正协调脚本，未改变产品或期望；最终preservation.json通过，2044个起始文件中2026个未变。
