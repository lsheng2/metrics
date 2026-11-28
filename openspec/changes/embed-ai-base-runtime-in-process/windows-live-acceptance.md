# Windows Real Provider And Model Acceptance

Status: authorized, in progress (2026-11-28).
Profile source: repo-local. Agent routing mode: multiagent-configured.
Docs impact: operations, configuration, validation.
Task authority: this change's `tasks.md`, `LIVE.*` nodes only.

## Outcome And Authority

The owner approved replacing a synthetic-only delivery boundary with actual
provider/model acceptance. A green synthetic suite remains a regression gate;
it cannot establish live business acceptance. This packet qualifies the
selected Windows Dashboard/AIB composition, not every provider, Linux, full
performance certification or production deployment.

Baseline: Dashboard `ab28eb7882d8e7d3b1758998c9b1b2ea3026ecae`,
AIB `9de48851ff4910ef98d414406077dbbcc93abb5b`, both clean on main.
Use installed `ai-base-runtime==0.1.1.dev10`, wheel SHA256
`18b5071ee9e601f6e36fb9f2cd563d43c8ce5a8beea5dafcb3f119e635ce7e55`.
Record the actual source again if a scoped repair changes it.

The existing source is Jira; the initial sample is a bounded subset of the
previously demonstrated scope. Freeze the exact query and membership in private
evidence before business execution. Use the existing configured AIB external
gateway/model, not a new endpoint or a fallback model. Configuration discovery
has identified `gpt-5.5`; network authentication and compatibility are not yet
proved. The source records may be sent only to this configured model gateway.

## Global Constraints

- Work in the owner-selected main checkouts; preserve unrelated work.
- Use a new, owned directory on D:, a fresh database/archive and distinct
  loopback port. Do not import or mutate the running 8017 service.
- Reuse existing credentials in memory. Do not print or persist tokens,
  authorization headers, cookies or provider exceptions containing secrets.
- Jira access is read-only. No provider writes, schedules, force refresh,
  data-Git remotes, email or external Grafana publication.
- Local report finalization and publication to a newly isolated local Grafana
  are authorized test effects. Human approval remains explicit.
- Use normal `manage.py serve`, the installed wheel, production adapters and
  task profiles. No fixture AppConfig, scripted model, patched transport or
  direct handler invocation may stand in for a successful live workflow.
- Do not weaken TLS, approval, deadlines, stop/leak budgets or numerical KPI.
- Do not modify AIB unless a reproduced AIB-owned blocker needs a separately
  reviewed source/wheel change. Never patch the installed wheel.
- Keep raw enterprise content, screenshots and generated reports outside Git.
  Public receipts contain only non-sensitive identity, counts and outcomes.
- At most three source items in the first vertical slice, at most twelve
  explicitly recorded model-backed user operations, and no equivalent retry
  after two failures without new evidence. These are execution bounds, not KPI.
- Start with prerequisites and one vertical flow. Do not rebuild or rerun
  all synthetic lanes for a documentation-only change.

## Contract Registry

| ID | Owner | Consumers | Risk | Disconfirming check |
| --- | --- | --- | --- | --- |
| LIVE-SCOPE | Private execution manifest | Source adapter, model config, publication target | high | Wrong root, endpoint, query, target or absent permission refuses execution |
| LIVE-NATIVE | Installed wheel and production composition | Browser, task-run, tools, approval | high | Fixture/synthetic implementation or absent actual model result cannot pass |
| LIVE-RESULT | Dashboard business validators | Saved report, chart preview, publication history | high | Wrong source facts, rejected candidate, mismatched approval/digest cannot pass |
| LIVE-EVIDENCE | Per-operation receipts | Final report and task ledger | high | Missing source/model/cleanup evidence or historical PASS cannot close a node |

## Propagation And Consumers

| Authority | Producer paths | Consumer paths | Required behavior / negative checks | Non-goals |
| --- | --- | --- | --- | --- |
| Live scope | Private manifest; deployment settings | `provider_sync/out/jira_capture.py`; `ai_host/settings.py` | Exact source/model, verified TLS; no default target or implicit credential switch | Other providers, production state |
| Actual execution | `ai_host/management/commands/serve.py`; `ai_host/package.py` | `ui_web` report/workbench pages; `ai_host/task_runs.py` | Same installed runtime and actual model; no synthetic response or handler shortcut | Replacing runtime |
| Business acceptance | `project_management` public APIs; `ai_host` tools | Editor Save/Finalize; Grafana import; publication history | Source-grounded output and explicit approval; rejected/duplicate requests preserve state | External publication |
| Delivery claim | Private receipts and reviewed public summary | Runbook; validation guide; this task ledger | Only executed, source-bound outcomes marked PASS | Changing old receipts or KPI |

Consumer universe: public API, internal service/facade, UI, reports, audit,
validation scripts, external local artifacts, CLI, operator docs and fixtures
apply as above. Migration applies only to the new empty validation database.
Scheduler is excluded. Cache/index ownership is unchanged; live records must
come from the current capture, not an old fixture or stale cache.

## Execution DAG

| Node | Depends on | Work and exit |
| --- | --- | --- |
| LIVE.PREFLIGHT | none | Freeze identity/scope; inspect configuration without secrets; record bounded GET-only results and any blocker; discovery completion is not live readiness |
| LIVE.PLAN.R | LIVE.PREFLIGHT | Independent architecture/validation review of scope, real-path discrimination, evidence and next executable slice |
| LIVE.CA | LIVE.PLAN.R | Reviewed, fail-closed Dashboard CA propagation repair, focused tests and actual installed-runtime prerequisite recheck |
| LIVE.REPORT | LIVE.CA | Fresh source capture, actual summary and authoring from the real UI; verify accepted facts, edit, Save, Finalize and readback |
| LIVE.CHART | LIVE.REPORT | Actual model selects tools from the real AI pane; validated preview, explicit approval, isolated Grafana import and matching history |
| LIVE.RECOVERY | LIVE.CHART | Same-session context changes, duplicate operation identity, a bounded refusal/recovery, restart readback and normal stop/no owned residue |
| LIVE.CLOSE.R | LIVE.RECOVERY | Independent source/evidence review; publish scoped non-sensitive receipt and manual-trial instructions |

These nodes are a serial validation slice, not multiple speculative
implementation waves. A discovered product defect pauses the affected node:
reproduce it, identify the owning module, freeze the smallest repair and its
tests, independently review it, then resume at the affected consumer. Replan
downstream checks when source or assumptions change. Do not mark a blocked
business node complete merely because its prerequisite probe passed.

Owned durable paths: this plan, this change's `tasks.md` and new live receipt,
`docs/validation/dashboard-ai-e2e-runbook.zh.md`,
`docs/development/reporting-delivery.md`, and `docs/README.md`.
Private deployment/test drivers and evidence live in `D:/AIGC/d10-live-1128/`.
Additional product/test paths require a recorded, narrowly scoped repair
amendment before editing. This is not permission to change shared AIB/KPI.

Independent Architect Planner Reviewer combines plan and validation review.
Main agent owns serial deployment and execution. Implementation Engineer and
Dashboard Debugger are not separately dispatched unless an actual repair can
benefit from a distinct, non-overlapping task.

## Required Observations

1. Source: endpoint/principal verification, exact query and item membership,
   complete capture, current source hashes and no provider mutation.
2. Model: configured model identity, actual dispatch/result evidence, original
   runtime run ids and tool calls. A health check or canned greeting is not
   business acceptance. Validate facts and schema, not fixed prose.
3. Report: browser submission, accepted summary, AI candidate, explicit Apply,
   human edit, Save/Finalize and unchanged download/reopen.
4. Chart: model tool choice, original preview bytes/digest, pending approval,
   explicit approve, isolated target and matching history. Refusal must not
   publish; do not auto-approve based on chat text.
5. Continuity: session retained on context change; active approvals keep their
   original context; same request key does not create another business operation.
   A failed/refused operation is preserved, with successful recovery separate.
6. Timing: setup, local request work, external model/provider waits and
   user-visible total duration separately when measurable. Unknown attribution
   stays unknown; no local-only metric proves total usability.
7. Cleanup: launch PID/incarnation, owned port/stop file, real exit status,
   normal-stop result and absence of owned descendants/listeners.

## Preflight Repair: Explicit Model CA

GET-only preflight on 2026-11-28 reproduced `SSLCertVerificationError` with
the current default trust. The same gateway, credential and model catalog
returned 200 with the existing configured enterprise CA. Jira identity also
returned 200 with an active verified principal. This is prerequisite evidence,
not an actual model inference or business PASS.

Root cause: `ai_host/settings.py` always constructs `NetworkPolicy()`; AIB
already supports `NetworkPolicy.ca_bundle` and intentionally sets
`trust_env=False`. Ambient `SSL_CERT_FILE` therefore cannot configure this
consumer. Correct the Dashboard owner, not AIB or TLS verification.

Add optional `METRICS_AI_MODEL_CA_BUNDLE` to `metrics/settings/defaults_metrics.py`
and `.env.example`, pass the explicit path to the existing public NetworkPolicy,
and document it in the validation guide. Empty configuration retains default
trust. Missing/unreadable/invalid explicit files must fail closed, never
silently revert to default trust or disable verification. No proxy or legacy
configuration fallback is added.

Before code: independent plan/validation review and RED tests in
`ai_host/tests/test_settings.py` or a focused sibling. Then minimal owner edit,
GREEN settings/host/local-runtime/serve-start coverage and live prerequisite
recheck through the installed runtime. Record source change separately from
the unchanged wheel. This repair is LIVE.CA; LIVE.REPORT remains
blocked until its review is complete.

## Validation And Evidence

PowerShell commands use the installed candidate interpreter
`D:/AIGC/d10-1127/venv/Scripts/python.exe`; no implicit legacy `.venv`.
Focused repair tests use `-I scripts/validation/run_report_authoring_tests.py`
with explicit test paths, `-q --tb=short -p no:cacheprovider` and
`-o asyncio_default_fixture_loop_scope=function`.
Run `scripts/check_file_size_limits.py --include-untracked`,
`scripts/check_diff_whitespace.py --include-untracked`, and
`npx --no-install openspec validate embed-ai-base-runtime-in-process --strict`.
Use isolated Django `check` before serving.

Private evidence is append-only per attempt, with UTC timestamps and source,
wheel, configuration-without-secrets and input identities. Failed attempts stay
failed. The final public receipt must distinguish executed PASS, blocked,
not-run and operator judgement; an agent's browser check is not the owner's
personal acceptance. A live PASS does not close C5, R4/R7 or full performance
certification without their own evidence.

Preflight review must check node dependencies, owner paths, negative cases and
the sole checkbox ledger together. No second execution ledger is introduced.
