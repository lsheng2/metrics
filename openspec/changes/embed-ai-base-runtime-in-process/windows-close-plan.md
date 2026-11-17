# Windows Closure Implementation Plan

> Agent execution: use the existing OpenSpec ledger with
> `superpowers:executing-plans` or `superpowers:subagent-driven-development`.
> Only `tasks.md` contains execution checkboxes. This document and the JSON DAG
> define work; they do not maintain another progress ledger.

## Goal And Authorization

Finish the owner's four-point **Windows AIB + Dashboard delivery milestone**:
pin the runtime artifact; finish the Dashboard consumer/entrypoint migration;
qualify the real joined workflow and failure lifecycle; then permit a separate
decision about resuming other Apps. This is not full AIB repository release.

- This revision is **planning-only**, requested on 2026-11-17. Product execution
  requires both `PLAN.R` and a subsequent explicit owner resume/approval.
- Update this existing change, not a new competing OpenSpec: the product
  architecture and original requirement IDs remain authoritative.
- Linux, WSL and Linux-container execution is deferred by the owner. Preserve
  their interface/environment definitions; do not mark them tested or remove
  them to make a Windows scan green.
- Other App/generic-capability WIP, live provider/model use, real-user data
  changes, main integration, push and worktree deletion are not authorized here.
- `WIN.ACCEPT` records the Windows milestone. It does **not** archive MDB-2 or
  close AIB `W3.APPS`, `W4.QUAL`, `CLOSE.R`, `DELIVERY`, or original deferred
  MDB-2 requirements. Whole-change archival needs their actual completion or a
  separately approved specification amendment.

## Baseline And Established Architecture

| Binding | Value |
| --- | --- |
| Dashboard source | `d0c395eb8649a90d2a2cae09d1f5362252bb0353`; clean at plan creation |
| AIB candidate source | `d589ac8e6572a903edc3846e7d78195e85858868` |
| Runtime | `ai-base-runtime==0.1.1.dev4` |
| Wheel SHA256 | `b332f338f77bf2e966de7495eea6b5968606eb670287588d97a3a4d82905ec94` |
| Artifact/import authority | `ai_host/runtime_artifact.json`, `ai_host/admission.py` |
| Candidate environment | Current explicit interpreter in `docs/development/reporting-delivery.md` |
| Project profile | `.github/skills/lsheng2-dag-based-planning/templates/project-profile.md` |
| Profile/routing | `profile_source=repo-local`; `agent_routing_mode=multiagent-configured` |
| Spec | `proposal.md`, `design.md`, all nine `specs/*/spec.md` deltas |
| Detailed steps | [windows-close-steps.md](windows-close-steps.md) |
| Gates and coverage | [windows-close-validation.md](windows-close-validation.md) |
| Structural graph | [windows-close-dag.json](windows-close-dag.json) |

One App, one host process, one security boundary. Django stays threaded WSGI;
the installed runtime owns its loop thread, task execution, sessions and
approvals. `ai_host` owns composition/auth/lifecycle and public runtime adapters.
`project_management` owns business acceptance and native archive bytes;
`bug_metrics` owns chart publication; the existing service lifecycle engine
(SLE) owns process provenance. Do not introduce another SDK, journal, process
manager, bootstrap authority, sidecar fallback or provider abstraction.

Tech stack stays Python 3.13, Django 6.0.7, WhiteNoise 6.12.0, Waitress 3.0.2,
portalocker 4.4.2, the pinned runtime, existing htmx/Meridian UI and local Grafana.
This is a target dependency set; `requirements.txt` does not yet implement it.

### Verified Planning Gaps

- Standard requirements do not declare runtime/Waitress and still select
  portalocker 4.4.1. Candidate admission requires the wheel's
  `direct_url.json.archive_info.hashes.sha256`: a name-only install is not a
  substitute for direct installation of the pinned wheel.
- Runtime-instance profiles still contain AI Base backend/frontend bindings.
  Standard launchers use `runserver`; the local stop script can adopt/kill an
  unrelated listener. Replace those paths through SLE, not more PID-file logic.
- `serve`/`stop_owned_resources` implement the working slice, not all signed
  lifecycle requirements: absolute shutdown stages, watchdogs, runtime-ended
  monitoring, full exit inventory and some binding policy need implementation.
  W2 is therefore **implementation plus qualification**, not just test writing.
- Existing publication and retirement packets prove real bounded paths.
  They are candidates for reuse, not proof that every unchecked task is done.

## Contract Registry And Propagation

All contracts below are high risk. Check references resolve in the validation
matrix; every named consumer must have its assigned negative check.

| ID | Authority and producer | Concrete consumers | Required behavior / negative check |
| --- | --- | --- | --- |
| INV-1 | Candidate bytes: `runtime_artifact.json`, `admission.py` | `serve.py`, `local_runtime.py`, standard installer, final qualifier | exact wheel/import/files; reject tamper, editable, shadowed, unavailable wheel (`V1`) |
| INV-2 | Process identity: `dashboard_runtime_instance_profile.py`, SLE `ServiceSpec`/provenance | `e2e_bug_trend.py`, `local_*_backend.ps1`, `e2e_dashboard_ai_stack.ps1`, process/boot audits | same owned instance and stop-file; reject schema 1, foreign listener, stale PID and early process death (`V2`) |
| INV-3 | Host lifetime: `serve.py`, `state.py`, `lifecycle.py`, planned `serve_control.py` | WSGI dispatch/iterators, project runtime, signal handler, launcher termination evidence | bounded ordered shutdown and truthful 0/1/3/130; do not skip cleanup or count forced exit as normal (`V4`-`V8`) |
| INV-4 | Request/approval/business authority: `metrics/auth.py`, `ai_host` public adapters, App profiles | Django and `/ai`, Workbench frame/context, approved publication and task-run readers | identity/order/quota isolation, exact approved bytes, no duplicate dispatch (`V3`, `V6`, `V9`) |
| INV-5 | Preservation: native archive, DB and runtime state | migration/recovery harness, new host, isolated old-version restore | one stopped snapshot set; reject wrong owner/hash/schema, never mutate original user state (`V10`) |
| INV-6 | Acceptance/evidence authority: this plan, original tasks and frozen source/artifact | test selector, qualifier, review, ledger and delivery receipt | zero failures/required omissions; reject stale/mixed/collect-only/empty evidence; deferred is never passed (`V0`, `V11`) |

Non-goals: provider protocols, chart semantics, editorial behavior, new UI design,
other App workflows and runtime SPI redesign. If an acceptance failure requires
one of these, preserve the failing evidence and return to the owner with a
minimal cross-repository change request before implementation.

## Consumer Universe

| Category | Disposition and concrete scope |
| --- | --- |
| public API | applies: public task-run ports, runtime mount, App registration/package checker |
| internal service/facade | applies: existing host, run/report factories, SLE; no new business engine |
| UI route/template/component | applies: existing Workbench/pane/history/workflow acceptance; no redesign |
| export/report | applies: preserve summary/authoring/native publications; broader new export features not included |
| audit/log/event | applies: auth log, runtime audit, exit inventory and truthful stop records |
| validation script | applies: install, launcher, conformance, qualification and evidence consumers |
| migration/schema | applies: profile schema 2 and isolated DB/state/archive rehearsal |
| background job/scheduler | applies to project worker stop/recovery; scheduling activation is deferred with owner trigger |
| cache/index/search | applies to preservation/isolation only; index rebuild and new caches are not applicable |
| external artifact | applies to wheel, constraints, local Grafana import; Linux image qualification deferred |
| CLI/admin command | applies: serve, project-run local port and every current Windows launcher/stopper |
| docs/operator workflow | applies: requirements, README, runbook, reporting guide and canonical AI guidance |
| test double/fake/fixture | applies: synthetic upstreams only; real composition root and business stores remain |

## Execution DAG

The JSON stores node structure, not statuses. Its node IDs correspond one-to-one
to the `Windows Closure Execution Frontier` checkboxes in `tasks.md`.
`PLAN.R`, `OWNER.RESUME` and `OWNER.RELEASE` are explicit external gates, not
product progress rows. `PLAN.R` is the independent review of this revision;
its receipt is `.tmp/mdb2-windows-plan-review/state.json`.

| Node | Depends on | Deliverable |
| --- | --- | --- |
| WIN.RECONCILE | PLAN.R, OWNER.RESUME | clause-to-evidence census; executable rollback preconditions |
| W1.VA | WIN.RECONCILE | install/launcher/retirement test design accepted |
| W1.INSTALL | W1.VA | reproducible clean Windows environment and direct wheel admission |
| W1.LAUNCH | W1.INSTALL | actual Windows entrypoints and owner-safe graceful stop |
| W1.RETIRE | W1.LAUNCH | scoped absence/import gates and current operator docs |
| W1.R | W1.RETIRE | reviewed first delivery package |
| W1.REPLAN | W1.R | remaining host gaps rechecked against landed code |
| W2.VA | W1.REPLAN | discriminating native host/failure/performance test design |
| W2.HOST | W2.VA | missing signed host lifecycle implemented with focused tests |
| W2.CERTIFY | W2.HOST | complete Windows conformance and isolated 10.4 results |
| W2.R | W2.CERTIFY | reviewed qualified host package |
| W2.REPLAN | W2.R | final candidate/rehearsal feasibility frozen |
| W3.FREEZE | W2.REPLAN | immutable final source/artifact/fixture selection |
| W3.REHEARSE | W3.FREEZE | isolated state upgrade and rollback receipt |
| W3.JOIN | W3.REHEARSE | final joined Windows workflow plus required broad gates |
| CLOSE.R | W3.JOIN | independent finite acceptance/evidence review |
| WIN.ACCEPT | CLOSE.R | four-goal Windows milestone receipt and reconciled task status |
| DELIVERY | WIN.ACCEPT, OWNER.RELEASE | only the explicitly authorized publication/integration actions |

```mermaid
flowchart TD
  P["PLAN.R + OWNER.RESUME"] --> A[WIN.RECONCILE]
  A --> B[W1.VA] --> C[W1.INSTALL] --> D[W1.LAUNCH]
  D --> E[W1.RETIRE] --> F[W1.R] --> G[W1.REPLAN]
  G --> H[W2.VA] --> I[W2.HOST] --> J[W2.CERTIFY]
  J --> K[W2.R] --> L[W2.REPLAN] --> M[W3.FREEZE]
  M --> N[W3.REHEARSE] --> O[W3.JOIN] --> Q[CLOSE.R]
  Q --> R[WIN.ACCEPT]
  R --> S[DELIVERY]
  T[OWNER.RELEASE] --> S
```

## Ownership, Parallelism And Cost Controls

- One production writer per repository. Main agent coordinates and can be that
  writer; do not add an Implementation Engineer merely to duplicate the role.
- Architect Planner Reviewer owns `PLAN.R`, behavior review and final closure.
  A review and its following `REPLAN` can share one bounded invocation, but both
  outputs must be explicit. They do not mean two whole-repository review runs.
- Validation Engineer participates at `W1.VA`/`W2.VA` only for their distinct
  failure/measurement design. No generic explorer or debugger is started unless
  a concrete question or reproduced failure needs that role.
- Codex subagents always explicitly use `gpt-5.5`, reasoning `xhigh`.
- Parallel-safe: source/evidence census, docs/reference checks, and independent
  tests against frozen disjoint inputs with separate data roots. They never
  update source while another job qualifies those same bytes.
- Exclusive: state copy/restore, candidate install mutations, final graph
  acceptance, and all 10.4 measurement windows. During `HEAVY_RUN_ACTIVE`, no
  other Metrics tests, Python jobs or Git writes; capture process/CPU evidence.
- First use narrow failing checks, then affected suites. Full UI/publication
  and broad release checks run on the final frozen candidate, not after every
  wording change. Already unchanged proof is reused only by `V0`'s mapping.
- Keep exact-pass target at the existing default **one clean pass**. Review the
  selected packet and affected consumers, not unrelated historical modules.
  A required issue still blocks its packet; low severity is not permission to
  claim a clean pass.
- Give reviewers the literal receipt template with four separate severity
  lines; require a format self-check before they return. Never edit their
  findings/verdict. The previously discussed supplemental-format policy remains
  a proposal requiring explicit owner approval; this plan does not bypass the
  installed exact-pass protocol.
- After two equivalent failures without new evidence, stop that retry pattern.
  Change the hypothesis/instrumentation and record why. After 60 minutes on one
  question, record continue/narrow/owner-decision and the next falsifying check.
  These are control limits, not promised completion estimates.
- At each `REPLAN`, classify remaining work `continue`, `amend`, `supersede` or
  `retire`. Non-continue records contain `refreeze_actions`, `updated_artifacts`,
  `rerun_gates`, and `post_refreeze_preflight_result`; do not silently expand scope.

## Stop And Escalation Rules

Stop the affected node, preserve evidence and report the exact missing input:
candidate hash/import mismatch; unavailable rollback executable/artifact;
uncontrolled data root/process; a frozen runtime SPI change; measurement source
drift; mandatory Windows test unavailable or failing; repeated equivalent error.
Do not substitute old SDK mode, skip/xfail, larger deadlines, relaxed thresholds,
unknown identities or edited historical receipts. Other independent read-only
work may continue, but dependent nodes cannot pass.

Review acceptance is not execution authorization; Windows acceptance is not
Linux or whole-AIB acceptance; a commit is not main merge or push.

## Plan Preflight And Truth Sync

Use the repo profile's explicit preflight procedure, not the shared checker's
sample mode. Check JSON parsing, 18 unique node IDs, acyclicity, all references,
the table/graph/ledger ID sets, both `REPLAN` dependencies, validation IDs,
contract IDs, owner path syntax and original-task coverage. Check current paths
exist; new paths are explicitly labelled **planned** in the detailed steps.
Inspect the structured executor/argv taxonomy in the validation document.
Record this as `PF-DAG` with the actual plan path and findings; a structural PASS
does not mean product requirements passed.

Before counted plan review run OpenSpec strict, scoped file-size and whitespace
checks. This planning round does not run product, model, browser or Linux tests.
The independent `dag-plan-doc-review` uses the project overlay and reviews all
three documents, DAG, ledger links and changed profile/guide/index surfaces.

Docs impact: operations/configuration/validation planning. Update this change,
the reporting guide's plan entry, documentation index and stale project-profile
runtime references. No production behavior is changed by this planning commit.
Future node commits update their current operator docs alongside implementation.
Keep historical receipts and prior requirements; annotate deferred/superseded
scope explicitly instead of deleting inconvenient acceptance conditions.
