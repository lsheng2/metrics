# MVP Implementation Start

Date: 2026-08-19

## Git Baseline

Baseline repository: `clutcher/metrics`

Current fork remote:

```text
origin   https://github.com/lsheng2/metrics.git
upstream https://github.com/clutcher/metrics.git
```

Current branch:

```text
mvp/intel-jira-connectivity
```

Baseline commit:

```text
dce92c9801628184fa04f0caf4b4f7471a2eb4fd chore: update dependencies
```

## Setup Validation

Python environment:

```text
.venv, Python 3.13.7
```

Dependency status:

```text
Django 6.0.7 imports successfully.
```

Django validation:

```text
python manage.py check
```

Result:

```text
System check passed with one non-blocking warning:
caches.W003 task_search_results cache LOCATION path is relative.
```

## First MVP Gate

The first implementation gate is Intel Jira connectivity with Server/Data Center PAT auth.

Do not build bug or feature charts before this gate passes.

Required minimal change:

- Add `METRICS_JIRA_AUTH_MODE`.
- Preserve existing `cloud_basic` behavior.
- Add `server_pat` behavior using `Jira(url=..., token=...)`.
- Validate against `https://jira.devtools.intel.com/rest/api/2/issue/STDEL-8942` using a PAT supplied only through local environment variables.

No PAT or credential should be committed, logged, or pasted into chat.

## M0 Connectivity Result

Status: passed on 2026-08-19.

Validated paths:

- Direct REST request to `/rest/api/2/serverInfo` returned HTTP 200 and Jira version `10.3.8`.
- Direct REST request to `/rest/api/2/issue/STDEL-8942` returned HTTP 200.
- Baseline task search path returned one task for `STDEL-8942` through `tasks_container.task_search_api.search_by_ids`.

Implementation changes made for M0:

- Added `METRICS_JIRA_AUTH_MODE=server_pat` support.
- Added a local Server/Data Center Jira task provider using `jira_client.jql(...)` with `startAt`/`maxResults` pagination.
- Added `METRICS_JIRA_VERIFY_SSL` and `METRICS_JIRA_CA_BUNDLE` so corporate certificate handling has an explicit configuration path.

Known follow-ups:

- Local `.env` uses `METRICS_JIRA_VERIFY_SSL=false` for the current corporate/self-signed certificate chain. Replace this with `METRICS_JIRA_CA_BUNDLE=<corporate CA bundle path>` before any shared deployment.
- `STDEL-8942` currently maps to `status=todo` and `stage=None` because the local workflow config does not yet include Intel Jira's `Fixed` status. Field and workflow discovery is the next setup task.
- Rotate the PAT that appeared in chat context, then place the replacement only in local `.env` or an approved secret store.

## P0c Scope Audit Workflow

The next Bug Trend productization step is a read-only Scope Audit for saved Jira scopes.

Operator workflow:

1. Open the Bug Trend page for a saved scope.
2. Open `bug-trend/scope-audit/?scope_id=<id>` from the Audit action.
3. Review observed issue types, statuses, resolutions, priorities/severities, components, and coverage counts.
4. Use mapped/unmapped status to decide whether the saved `JiraScopeConfig` needs a later P0d config edit and recalculation.

Ownership rules:

- `jira_history` owns observed values and raw coverage counts from local persisted Jira issue/transition rows.
- `JiraScopeConfig` owns mapping truth.
- `bug_metrics` resolves saved `scope_id`, compares observed values to `JiraScopeConfig`, and transports coverage counts unchanged.
- `ui_web` renders the audit result without recomputing mappings or coverage.

Non-goals for P0c:

- No unsaved draft audit preview.
- No automatic mapping edits.
- No live Jira query.
- No latest sync or Data Health status.
