## Why

当前 AI-centric E2E 需要同时打开 Django Dashboard、Grafana 和 AI Base 三个 Web 窗口，用户需要在窗口之间手动切换上下文。下一阶段还要求用户点击 Grafana bug trend bar 后，下方 Jira/HSD-ES ticket evidence list 自动刷新到对应 bucket/series，这已经超出“把三个页面 iframe 放在一起”的 UX 范围。

本 change 建立一个 Dashboard-owned unified workbench shell：一个 Web UI 承载 chart、ticket evidence、AI chat、Django settings/publish/audit 等可插拔 pane，并用 Metrics-owned PageQueryState 和 evidence contract 保证 Grafana/Chart.js/AI-generated chart 都能安全地驱动 deterministic evidence。

## What Changes

- 新增统一 Metrics Workbench UI capability，定义 shell layout、pane registry、layout persistence、read-only/interactive pane 状态和 single-window runtime。
- 修改 Dashboard UI baseline，使现有 Django 页面可以作为 workbench pane/route 被挂载，而不是只能作为互相独立的 full page。
- 修改 Grafana dashboard parity，要求 evidence-backed Grafana panel click/data link 必须映射到 Metrics PageQueryState；不支持映射的 chart 只能展示 read-only 或 range-only evidence 状态。
- 明确 workbench 中的 Grafana chart pane 优先使用 compact single-panel embed，而不是完整 Grafana dashboard page；完整 Grafana UI 仅作为 diagnostics/admin 或 fallback 入口。
- 修改 Provider AI Dashboard Composition，要求 AI Base 作为 workbench sidebar/pane 进入 unified UI，并从 shell 传入当前 profile/range/chart/selection context。
- 保留 Dashboard 对 provider facts、chart recipes、evidence、validation、approval 和 Grafana publication 的 source-of-truth 权限；AI Base 和 Grafana 仍是 clients/renderers/operators。
- 引入开源 dock/window frame dependency 的选型约束，优先采用轻量 dock layout layer，而不是把产品迁移到 Backstage、low-code portal 或 Grafana-only app。

## Capabilities

### New Capabilities

- `unified-metrics-workbench-ui`: 定义单 Web UI workbench shell、pane composition、shared page state、chart-to-evidence interaction 和 layout/runtime 行为。

### Modified Capabilities

- `dashboard-ui-baseline`: 现有 Django dashboard 页面和 partial 需要可被 workbench shell 复用、挂载和局部刷新。
- `grafana-dashboard-parity`: Grafana panel evidence capability 需要从“能打开 evidence link”升级为“能与 workbench shell 同步 validated selection state”。
- `provider-ai-dashboard-composition`: AI Base 入口需要作为 workbench pane/sidebar 参与当前 dashboard context，而不是独立窗口里的孤立 chat。

## Impact

- Affected code: `ui_web` routes/views/templates/static assets, `bug_metrics` chart/evidence/page-query APIs, Grafana panel embed/artifact/render config generation, AI dashboard workflow views, local E2E launcher scripts.
- Affected APIs: `/api/charts/data/`, `/api/charts/evidence/`, `/api/provider-charts/data/`, `/api/provider-charts/evidence/`, `/api/ai-dashboard/*` may need additional shell-context fields, pane metadata, or selection sync semantics.
- Affected systems: Django Dashboard, local Grafana, AI Base app, reverse-proxy/local launcher, browser E2E validation.
- Dependencies: MAY add a lightweight dock layout library for the shell, with preference for a framework-neutral or isolated integration so the existing Django/Bulma/HTMX baseline is not rewritten wholesale.
