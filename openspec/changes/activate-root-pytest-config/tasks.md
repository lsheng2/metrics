# Tasks

## 1. 根配置生效与子进程回收（D1–D4）

- [x] 1.1 把根 `pytest.ini` 第 1 行的 `[tool:pytest]` 改为 `[pytest]`，其余键与取值不变（D1）。验证：按 `docs/development/reporting-delivery.md` 的 Environment 定义 `$reportingPython`，在仓库根运行 `& $reportingPython -m pytest --collect-only -qq`（addopts 的 `--verbose` 会抵消一个 `-q`，用 `-qq` 才输出 node id），node id 只来自 `tasks`、`forecast`、`velocity`、`ui_web` 4 个根（spike 实测 985 项），且不含 `bug_metrics/app/api/provider_profile_connection_test.py`；普通 pytest 与经 `scripts\validation\run_report_authoring_tests.py` 运行的 `--markers` 都列出 `browser`；`& $reportingPython -m pytest scripts\tests\test_service_lifecycle_process.py scripts\tests\test_service_lifecycle_engine.py -q` 得到分诊记录的 7 个 `PytestUnraisableExceptionWarning` 失败（RED）。
- [x] 1.2 在 `scripts/tests/test_service_lifecycle_platform_ops.py` 新增 4 个聚焦测试。它们经默认的 `platform_ops.start_process` 启动真实子进程，并用 `weakref` 观察句柄是否被释放：
  - 立即退出的子进程：丢弃句柄后，`process_exists(pid)` 在时限内返回 False，`gc.collect()` 后句柄已释放；
  - 长驻子进程：丢弃句柄后按 pid 调用 `kill_process`，`wait_process_exit` 返回 True，`gc.collect()` 后句柄已释放；
  - 已收集退出码的旧句柄：测试保留句柄并直接调用 `wait()`，再用 monkeypatch 把当前平台的 OS 级原语改为报告"存在"（Windows 上为 `platform_ops.process_exists_windows`，POSIX 上为 `os.kill`），以此模拟 pid 被复用；`process_exists(pid)` 返回 True；
  - launcher 退出：测试启动一个 Python launcher 子进程，launcher 经 `start_process` 启动长驻孙进程，输出孙进程 pid 后正常退出。launcher 在时限内退出，孙进程仍然存活；测试随后按 pid 停止孙进程并等待它退出。

  验证：在 1.3 之前，前两例因丢弃句柄时发出的 `ResourceWarning` 失败（RED），后两例通过。
- [x] 1.3 在 `scripts/service_lifecycle_engine/platform_ops.py` 增加进程级注册表 `_SPAWNED_CHILDREN`，用 `threading.Lock` 保护（D2、D3）：
  - `start_process` 先对已登记的句柄做非阻塞 `poll()`，移除已退出的条目，再创建、登记并返回新句柄；
  - `process_exists` 命中 `returncode` 为 None 的条目时调用 `poll()`：仍在运行返回 True，已退出则移除条目并返回 False；命中已收集退出码的条目时，移除条目并改走 OS 检查；未命中时走原有的 OS 检查；
  - 各函数签名不变，`PlatformOperationSet` 与 `engine.py` 都不改。

  验证：1.2 的 4 个测试通过。1.1 的失败中，泄漏来自 `platform_ops.py:65` 的 4 个用例通过：`test_start_and_stop_service_writes_termination_ledger`、`test_stop_all_recovers_from_pid_file_when_state_is_missing`、`test_start_service_writes_launch_authority_with_identity_probe`，以及 engine 的 `test_shouldPersistPreparedThenAbortedWhenDirectStartFails`。
- [x] 1.4 把 `scripts/tests/test_service_lifecycle_process.py` 的 helper `stop_process` 改为接收句柄：`poll()` 为 None 时按 pid 调用 `kill_process`，然后 `wait(timeout=5)`；`:63`、`:206`、`:228` 三个调用点改为传句柄（D4）。验证：使用测试自建 Popen 的 `test_waitReadyShouldAcceptHealthyEndpointWhenLauncherExitsCleanly`、`test_prepare_startup_does_not_force_stop_unowned_ports_by_default` 与 `test_prepare_startup_force_stops_unowned_ports_when_requested` 通过；`& $reportingPython -m pytest scripts\tests -q` 全部通过，1.1 的 7 个失败全部转为通过。

## 2. 测试启动的 worker 线程关闭自己的连接（D8）

- [x] 2.1 在 `ui_web/tests/test_report_daily_ui_browser.py` 新增模块内 helper，包装 `worker.execute`：每次执行结束时（含异常），在 worker 线程内对 `connections.all(initialized_only=True)` 逐个调用 `BaseDatabaseWrapper.close`，并旁注说明为何绕过 sqlite 后端对内存库的 `close()`。在 `test_shouldRefreshThroughRegisteredWorkerAndReuseSameMeetingFromVisibleControls` 中，于 `build_project_runtime()` 之后、`runtime.start()` 之前调用它。生产代码与 runner 不改。验证：改动前用 `& $reportingPython -I scripts\validation\run_report_authoring_tests.py ui_web\tests\test_report_daily_ui_browser.py -q --tb=short -p no:cacheprovider` 运行整个文件，得到 1 failed、3 passed，失败的是 `test_shouldReprepareFromVisibleDetailsWithoutChangingOriginalHumanNote`，原因是 `ResourceWarning: unclosed database`（RED）；改动后同一命令 4 passed。

## 3. 同步 gate 文档与 MDB-2 5.10（D5–D7）

- [x] 3.1 重写 `openspec/docs/validation/gate-and-ci-plan.md` 的 Full Local Gate（D5）：
  - 引用 `docs/development/reporting-delivery.md` 的 Environment 定义 `$reportingPython`，不复制解释器路径；
  - 普通通道：`& $reportingPython -m pytest tasks\tests forecast\tests velocity\tests bug_metrics\tests jira_history\tests jira_sync\tests metrics\tests provider_sync\tests pull_requests\tests scripts\tests -q`；
  - runner 通道：`& $reportingPython -I scripts\validation\run_report_authoring_tests.py ui_web\tests project_management\tests -q --tb=short -p no:cacheprovider`；
  - `manage.py check` 与两个 hygiene 脚本改用 `$reportingPython`；
  - 删除"`pytest.ini` 不包含全部测试根，所以第二条命令是显式的"这句说明，改为说明通道划分：每个测试根恰好属于一条通道，新增测试根的变更同时把它加入对应通道。附核对命令 `git ls-files '*/tests/test_*.py' | ForEach-Object { ($_ -split '/')[0] } | Sort-Object -Unique`；
  - gate 表中 Full local gate 一行的 Required Commands 改为两条测试通道、Django check 与 hygiene 脚本。

  验证：核对命令列出的 12 个顶层目录与两条通道的根一一对应，`ui_web` 只在 runner 通道；两条通道的命令把 `-q` 换成 `--collect-only -qq` 后都成功，node id 只来自各自列出的根。
- [x] 3.2 Release Gate 改为"先完整运行 Full Local Gate，再运行以下命令"，只保留 Grafana validator、browser 与 C0/C1 命令；Proposed CI Job 1 改为运行 Full Local Gate 的两条测试通道（D6）。验证：Release Gate 与 Job 1 不再重复 Full Local Gate 的 pytest、check 与 hygiene 命令；`git diff` 显示 Local MVP Governance Gate、Browser And Runtime Gate、Release Gate 保留的命令以及 Job 2–6 的 `.venv` 命令都没有变化。
- [x] 3.3 同步描述 Full Local Gate 组成的现行文档，改为两条测试通道：`openspec/docs/validation/test-strategy.md` 的 Full local 行；`ai-validation-operating-model.md` 中 `full local gate passed` 的定义、`all tests passed` 的使用条件，以及 CI Evolution Path 第 1 项。验证：在 `openspec/docs/validation` 中搜索 `default pytest`、`` non-`pytest.ini` `` 与 `explicit excluded roots`，只剩 `jira-grafana-test-plan.md:12` 这条 MVP gate 历史结果。
- [x] 3.4 按 D7 改写 MDB-2 `openspec/changes/embed-ai-base-runtime-in-process/tasks.md` 5.10 中关于根 `pytest.ini` 的括注，描述配置生效后的现状；`s0-spike-report.md` 与 `s0b-*` 不改。验证：`& $reportingPython -m pytest -o ai_host_modes=blocking_wsgi --collect-only -q metrics\tests` 以 INTERNALERROR 退出（exit 3），加 `-o filterwarnings=` 后收集成功，只报告 `PytestConfigWarning`；`npx --no-install openspec validate embed-ai-base-runtime-in-process --strict` 通过。

## 4. 集成验证

- [x] 4.1 在同一收尾窗口内，按 gate-and-ci-plan 原样运行 Full Local Gate 的全部命令：两条测试通道、`manage.py check`、`check_file_size_limits.py --include-untracked` 与 `check_diff_whitespace.py --include-untracked`。验证：全部通过；普通通道的 skip 只有两个需环境变量开启的 `provider_sync` live/perf 用例；按现有"Current observed result on <date>"惯例，把各命令的结果与两条通道的时长记入 Full Local Gate。结果（2026-11-13，窗口 07:35:44–09:34:28）：五条命令都以 0 退出；普通通道 932 passed、2 skipped（242.90 秒），runner 通道 1700 passed（6869.90 秒），已记入 Full Local Gate。
- [x] 4.2 用 legacy `.venv` 解释器运行仍写作 `.venv` 的 Local MVP Governance Gate 两条 pytest 命令，以及 Browser And Runtime Gate 的 browser 命令（本 worktree 没有 `.venv`，使用主工作区的 `.venv`）。验证：三条命令都以 0 退出（分诊时分别为 157、38、4 passed），结果记入本任务。结果（2026-11-13，配置已生效，1.x 与 2.1 的改动已就位）：三条命令都以 0 退出，分别为 157 passed（28.60 秒）、38 passed（2.48 秒）、4 passed（13.00 秒）。
- [x] 4.3 核对待提交范围并校验本 change。验证：`git status` 只含 `pytest.ini`、`scripts/service_lifecycle_engine/platform_ops.py`、`scripts/tests/test_service_lifecycle_platform_ops.py`、`scripts/tests/test_service_lifecycle_process.py`、`ui_web/tests/test_report_daily_ui_browser.py`、`openspec/docs/validation/` 下的三份文档、MDB-2 的 `tasks.md` 与本 change 目录；`npx --no-install openspec validate activate-root-pytest-config --strict` 通过。

## Workflow follow-up

- 按 allowlist 提交，commit 带 Co-authored-by trailer。配置生效与它暴露的失败的修复放在同一个提交里，所有提交一次 push。
- 评审通过后归档本 change：新建主 spec `repository-test-gates`，把新增需求合入 `service-lifecycle-engine`；归档后运行 `npx --no-install openspec validate --specs --strict`。
- 测试库改用文件库、负载下连锁锁死的排查，另起后续 change（见 design Open Questions）。
