## Why

当前系统已经把 Provider Profile 作为 Dashboard、Workbench、Grafana 和 AI 的数据源 authority，但客户只能在 Scope Library 中查看/绑定已有 profile，不能像建立 scope 一样通过菜单创建、审查、归档、导入或导出 profile。随着 Jira、HSD-ES 和未来 GitHub provider 并存，缺少 Provider Setup 会让用户把 provider、profile、scope、metadata mapping 混在一起，尤其对低上下文/误操作用户很不友好。

## What Changes

- 增加 `Provider Setup` 管理入口，用 provider-first 向导帮助用户创建和维护 provider profiles。
- Provider Setup SHALL 使用与 Scope Config 一致的 UI 语言、密度、颜色和 lifecycle/readiness 表达：Jira 绿色，HSD-ES 蓝色，GitHub 紫色，其他 future provider 使用可配置中性样式。
- Provider Setup SHALL 覆盖 create、edit、archive、protected delete、export、import、duplicate、readiness check 和从 profile 创建/绑定 scope 的流程。
- Provider Setup SHALL 使用 provider setup template/adapter registry 管理 provider-specific 表单段、metadata capability、source query label、field/value mapping rows 和 validation，而不是为每个 provider 复制页面。
- Provider Profile 与 Scope 的对接 SHALL 清楚：profile 是 provider/source/mapping authority，scope 是 dashboard calculation/use-case view，binding 连接二者。
- 复用 Scope Library 已有的 archive/delete/import/export/audit pattern、help tip、high-density admin table、provider color token、binding editor 和 dirty-form guard；不重复实现不必要的 UI/服务层机制。

## Capabilities

### New Capabilities

- `provider-setup-management`: Provider Profile 的客户自助创建、编辑、生命周期、导入导出、模板化 provider 表单、metadata mapping 和 Scope handoff 工作流。

### Modified Capabilities

- `provider-profile-registry`: Provider Profile Registry 从只读 JSON authority 扩展为可被 UI 管理的版本化 profile lifecycle authority，同时保持 registry contract 对 consumers 稳定。
- `provider-scope-wizard`: Scope Config 与 Provider Setup 的 provider-first 选择、profile handoff 和一键创建/绑定 scope 流程保持一致。

## Impact

- Affected UI: 新增 Provider Setup menu/page，Scope Library provider profile rows，Scope Config provider-first handoff。
- Affected API/service: provider profile CRUD、archive/delete impact、export/import package、template registry、metadata/readiness validation、audit event。
- Affected storage: 需要评估是否从 JSON file registry 迁移到 DB-backed editable profile store，或引入 DB draft/override + JSON baseline merge；设计必须明确 source of truth 和 migration path。
- Affected tests: provider setup facade/view/API tests，import/export round-trip，archive/delete protection，template extensibility，Scope handoff，monkey-user UI assertions。
- Non-goal: 本 change 只创建 OpenSpec，不实现代码；HSD-ES live metadata/write behavior 必须等权威 API 资料确认后才可实现。
