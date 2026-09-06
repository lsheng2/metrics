## Why

Scope binding 已经从兼容迁移进入产品化阶段，但当前操作仍偏单点修复：operator 需要逐行确认 compatibility binding，Data Health 只能显示现状，Workbench 对兼容/阻塞状态的提示不够系统，binding 变更也缺少可追踪的审计轨迹。现在需要把 scope binding 从“能修”升级为“可批量治理、可投产判断、可审计、可高密度操作”的产品能力。

## What Changes

- Scope Library 增加批量确认 compatibility bindings 的能力，并保持单行修复/确认动作可用。
- Data Health 增加 explicit-only readiness gate，提前展示如果关闭 compatibility runtime 会被阻塞的 scopes。
- Workbench 增加统一 warning policy：compatibility binding 只警告不阻断，configuration_required/ambiguous/disabled 阻断 provider-backed panes 并给出修复入口。
- Binding 操作写入审计轨迹，记录 old/new profile、provider、status、provenance、actor 和批量操作上下文。
- Scope Library binding 区域做高密度产品化整理，减少行高和重复文字，让大量 scopes 更容易扫描。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `provider-profile-registry`: 增加批量确认、explicit-only readiness policy 和 binding audit trail 的 registry-level 行为。
- `provider-scope-wizard`: 增加 Scope Library 的批量 binding 操作和高密度控件行为。
- `dashboard-ui-baseline`: 增加 Data Health explicit-only readiness gate 展示和修复入口。
- `unified-metrics-workbench-ui`: 增加 Workbench 对 binding warning/blocking 的统一策略。

## Impact

- Affected code: `bug_metrics` scope binding resolver/API/model audit event usage, `ui_web` facades/views/templates/CSS, existing scope binding and workbench tests。
- APIs: Dashboard internal public API 增加 bulk confirmation、audit projection/readiness projection，不改变 provider profile registry 的 source authority。
- Data model: 优先复用现有 `BugTrendAuditEvent`，只有现有字段无法承载审计时才增加 migration。
- UI: 仅影响 Metrics Dashboard 的 Scope Library、Data Health 和 Workbench；不修改 Grafana UI，也不修改 AI Base app UI。
