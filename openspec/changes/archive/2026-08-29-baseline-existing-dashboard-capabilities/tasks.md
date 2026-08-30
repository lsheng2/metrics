## 1. Baseline Spec Quality Gate

- [x] 1.1 Review `dashboard-ui-baseline` against `ui_web/urls.py`, `ui_web/views/`, `ui_web/facades/`, and `ui_web/tests/`; verify every listed page/partial/API surface is either present in code or removed from the spec before approval.
- [x] 1.2 Review `engineering-metrics-baseline` against `tasks/app/api/`, `forecast/app/api/`, `velocity/app/api/`, `pull_requests/app/api/`, `metrics/settings/defaults_metrics.py`, and related tests; verify Jira/Azure, lazy current tasks, forecast, velocity, and PR gate claims match current code.
- [x] 1.3 Review `bug-trend-baseline` against `bug_metrics/`, `jira_sync/`, `jira_history/`, `ui_web/facades/bug_trend_facade.py`, `ui_web/views/bug_trend_view.py`, Grafana validation scripts, and tests; verify scope config, sync/history, calculation, evidence, audit, chart catalog, data health, Grafana rows, and AI chart governance claims match current code.
- [x] 1.4 Review `provider-facts-and-sync` delta against the existing main spec and current Jira sync/history code; verify it adds Jira current-baseline behavior without converting Jira implementation into the provider-neutral final architecture.

## 2. OpenSpec Validation And Archive Preparation

- [x] 2.1 Run `openspec validate "baseline-existing-dashboard-capabilities" --strict` and verify the change passes with no spec formatting, scenario heading, missing purpose, or zero-delta errors.
- [x] 2.2 Run `openspec status --change "baseline-existing-dashboard-capabilities"` and verify `proposal`, `specs`, `design`, and `tasks` are all complete before asking for review.
- [x] 2.3 After user approval, sync the OpenSpec delta specs for `baseline-existing-dashboard-capabilities` into main specs and verify new main specs exist under `openspec/specs/dashboard-ui-baseline/`, `openspec/specs/engineering-metrics-baseline/`, `openspec/specs/bug-trend-baseline/`, and updated `openspec/specs/provider-facts-and-sync/`.

## 3. Existing Docs Classification And Migration

- [x] 3.1 Create a docs classification inventory that labels each migrated legacy docs file as `current-baseline`, `future-target`, `validation-runbook`, `historical`, or `backlog`; verify every migrated file appears exactly once in the inventory.
- [x] 3.2 Move or merge `current-baseline` content from legacy architecture, Bug Trend architecture, and matching Grafana contract docs into OpenSpec main specs or supporting OpenSpec notes; verify no migrated normative statement conflicts with current code/tests.
- [x] 3.3 Route `future-target` content to the matching active/future OpenSpec area, especially Grafana-first/Jira-HSD-ES target content; verify HSD-ES and final Grafana UI goals are not represented as completed baseline.
- [x] 3.4 Preserve `validation-runbook` and evidence docs as operational material under `openspec/docs/validation/`; verify commands and evidence paths still resolve.
- [x] 3.5 Preserve `historical` and `backlog` docs with clear non-normative labels or archive pointers; verify agents can distinguish historical notes from active specs.

## 4. Link, Search, And Agent Guidance Cleanup

- [x] 4.1 Update the docs/OpenSpec index so humans and agents know `openspec/specs/` is the normative source for baseline requirements; verify old docs that remain point to the new source of truth.
- [x] 4.2 Search for moved document paths in repo docs and agent instructions with `rg "<old-doc-path>"`; verify every reference is updated or intentionally left as historical.
- [x] 4.3 Run `openspec validate --strict` after docs migration and verify all main specs remain valid.
  - Current CLI requires an explicit validation target for non-interactive use; `openspec validate --specs --strict` passed for all main specs.
- [x] 4.4 Run repository hygiene checks `python scripts/check_file_size_limits.py --include-untracked` and `python scripts/check_diff_whitespace.py --include-untracked`; verify no migrated docs or generated specs violate local gates.
  - Full file-size gate currently reports unrelated pre-existing `.github/skills/openspec-explore/SKILL.md` and `.github/skills/openspec-sync-specs/SKILL.md` line-limit findings; focused file-size gate for this baseline/docs migration passed.
- [x] 4.5 Run the OpenSpec archive workflow for `baseline-existing-dashboard-capabilities` and verify the change moves under `openspec/changes/archive/` with all tasks complete.
