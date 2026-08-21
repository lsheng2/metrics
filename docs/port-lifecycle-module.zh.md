# Port Lifecycle 模块设计与使用手册

## 目标

`PortLifecycle` 是一个可跨项目复用的本地多服务启动模块，用于解决一个开发机上多个项目、多个 instance、多个 service 的端口冲突问题。

它提供统一流程：

1. 为每个 service 声明 preferred ports。
2. 启动前检测端口是否可用。
3. 自动选择第一个可用端口。
4. 记录 state file 和 pid file。
5. stop/restart 时只停止本模块登记过的 owned process。
6. graceful stop 超时后 force stop。

核心实现是 Python stdlib，支持 Windows、Linux、macOS。PowerShell、Bash、VS Code tasks 只作为薄 wrapper。

## 文件位置

```text
scripts/port_lifecycle/
  __init__.py
    config.py
    models.py
    platform_ops.py
  port_lifecycle.py
scripts/tests/test_port_lifecycle.py
```

本项目 Bug Trend E2E 的使用样例：

```text
scripts/e2e_bug_trend.py
scripts/e2e_start_bug_trend.ps1
scripts/e2e_stop_bug_trend.ps1
```

## API 速查表

### Public API

| API                                                                                             | 类型    | 用途                                                                                                         | 关键参数                                                                                                                            | 返回值 / 输出                    |
| ----------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| `ServiceSpec.from_values(...)`                                                                | factory | 声明一个可启动/可停止的 service。                                                                            | `name`, `preferred_ports`, `command`, `stop_command`, `host`, `cwd`, `env`, `health_url`, `listener_identity_url` | `ServiceSpec`                  |
| `PortLifecycle(...)`                                                                          | class   | 创建一个 project instance 的 lifecycle context。                                                             | `project_name`, `workspace`, `instance_name`, `state_directory`, `pid_directory`, `log_directory`                       | `PortLifecycle`                |
| `resolve_port(spec)`                                                                          | method  | 从一个 service 的 preferred ports 中选择第一个可用端口；如果 state 里已有 live owned process，会复用原端口。 | `ServiceSpec`                                                                                                                     | `int` port                     |
| `resolve_plan(specs)`                                                                         | method  | 为多个 services 一次性解析端口。                                                                             | `Sequence[ServiceSpec]`                                                                                                           | `dict[str, int]`               |
| `prepare_startup(service_specs, force_by_port=False, ...)`                                    | method  | 启动前统一释放当前 instance 的 owned services；需要接管端口时再显式清理候选端口上的 listener。               | `service_specs`, `graceful_timeout_seconds`, `force_by_port`, `force_graceful_timeout_seconds`                                    | `list[StopResult]`             |
| `start_service(spec, port=None)`                                                              | method  | 启动 service、等待 readiness、写 state/pid/log/launch authority。                                            | `ServiceSpec`, optional `port`                                                                                                  | `ServiceState`                 |
| `stop_service(name, graceful_timeout_seconds=5.0)`                                            | method  | 停止 state 中登记的单个 owned service。                                                                      | `name`, `graceful_timeout_seconds`                                                                                              | `StopResult`                   |
| `stop_all(graceful_timeout_seconds=5.0)`                                                      | method  | 停止当前 instance 的所有 owned services，并清理 state。                                                      | `graceful_timeout_seconds`                                                                                                        | `list[StopResult]`             |
| `force_stop_by_ports(service_specs, graceful_timeout_seconds=0.5, port_process_resolver=...)` | method  | 显式兜底：按 service preferred ports 找 listener PID 并停止。默认不调用。                                    | `service_specs`, optional resolver                                                                                                | `list[StopResult]`             |
| `check_services(callback=None)`                                                               | method  | watchdog 单轮检查：发现 missing pid、health fail、identity drift 时生成事件。                                | optional callback                                                                                                                   | `list[dict[str, object]]`      |
| `read_state()`                                                                                | method  | 读取当前 instance 的 state file。                                                                            | 无                                                                                                                                  | `dict[str, dict[str, object]]` |
| `write_state(services)`                                                                       | method  | 写入当前 instance 的 state file；通常只给 launcher/test 使用。                                               | service state mapping                                                                                                               | none                             |
| `load_service_specs(path, workspace, variables)`                                              | function | 从 JSON 文件读取 services 并生成 `dict[str, ServiceSpec]`。                                                  | JSON path, workspace, template variables                                                                                             | `dict[str, ServiceSpec]`       |
| `load_project_name(path, default)`                                                            | function | 从 JSON 文件读取 `project_name`，用于创建 `PortLifecycle`。                                                  | JSON path, fallback project name                                                                                                     | `str`                          |

### Data Models

| Model            | 用途                         | 关键字段                                                                                                                |
| ---------------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `ServiceSpec`  | service 声明。               | `name`, `preferred_ports`, `command`, `stop_command`, `health_url`, `listener_identity_url`, timeout fields |
| `ServiceState` | service 启动后的实际状态。   | `name`, `host`, `port`, `pid`, `command`, `stdout_log`, `stderr_log`, `launch_authority_file`           |
| `StopResult`   | stop/force-stop 的审计结果。 | `name`, `port`, `pid`, `stopped`, `forced`, `reason`                                                        |

### Platform Helpers

| API                                       | 用途                              | 说明                                                                   |
| ----------------------------------------- | --------------------------------- | ---------------------------------------------------------------------- |
| `is_port_available(host, port)`         | 检查端口是否可 bind。             | 用于 preferred port selection。                                        |
| `process_exists(pid)`                   | 检查 pid 是否仍存在。             | Windows 使用 Win32 API，POSIX 使用`os.kill(pid, 0)`。                |
| `get_listening_process_ids(host, port)` | best-effort 端口到 PID resolver。 | 只在显式 force-by-port 时使用；项目可替换为更安全 resolver。           |
| `http_probe(url)`                       | HTTP identity probe。             | 返回 reachable/status/body fingerprint，用于 listener identity check。 |

### CLI / Wrapper API

| 命令                                                     | 用途                                       |
| -------------------------------------------------------- | ------------------------------------------ |
| `python scripts/e2e_bug_trend.py start [--force-by-port]` | 启动 Bug Trend E2E runtime，自动选择端口；可在写 DB 前接管候选端口。 |
| `python scripts/e2e_bug_trend.py stop`                 | 安全停止 owned E2E services。              |
| `python scripts/e2e_bug_trend.py restart`              | stop 后重新 start。                        |
| `python scripts/e2e_bug_trend.py stop --force-by-port` | 显式按候选端口兜底清理。                   |
| `scripts/e2e_start_bug_trend.ps1 [-ForceByPort]`       | Windows/VS Code task wrapper。             |
| `scripts/e2e_stop_bug_trend.ps1 [-ForceByPort]`        | Windows/VS Code task wrapper。             |

## 核心概念

### Context

`PortLifecycle(project_name, workspace, instance_name)` 定义一个可独立运行的 project instance。

- `project_name`：项目或 demo 名称，例如 `metrics-bug-trend`。
- `instance_name`：同一项目多个 instance 的隔离键，例如 `default`、`alice`、`pr-123`。
- `state_directory`：保存 state 和 pid/log 文件的位置。

不同 `instance_name` 会得到不同 state file，因此同一项目可以并行启动多个 instance。

### ServiceSpec

一个 service 的声明包含：

- `name`：服务名，例如 `django`、`grafana`、`api`、`worker`。
- `preferred_ports`：候选端口列表，按优先级排列。
- `command`：启动命令，支持 `{host}`、`{port}`、`{workspace}` 占位符。
- `health_url`：可选 HTTP readiness URL；应选择稳定、轻量、不依赖特定 demo 日期或业务数据的端点。
- `startup_timeout_seconds`：启动等待时间。
- `graceful_timeout_seconds`：停止时 graceful wait 时间。

### State 与 pid file

模块写两类文件：

- state file：记录所有 service 的 `pid`、`port`、command、log path。
- pid file：每个 service 一个 owned pid 记录。

Stop 优先读 state；如果 state 被误删，仍会扫描本 instance 的 pid files 并停止 owned processes。模块不会按端口杀未知进程，因为跨 OS 端口反查 pid 依赖系统工具，且容易误杀其他项目。

### Launch authority 与 termination ledger

模块会为每次启动写 launch authority：

```text
state/port-lifecycle/launch-authority/<project>-<instance>-<service>.json
```

它记录 service、port、wrapper pid、health URL、log path 和启动命令。这个设计来自另一个多服务 launcher 的经验：有些服务由 shell、dev server、reload supervisor 或 terminal pane wrapper 启动，启动进程 PID 不一定等于最终监听端口的 listener PID。跨 OS 通用模块默认只记录 owned wrapper PID 和 health endpoint；如果某个 service 会 detach listener，项目 launcher 应提供 service-specific `stop_command` 作为 graceful stop，然后让模块做 pid 兜底。

停止时会追加 termination ledger：

```text
state/port-lifecycle/termination-ledger.jsonl
```

ledger 记录 service、pid、port、是否 force、原因和时间。它用于区分“我们主动 stop”与“服务意外消失”，也方便后续 watchdog 或诊断页面复用。

## 端口选择策略

端口选择使用 bind 检测：

```text
for port in preferred_ports:
    if host:port can bind:
        choose port
```

如果端口被其他项目占用，模块跳到下一个 preferred port。如果 preferred list 全部不可用，启动失败并报告候选列表。

建议每个项目避开常见端口池，例如：

```python
api_ports = (8002, 8012, 8022, 8032, 8042)
grafana_ports = (3001, 3011, 3021, 3031, 3051)
```

如果你的机器上已有常用端口 `3000, 8000, 4000, 3100, 3040, 13133, 4318, 2026`，不要放在 preferred list 的前段，或直接不使用。

## Python 使用示例

```python
from pathlib import Path
from scripts.port_lifecycle import PortLifecycle, ServiceSpec

workspace = Path.cwd()
lifecycle = PortLifecycle(
    project_name="my-dashboard",
    workspace=workspace,
    instance_name="default",
)

api = ServiceSpec.from_values(
    name="api",
    preferred_ports=[8010, 8020, 8030],
    command=["python", "manage.py", "runserver", "{host}:{port}", "--noreload"],
    cwd=workspace,
    health_url="http://{host}:{port}/health/",
)

port = lifecycle.resolve_port(api)
lifecycle.start_service(api, port=port)
```

停止：

```python
lifecycle.stop_all(graceful_timeout_seconds=5)
```

## JSON Service Spec 配置

推荐把 service 声明放到 JSON，launcher 只保留项目流程编排。这样后续新增 service、调整 preferred ports、改 health URL 不需要改 Python 代码。

示例：

```json
{
    "project_name": "my-dashboard",
    "services": [
        {
            "name": "api",
            "preferred_ports": [8010, 8020, 8030],
            "command": ["{python}", "manage.py", "runserver", "{host}:{port}", "--noreload"],
            "host": "127.0.0.1",
            "cwd": "{workspace}",
            "health_url": "http://{host}:{port}/health/",
            "listener_identity_url": "http://{host}:{port}/identity",
            "startup_timeout_seconds": 30,
            "graceful_timeout_seconds": 5,
            "port_release_timeout_seconds": 2
        }
    ]
}
```

读取：

```python
from scripts.port_lifecycle import PortLifecycle, load_project_name, load_service_specs

project_name = load_project_name("scripts/e2e.services.json", "fallback-name")
lifecycle = PortLifecycle(project_name, workspace)
specs = load_service_specs(
        "scripts/e2e.services.json",
        workspace,
        {"python": python_executable},
)
```

模板变量分两层：

| 变量 | 展开时机 | 说明 |
| --- | --- | --- |
| `{workspace}`, `{python}`, `{grafana_bin}`, `{grafana_homepath}`, `{grafana_config}` | JSON loader 读取时 | launcher 提供的项目变量。 |
| `{host}`, `{port}` | `start_service()` 启动时 | lifecycle 根据实际选择的端口展开。 |

判断边界：JSON 适合放 service 声明；migrate/seed/check、dashboard import、datasource rewrite、浏览器打开等项目流程仍应放在 launcher 代码里。

## CLI/launcher 推荐模式

建议每个项目写一个很薄的 launcher，例如：

```text
scripts/e2e_my_project.py start
scripts/e2e_my_project.py stop
scripts/e2e_my_project.py restart
```

launcher 负责：

- 声明 service specs。
- 运行项目自己的 migrate/seed/check。
- 调用 `PortLifecycle` 启停服务。
- 写项目级 summary，例如实际 URL。

VS Code task、PowerShell、Bash 只调用 launcher，不复制端口逻辑。

## Windows/Linux/macOS 调用方式

Windows PowerShell：

```powershell
.venv\Scripts\python.exe scripts\e2e_bug_trend.py start
.venv\Scripts\python.exe scripts\e2e_bug_trend.py stop
.venv\Scripts\python.exe scripts\e2e_bug_trend.py restart
```

Linux/macOS shell：

```bash
.venv/bin/python scripts/e2e_bug_trend.py start
.venv/bin/python scripts/e2e_bug_trend.py stop
.venv/bin/python scripts/e2e_bug_trend.py restart
```

## Stop 语义

Stop 只停止本模块登记过的 owned process：

1. 读取 state file 中的 pid。
2. 如果 state 缺失，扫描本 instance 的 pid files。
3. 校验当前 PID 仍匹配启动时记录的 command identity；不匹配时保留 state/pid/authority，避免误杀 PID 复用后的未知进程。
4. 如果 service 声明了 `stop_command`，先执行它并等待 `graceful_timeout_seconds`。
5. 如果仍未退出，对 verified owned pid 发送 graceful terminate，再等待 `graceful_timeout_seconds`。
6. 如果仍未退出，发送 force kill。
7. 只有确认 PID 已退出后才删除对应 state/pid/authority file；失败停止会保留恢复证据。

不会因为某个 preferred port 正在 listen 就直接杀进程。未知 listener 只会让 start 跳到下一个端口。

## Force By Port 兜底接口

普通 stop 不会按端口杀未知进程；但很多项目需要一个显式兜底入口，例如 `Stop` 和 `Stop (Force By Port)` 两个 task。模块提供 opt-in API：

```python
results = lifecycle.force_stop_by_ports(
    service_specs=[api, frontend],
    port_process_resolver=my_project_port_resolver,
)
```

`port_process_resolver(host, port) -> Sequence[int]` 由项目提供，负责把端口解析成可以停止的 PID。模块拿到 PID 后会执行 graceful/force stop，并写 termination ledger，reason 前缀为 `force_by_port:`。

模块也提供 best-effort 默认 resolver：

| OS      | 默认 resolver                             |
| ------- | ----------------------------------------- |
| Windows | `netstat -ano -p tcp`                   |
| macOS   | `lsof -nP -iTCP:<port> -sTCP:LISTEN -t` |
| Linux   | 优先`lsof`，fallback `ss -ltnp`       |

默认 resolver 只在显式调用 `force_stop_by_ports()` 时运行。项目如果要更安全，可以传入自己的 resolver，在 resolver 内做 command-line、workspace path、service marker、launch authority 等过滤。

### Force By Port 的建议用法

1. 默认 `Stop`：只停 state/pid file 登记的 owned process。
2. `Stop (Force By Port)`：先跑默认 stop，再显式按候选端口兜底清理。
3. CI 或共享机器上默认不要自动 force-by-port；除非 resolver 能证明 PID 属于本项目。
4. force-by-port 结果必须写入 ledger，便于事后判断是主动清理还是服务 crash。

### Graceful stop 与 force stop

通用模块支持两层 stop：

1. `stop_command`：项目可选声明的服务级 graceful stop 命令，例如调用框架 stop API、发送 shutdown endpoint、运行官方 CLI stop。
2. owned pid fallback：如果 `stop_command` 等待 `graceful_timeout_seconds` 后进程仍存在，模块会对 verified owned pid 发送 graceful terminate，再等待同一个 timeout，最后才 force stop owned pid。

Windows 上 generic console signal 容易误伤调用方或同一 console group，因此通用模块不尝试发送 Ctrl-C 类控制信号。需要真正 graceful shutdown 的服务应通过 `stop_command` 暴露明确停止路径。

## 扩展更多 service

后期新增 service 时，只需要增加一个 `ServiceSpec`：

```python
worker_ui = ServiceSpec.from_values(
    name="worker-ui",
    preferred_ports=[5101, 5111, 5121],
    command=["node", "server.js", "--port", "{port}"],
    cwd=workspace / "worker-ui",
    health_url="http://{host}:{port}/healthz",
)
```

然后在 launcher 里加入：

```python
port = lifecycle.resolve_port(worker_ui)
lifecycle.start_service(worker_ui, port=port)
```

如果 service 之间有依赖，例如 Grafana datasource 要指向 Django 的实际端口，就在两个 service 都启动后读取实际端口并写入配置。

## 来自 system_integration_agent_ai 的设计学习

调研 `D:\AIGC\system_integration_agent_ai` 的 `fullstack-start.ps1`、`fullstack-stop.ps1`、`gateway-runner.ps1`、`gateway-stop.ps1`、`service-watchdog.ps1` 后，吸收了这些模式：

| 外部项目模式                      | 学到的问题                                                                                  | 合并到本模块的方式                                                                                                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `launch-authority`              | wrapper PID 与 listener PID 可能不同，特别是 reload supervisor、terminal pane、dev server。 | 新增 launch authority 文件，记录 owned wrapper pid、health endpoint、command、log path。                                                                              |
| `termination-ledger.jsonl`      | stop 动作需要证据，watchdog 需要区分 intentional stop 和 crash。                            | 新增 termination ledger，每次 stop 追加 JSONL 记录。                                                                                                                  |
| `ForceByPort` 是显式开关        | 默认按端口杀进程会误杀其他项目；但现场清理有时需要强制端口清理。                            | 默认不按端口杀未知进程；文档建议把 force-by-port 做成项目级显式操作，而不是通用默认。                                                                                 |
| watchdog rebind listener          | PID file 可能指向短命 wrapper，listener 可漂移。                                            | 通用模块保留 health/authority 证据；detach 型服务通过`stop_command` 负责 graceful stop。跨 OS listener PID rebind 不作为默认，因为 Linux/macOS/Windows 实现差异大。 |
| SingleWindow/pane wrapper cleanup | UI launcher 可能留下 terminal wrapper 进程。                                                | 通用模块只管理它启动并登记的进程；项目若需要 pane cleanup，应作为项目级 cleanup step。                                                                                |
| UTF-8 环境设置                    | Windows 子进程 stdout 编码可能导致服务启动失败。                                            | 项目 launcher 仍可在`ServiceSpec.env` 中设置 `PYTHONUTF8`、`PYTHONIOENCODING` 等变量。                                                                          |

## 是否能 port 回 system_integration_agent_ai

可以 port，但建议分阶段做，不要一次替换所有 launcher 行为。

### 适合直接复用的部分

1. `preferred_ports -> detect -> auto assign`：可用于 gateway、frontend、Flowise、LiteLLM、Aegra、Langfuse 等本地服务。
2. `instance_name` 隔离：可支持同一项目多个 workspace/profile/PR instance 并行运行。
3. state/pid/log 统一目录：可减少每个脚本重复维护 `gateway.pid`、`frontend.pid`、`flowise.pid`。
4. launch authority 与 termination ledger：可以替代或补强现有 diagnostics 写入。

### 不应直接替换的部分

1. `ForceByPort` 的项目特化实现：通用模块已经提供 opt-in `force_stop_by_ports()` 接口，但外部项目现有 Windows-specific 强清理逻辑还包含 `taskkill /T /F`、pane wrapper cleanup、WhatIf preview、command-line 过滤等项目语义。这些不应被通用默认行为直接替换；应作为项目级 resolver/cleanup 接入通用接口。
2. watchdog listener rebind：外部项目的 watchdog 依赖 Windows CIM 和 launch-authority command line 匹配。通用跨 OS 模块不应直接复制这层 Windows-specific 判断。
3. Windows Terminal tiled panes：这是 UX launcher 功能，不属于端口生命周期核心。
4. runtime secret 注入、NO_PROXY、SSL trust bundle：这是外部项目服务配置职责，不属于 port lifecycle。

### 推荐迁移路径

1. 先把 `PortLifecycle` 复制到外部项目 `scripts/port_lifecycle/`。
2. 新增一个小型 Python launcher，例如 `scripts/fullstack_lifecycle.py`，只启动 1-2 个低风险 service。
3. 保留现有 `fullstack-start.ps1` UI wrapper，让它调用 Python launcher，但暂时不删旧逻辑。
4. 将现有 diagnostics 的 `launch-authority` 和 `termination-ledger` 输出对齐到模块 state。
5. 等端口选择、state、stop 行为稳定后，再考虑把 backend/frontend/Flowise/LiteLLM 都迁入 `ServiceSpec`。
6. `ForceByPort`、watchdog、Windows Terminal pane cleanup 继续留在外部项目 launcher 层，作为平台/项目特化能力。

### Port 回去时可接入的扩展点

为了完整承接外部项目，模块已经提供三项可选扩展：

1. `force_by_port` plugin interface：`force_stop_by_ports()` 接受项目提供的 OS-specific resolver/cleaner，模块负责执行 stop 并写 termination ledger。
2. `watchdog callback`：`check_services(callback=...)` 对 state 中的 owned services 做一轮检查；发现 `pid_missing`、`health_unreachable` 或 `listener_identity_changed` 时，把事件交给项目自己的 incident writer。
3. `listener_identity_probe`：`ServiceSpec.listener_identity_url` 可声明 HTTP identity endpoint；模块启动时记录 fingerprint，watchdog 检查时对比当前 fingerprint，用于发现 wrapper/listener 漂移或端口被其他服务接管。

示例：

```python
api = ServiceSpec.from_values(
    name="api",
    preferred_ports=[8010, 8020],
    command=["python", "-m", "my_api", "--port", "{port}"],
    health_url="http://{host}:{port}/health",
    listener_identity_url="http://{host}:{port}/identity",
)

lifecycle.check_services(callback=my_incident_writer)
lifecycle.force_stop_by_ports([api], port_process_resolver=my_safe_resolver)
```

## 本项目 Bug Trend E2E

本项目的 VS Code tasks 只暴露四个入口：

- `E2E: Start Bug Trend`
- `E2E: Stop Bug Trend`
- `E2E: Stop Bug Trend (Force By Port)`
- `E2E: Restart Bug Trend`

它们调用：

```text
scripts/e2e_bug_trend.py
```

默认候选端口：

| Service | Preferred ports                  |
| ------- | -------------------------------- |
| Django  | `8002, 8012, 8022, 8032, 8042` |
| Grafana | `3001, 3011, 3021, 3031, 3051` |

service spec 来自：

```text
scripts/e2e_bug_trend.services.json
```

启动后会写 summary：

```text
state/e2e/bug_trend_ports.json
```

## 验证

运行模块测试：

```powershell
.venv\Scripts\python.exe -m pytest scripts\tests\test_port_lifecycle.py -q
```

Linux/macOS：

```bash
.venv/bin/python -m pytest scripts/tests/test_port_lifecycle.py -q
```

本项目完整 E2E 验证：

```powershell
.venv\Scripts\python.exe scripts\e2e_bug_trend.py restart
```

Force-by-port 兜底：

```powershell
.venv\Scripts\python.exe scripts\e2e_bug_trend.py stop --force-by-port
```
