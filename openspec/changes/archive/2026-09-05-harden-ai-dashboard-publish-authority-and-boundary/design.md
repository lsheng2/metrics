## Overview

本 change 关闭 AI-centric dashboard 从 chat 到 Grafana publish 的 authority gap。核心设计不是增加更多 if-check，而是把四个边界提升为显式 authority：

1. **PublishAuthorization**: Dashboard/Metrics 签发并校验的发布授权对象。
2. **Immutable Artifact Revision**: AI Base 保存可重放 artifact version/content hash。
3. **Workspace Boundary Policy**: AI Base connector runtime 使用 active workspace boundary 约束 model-visible tool arguments。
4. **Connector Identity Policy**: AI Base 在调用 Dashboard connector 前验证 local sidecar identity，并对 loopback 禁用环境代理。

## Architecture Decisions

### Decision 1: Dashboard owns publish authorization

Dashboard 已经是 Metrics semantics、Grafana render config 和 provider profile 的 authority，因此最终 publish authorization 也应由 Dashboard 签发/验证。AI Base 可以存储 artifact 和 proof，但不能通过构造字符串绕过 Dashboard 的 authorization state。

PublishAuthorization 绑定：

- `authorization_id`
- `approval_id`
- `dry_run_proof_id`
- `artifact_ref`
- `artifact_version`
- `artifact_hash`
- `workspace_key`
- `provider_id`
- `profile_id`
- `dashboard_uid`
- `chart_id`
- `requested_series`
- `range_mode`
- `range_start`
- `range_end`
- `operation`
- `actor`
- `status`
- `created_at`
- `expires_at`

Publish 只接受 `approved` 且 tuple 完全匹配的 authorization。

### Decision 2: Dry-run proof is checked by tuple binding

现阶段 Dashboard 无法直接读取 AI Base 的 internal proof DB；因此本 change 的第一阶段通过 Dashboard authorization record 绑定 proof id 与 artifact tuple。后续如果 AI Base 提供 proof introspection endpoint，可把 proof hash/executable/env fingerprint 纳入 Dashboard 验证。

### Decision 3: AI Base connector boundary belongs below tool binding

Chat shortcut 层的 profile/workspace 检查不足以保护 generic runtime tools。Connector operation 调用前必须读取 session workspace binding，并按 Metrics workspace boundary 校验 `profile_id`、`provider_id`、`workspace_key`、range mode 和 project labels。Model-visible tools 只能是 read/validate 类型；mutation/publish/callback 必须走 governed workflow。

### Decision 4: Connector operation policy is data-driven

AI Base 不应把 Dashboard artifact policy 永久硬编码在 shared core。短期修复可以保持 backward compatible，但最终应通过 manifest/registry 声明：

- operation sensitivity: `read`, `validate`, `workflow`, `mutation`, `callback`
- model visibility eligibility
- required workspace boundary
- required approval policy
- artifact kind owner policy

### Decision 5: Open-bug trend remains fixture, not framework

`open_bug_trend` 继续作为 deterministic demo/fixture，但新的 generic chart authoring path 应围绕 `ChartArtifactIntent`、catalog/data-block metadata 和 Metrics validation 运行。对新 chart 的支持应通过 catalog/recipe/data-block 增量，而不是继续扩展 hard-coded parser。

## Implementation Plan

1. Dashboard: add publish authorization contract/service and tests for forged/mismatched approval/proof rejection.
2. Dashboard: enforce `workspace_key == metrics.{provider_id}.{profile_id}` during artifact validation.
3. Dashboard: update publish flow to require approved authorization tuple and remove prefix auto-approval.
4. AI Base: add immutable artifact revision storage/hash retrieval.
5. AI Base: add connector operation sensitivity/workspace-bound policy and fail-closed model-visible exposure.
6. AI Base: pass active session/workspace context into connector tool handlers and validate operation arguments before HTTP invocation.
7. AI Base: add Dashboard connector identity check and loopback proxy bypass.
8. AI Base/Dashboard: update e2e runbook and smoke scripts for proof/approval/publish authority.

## Compatibility

- Existing non-AI Dashboard workflows remain unchanged.
- Existing draft validation APIs remain source-compatible, but invalid cross-workspace artifacts now fail.
- Local demo publish requests that relied on `approval_chat_demo_*` auto-approval become blocked until a real authorization is approved.
- AI Base Dashboard connector operations may become unavailable in chat sessions without a synced Metrics workspace context.

## Risks

- Full proof introspection across apps may need an additional AI Base endpoint if Dashboard must independently verify executable/env fingerprints.
- Connector workspace policy must avoid over-constraining pure catalog discovery before workspace sync; unbound catalog lookup may remain allowed only if it returns non-sensitive global capability metadata.
- Append-only artifact revisions may need state migration for existing single-record artifacts.
