# P10-01 / P10-06 验收

仅验收 shape 合约和本次配套交付；P10-02—05、07、08没有因此完成。实现规则见[Web 集中契约](../../docs/runtime/web.md)，操作见[独立示例](../../examples/contracts/README.md)。

## 执行入口

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest tests.test_contracts -v
.\.venv\Scripts\python.exe -X utf8 -m tests.web_http --report dist/p10-http-repeat.json
.\.venv\Scripts\python.exe -X utf8 -m tests --report dist/p10-core-repeat.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.ci static --output dist/p10-static-repeat
.\.venv\Scripts\python.exe -X utf8 -m benchmarks.contracts --output dist/p10-measurement-repeat.json --repeats 30
```

HTTP 专项需安装 Web extra 及 `scripts/ci/contract-requirements.txt` 的 jsonschema；核心回归不导入此验证器、不需要可选依赖。输出文件/目录用新的名字，不覆盖失败证据。运行器坚持非空收集、执行数一致、零失败/跳过/expected failure。

## 覆盖映射

| 要求 | 实际用例 |
|---|---|
| 必填、默认、Null、严格标签、安全整数 | test_contracts 的 required_defaults_and_null、numeric_tags_and_safe_integer |
| 嵌套/未知字段路径、开放 Array/Map | nested_paths_open_containers、unicode_names_and_bounded_diagnostics |
| 无注解、递归、句柄等拒绝；普通 shape 保留 | unsupported_definitions_do_not_restrict_plain_shapes、imported_shape_static_identity_and_alias_rejection |
| 生成不执行 I/O/Lazy/业务；核心可独立用 | generation_does_not_execute_and_cli_is_core_only、input_rejected_before_initialization、安装 probe |
| 静态深度/字段数、运行分配/取消/清理 | conversion_limits_cancellation_and_recovery、depth_bound_and_failed_cli_does_not_overwrite |
| 固定 schema、生成确定、响应默认、唯一 operationId | fixed_schema_and_deterministic_generation、response_defaults_and_distinct_operation_ids |
| 改一个字段同步生效 | one_field_change_updates_validation_and_schema |
| HTTP 正常/字段失败/业务失败/响应失败及恢复 | web_http 的 contract_example_default_shared_and_openapi、contract_rejection_before_business_and_response_statuses |
| 默认/shared 实际交错、可变 Array/Map 请求隔离 | contract_interleaving_isolation_and_resource_recovery、contract_open_container_mutation_is_per_request |
| shared 初始化前拒绝非法合约 | contract_generation_rejects_bad_shapes_before_shared_init |
| 独立标准验证及数值差异 | schema_contracts 的 4 项 Draft202012Validator 测试，显式接入 web_http，不进核心 discovery |

原有 14 项 HTTP 全保留，包括大小/JSON/超时/断连、事件循环、共享冻结、SQLite 持久化；新增 5 项 HTTP 及 4 项独立 Schema，共 23 项。核心新增 14 项，每项包含独立子例和真实 ZZY 执行；不减少原 2027 项与 1738 个外部 CLI 用例。

## 测量

[最终原始测量](measurement-final.json)（初版保留[measurement.json](measurement.json)）保存 CPython/OS、资源配置、源码哈希、每档 30 次原始纳秒样本、min/max/median/pstdev；三档输入分别为 4、32、128 字段，每字段 String 长16。

| 字段数 | 准备中位数 ms | 合约生成中位数 ms | 校验中位数 ms |
|---|---|---|---|
| 4 | 3.2545 | 0.1429 | 0.0635 |
| 32 | 4.1582 | 0.2981 | 0.3887 |
| 128 | 6.6476 | 0.8919 | 1.6050 |

准备含读取/前端；合约生成含已准备 Program 上的 IR 编译、Schema 构建及编码限额检查；校验含字段遍历、默认处理和 Map 分配，不含 JSON 解析、业务、HTTP 或清理。每次均核对结果及资源释放；无等价旧实现对照，不声称提速。这是本机小规模测量，不是吞吐/尾延迟或最坏容量承诺。

## 结果与范围

[核心专项](core-specialist.json)14/14；[最终 HTTP 专项](http-final.json)23/23（初版[http.json](http.json)22/22）。[最终核心回归](core-regression.json)2041/2041、919.828秒，零失败/错误/跳过；[最终安装HTTP](installed-http-final.json)23/23、7.282秒；[核心安装](package.json)44源码一致；[静态](static.json)和[本地汇总门禁](gate.json)通过。最终运行时/测试源码哈希见[source.json](source.json)。P10-01/P10-06现已勾选，其余保持延期。

人工记录在[示例人工清单](../../examples/contracts/manual-acceptance.md)，本轮不预填；没有重跑真实 Tk GUI、其他 OS 或云端 CI。P08 原人工资料和 requirement 原文保持不变。

重叠状态码补充：schema_contracts.test_adapter_errors_share_status_with_business_contract独立验证422/500/503上的业务shape和适配错误包均被文档覆盖；web_http实际请求确认失败包不会被递归套业务shape。

[CLI演示证据](cli-demo.json)为两个独立进程及10次POST；生成命令无业务副作用，新增note字段后的文档与校验同步。初轮完整回归见[initial报告](core-regression-initial.json)，在重叠状态码Schema修正后重新完整回归与安装，不把旧报告代替最终代码。
