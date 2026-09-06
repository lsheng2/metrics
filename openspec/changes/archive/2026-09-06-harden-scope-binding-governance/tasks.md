## 1. OpenSpec Contract

- [x] 1.1 编写 scope binding governance 的 proposal/design/spec delta，并通过 `openspec validate harden-scope-binding-governance --strict` 验证。

## 2. Registry API 与 Audit

- [x] 2.1 增加 bulk confirm compatibility binding 的 public API/resolver 方法，并用 backend tests 验证 changed/skipped 行为。
- [x] 2.2 为 confirm/save/bulk confirm 写入 binding audit event，并用 backend tests 验证 old/new snapshot、actor 和 operation type。
- [x] 2.3 扩展 binding health projection 的 explicit-only readiness 字段，并用 backend tests 验证 ready/blocked/impacted rows。

## 3. Dashboard UI

- [x] 3.1 在 Scope Library 增加 bulk confirm action 和高密度 binding controls，并用 view tests 验证 action 可见性、提交结果和 compact row 内容。
- [x] 3.2 在 Data Health 增加 explicit-only readiness gate 和 impacted scopes repair links，并用 view tests 验证 ready/blocked 展示。
- [x] 3.3 在 Workbench 增加 compatibility warning 与 unresolved binding blocking policy，并用 workbench view tests 验证不会显示 stale provider-backed content。

## 4. Product Validation

- [x] 4.1 运行 focused Django tests、`python manage.py check`、`python manage.py makemigrations --check --dry-run`、`git diff --check`。
- [x] 4.2 运行 `openspec validate --specs --strict`，确认主 specs 仍然一致。
- [x] 4.3 拉起 full stack，检查 boot log/process inventory，并用真实浏览器检查 Scope Library、Data Health、Workbench UI 截图。

## 5. Closure

- [x] 5.1 将完成的 OpenSpec change archive，同步主 spec 后再次 strict validate。
- [x] 5.2 做 scoped commit，并在提交信息中包含 Why/What/Validation。
