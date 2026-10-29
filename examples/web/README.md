# ZZY Web 与 Python 示例（P08-01—03）

业务源码[app.zzy](app.zzy)处理GET问候与POST姓名校验；同源页面[index.html](index.html)。[正式契约](../../docs/runtime/web.md)列出所有边界。Python嵌入见下文，SQLite见[独立互联示例](../sqlite/README.md)。共享冻结模式加--shared，默认模式仍逐请求实例化。

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

共享模式启动时执行一次初始化，拒绝模块级zyes、可达Lazy、捕获Cell的闭包和原生句柄；不会自动退回默认模式。共享数组/Map/结构/Machine只读，业务可变状态用请求局部值，持久化见已实现的[SQLite示例](../sqlite/README.md)。修改代码后需要重启，你先前启动的服务不会热更新。

## Python直接调用同一业务函数

核心安装即可使用，无需Web依赖。仓库根目录运行：

```powershell
.venv/Scripts/python.exe -X utf8 -m examples.web.embed
```

[embed.py](embed.py)直接调用同一app.zzy的greet，输出`{"status": 200, "body": {"message": "你好，Ada"}}`。Python只负责数据传入和展示；姓名校验、问候和业务状态码仍由ZZY处理。

```python
from zzy.embedding import load_module

with load_module("examples/web/app.zzy") as module:
    result = module.call("greet", {"body": {"name": "Ada"}})
    print(result.value)
    print(result.stdout, end="")
```

load不运行初始化；每次call独立执行，结束自动释放上下文，with退出释放模块。参数和结果自动按集中契约深复制/校验，结果为普通Python数据；不会返回内部ZZY句柄。Python支持资源限额内的int，HTTP仍拒绝超出安全整数范围的JSON数值，大整数HTTP字段须明确约定十进制字符串。

取消可传`CancellationToken`并由宿主线程调用cancel；它是协作式取消。同步call在返回/抛错前完成清理；并发在途时close明确报错，先取消并等待调用结束再关闭。模块不共享可变运行数据；如需持久化，参见独立SQLite示例。
