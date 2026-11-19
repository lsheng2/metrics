# repository-test-gates Specification

## Purpose
定义仓库级 pytest 配置与本地测试门禁的契约，包括三点：根配置必须真正生效；警告在产生它的代码处修复；Full Local Gate 显式覆盖全部模块测试根，并按运行环境划分通道。

## Requirements

### Requirement: Root pytest configuration is effective
仓库根 pytest 配置 SHALL 被 pytest 实际读取，具体要求如下：

- 不带路径运行时，默认收集范围 SHALL 仅为 `tasks/tests`、`forecast/tests`、`velocity/tests` 与 `ui_web/tests`；
- 测试模块 SHALL 只匹配 `test_*.py`；
- `browser` marker SHALL 已注册；
- 经 no-dotenv runner 运行的 pytest SHALL 读取同一份根配置。

#### Scenario: Pathless run collects only the default roots
- **WHEN** 在仓库根不带路径运行 pytest
- **THEN** pytest SHALL 报告根 `pytest.ini` 为 configfile，并且只收集 4 个默认根中的测试
- **AND** 其他模块的测试根与名为 `*_test.py` 的生产模块 SHALL NOT 被收集

#### Scenario: Runner lane uses the same configuration
- **WHEN** 测试经 `scripts/validation/run_report_authoring_tests.py` 运行
- **THEN** runner 内的 pytest SHALL 报告同一个根 `pytest.ini` 为 configfile，并执行其中的警告策略与 marker 注册

### Requirement: Warnings fail tests and are fixed at their source
根配置 SHALL 把测试期间未处理的警告视为错误，包括经 unraisable 路径报告的 `ResourceWarning`。

- 仓库 MUST NOT 用全局 `ignore` 过滤、skip 或 xfail 消除这类失败。
- 警告 SHALL 在产生它的代码处修复。

#### Scenario: Unreaped subprocess handle fails the test
- **WHEN** 测试期间有子进程句柄在退出码尚未收集时被垃圾回收，并因此发出 `ResourceWarning`
- **THEN** 该测试 SHALL 失败

#### Scenario: Test-started thread leaves its database connection open
- **WHEN** 测试启动的线程访问过 ORM，结束时它的数据库连接仍未关闭，随后被垃圾回收并发出 `ResourceWarning`
- **THEN** 当时运行的测试 SHALL 失败
- **AND** 修复 SHALL 落在启动该线程的测试中，由该线程在结束前关闭自己的连接

#### Scenario: Warning from code the repository cannot change
- **WHEN** 警告来自仓库无法修改的第三方代码
- **THEN** 只允许添加按警告类别与来源模块精确匹配的过滤项
- **AND** 该过滤项旁 SHALL 注明来源与移除条件

### Requirement: Full Local Gate covers every module test root explicitly
Full Local Gate SHALL 显式列出仓库中每个模块的 `tests` 根，不依赖默认收集范围，并按以下方式划分：

- `ui_web` 与 `project_management` SHALL 经 no-dotenv runner 运行；
- 其余测试根 SHALL 由普通 pytest 通道运行；
- 两条测试通道、Django check、文件大小检查与空白检查 SHALL 使用同一个选定解释器。

#### Scenario: Each test root belongs to exactly one lane
- **WHEN** 对照仓库跟踪的 `*/tests/test_*.py` 所属测试根核对 Full Local Gate
- **THEN** 每个测试根 SHALL 恰好出现在一条通道中
- **AND** `ui_web` SHALL NOT 由普通 pytest 通道重复运行

#### Scenario: New test root is added
- **WHEN** 某个变更新增模块测试根
- **THEN** 同一变更 SHALL 把该测试根加入 Full Local Gate 的对应通道

#### Scenario: Full local gate pass claim
- **WHEN** 有人声称 full local gate 通过
- **THEN** 两条测试通道、Django check、文件大小检查与空白检查 SHALL 在同一收尾窗口内全部通过
