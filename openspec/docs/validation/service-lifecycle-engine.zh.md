# Service Lifecycle Engine 设计与使用说明

## 目标

`service_lifecycle_engine` 是本项目唯一的 generic service lifecycle engine。它负责本地 launcher-managed services 的 service spec、端口规划、进程启停、readiness、provenance、diagnostics evidence、startup/termination ledgers、安全 stop policy 和 typed live service resolution。

它不负责外部系统的 endpoint truth。需要把 ready service 发布给 runtime consumers 的项目，应通过 lifecycle event adapter 自己写入项目持有的 endpoint authority。

## Zero Compatibility

旧 lifecycle 入口不再保留。不要使用：

```python
from port_lifecycle import PortLifecycle, ServiceSpec
```

必须使用：

```python
from service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec
```

`scripts/port_lifecycle/` 和 `scripts/port_lifecycle_cli.py` 在迁移后应不存在。旧 import / 旧 CLI fail 是预期行为，不应添加 compatibility alias。

## Lifecycle State

Persisted lifecycle state 只使用：

| State | 含义 |
| --- | --- |
| `planned` | service 已声明或已进入计划，但还没有准备启动事务。 |
| `prepared` | 已解析端口或准备启动事务，但不能作为 consumer-ready endpoint。 |
| `ready` | readiness 已通过，并满足调用方要求的 provenance level。 |
| `stopped` | lifecycle owner 已停止 owned service。 |
| `aborted` | prepared startup 未能 ready，已进入 terminal non-ready state。 |

`failed` 不是 persisted lifecycle state，只能作为 operation result reason 或 lifecycle event reason，例如 `failed:TimeoutError`。

## Event Boundary

Engine 可发出以下 event：

- `prepared`
- `ready`
- `aborted`
- `stopped`

Event payload 包含 service identity、host、port、generation、reason、metadata，以及可选 `ProcessProvenance`。外部项目可以用 adapter 消费这些 event，例如发布 runtime endpoint binding、写 dashboard runtime config，或追加项目自己的审计记录。

Engine 不直接写项目业务状态，也不读取项目业务模块。

## Provenance Levels

Provenance 是 capability-based：

| Level | 用途 |
| --- | --- |
| wrapper-only | 可用于 diagnostics 和 registered process management。 |
| command-matched registered process | 可用于默认 registered process stop。 |
| owned listener | 可证明 listener 属于 wrapper/process group，可用于 owned listener stop。 |
| endpoint-grade | 可供外部 endpoint authority adapter 拒绝 stale/mismatched listener。 |
| HTTP identity | 语义身份补充证据，不能单独证明 OS listener ownership。 |

不是所有 service 都必须提供最强 provenance。Wrapper-only service 可以继续运行，只是 diagnostics 会显示 degraded evidence。

`ServiceState` 在可观测时保存相同的 provenance bundle，便于后续 diagnose / stop / adapter decision 识别 wrapper process、owned listener、HTTP semantic identity 和降级原因。

公共 helper：

- `capture_process_provenance(...)`
- `resolve_owned_listener(...)`
- `provenance_capability_for(...)`

这些 helper 只依赖 generic `PlatformOperationSet`，不依赖 Scrum Dashboard 或 Agora 的业务模型。

## Stop Safety

默认 stop 只停止：

1. lifecycle state 中登记且 command identity 匹配的 process；
2. 或可证明属于该 service 的 listener。

Unproven listener by port 必须 fail closed。按端口清理必须显式请求 force-by-port。

Stop result 中：

- `stop_source` / `force_requested` 表示 caller intent 或 stop 来源；
- `forced` 只表示 graceful terminate 失败后发生 kill escalation。

## State Store

`LifecycleStateStore` 至少提供：

- `exists`
- `read_json`
- `write_json_atomic`
- `append_jsonl`
- `lock`

Filesystem implementation 必须满足：

- persisted state 带 schema version；
- project / instance / service identity 隔离；
- destructive mutation 的 lock scope 覆盖被修改的 identity；
- corrupt 或 unsupported state fail closed，不静默删除或覆盖；
- state snapshot 使用 atomic replacement；
- append ledgers 保持写入顺序。

`ServiceLifecycleEngine` 默认使用 `FilesystemLifecycleStateStore`，也允许通过 `state_store=...` 注入 project-owned 或 in-memory store。

## Platform Operations

`ServiceLifecycleEngine` 默认使用 production `PlatformOperationSet`，也允许通过 `platform_ops=...` 注入 fake 或 project-owned platform operations。以下行为必须走注入 seam：

- port availability；
- process existence；
- command identity；
- listener discovery；
- process group / start marker；
- HTTP readiness / identity probe；
- terminate / kill / wait；
- port release wait。

## Live Service Resolver

Typed live service resolver 为 smoke、validation、dev task、signoff 和 live probes 提供统一读取面。Resolution result 至少包含：

- service id；
- host；
- port；
- base URL；
- resolution source；
- fallback/degraded diagnostics。

推荐 resolution 顺序：

1. explicit input；
2. lifecycle state；
3. project-provided runtime projection；
4. default fallback。

Hermetic command 可以禁用 projection source，只允许 explicit input 或 default fallback。

## Scrum Dashboard Adoption

本项目采用 breaking migration 路径：

1. 所有 active launcher/tests/docs 改用 `service_lifecycle_engine`。
2. 删除旧 `port_lifecycle` package 和旧 CLI。
3. 保持 E2E start/stop/restart runtime behavior 等价。
4. 增加 lifecycle events、state store、fakeable platform ops 和 resolver tests。
5. 增加 negative tests 确认旧 import/CLI 不再可用。

## 验证

Focused validation:

```powershell
python -m pytest scripts\tests\test_service_lifecycle_engine.py scripts\tests\test_service_lifecycle_state_store.py scripts\tests\test_service_lifecycle_platform_ops.py scripts\tests\test_service_lifecycle_resolver.py -q
python -m pytest scripts\tests\test_service_lifecycle_provenance.py scripts\tests\test_service_lifecycle_process.py scripts\tests\test_service_lifecycle_cli.py scripts\tests\test_e2e_bug_trend_launcher.py scripts\tests\test_e2e_provider_parity_launcher.py -q
```
