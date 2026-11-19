# W5 接入反馈给 AI Base Agent

> 2026-11-11起已被[MDB-2](../embed-ai-base-runtime-in-process/proposal.md)取代：本文件仅为历史证据，不定义剩余工作。

日期：2026-11-02。范围：实际消费a2过程中发现的跨应用接入问题。
本文件不修改FZ-01、a1/a2制品或基座任务状态；应用业务联调结果由单独回执确认。

## 需要基座处理

1. **RunSubmit schema缺少实际deadline格式约束。**
   `template_runtime/task_runs/contracts.py:utc_milliseconds`要求
   `YYYY-MM-DDTHH:MM:SS.sssZ`，但a2 `schemas/RunSubmit.json`只声明string。
   因此通过发布schema的请求仍被真实HTTP返回422/invalid_request。
   Dashboard已在发送前检查格式，并以UTC三位毫秒、向下截断方式生成新请求；
   已持久化的旧失败attempt未修改。该实验的Base task_runs为0，executor未执行。
   请在新的版本制品中补pattern/格式说明及相应conformance向量，不修改旧a2 bytes。
   这对任何按schema生成客户端的应用都有影响，不是Dashboard特有字段。

2. **请优先提供官方的显式合成向量入口。**
   现有默认launcher只接受占位Project/Stage/规则hash，不能直接验证应用生成的真实身份。
   我方通过现有`create_task_run_candidate`装配了仅接受一个显式向量的测试executor，
   不改公共协议。后续可在官方合成launcher增加经过schema/hash校验的fixture-pack输入，
   使各应用不必分别编写server装配和进程控制。不要允许任意代码插件或真实模型fallback。

3. **合成server交付应列全运行资源闭包。**
   factory导入会经全局routes/services读取根目录`config/app-profiles.json`等资源。
   仅复制services/app-service不足。我方已使用固定完整commit加交付overlay，
   844个文件逐一核验，并增加私有环境、禁外网的导入探针。
   推荐基座提供自包含的合成runtime包，或在交接中明确完整源码及根配置要求。

Windows venv存在launcher/worker PID不同的情况。我方已核验操作系统父子关系与
完整fixture argv，正常停止使用唯一stopFile并验证worker退出；未修改基座通用生命周期。
官方launcher若提供PID元数据，建议区分launcher和worker，避免其他应用重复遇到此边界。

## 双方继续方式

Dashboard负责真实Project/Stage/capture输入、持久attempt、原结果与领域接受。
Base负责通用Run/SDK、真实backend资格、取消/unknown/恢复及新版本合同交付。
以上增强无需重开FZ-01，也不必等待Dashboard名单/附件功能全部完成。
请优先确认第1项并返回对应任务及新版制品计划；我方使用现有协议正确格式继续合成联调，
不等待全面平台改造，不代签真实模型或正式部署资格。
