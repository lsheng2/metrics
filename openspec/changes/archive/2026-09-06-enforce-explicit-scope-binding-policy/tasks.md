## 1. OpenSpec Contract

- [x] 1.1 编写 runtime policy、audit UI 和 full smoke 的 proposal/design/spec delta，并通过 `openspec validate enforce-explicit-scope-binding-policy --strict` 验证。

## 2. Runtime Policy

- [x] 2.1 增加 `METRICS_SCOPE_BINDING_POLICY` 默认值和读取路径，并用 tests 验证默认是 `compatibility_allowed`。
- [x] 2.2 让 resolver 在 `explicit_only` 下拒绝 compatibility runtime binding，并用 backend/workbench tests 验证 explicit 可用、compatibility 被阻断。
- [x] 2.3 在 Data Health/Scope Library 显示当前 policy 和 readiness，并用 view tests 验证。

## 3. Audit UI

- [x] 3.1 增加 binding audit history API/facade projection，并用 backend tests 验证只返回 binding mutation events。
- [x] 3.2 在 Scope Library 或 Data Health 显示 Binding Audit History，并用 view tests 验证 empty state 和 event rows。

## 4. Product Operations And E2E

- [x] 4.1 批量确认当前本地 compatibility scopes，并验证 Data Health explicit-only readiness 变为 ready。
- [x] 4.2 运行 focused tests、Django check、migration dry-run、OpenSpec strict validate 和 diff whitespace gate。
- [x] 4.3 重启 full stack，检查 boot log/process inventory，并用真实浏览器检查 Scope Library、Data Health、Workbench UI。
- [x] 4.4 尝试 `-FullAiChatSmoke`，如果外部模型网关不可用则记录 blocker 和失败证据。

## 5. Closure

- [x] 5.1 Archive OpenSpec change，同步主 specs 后再次 strict validate。
- [x] 5.2 准备 scoped commit/push evidence。
