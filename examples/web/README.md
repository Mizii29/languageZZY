# ZZY Web 示例（P08-01 / P08-02）

业务源码[app.zzy](app.zzy)处理GET问候与POST姓名校验；同源页面[index.html](index.html)。[正式契约](../../docs/runtime/web.md)列出所有边界。公开Python嵌入、SQLite尚未交付。共享冻结模式加--shared，默认模式仍逐请求实例化。

仓库根目录，Python 3.12.14、有pip的环境：

```powershell
python -m pip install ".[web]"
python -m zzy.web examples/web/app.zzy --route GET /api/hello hello --route POST /api/greet greet --page examples/web/index.html
```

打开 http://127.0.0.1:8000/ ，自动显示GET结果；输入姓名点击POST，空姓名显示HTTP422中文原因。Ctrl+C关闭；源码修改需重启。不要将服务暴露到公网，本例没有认证或TLS。只有显式Web入口加载第三方依赖，核心CLI/check/headless不加载Web或GUI。

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/hello
Invoke-RestMethod http://127.0.0.1:8000/api/greet -Method Post -ContentType 'application/json' -Body '{"name":"Ada"}'
python -X utf8 -m tests.web_http --report tests/p08/http.json
python -X utf8 -m tests
```

第一条返回message和language=ZZY，第二条message=你好，Ada。HTTP测试必须安装可选依赖，缺依赖即失败，绝不跳过。源码运行在本机可将python换为`.venv/Scripts/python.exe`。若该环境没有pip，用已有pip的解释器执行`python -m pip --python .venv/Scripts/python.exe install ".[web]"`。


P08-02共享模式启动（示例只有只读模块定义，可直接使用）：

```powershell
python -m zzy.web examples/web/app.zzy --route GET /api/hello hello --route POST /api/greet greet --page examples/web/index.html --shared
```

共享模式启动时执行一次初始化，拒绝模块级zyes、可达Lazy、捕获Cell的闭包和原生句柄；不会自动退回默认模式。共享数组/Map/结构/Machine只读，业务可变状态用请求局部值（数据库待P08-04）。修改代码后需要重启，你先前启动的服务不会热更新。
