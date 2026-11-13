# Spec Delta

## ADDED Requirements

### Requirement: Default platform operations reap the child processes they start
默认 `PlatformOperationSet` SHALL 在当前 OS 进程内持有经其 `start_process` 启动的子进程句柄，直到观察到该子进程退出。

- 进程存在性检查与等待退出 SHALL 先依据这些句柄判定，并收集已退出子进程的退出码；
- 其余 pid SHALL 使用 OS 级检查；
- 注入的平台操作不受本需求约束。

#### Scenario: Ready service handle is retained
- **WHEN** `start_service` 经默认平台操作启动服务，readiness 通过后返回，调用方随后执行垃圾回收
- **THEN** 系统 SHALL NOT 因子进程仍在运行而发出 `ResourceWarning`

#### Scenario: Stopping in the same OS process reaps the child
- **WHEN** 同一 OS 进程内任一 engine 实例停止该服务并等待其退出
- **THEN** 等待 SHALL 报告已退出，并且该子进程的退出码 SHALL 已被收集
- **AND** 此后的垃圾回收 SHALL NOT 发出 `ResourceWarning`

#### Scenario: Aborted start reaps the child
- **WHEN** readiness 失败，abort 路径终止子进程并等待其退出
- **THEN** 子进程的退出码 SHALL 已被收集
- **AND** `start_service` 抛出原异常后，垃圾回收 SHALL NOT 发出 `ResourceWarning`

#### Scenario: Exited child is reported as absent
- **WHEN** 经默认平台操作启动的子进程已经退出，但退出码尚未收集
- **THEN** 进程存在性检查 SHALL 返回不存在，并收集退出码
- **AND** 在 POSIX 上 SHALL NOT 把该子进程的僵尸状态报告为存在

#### Scenario: Other pids use the operating system check
- **WHEN** 被检查的 pid 不对应当前 OS 进程持有、且退出码尚未收集的子进程句柄
- **THEN** 进程存在性检查 SHALL 使用 OS 级检查
- **AND** SHALL NOT 依据已收集退出码的旧句柄作出判断

#### Scenario: Launcher exit neither waits for nor terminates running children
- **WHEN** 启动服务的 OS 进程（例如 CLI `start`）在服务就绪后正常退出
- **THEN** 该进程 SHALL NOT 等待或终止仍在运行的子进程
- **AND** 服务 SHALL 继续运行，并可由之后的进程按 lifecycle state 停止
