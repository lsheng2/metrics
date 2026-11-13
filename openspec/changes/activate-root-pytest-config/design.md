# Design

## Context

动机见 proposal.md「Why」，需求见 `specs/repository-test-gates` 与 `specs/service-lifecycle-engine`。这里只列决定方案的现状与约束。

**pytest 如何读取根配置**

- pytest 9.1.1 只从 `pytest.ini` 的 `[pytest]` 节读取选项（`_pytest/config/findpaths.py:69-77`）。
- 没有该节的 `pytest.ini` 仍决定 rootdir，并在会话头显示为 `configfile`，但不提供任何选项。所以 `configfile: pytest.ini` 不能证明配置生效，验收要看收集范围与警告行为。
- 两条测试通道都从仓库根启动，因此读取同一份配置：
  - 普通通道：`python -m pytest <roots>`；
  - runner 通道：`scripts/validation/run_report_authoring_tests.py` 先用内存 sqlite 与合成环境调用 `settings.configure`，禁用 dotenv，只放行 loopback socket，再调用 `pytest.main`。

**生效后哪些行为会变**

- 会变的只有三项：默认收集范围（4 个根）、不再收集 `*_test.py`、警告即错误（同时注册 `browser` marker）。
- 其余键不改变现有行为：
  - `DJANGO_SETTINGS_MODULE` 来自根 `conftest.py:5` 的 `setdefault`，不来自 ini；
  - 测试库是没有 TEST NAME 的 sqlite 内存库，`--reuse-db` 无实际作用；
  - addopts 的 `--verbose` 与 gate 命令的 `-q` 相抵；
  - `python_functions = test_*` 比默认的 `test` 前缀窄，但 12 个根在两种设置下收集到的 2,630 个节点完全相同。

**解释器**

- `docs/development/reporting-delivery.md` 定义选定解释器 `$reportingPython`。它的 `.pth` 把 legacy `.venv` 的 site-packages 加入路径，所以等于 legacy 依赖加 SDK 0.2.0a1。
- AI_CONTRACT §4 要求 reporting、`ui_web`、`project_management` 测试用它经 runner 运行。
- 本 worktree 没有 `.venv` 与 `.env`；`manage.py check` 在两个解释器下都通过。

**Spike 分诊**（只改节头）

- 普通通道（10 个根、930 项，选定解释器）：7 failed、921 passed、2 skipped，227 秒。7 个失败都是 `Popen.__del__` 发出的 `ResourceWarning`，经 unraisable 钩子转为 `PytestUnraisableExceptionWarning`。
- runner 通道（`ui_web`、`project_management`，1,700 项）：1 failed、1,699 passed，原因见下文「测试库与线程连接」。
- 仍用 legacy `.venv` 的 gate 命令：Local MVP Governance Gate 的两条 pytest 命令 157、38 passed；Browser And Runtime Gate 的 browser 命令 4 passed。

**Popen 句柄为何泄漏**

- `Popen.__del__` 在 `returncode is None` 时发出 `ResourceWarning`。子进程已退出、但没人调用 `poll()` 或 `wait()` 时也会发出。
- POSIX 上，CPython 把被丢弃的运行中句柄放进 `subprocess._active`，之后创建 Popen 时由 `_cleanup()` 回收；Windows 上 `_active` 为 None。
- POSIX 上 `os.kill(pid, 0)` 对僵尸进程返回成功；Windows 上，进程句柄关闭前 pid 不会被复用。
- 泄漏来源：
  - 生产代码：`engine.py:69` 经 `platform_ops.start_process`（`platform_ops.py:57-65`）拿到句柄，readiness 通过后 `start_service` 返回时把它丢弃。abort 路径（`engine.py:115-125`）按 pid terminate 或 kill，再用 `wait_process_exit`（`platform_ops.py:240-246`）按 pid 轮询 OS，从不经句柄收集退出码。受影响的是 process 测试 `:122`、`:136`、`:149` 与 engine 测试 `:358`。
  - 测试代码：`test_service_lifecycle_process.py` 自建的 Popen（`:46`、`:192`、`:212`）由 helper `stop_process(pid)`（`:258-261`）按 pid 停止，从不回收句柄。

**测试库与线程连接**

- 两条通道的测试库都是没有 TEST NAME 的 sqlite 内存库。Django 把它建成 `file:memorydb_default?mode=memory&cache=shared`；各线程的连接共享同一个库，只要测试线程的连接还开着，库就存在。
- Django 6.0.7 的 sqlite `close()` 对内存库直接忽略（`django/db/backends/sqlite3/base.py:221-227`），以防误删测试库。
- 因此 `ProjectRunRuntime._run` 结束时的 `connections.close_all()`（`project_management/runtime.py:118`）在测试中关不掉 worker 线程的连接。生产库是文件库（`metrics/settings/defaults_metrics.py:46-53`），关闭正常生效。
- 线程退出后，这个 `sqlite3.Connection` 要等之后的循环 GC 才被回收。Python 3.13 此时发出 `ResourceWarning: unclosed database`，经 unraisable 钩子落在当时正在运行的用例上。
- 临时连接探针的定位结果：
  - 连接由 `project-run-worker` 线程在 `test_report_daily_ui_browser.py:446` 的用例中创建，调用链为 `runtime.py:103` → `project_run_worker.py:57` → … → `report_templates.py:159` 的 `transaction.atomic()`；
  - 警告落在按字母序紧随其后的 `:495` 用例。单独运行该用例会通过，运行整个文件可以复现。
- 只有这一个测试启动了访问 ORM 的真实 worker 线程：
  - 其他构造 `ProjectRunRuntime` 的测试不调用 `start()`；
  - `project_run --execute-local` 在调用线程内同步执行；
  - `test_project_runtime.py` 不使用数据库。
- LiveServer 在内存库下让服务线程共享测试线程的连接，不会产生独立连接。

## Goals / Non-Goals

**Goals:**

- 生产修复只落在默认平台操作内部：`PlatformOperationSet` 的签名、`engine.py` 与注入 fake 的调用方都不改。
- 在同一 OS 进程内，子进程的回收与 pid 判定保持一致，跨 engine 实例有效。
- gate 命令只有一个来源：Release Gate 与 CI Job 1 引用 Full Local Gate，解释器路径只在 `reporting-delivery.md` 定义一次。
- 测试线程的连接泄漏在启动该线程的测试内修复，生产代码与 runner 都不改。

**Non-Goals:**

- 不让 CLI `start` 在退出时等待或终止分离的服务，不注册 atexit 钩子。
- 不改测试库与 runner 的隔离方式：两条通道继续使用 sqlite 内存测试库；runner 的 settings、dotenv 与 socket 守卫不变。
- 不引入新的 pytest 插件（如 pytest-timeout、xdist），也不新增 `strict`、`--strict-markers` 等选项。
- 不处理未登记子进程在 POSIX 上的僵尸判定（见 Risks）。
- 不为"新增测试根"写自动检查脚本，靠 gate 文档里的核对命令与评审。

## Decisions

### D1. 只改节头，键全部保留

把 `[tool:pytest]` 改为 `[pytest]`，键与取值不变。

备选：

- 迁到 `pyproject.toml` 或 pytest 9 的 `pytest.toml`：格式迁移不带来行为收益，只会扩大 diff。
- 删除 `pytest.ini`，把文档改成"没有根配置"：会丢掉现有文档都假定的警告即错误策略。
- 顺带收紧（加 `strict`、调整 `testpaths`）：超出 owner 选定的 minimal 范围。

### D2. 默认平台操作用进程级注册表持有并回收子进程

`platform_ops` 增加模块级 `_SPAWNED_CHILDREN: dict[int, subprocess.Popen]`，由 `threading.Lock` 保护：

- `start_process`：先对已登记的句柄做非阻塞 `poll()`，移除已退出的条目（与 CPython 的 `_cleanup()` 对称，Windows 上同样生效）；再创建、登记并返回句柄。
- `process_exists(pid)`：命中、且 `returncode` 为 None 时调用 `poll()`；仍在运行返回 True，已退出则移除条目并返回 False。未命中时走原有的 OS 检查。
- `wait_process_exit` 经 `process_exists` 轮询，因此自动回收。`terminate_process`、`kill_process` 仍按 pid 操作。

为什么放在进程级：lifecycle state 以 JSON 跨进程持久化，停止可能由另一个 engine 实例或 `stop_all` 发起，只有进程级注册表能让同一 OS 进程内的任何调用都回收到句柄。engine 测试 `:358` 注入了 `process_exists=lambda pid: True`，但默认的 `wait_process_exit` 调用模块级实现，所以 abort 路径照样回收。

退出语义：不在退出时 kill 或 wait。解释器退出时仍在运行的句柄被直接丢弃，由此产生的 `ResourceWarning` 被默认警告过滤器忽略。CLI `start` 的分离服务语义不变，由聚焦测试覆盖"launcher 退出后服务仍在运行"。

备选：

- 每个 engine 实例保存句柄：跨实例停止与 `stop_all` 回收不到。
- 把句柄放进 lifecycle state 由调用方持有：state 要跨进程持久化，句柄无法序列化，跨进程停止仍要按 pid。
- 只在 abort 路径补 `poll()`：漏掉 readiness 通过后丢弃句柄的路径。
- 每个子进程配一个后台回收线程：实现复杂，会与按 pid 的检查竞争，还会在退出时留下线程。
- 用 `filterwarnings` ignore 或 marker 屏蔽：掩盖真实泄漏，违反 `repository-test-gates`。
- 直接给 `returncode` 赋值消除警告：篡改标准库对象的状态。

### D3. 已收集退出码的条目不参与 pid 判定

命中的条目如果 `returncode` 已设置，说明调用方已经直接对同一句柄调用过 `poll()` 或 `wait()`，例如 `wait_ready` 每轮的 `poll()`、abort 路径 `engine.py:115`。这时移除条目，改走 OS 检查。

理由：POSIX 上子进程被回收后，pid 可能被无关进程复用。只有"仍持有且尚未收集退出码"的句柄能保证 pid 仍指向该子进程：POSIX 上未回收前 pid 不会释放，Windows 上句柄未关闭前 pid 不会复用。

备选：保留条目并直接返回 False。pid 被复用时会把无关进程误报为不存在。

### D4. 测试自建的子进程由测试自己回收

helper 改为接收句柄：`poll()` 为 None 时调用 `kill_process(pid)`（保留按进程树强杀的语义），然后 `wait(timeout=5)`。三个调用点改为传句柄。

备选：

- `with Popen(...)`：`__exit__` 无超时等待，测试失败时可能挂起。
- 把测试句柄登记进 `platform_ops` 的注册表：测试会依赖私有模块状态。

### D5. Full Local Gate 的通道与解释器

- 普通通道跑 10 个根：`tasks`、`forecast`、`velocity`、`bug_metrics`、`jira_history`、`jira_sync`、`metrics`、`provider_sync`、`pull_requests`、`scripts`。
- runner 通道跑 `ui_web` 与 `project_management`（AI_CONTRACT §4）。`ui_web` 不再由普通通道重复运行。
- 两条通道、`manage.py check` 与两个 hygiene 脚本统一使用 `$reportingPython`。gate 文档引用 `reporting-delivery.md` 中的定义，不复制路径。
- gate 文档附一条核对命令：用 `git ls-files` 列出所有 `*/tests/test_*.py` 的顶层目录，再与两条通道比对。

备选 A：普通通道、check 与 hygiene 继续用 `.venv`。

- 同一个 gate 会用两个解释器；
- worktree 里没有 `.venv`，命令无法直接执行；
- 与 AI_CONTRACT §4"不在 legacy `.venv` 中运行已迁移消费者"的取向相悖。

### D6. Release Gate 与 CI Job 1 引用 Full Local Gate

- Release Gate 改为"先完整运行 Full Local Gate，再运行以下命令"，只保留 Grafana validator、browser 与 C0/C1 命令。
- Job 1 改为"运行 Full Local Gate 的两条测试通道"。

理由：这次漂移正是因为同一组命令在三处各存一份，然后各自过时。

备选：三处同步复制同一组命令。副本依旧存在，下次还会漂移。

### D7. MDB-2 5.10 只改写关于根配置的括注

改写后描述现状：

- 根配置已生效，含 `filterwarnings = error`；
- 根 `pytest.ini` 不声明 `ai_host_modes`，addopts 也不加载插件；
- 未加载插件时，未知的 ini 选项不论写在 `pytest.ini` 里还是经 `-o` 传入，都会触发 `PytestConfigWarning`，在 `filterwarnings = error` 下以 INTERNALERROR 退出；
- 一致性通道以 `-p` 加载插件，`ai_host_modes` 在那里是已声明的选项；该通道同样执行根配置的警告策略。

Spike 下已实测：`-o ai_host_modes=blocking_wsgi --co metrics/tests` 以 3 退出；加 `-o filterwarnings=` 后只告警。

不改的文件：`s0-spike-report.md:217` 与 `s0b-*` 是历史回执；MDB-2 `design.md:933` 在修复后仍然准确。

### D8. 启动 worker 的测试让 worker 线程自行关闭连接

在 `test_report_daily_ui_browser.py:446` 的用例中，`runtime.start()` 之前包装 `runtime.worker.execute`：每次执行结束时（含异常），在 worker 线程内对本线程已初始化的连接调用 `BaseDatabaseWrapper.close`。

- 显式调用基类的 `close()`，绕过 sqlite 后端对内存库的忽略逻辑。共享缓存的内存库仍由测试线程的连接保持存活，数据不受影响。
- 关闭发生在创建连接的线程内，不需要 `inc_thread_sharing()`，也不用私有的 `_close()`。
- helper 放在该测试模块内，旁注说明为何绕过 sqlite 的 `close()`。以后若有测试启动访问 ORM 的线程，警告即错误会让泄漏直接失败；届时再把 helper 移到共享测试支持模块。
- 分诊用临时插件验证了同一机制：内存库下 daily 文件 4 passed（353 秒）；不包装时 1 failed、3 passed（347 秒）。

备选：

- 让 runner 改用每次运行临时目录中的文件库（`NAME` 与 `TEST.NAME`）：
  - 优点：与生产一致，从根上消除这类泄漏，daily 文件单独验证也通过；
  - 问题：完整 runner 通道在高负载下，从 `test_report_history_ui_browser.py` 的第 8 个用例起连续 failed + error，此后 61 个用例（含非浏览器的 transactional 用例）全部受影响，直到运行在 27% 处被停止，表现为 DB 被持续锁住；
  - 无负载时按原顺序定向重放 12 个文件、71 项全部通过，根因未查明；
  - 采用它需要先查清这个问题，超出本 change 范围（见 Open Questions）。
- 测试线程记录 worker 连接，在 `runtime.stop()` 后用私有的 `_close()` 关闭：依赖私有 API，还要绕过跨线程共享校验。
- 让 worker 线程共享测试线程的连接（同 LiveServerThread 的做法）：worker 的 `transaction.atomic()` 会与并发请求线程在同一个 `DatabaseWrapper` 上交错，事务状态不安全。
- 过滤该警告：违反 `repository-test-gates`；而且警告在 GC 时于任意栈帧发出，无法按来源模块精确匹配。

## Risks / Trade-offs

- [未登记的子进程在 POSIX 上被判为存在] `test_service_lifecycle_process.py:226` 对测试自建、未登记的子进程断言 `not process_exists(pid)`。POSIX 上被 kill 但未回收的子进程是僵尸，`os.kill(pid, 0)` 会成功，断言因此失败。→ 这是既有问题，当前 gate 只在 Windows 上运行，本 change 不修。将来引入 POSIX CI 时，改为对句柄 `wait(timeout)` 断言。
- [注册表持有句柄，直到观察到退出] 长时间运行、反复启动服务的进程会累积条目。→ `start_process` 每次先清理已退出的条目；条目数受服务数量约束。
- [测试遗留的运行中子进程不再以 `ResourceWarning` 暴露] 句柄由模块全局持有，pytest 会话内不会被回收。→ 现有 lifecycle 测试在 `finally` 中停止自己启动的服务；新增聚焦测试断言停止后句柄被释放。会话级检查见 Open Questions。
- [退出时仍在运行的句柄] 解释器退出时的 `ResourceWarning` 只在 `-X dev` 或显式 `-W` 下可见，不影响退出码。→ 这是分离服务的预期语义，由 launcher 退出的聚焦测试固定。
- [选定解释器位于 `.tmp/`] gate 依赖一个临时的 SDK join venv；MDB-2 换成 `ai_base_runtime` 时它会变化。→ gate 文档只引用 `reporting-delivery.md` 的 `$reportingPython`；MDB-2 5.7 改写该环境说明时，gate 自动跟随。
- [不带路径的 pytest 覆盖面缩小] 过去会跑 12 个根，现在只跑 4 个。→ AI_CONTRACT、reporting-delivery 与 gate 文档都已写明默认范围；只有 Full Local Gate 通过后才能声明 all tests passed。
- [警告策略作用于所有从仓库根启动的 pytest] 包括 Local MVP Governance Gate、Browser And Runtime Gate 中仍用 `.venv` 的命令，以及 MDB-2 的一致性通道。依赖升级或嵌入 AI Base 后新出现的第三方警告会让测试失败。→ 按 `repository-test-gates` 的第三方警告规则处理。分诊时这些命令在配置生效下全部通过（见 Context），目前没有新暴露的第三方警告。
- [Full Local Gate 变长] 分诊中普通通道 930 项用时 227 秒；runner 通道 1,700 项用时 6,582 秒（1:49:42），期间与其他分诊运行并行，数值偏高。→ gate 文档按现有惯例记录实施时的实测结果与时长，便于设置超时。
- [以后启动线程的测试再次泄漏连接] helper 只用于当前唯一启动 worker 的测试。→ 警告即错误会让新的泄漏直接失败；`repository-test-gates` 的场景规定由启动线程的测试修复。
- [`BaseDatabaseWrapper.close` 绕过了 sqlite 的保护] 如果在测试线程的连接上调用，会销毁内存测试库。→ helper 只在 worker 线程内、只关闭该线程自己的连接；测试线程的连接仍由 Django 测试框架管理。

## Migration Plan

1. 按 tasks 顺序在同一分支实施：先让配置生效并修复它暴露的失败，再同步文档。所有提交一次 push，远端不会出现"配置已生效但泄漏未修"或"文档与行为不符"的状态。
2. 无数据迁移。旧代码启动、仍在运行的服务不受影响，停止仍按 pid 进行。
3. 回滚：revert 本 change 的提交。注册表在配置未生效时也无害。

## Open Questions

- 是否在 `scripts/tests` 增加会话级检查，要求测试结束时注册表里没有仍在运行的子进程。可以留给后续 change 决定，不影响本 change 的 specs、方案与任务。
- 是否让测试库改用每次运行临时目录中的文件库，使线程与连接语义和生产一致。这需要先在一个后续 change 中查清 D8 记录的负载下连锁锁死：在高负载下复现，拿到首个失败的 traceback 和持锁线程，再判断它是测试夹具的问题，还是生产代码在文件库下真实存在的并发缺陷。
