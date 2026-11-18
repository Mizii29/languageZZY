# N3 核心执行：逐批交接

2026-11-18。基线 156a85b（N2 正式 MSVC 验收）。N3 开发中，尚未达到总体出口；不将下述组件结果冒充完整 run 或所有资源键验收。

## 批次 A：核心数值、追踪堆和原子配额

已实现 `bigint.hpp`：带符号 32 位 limb、任意精度加减乘、负无穷取整除法/余数、十进制转换、有限 binary64 的精确有理表示及 Int/Float 比较。固定答案写在 `runtime_values.cpp`，不是由 Python/被测后端生成；除固定大数外，穷举 -300…300 与 -17…17 的非零除数，与独立宿主整数公式核对。

`runtime_heap.hpp` 是真实运行时的类型节点和非拥有边，外部 Value 通过 RootToken 保根；节点不持有 RootToken。可在同一请求中回收 Array→Function→Cell→Map→Array 环，归还对象/槽位/载荷。跨请求句柄拒绝。三键预留全有或全无，分配失败回滚，配额不足先收集再判定。取消/关闭路径幂等释放，不依赖进程退出。

实际 MSVC Debug/Release 组件 CTest 均 6/6，分别 0.63s / 0.23s。命令：

```powershell
cmake --preset native-debug -S native_runtime
cmake --build build/native-debug --config Debug --target native-runtime-values-tests
ctest --test-dir build/native-debug -C Debug -R '^runtime-values-' --output-on-failure --no-tests=error
cmake --preset native-release -S native_runtime
cmake --build build/native-release --config Release --target native-runtime-values-tests
ctest --test-dir build/native-release -C Release -R '^runtime-values-' --output-on-failure --no-tests=error
```

首次 5/6：误复用 N2 Program 专属空选择文案检查。新增独立运行时选择门禁后 6/6；没有放宽 N2 断言。尚未验证整套既有 CTest、CLI run、求值语义、运行期中间空间、完整 Quantity、真实手动 Ctrl+C、Sanitizer 或性能。

下一批：最小执行器和 io.print；再接控制流/函数、闭包/特色、累计验收。N3-01—05 继续未勾选。

## 批次 B：最小 run 与输出

MSVC Debug/Release 各 18/18 CLI 固定用例通过，独立程序/期望为 tests/runtime。无 Python PATH 下运行；新增 PowerShell runner 接入 CTest，拒绝空清单/重复 ID，保留退出码和完整流。run 在准备失败时仍退出 2，执行错误退出 1；test 仍 E402。io.print/len/str/range 为本批最小垂直链，不宣称 N4 库已完成。info 阶段为 N3-dev。

首次 E302 来自将 Resolver 的 builtin 属性误当独立 reference.kind；核对 Program 实际布局后修复。另有 Float 指数夹具不属正式语法，改为等值十进制字面量，保持溢出期望 E208。剩余控制流/函数/特色/完整资源测试尚未验证。
