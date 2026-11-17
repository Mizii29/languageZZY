# N0 固定语言期望

cases.json 使用现有 tests.blackbox schema；输入和期望在运行前人工固定，来源为 syntax 第5/6/7/8节、stdlib 的 Map/Array 规则和 diagnostics 第2节。
不从 Python 或原生后端输出反向写入期望。稳定 Python 解释器仅用于发现差异；N0 原生 run 尚不可用，不能将 Python 结果算原生通过。

| ID | 独立推导 |
|---|---|
| scalars | 2^64+1=18446744073709551617；floor(-7/3)=-3，余数2；校园与 emoji 共3码点；Bool≠Int，1与1.0数学相等 |
| aliases | Array 别名共享追加，自环仍指向同一对象；Map 的 self 键仍为自身；data.kind 的公开标签为小写 map（与内部 Value.kind 的 Map 不同） |
| closure-cycle | 返回闭包捕获可变 a 的 Cell；数组中保存同一闭包，长度1且身份相等 |
| order | mark(1)、mark(2) 从左到右打印，和3；false and 不调用 mark(99) |
| type-error | Bool 不参与加法，E201 运算符 + 第1行[12,13)，退出1；check只准备，不执行且退出0 |

另有原生 heap.cpp 的固定图与计数断言：Array(1对象1槽0载荷)、Map+单字符键(1对象2槽4载荷)、Array→Closure→Cell→Array(2对象3槽0载荷)。这些断言独立于运行时实际计数生成，来源为 resources.md 的逻辑对象/引用槽/标量载荷定义；String与Cell可被GC追踪，但不额外计runtime_objects。
与 Language golden 的联系是所有权图；没有声称堆原型已实现数组写入/Map 覆盖/闭包执行等语言规则。

复核：` .\.venv\Scripts\python.exe -X utf8 -m tests.blackbox native_runtime/tests/golden/cases.json`。
