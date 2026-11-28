# Windows Real Provider And Model Acceptance

Status: bounded execution and independent evidence review passed; publication and owner acceptance remain separate (2026-11-28).
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
After the owner-authorized schema-delivery repair, use `ai-base-runtime==0.1.1.dev11`,
source `d066c104e4394a570ba054098d3d6ed4b5597f2c`, wheel SHA256
`a05cbd5d8fdabcd48f7ec5c106432370b1d461f0e080a11e0fad04a67a6f9931`.
Qualified Dashboard product source: `6dcf9b0159741669843b43663aabb84786fe4d75`.
The [live receipt](evidence/windows-live-acceptance-dev11.json) binds current package
bytes, private evidence hashes and later governance-only source equivalence.

The existing source is Jira; the initial sample is a bounded subset of the
previously demonstrated scope. Freeze the exact query and membership in private
evidence before business execution. Use the existing configured AIB external
gateway/model, not a new endpoint or a fallback model. Configuration discovery
identified `gpt-5.5`; actual summary, authoring and tool/approval flows now pass
within the recorded bounds. Source records may be sent only to this configured gateway.

The original member exceeded the unchanged 65536-byte summary input limit.
A second member of the same authorized parent scope was frozen separately and
qualified, without deleting the first refusal or truncating source records.
This is not qualification of oversized input or real changed multi-day history.

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
- The owner authorized the reproduced AIB output-schema repair; source review,
  source joins and private-wheel gates passed. Never patch an installed wheel.
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

## Model Output Contract Repair

The owner subsequently authorized the confirmed AIB schema-delivery blocker.
Shared source delivers the original output schema in trusted instructions and
retains post-validation, retries0 and every budget. Source78, Dashboard schema
joins2, source-host22 and private-wheel23 passed; independent source review
found no remaining issues. Actual-model synthetic-input probes establish schema
delivery only, not a filled authoring candidate or real-source business acceptance.
The new immutable dev11 payload differs from dev10 in one backend file;
dependencies/assets/testkit are unchanged. Install into a fresh environment,
then run LIVE.REPORT/CHART/RECOVERY. Preserve all dev10 receipts and performance
references; do not certify dev11 using the historical dev10 functional receipt.

## Validation And Evidence

PowerShell commands use the installed candidate interpreter
`D:/AIGC/d11-1128/venv/Scripts/python.exe`; no implicit legacy `.venv`.
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

## Primary-Issue Eligibility Repair

The actual read-only Jira capture was consistent with complete facts, comments
and history, but the initial `review-1` readiness predicate refused retained
attachment/link metadata before model dispatch. Independent architecture review
confirmed the bounded primary-issue flow can admit this state without fetching
those bodies. This amendment supersedes the empty-only optional-part restriction
in `add-provider-neutral-project-reporting/early-ai-integration.md` for the new
`metrics.project_summary@2` profile, not historical requests or receipts.

Dashboard owns this repair. Keep all three required parts complete and the
snapshot consistent. Optional parts admit only existing empty states or exact
`partial + BODY_NOT_REQUESTED` metadata whose observed/total counts match the
retained map. Unsupported/access-lost states, mismatched counts, unknown reasons
and positive body-complete claims remain refused. Apply the same predicate to
initial, cumulative and no-work paths. Do not strip source maps or rewrite hashes.
The model receives only primary facts/comments/history and is instructed not to
infer attachment or linked-item bodies. An application-owned report message
always discloses this scope; model evidence-reference limitations keep their
existing meaning and raw model output stays immutable.

Owned product paths: `project_management/app/domain/summary_input.py`,
`project_management/ai_profiles/project_summary.json`,
`project_management/services/report_sources.py`, and a cohesive disclosure helper
if required by the existing file-size gate. Owned tests are the corresponding
input/delta/profile/acceptance/report-source suites and typed-task contract tests.
No AIB, provider adapter, output-schema relaxation, historical v1 compatibility,
budget or performance change is included.

RED/GREEN must prove metadata-only admission and rejection of each invalid
sibling state, retained-chain checks, v2 profile/hash binding, deterministic
disclosure and actual task preparation. Run the installed task joins after the
focused tests, then independent source review before resuming LIVE.REPORT.
Existing v1 data remains immutable; mixed-version accepted-history migration is
outside this empty-instance qualification. Stop and report if that migration is
needed. A source repair PASS is not a live business PASS.

## In-Flight Observation Repair

Real run `39d6a7e2-6c7e-437f-b5c1-d158b2be3d04` completed successfully with
the configured model after 23.4 seconds. Dashboard stopped observing earlier:
`SummaryAnalysisService.advance` returned `unknown` for a known `running`
snapshot whose dispatch uncertainty was still unknown. The worker then produced
a partial report, despite the later valid runtime result.

Keep `queued` and `running` snapshots observable under their lifecycle status;
retain their original uncertainty in the durable observation. Unknown terminal
dispatch, missing lookup and transport errors remain unaccepted. Do not resend,
replace keys/deadlines, or change the 16-observation bound or any runtime/KPI
limit. Owned changes: `project_management/services/summary_analysis.py`, its
focused regression tests, this amendment and current reporting guidance.
Test queued/running uncertainty followed by the same run's confirmed result,
one admission only, and the existing uncertain-success/cancellation negatives.
Run the installed summary join and independently review before live revalidation.
Use a fresh isolated stage of the same bounded source for revalidation; preserve
the expired/partial experiment unchanged. This does not promise all oversized
source records fit the unchanged 65536-byte profile limit.

The retained real v2 result also exposed a model-facing schema gap: reference
arrays permitted arbitrary strings although the existing business validator
requires exact input evidence IDs. It correctly refused explanatory prose with
bracket citations. `metrics.project_summary@3` strengthens all four reference
array item schemas with their existing identifier grammar and explicit field
descriptions. It supersedes v2 only prospectively; no output is normalized or
retrospectively accepted. Membership, quote, owner and binding validation remain
unchanged, as do all limits. Additional owned paths: the summary profile,
`test_ai_profiles.py`, `test_typed_task_contracts.py`, and
`test_summary_acceptance.py`. RED must expose the old schema accepting prose;
GREEN also proves a syntactically valid but absent ID still fails business
membership. Revalidate the final profile through the installed summary join.
