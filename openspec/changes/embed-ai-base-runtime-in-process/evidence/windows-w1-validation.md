# W1 Validation Architecture Signoff

Date: 2026-11-17. Reviewer: `01a1e760-9cda-72c3-949c-4f3b1fd692ae`,
Validation Engineer, `gpt-5.5` / `xhigh`.
This signs off validation design, not implementation or release readiness.

## Reviewer Receipt

No blocking W1.VA design hole found. Read-only validation only: no edits, no tests, no servers. zvec index was missing and I did not build it; I used codebase-memory plus actual source reads. The current source matches the intended failing baseline: `requirements.txt` lacks the runtime/Waitress target and still pins `pytest==9.1.1`; profile schema is still `1`; launchers still use `runserver`, temp PID/port ownership, and old AI Base bindings.

Dependency-design addendum for V1: W1.INSTALL must align validation pins to the tested candidate: `pytest==9.2.0`, `pytest-asyncio==1.5.0`, keep `pytest-django==4.12.0` and `playwright==1.57.0`, and keep Django/WhiteNoise/runtime versions unchanged. The install smoke should assert those versions, `pip check`, no `.pth` or shared-site leakage, and direct wheel install before named requirements.

| ID | Authority | Producer | Consumers | Required negatives |
| --- | --- | --- | --- | --- |
| V1 | Standard install and runtime artifact identity | `C:/Users/lsheng2/orca/workspaces/scrum_dashboard/moonfish/ai_host/admission.py`, `requirements.txt`, planned `scripts/validation/windows_install_smoke.py` | `serve`, package checker, conformance lane, final qualifier | old requirements-only env not admitted; wrong hash/version/files; editable/shadowed/absent wheel; online fallback; current-vs-new interpreter mix; shared dependency leakage |
| V2 | Windows launcher ownership and stop truth | `dashboard_runtime_instance_profile.py`, SLE `ServiceSpec`/provenance, PowerShell launchers | `local_*_backend.ps1`, `e2e_dashboard_ai_stack.ps1`, audits, `e2e_bug_trend.py` | schema 1 rejected; foreign listener/stale PID/wrong command/start identity refused; stop-file then >=15s; Windows terminate/kill classified abnormal when used |
| V3 | Retired legacy paths and boundary checks | planned `check_embedded_runtime_boundaries.py`, `check_retired_ai_paths.py`, docs/runbook updates | current code/config/docs, package profile validation, checker tests | legacy route/config/import/asyncio/doc mutation rejected; zero-scan fails; false exclusion and misplaced test literal fail; Linux/global deferrals stay visible |

First focused checks after implementation starts:
- V1: `test_admission.py` plus new `test_windows_install_smoke.py`, using a fresh owned env and offline wheelhouse.
- V2: profile/SLE/provenance/audit tests plus new `test_windows_launchers.py`.
- V3: new checker unit tests proving mutations fail before trusting green checker output.

Gate selection: W1 uses `governance` for the validation/evidence/retirement boundary, with `artifact` coverage for V1 install and `runtime` coverage for the launcher start/stop smoke. Not a release gate.

Old baseline remains read-only historical shared-dependency style and must be revalidated at W3; it is not the new install method.

Reviewer clarification: the `.pth` rule rejects unmanaged or external site-path
injection, not distribution-owned venv-local files such as pywin32's bootstrap.
Verify resulting `sys.path`, module/distribution locations and disabled user-site;
only the selected venv, project source and standard library are allowed.

VALIDATION_NODE: W1.VA
VERDICT: PASS
