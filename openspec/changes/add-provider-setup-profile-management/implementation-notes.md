## Implementation Notes

- Provider Setup 复用 Scope Library 的 lifecycle 心智：archive 是默认安全移除，hard delete 只允许 archived profile，并要求 `DELETE <profile_id>` 确认。
- Provider Setup 复用 Scope Config 的 provider-first template projection：Jira 使用绿色，HSD-ES 使用蓝色，GitHub 使用紫色，其他 future provider 使用 neutral；Scope Config 只允许选择已有可绑定 profile，Provider Setup 允许从 template-only provider 创建 draft。
- Provider Profile 的 managed store 保持 registry consumer contract 稳定：bundled JSON 继续作为 baseline，DB managed profile 覆盖同 id bundled profile，并携带 lifecycle、source hash、mapping hash 和 provenance。
- 运行期可创建的 managed profile 不能被长生命周期 service 缓存成启动快照；scope binding、readiness、aggregate 和 dashboard provider resolution 的默认 registry 都按需读取当前 bundled+managed view，只有测试显式注入 registry 时才固定快照。
- Scope handoff 仍通过 existing scope-provider binding authority 完成；Provider Setup 的 Bind Scope/Create Scope 不直接修改 profile source、field bindings 或 value mappings。
- Metadata refresh 继续由 Scope Config 的 Jira adapter-backed path 承担；HSD-ES 和 GitHub template 显示 configuration_required/unsupported guidance，不调用 Jira metadata adapter。
- Provider Setup UI 二次整理后使用页面级 namespace：profile table 主动作限制为 Edit/Create Scope/Export/More，scope binding 独立为一行短表单；existing profile 的 Advanced JSON 默认折叠，new profile 保持展开；browser smoke 检查按钮高度一致、provider selector 高度、desktop/mobile 无横向溢出。
- 后续 UI change 在 OpenSpec 建立阶段必须引用 `openspec/docs/validation/ui-change-quality-gate.zh.md`，并在 proposal/design/tasks 中写清布局、状态、组件密度、responsive viewport 和 screenshot/browser smoke 验收。
