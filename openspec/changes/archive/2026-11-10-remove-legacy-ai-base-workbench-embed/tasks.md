# Tasks

## 1. 删除 legacy embed 模式

- [x] 1.1 `ui_web/ai_base_workbench_adapter.py` 只生成 `embed=app-chat` URL，删除 `embed=workbench` 分支和 payload 中只服务旧 URL 的 `agent_id`；验证：`ui_web/tests/test_ai_base_workbench_adapter.py` 通过，并断言 iframe URL 与 public binding request 不含 instance token 或 credential reference。
- [x] 1.2 删除 `METRICS_AI_BASE_EMBED_MODE` setting 和 unified stack launcher 中的同名环境变量；验证：`scripts/tests/test_e2e_dashboard_ai_stack_launcher.py` 通过，`EMBED_MODE` 在代码、配置和当前文档中零命中（archive 历史除外）。
- [x] 1.3 Workbench 页面测试只断言 app-chat iframe，未绑定 scope 的否定断言改为检查 workspace key 本身；验证：`ui_web/tests/test_workbench_ai_host_actions.py`、`ui_web/tests/test_workbench_scope_profile_sync.py` 和其余 workbench 测试（含 `ui_web/tests/test_workbench_high_density_browser.py`）通过，0 skipped。

## 2. 规格同步

- [x] 2.1 delta spec 把 `unified-metrics-workbench-ui` 的 AI Base 嵌入 scenario 改为 app-chat binding 契约；验证：`openspec validate remove-legacy-ai-base-workbench-embed --strict` 通过。

## Workflow follow-up

- 归档本 change，使 baseline `openspec/specs/unified-metrics-workbench-ui/spec.md` 同步为 app-chat 契约；归档后运行 `openspec validate --specs --strict`。
