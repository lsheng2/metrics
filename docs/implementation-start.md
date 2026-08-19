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
- Added `METRICS_JIRA_VERIFY_SSL` so local corporate certificate issues can be handled explicitly.

Known follow-ups:

- Local `.env` uses `METRICS_JIRA_VERIFY_SSL=false` for the current corporate/self-signed certificate chain. Replace this with a trusted corporate CA bundle before any shared deployment.
- `STDEL-8942` currently maps to `status=todo` and `stage=None` because the local workflow config does not yet include Intel Jira's `Fixed` status. Field and workflow discovery is the next setup task.
- Rotate the PAT that appeared in chat context, then place the replacement only in local `.env` or an approved secret store.
