# SQLite互联演示

从仓库根目录运行，Python 3.12.14，Web安装沿用 `pip install ".[web]"`。

```powershell
.venv/Scripts/python.exe -X utf8 -m zzy.web examples/sqlite/app.zzy --route GET /api/tasks handle --route POST /api/tasks handle --page examples/sqlite/index.html --shared --port 8001
```

打开 http://127.0.0.1:8001/ 添加任务、刷新列表；空标题显示422。页面文本使用textContent，业务校验、SQL与处理全部在app.zzy。Python只提供通用事务/绑定能力。此例独立于校园CLI，不改变其JSON文件格式。

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/tasks -Method Post -ContentType 'application/json' -Body '{"title":"homework"}'
Invoke-RestMethod http://127.0.0.1:8001/api/tasks
```

Ctrl+C关闭，再运行同一启动命令；GET仍应返回已写入的任务。数据在examples/sqlite/tasks.sqlite3（已忽略），不要删除该文件来验证重启。数据库路径由受信任源码指定，不接受客户端路径或SQL。

Python同样调用该业务：

```python
from zzy.embedding import load_module
with load_module("examples/sqlite/app.zzy") as module:
    print(module.call("handle", {"method":"GET", "body":None}).value)
```

[集中契约](../../docs/runtime/web.md)维护参数、事务边界、取消和限制；[测试证据](../../tests/p08/README.md)区分核心、HTTP、安装和未验证范围。已有hello网页和Python示例仍见[Web演示](../web/README.md)。
