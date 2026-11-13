# Proposal

## Why

根 `pytest.ini` 自 `9a894fc`（2025-08-13）起只有 `[tool:pytest]` 节。pytest 9.1.1 在 `pytest.ini` 中只读取 `[pytest]` 节，所以这份配置从未生效：

- `testpaths` 不生效，不带路径的 pytest 会收集全部 12 个测试根，还会把生产模块 `bug_metrics/app/api/provider_profile_connection_test.py` 当作测试收集。
- `filterwarnings = error`、`browser` marker 注册和 `python_files` 都不生效。

AI_CONTRACT、repo-context、reporting-delivery 和 gate-and-ci-plan 都假定默认只收集 4 个根、警告即错误，但这与实际行为不符。按现有命令写出的 Full Local Gate 也漏掉了 `metrics`、`provider_sync`、`scripts` 和 `project_management`。

分诊表明，配置生效后，`filterwarnings = error` 会立即暴露两处真实的资源泄漏：

- lifecycle engine 的子进程句柄：普通通道 7 个用例因 `Popen.__del__` 的 `ResourceWarning` 失败；
- daily 浏览器测试启动的 worker 线程，在 sqlite 内存测试库上留下未关闭的连接：runner 通道 1 个用例失败。

此外，进行中的 MDB-2 task 5.10 把一致性通道的设计建立在根配置语义上，它的描述仍停留在"配置未生效"的状态。

所以现在应让配置真正生效，从源头修复它暴露的问题，并让 gate 文档与实际行为一致。

## What Changes

- 把根 `pytest.ini` 的节头改为 `[pytest]`，其余键保持不变：
  - 默认根仍是 `tasks`、`forecast`、`velocity`、`ui_web`；
  - `filterwarnings = error`；
  - `browser` marker；
  - `python_files = test_*.py`。
- 在 `scripts/service_lifecycle_engine` 的默认平台操作中，由当前 OS 进程持有并回收经它启动的子进程：
  - readiness 通过后不再丢弃仍在运行的子进程句柄；
  - 停止和 abort 路径会收集退出码；
  - 在 POSIX 上，未回收的僵尸子进程不再被报告为"仍存在"；
  - `PlatformOperationSet` 接口不变。
- 修复 `scripts/tests/test_service_lifecycle_process.py` 中测试自建 `Popen` 的回收：停止 helper 改为接收句柄，并等待回收。
- 修复 `ui_web/tests/test_report_daily_ui_browser.py` 中测试启动的 project-run worker 线程的连接泄漏：该测试让 worker 线程在每次执行结束时关闭自己的数据库连接。Django 对 sqlite 内存库忽略 `close()`，所以生产代码在线程结束时的关闭在测试中不起作用。生产代码与 runner 都不改。
- 重写 `openspec/docs/validation/gate-and-ci-plan.md` 的 Full Local Gate：
  - 显式覆盖全部 12 个测试根，不再依赖默认 `testpaths`；
  - `ui_web` 与 `project_management` 经 no-dotenv runner 运行；
  - 其余 10 个根用普通 pytest 运行；
  - 统一使用 `reporting-delivery.md` 定义的选定解释器。
- Release Gate 与 Proposed CI Job 1 改为引用 Full Local Gate，不再重复列出其中的命令。
- 同步描述 Full Local Gate 组成的现行文档：
  - `test-strategy.md` 的 Full local 行；
  - `ai-validation-operating-model.md` 的收尾声明用语与 CI 演进项；
  - gate-and-ci-plan 的 gate 表。
- 改写 MDB-2 `embed-ai-base-runtime-in-process/tasks.md` 5.10 中关于根 `pytest.ini` 的描述，使其反映配置生效后的现状。历史回执 `s0-spike-report.md` 保持不变。

**非目标**：

- 不改变默认 `testpaths` 的 4 个根。
- 不建立 hermetic 统一测试入口。
- 不改测试库：两条通道继续使用 sqlite 内存测试库。是否改用文件库，留作后续 change 的待决项（见 design Open Questions）。
- 不修复与配置生效无关的既有失败。
- 不改以下段落里的 `.venv` 命令：Local MVP Governance Gate、Browser And Runtime Gate、Release Gate 在 Full Local Gate 之外追加的命令，以及 Job 1 以外的 Proposed CI Jobs。

## Capabilities

### New Capabilities

- `repository-test-gates`：仓库级 pytest 配置与本地测试门禁的契约，包括以下内容：
  - 根配置生效后的默认收集范围；
  - 警告即错误的策略，以及在来源处修复警告的约束；
  - Full Local Gate 对全部测试根的显式覆盖与通道划分。

### Modified Capabilities

- `service-lifecycle-engine`：新增一项需求。默认平台操作在同一 OS 进程内持有并回收自己启动的子进程，readiness 后和 abort 后都不留下未回收的句柄，进程存在性检查不把已退出的子进程报告为存在。

## Impact

- **配置**：根 `pytest.ini`。普通 pytest 与 `scripts/validation/run_report_authoring_tests.py` 内部的 `pytest.main` 都会读取它，因此两条通道都开始执行警告即错误。
- **生产代码**：`scripts/service_lifecycle_engine/platform_ops.py`（`start_process`、`process_exists`；`wait_process_exit` 经 `process_exists` 间接受影响）。`engine.py` 与 `PlatformOperationSet` 的签名不变，注入 fake 平台操作的调用方不受影响。
- **测试**：
  - `scripts/tests/test_service_lifecycle_process.py`；
  - `scripts/tests/test_service_lifecycle_platform_ops.py`（新增聚焦测试）；
  - `ui_web/tests/test_report_daily_ui_browser.py`。
- **文档**：
  - `openspec/docs/validation/gate-and-ci-plan.md`、`test-strategy.md`、`ai-validation-operating-model.md`；
  - `openspec/changes/embed-ai-base-runtime-in-process/tasks.md`（5.10）。
- **开发者行为**：不带路径的 pytest 只收集 4 个默认根，比现在少 8 个根。需要覆盖其他模块时，必须按 gate 文档显式运行。
