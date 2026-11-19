# Spec Delta

## MODIFIED Requirements

### Requirement: Sidecar handshake is identity-checked
Dashboard SHALL check the AI Base sidecar's declared identity before treating any local service as the active sidecar. 这项检查只用于发现配置错误：Dashboard SHALL NOT 把未鉴权握手返回的任何值当作 AI Base 的身份证明。

#### Scenario: Expected sidecar responds
- **WHEN** Dashboard probes AI Base
- **THEN** Dashboard SHALL verify `serviceId`, profile id, health path and app capability summary before enabling AI UI

#### Scenario: Wrong sidecar responds on the port
- **WHEN** a local HTTP service responds but service identity does not match the configured sidecar
- **THEN** Dashboard SHALL treat AI as unavailable and SHALL NOT send dashboard context, user prompts or artifact references to that service

#### Scenario: Handshake publishes an instance token
- **WHEN** 握手响应携带的 `instanceToken` 与 Dashboard 用于 binding 的 token 不一致
- **THEN** Dashboard SHALL NOT 比对这个值，也 SHALL NOT 据此判定 sidecar 是否就绪，因为未鉴权端点会把它返回给任何调用方
- **AND** sidecar 状态 SHALL NOT 包含任何 token
