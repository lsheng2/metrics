# W2.VA Receipt

Date: 2026-11-17. Reviewed Dashboard HEAD:
`1dbdd338efaa31f8df1d2f8d9a55a6218c35536e`.
Independent Validation Engineer: `01a1e932-060b-75d0-b8d6-4db63625d1a9`,
`gpt-5.5`, `xhigh`. The two responses below are preserved verbatim.
This is validation design evidence, not implementation or qualification evidence.
Angle-bracket command arguments below describe future resolved inputs, not commands run.

## Validation Response

PASS: W2.VA validation architecture signoff approved.

No blocking findings. I approve the faithful S0b baseline adaptation, with the baseline decision bounded exactly as a test fixture: preserve the old `ThreadingMixIn` + Django `WSGIServer` + `WSGIRequestHandler` + `StaticFilesHandler` shape, the 0.5s server timeout/daemon request-thread posture, and the real idle `ProjectRunRuntime` worker lifetime via current App contracts and a synthetic no-dispatch worker/read-service wrapper. Do not restore `project_serve`, the retired factory setting, or any production alias.

This is not W2.HOST implementation approval, not V8 performance qualification, and not Windows milestone closure.

**Baseline Decision**
- Approved comparison inputs: S0b hashes match the W1 preflight; `serve_baseline.py` still calls retired `project_serve`, but the referenced old source proves the intended server architecture.
- Required adaptation: both arms use the same current Django/settings/routes/assets/report fixtures/auth posture/sample recipe, while the candidate uses current `serve` + pinned `ai-base-runtime`.
- Required equivalence checks before heavy V8: route set, asset set, static/auth posture, seeded pages, report fixtures, sampling recipe, baseline worker start/stop/no-dispatch behavior, source/env/wheel fingerprints.
- Preserve thresholds: B1 second signal `130 <=1s`; B3 first event `<=200ms`, inter-arrival p95 `<=150ms`; B5 terminal-before-close and exit `<=10s`; B6/B9 page+asset p95 `<=1.2x` baseline; B9 excess stream `503 Retry-After: 2` and all short requests `200 <100ms`; production B6 with `DEBUG=False` + `collectstatic` is a separate row.

**Matrix**
| Authority | Owner | Producers | Consumers / Closure |
| --- | --- | --- | --- |
| Bind/static/liveness | W2.HOST | `ai_host/settings.py`, `state.py`, `management/commands/serve.py` | V4 tests, V8 driver |
| Stop budget / exit inventory | W2.HOST | `ai_host/serve_control.py`, `lifecycle.py`, `serve.py`, `manage.py`, `project_management/runtime.py` | V5 tests, native child receipts |
| HTTP/auth/order/body | W2.HOST | `ai_host/wiring.py`, `settings.py`, runtime adapter | V6/V7 conformance cases |
| Runtime recovery/transport | W2.HOST | `ai_host/task_runs.py`, current App runtime, `project_management/app/api/run_factories.py` | V7 recovery/runtime cases |
| Native measurement | W2.CERTIFY | actual `serve`, pinned runtime, adapted S0b baseline | `windows_host_qualification.py` conformance/performance phases |
| Migration rehearsal | W3.REHEARSE | `windows_migration_rehearsal.py` | V10 old/new snapshot and restore |
| Aggregate qualification | W3.JOIN | `qualify_ai_runtime.py` | V11 final candidate gate |

**First Negative Checks**
- V4: occupied port fails within 2s before runtime import/lock; dev non-loopback bind refused; static autoreload false; `handle.ended` latches failure/stop visibility.
- V5: second native signal during drain/flush/final stop exits 130 within 1s; blocked stdout watchdog exits 3; unknown callback/thread/child/finalizer fails inventory; active project run extends/tightens watchdog.
- V6: invalid Host x credentials x running/stopping across Django, `/ai`, assets; valid Host during stop returns L1 503 before auth; IPv6/configured host; auth saturation.
- V7: content-length/chunk/incomplete body before admission; stream heartbeat/disconnect/repeated abort; facade timeout cancellation; blocked loop; persisted recovery; global handler preservation.
- V8: mismatched baseline/candidate fixture identity, source drift, missing raw sample, missing terminal event, forced cleanup, or missing `HEAVY_RUN_ACTIVE` fails.
- V10: wrong snapshot owner, reparse escape, missing/mixed member, corrupt hash, old active-wire input fails.
- V11: wrong candidate, missing mandatory row, false pass, empty selection, command failure, stale artifact fails.

**Closure Commands**
Use:
`D:/AIGC/artifacts/mdb2-windows-20261117/windows-venv-r4/Scripts/python.exe`

Focused W2 host/conformance:
```powershell
& $python -I scripts/validation/run_report_authoring_tests.py ai_host/tests/test_serve_binding.py ai_host/tests/test_serve_liveness.py ai_host/tests/test_serve_shutdown_budget.py ai_host/tests/test_serve_exit_inventory.py ai_host/tests/test_settings.py ai_host/tests/test_serve_lifecycle.py ai_host/tests/test_lifecycle.py project_management/tests/test_project_runtime.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
& $python -I scripts/validation/run_report_authoring_tests.py ai_host/tests/conformance_suite.py ai_host/tests/conformance_host_cases.py ai_host/tests/conformance_http_cases.py ai_host/tests/conformance_order_cases.py ai_host/tests/conformance_process_cases.py ai_host/tests/conformance_runtime_cases.py ai_host/tests/conformance_recovery_cases.py -p ai_base_runtime.testkit.pytest_plugin -p ai_host.tests.conformance_fixtures -o ai_host_modes=blocking_wsgi -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
```

Tool/unit and final lanes:
```powershell
& $python -I scripts/validation/run_report_authoring_tests.py scripts/tests/test_windows_host_qualification.py scripts/tests/test_windows_migration_rehearsal.py scripts/tests/test_qualify_ai_runtime.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function
& $python -I scripts/validation/windows_host_qualification.py --inputs <approved-inputs.json> --output <receipt.json> --phase conformance
& $python -I scripts/validation/windows_host_qualification.py --inputs <approved-inputs.json> --output <receipt.json> --phase performance
& $python -I scripts/validation/windows_migration_rehearsal.py --inputs <frozen-inputs.json> --output <receipt.json>
& $python -I scripts/validation/qualify_ai_runtime.py --inputs <final-release-inputs.json> --output <receipt.json>
& $python scripts/check_file_size_limits.py --include-untracked
& $python scripts/check_diff_whitespace.py --include-untracked
openspec validate embed-ai-base-runtime-in-process --strict --no-interactive
```

Missing preconditions are expected implementation inputs, not W2.VA blockers: W2.HOST must create the planned helper/test files, V8 needs approved baseline/candidate input JSON and exclusive measurement window, and W3 V10/V11 need W2.REPLAN/W3.FREEZE frozen identities first. Also, `app/api/run_factories.py` is shorthand here; the current source path is `project_management/app/api/run_factories.py`.

## Authorization Clarification

Yes: my `PASS` clears **W2.VA validation architecture signoff**.

It does **not** claim W2.HOST has been implemented, validated, or certified, and it does **not** grant any separate release/push/merge authority.

No additional concrete gate blocks beginning **W2.HOST** under the existing continuous implementation authorization. W2.HOST can start next, preserving the signed baseline/thresholds and producing the planned helper/test paths before W2.CERTIFY/W2.R can claim evidence.
