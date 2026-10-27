# P08-01 验收

本轮仅HTTP子集；集中规则见[Web契约](../../docs/runtime/web.md)，[启动说明](../../examples/web/README.md)。core与可选HTTP分别收集，缺Web依赖必须失败，不跳过。业务为ZZY。

实际命令（仓库根目录）：

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_web_core -v
.venv/Scripts/python.exe -X utf8 -m tests.web_http --report tests/p08/http.json
.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression.json
.venv/Scripts/python.exe -X utf8 -m scripts.ci package --output dist/p08-package --installer C:/Users/13691/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe
```

- core专项3/3：无第三方导入、Bool/Int/Null/转义、完整请求状态重建和计量归零、示例check静默。
- HTTP专项8/8，真实监听TCP/实际HTTP客户端，无TestClient模拟传输。正常GET/POST与静态页；非法媒体/路径/方法；重复键/溢出/安全整数/非法编码/尾部注入；65536与65537字节；500错误后仍可请求；无限循环取消；慢body；断连释放；12次并发独立计数。详细结果[http.json](http.json)。
- wheel核心隔离安装通过，40份源码核对，见[报告](package.json)及[探针](package-probe.json)。另建dist/p08-web-installed/env，安装该wheel的web extra，`python -I .../probe.py`断言导入路径位于新环境，重复全部8项真实HTTP通过，见[installed-http.json](installed-http.json)。临时目录只放测试与ZZY夹具，无zzy源码。
- 浏览器真实点击：GET显示ZZY字段、POST同学显示问候、空姓名显示422中文提示。[截图](browser-failure.png)和[环境/源码哈希](environment.json)保留证据。此为自动操作浏览器证据，不是用户人工测试签收。
- 完整回归2005/2005、877.547秒，失败/错误/跳过/expected failure均0；[原始报告](core-regression.json)。原有2002项全部保留，新增3项核心用例。
- CI新增独立web-http job安装可选依赖/执行真实HTTP/上传报告，ci-gate依赖其成功；本轮未推送，云端运行未验证。GUI未改动也未重跑，不以HTTP/核心通过替代GUI验收。

限制：只有Windows11/CPython3.12.14；无公网认证/TLS或负载性能承诺。线程取消不能强制打断任意阻塞宿主调用。共享冻结模块捕获、公开Python API、SQLite尚未交付，P08-02—05保持未勾选。
