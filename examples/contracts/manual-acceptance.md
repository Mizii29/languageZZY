# P10-01 人工验收清单

按 [演示指南](README.md)运行。下表不代表自动测试结果；实际操作者执行后填写时间、环境、提交号及证据。当前均未执行，不预填通过。

| 操作 | 预期 | 人工结果 |
|---|---|---|
| 生成 openapi.json，浏览器查看 /openapi.json | 3.1.1，Task/Accepted/Rejected 字段与源码一致 | 待执行 |
| POST Homework，省略 priority | 200，priority=1，accepted=true | 待执行 |
| POST title=false，然后正常请求 | 422，body.task.title/type；下一请求成功 | 待执行 |
| POST 空白标题 | 409，业务错误 message | 待执行 |
| 启用 shared 重复正常和错误请求 | 与默认模式输出一致 | 待执行 |
| 在副本加 note 字段，重新生成/重启 | 新文档同步；String 成功，Bool 在 body.task.note 拒绝 | 待执行 |

日期：待填写。环境/提交：待填写。证据位置：待填写。问题：待填写。
