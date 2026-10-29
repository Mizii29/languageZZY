# shape 合约演示

P10-01 使用同一份 shape 字段描述生成校验、Map 布局及 OpenAPI 3.1.1。正式规则只维护在[集中契约](../../docs/runtime/web.md)。业务仍在 [app.zzy](app.zzy)：标题非空/长度及优先级 1—5 不由普通类型检查代替。

以下 PowerShell 命令在项目根目录执行。核心生成不需第三方库；服务器需已有 Web 可选依赖。首次在带 pip 的 Python 3.12.14 环境执行 `python -m pip install ".[web]"`。源码环境的实际 Python 是 `.venv/Scripts/python.exe`，应确保依赖安装在运行服务器的同一环境。

## 生成与运行

```powershell
.\.venv\Scripts\python.exe -X utf8 -m zzy check examples/contracts/app.zzy
.\.venv\Scripts\python.exe -X utf8 -m zzy.contracts examples/contracts/app.zzy --route POST /api/tasks submit --contracts examples/contracts/routes.json --output examples/contracts/openapi.json
.\.venv\Scripts\python.exe -X utf8 -m zzy.web examples/contracts/app.zzy --route POST /api/tasks submit --contracts examples/contracts/routes.json --port 8001
```

另一个终端调用；GET `/openapi.json` 可直接在浏览器查看 JSON，没有 Swagger UI：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/openapi.json
Invoke-RestMethod http://127.0.0.1:8001/api/tasks -Method Post -ContentType application/json -Body '{"task":{"title":"Homework"}}'
```

第二条应得到 title=Homework、priority=1、accepted=true；priority 由项目校验器补默认。下面的失败请求会使 PowerShell 抛出 HTTP 异常；Windows PowerShell 5.1 可用异常 Response 流查看 JSON：

```powershell
try {
    Invoke-RestMethod http://127.0.0.1:8001/api/tasks -Method Post -ContentType application/json -Body '{"task":{"title":false}}'
} catch {
    $_.Exception.Response.StatusCode.value__
    $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
    $reader.ReadToEnd()
    $reader.Dispose()
}
```

应得到 422、contract_input、body.task.title、type。将 title 改为一个空格时返回业务 409/message；这不是字段类型失败。停止服务器后在启动命令尾部加 `--shared` 可复验相同请求。默认与 shared 的初始化语义仍以 P08 为准。

## 只改一个字段

先提交 `{"task":{"title":"Homework","note":"read"}}`，当前版本应返回未知字段 `body.task.note`。在独立副本增加 note 字段，避免改测试夹具：

```powershell
New-Item -ItemType Directory -Force dist/p10-demo | Out-Null
$source = Get-Content examples/contracts/app.zzy -Raw -Encoding UTF8
$source.Replace('priority: (Int) := 1;', 'priority: (Int) := 1; note: (String) := "";') | Set-Content dist/p10-demo/app.zzy -Encoding UTF8
.\.venv\Scripts\python.exe -X utf8 -m zzy.contracts dist/p10-demo/app.zzy --route POST /api/tasks submit --contracts examples/contracts/routes.json --output dist/p10-demo/openapi.json
.\.venv\Scripts\python.exe -X utf8 -m zzy.web dist/p10-demo/app.zzy --route POST /api/tasks submit --contracts examples/contracts/routes.json --port 8002
```

在 8002 重发上述 note 字符串请求应成功，note=true 应返回 body.task.note/type。新 `/openapi.json` 的 Task 布局增加 note/string/default=""。无需修改校验器、转换器或文档生成器的字段列表；业务可继续忽略 note。

## Python 生成

```python
from zzy.contracts import generate_openapi
document = generate_openapi(
    "examples/contracts/app.zzy",
    [("POST", "/api/tasks", "submit")],
    {"POST /api/tasks": {"request": "Input", "responses": {"200": "Accepted", "409": "Rejected"}}},
)
print(document["openapi"])
```

已有 Python 嵌入 API 保持通用语义，不自动添加 Web 合约；本例 Web 在业务前验证后仍传 Map。`check` 也保持原来的语法/名称检查，显式合约检查使用生成命令。

Int 不接受 Bool 或 Float 1.0；Float 不接受 Int 1。标准 JSON Schema 的 integer/number 不能完整表达此差异，见生成文档的 x-zzy-rules 和字段 x-zzy-type。不要声称通用验证器可完整执行 ZZY 规则，也不要依赖第三方工具填 default。Array/Map 没有额外元素注解，开放内容仍受 JSON 安全边界约束。

自动证据见 [tests/p10](../../tests/p10/README.md)。[人工清单](manual-acceptance.md)保留待执行状态，由实际操作者填写。没有启动认证/TLS、热更新、缓存、VM 或 TypeScript 生成。
