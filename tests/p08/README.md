# P08 Web 验收

## P08-01 HTTP子集（历史记录）

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


## P08-02共享模式验收

P08-01段落及报告保留历史含义；当前新增显式shared=True/--shared，默认逐请求初始化兼容。共享图包括模块依赖、结构默认全局引用、只读闭包捕获；Lazy/可变绑定/Cell闭包/原生句柄/命名空间别名明确拒绝，不降级。数据写入复用E203和原始源码定位。

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_web_shared tests.test_web_core -v
.venv/Scripts/python.exe -X utf8 -m tests.web_http --report tests/p08/http-02.json
.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression-02.json
```

核心专项8/8；[Web专项12/12](http-02.json)包含真实TCP、屏障强制交错与故障恢复、忙worker时事件循环可响应、服务初始化仅一次/关闭计量归零。启动取消另用受控ASGI lifespan交错，明确不是TCP请求用例。依赖模块隐藏Lazy拒绝、默认新数组不共享、默认别名冻结、失败初始化不发布/资源归零、只读闭包捕获递归冻结、原生名义类型身份由宿主通过真实ZZY执行验证。

[最终wheel安装](package-02.json)与[核心安装探针](package-probe-02.json)核对41源码。保留已隔离Web环境，--force-reinstall --no-index --no-deps安装本轮wheel，再以python -I执行同一12项专项，导入包确在env中；[安装HTTP报告](installed-http-02.json)。[源码哈希](source-02.json)记录专项与完整回归对应实现。

实际CLI新增参数也经独立进程、临时端口验证：`python -X utf8 -m zzy.web examples/web/app.zzy --route GET /api/hello hello --route POST /api/greet greet --page examples/web/index.html --shared --port 62437`，GET返回language=ZZY，POST返回你好，Ada，见[CLI报告](cli-02.json)。探针退出时只终止自己的子进程；正常服务关闭证据由上述lifespan用例提供，用户原8000端口服务未操作。

完整核心回归[2010/2010、960.375秒](core-regression-02.json)，失败/错误/跳过/expected failure均0；原2005项及1738外部CLI完整保留，新加5项核心测试。未验证其他平台/最大压力/真实互联网部署；协作取消不能强制中止所有阻塞宿主调用。GUI与用户人工测试本轮未重跑；未执行P08-03公开嵌入/P08-04 SQLite。CI沿用已接入的Web专项job，本轮未推送云端。

## P08-03嵌入验收

公开接口与所有权以[集中契约](../../docs/runtime/web.md)为准；[Python示例](../../examples/web/embed.py)与Web调用同一greet。加载、参数拒绝不运行初始化；call每次独立执行，转换和执行的finally释放共用原解释器机制。旧P08-01/02段落及报告保留当时含义。

实际命令（根目录）：

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_embedding tests.test_web_core tests.test_web_shared -v
.venv/Scripts/python.exe -X utf8 -m examples.web.embed
.venv/Scripts/python.exe -X utf8 -m tests.web_http --report tests/p08/http-03.json
.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression-03.json
```

- [核心专项19/19](embedding-03.json)：11项新嵌入用例、8项原Web核心。覆盖精确类型、层数/容量阈值、别名复制、循环及不支持值拒绝、初始化/调用错误定位、捕获IO、取消、并发、close与计量归零。
- [Web专项13/13](http-03.json)：新增真实TCP与Python同一greet的正常/错误业务对照；原有安全整数边界及非法响应拒绝保留。
- [核心wheel安装](package-03.json)与[探针](package-probe-03.json)：42份运行时源码，核心不安装Web依赖即可调用嵌入API。CI安装探针已接入该检查，现有核心回归/Web job自动收集新用例，无新增第三方依赖。
- 隔离env离线重装本轮wheel，`python -I`实测[嵌入11/11](installed-embedding-03.json)、[HTTP13/13](installed-http-03.json)，确认从安装目录导入。源码及测试对应[冻结哈希](source-03.json)。

完整回归[2021/2021、966秒](core-regression-03.json)，失败/错误/跳过/expected failure全0；原2010项及1738外部CLI全部保留。只验证Windows11/CPython3.12.14；GUI、用户人工操作、云端CI和其他平台未重跑。无SQLite、隐式执行超时、自动缓存或热更新；线程协作取消不能打断所有阻塞宿主调用。

## P08-04/05 SQLite与整体验收

[SQLite示例及启动步骤](../../examples/sqlite/README.md)提供同源页面、HTTP、Python和重启命令，业务全部在ZZY。核心接口由db.transaction/db.query注册提供；详细规则见集中契约。

实际命令：

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_database -v
.venv/Scripts/python.exe -X utf8 -m tests.web_http --report tests/p08/http-04.json
.venv/Scripts/python.exe -X utf8 -m tests --report tests/p08/core-regression-05.json
```

[数据库专项](database-04.json)6/6、[真实HTTP](http-04.json)14/14通过；[独立CLI服务器进程重启](process-restart-04.json)验证写入后退出/新PID启动仍读取原数据。测试只终止自己的服务器，不操作用户原8000服务；正常关闭另由HTTP lifespan测试覆盖。

[核心隔离安装](package-05.json)、[安装探针](package-probe-05.json)核对43份源码并执行真实SQLite check/run；[安装后HTTP](installed-http-05.json)14/14。[源码哈希](source-05.json)锁定本轮实现。完整回归[2027/2027、838.109秒](core-regression-05.json)，失败/错误/跳过/expected failure均0。

未验证：新SQLite页面的浏览器人工交互、Tk GUI重测、云端CI、其他平台及断电恢复。SQL锁等待250ms、进度期限1秒；宿主文件阻塞无法强制打断。此前Git写权限阻塞已解除，SQLite及整体验收提交为0a70825。
