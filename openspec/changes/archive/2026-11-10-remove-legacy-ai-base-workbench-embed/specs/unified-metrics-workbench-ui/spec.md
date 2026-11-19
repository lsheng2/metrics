# Spec Delta

## MODIFIED Requirements

### Requirement: Workbench supports one-window local runtime
系统 SHALL provide a local runtime path that starts required Dashboard, Grafana and optional AI Base services but opens only the unified workbench UI for the user.

#### Scenario: Local E2E launcher starts the stack
- **WHEN** 用户运行 unified workbench local launcher
- **THEN** launcher SHALL start or detect Dashboard, Grafana and optional AI Base services
- **AND** launcher SHALL open one workbench URL
- **AND** launcher SHALL expose service health/status inside the workbench instead of asking the user to manually manage three browser windows
- **AND** launcher SHALL use one lifecycle state source for start, stale-process cleanup, boot-log audit and process-inventory audit
- **AND** launcher SHALL NOT clean up the current Dashboard or Grafana process tree after smoke checks have proven them ready

#### Scenario: Optional AI Base is disabled
- **WHEN** AI Base is disabled or not configured
- **THEN** workbench SHALL still support charts、evidence、settings、publish/audit and diagnostics surfaces
- **AND** AI pane SHALL render an unavailable or disabled state without blocking the rest of the app
- **AND** AI pane SHALL clearly explain whether the Dashboard process is not sidecar-enabled or AI Base is configured but unreachable
- **AND** AI pane SHALL provide the approved one-click stack launcher command or diagnostics link as the next action
- **AND** workbench SHALL NOT start AI Base or other external services as a side effect of rendering a web request

#### Scenario: AI Base is embedded in the workbench
- **WHEN** AI Base is ready and the workbench renders the AI assistant pane
- **THEN** Dashboard SHALL request only the AI Base app-chat embed surface (`embed=app-chat`) for the iframe
- **AND** AI Base SHALL render a sidebar-oriented chat surface without the full app shell navigation, session setup sidebar, session files panel, or app status chrome
- **AND** AI Base SHALL keep full application navigation available only through an explicit external/full-app link

#### Scenario: AI Base compact embed runs in Dashboard app context
- **WHEN** Dashboard embeds AI Base for a selected scope whose provider profile binding is resolved
- **THEN** the iframe URL SHALL carry the Dashboard app identity (`sourceAppId`), binding key, Dashboard agent key, session key and the workspace key derived from the bound provider and profile
- **AND** the iframe URL and the rendered page SHALL NOT contain the AI Base instance token or credential reference; Dashboard SHALL send them only in server-side binding and workspace-sync requests
- **AND** AI Base SHALL bind compact chat creation and session filtering to that app-owned workspace
- **AND** AI Base SHALL activate the Dashboard agent when it is available
- **AND** compact embed SHALL NOT expose arbitrary agent or workspace selection controls to the user
- **AND** if the fixed workspace is not synced, compact embed SHALL show an actionable sync/start-stack state rather than displaying unrelated sessions
