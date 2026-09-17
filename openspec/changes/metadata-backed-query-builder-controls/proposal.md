## Why

Jira Scope Config 的 Query Builder 现在仍要求用户手动输入 issue type、component、version、priority、resolution 和 custom field values，容易因为大小写、空格或字段 id 拼写错误生成错误 JQL。既然页面已经可以 refresh Jira metadata，就应该把这些候选值用于 Source population 控件，让用户优先点选，同时保留 metadata 不完整时的手动 fallback。

## What Changes

- Query Builder SHALL use refreshed Jira metadata to render selectable controls for supported source filters, including issue types、components、affected versions、fix versions、priorities 和 resolutions。
- Query Builder SHALL keep manual fallback inputs for every metadata-backed list so operators can add values that Jira metadata did not return。
- Query Builder SHALL allow selecting a custom Jira field from discovered field metadata, while preserving manual custom field id entry for fields that metadata cannot discover。
- Query Builder save handling SHALL merge metadata-selected values and manual fallback values into the same persisted builder state and generated JQL。
- Custom JQL mode SHALL remain independent: metadata-backed Query Builder selections SHALL NOT alter the saved runtime source query while Custom JQL is selected。
- Metadata refresh SHALL update the visible metadata-backed controls through the existing Django/htmx flow without introducing a JavaScript-heavy frontend framework。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `provider-scope-wizard`: Jira Scope Config Query Builder 的 source population controls 从纯文本输入升级为 metadata-backed selectable controls with manual fallback。

## Impact

- Affected UI/templates: `ui_web/templates/bug_trend_scope_config.html` and Scope Config metadata partials.
- Affected facade/view logic: `ui_web/facades/bug_trend_scope_config_facade.py` and `ui_web/views/bug_trend_scope_views.py`.
- Affected client behavior: `ui_web/static/js/main.js` Query Builder preview collection.
- Affected tests: focused facade/view/template tests for Query Builder metadata controls, save behavior, Custom JQL isolation, and metadata refresh partials.
- Validation: OpenSpec strict validation, focused Django tests, `manage.py check`, migration dry-run, whitespace check, and browser smoke for desktop/mobile Source population rendering.
