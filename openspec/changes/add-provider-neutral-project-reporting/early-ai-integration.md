# Early AI Business Integration

Status: implemented and synthetic-business-join verified after independent
CORE and harness review. Exact qualification and limitations are recorded in
[w5-join-delivery.json](w5-join-delivery.json). This does not close the full W5 wave.
The original packet was CODE_READY after Kuhn's independent plan review
(`01a19a29-9c70-75a1-b51f-12d398a478a6`).
Owner: Dashboard. Execution state is maintained only in tasks.md.
Docs impact: API, architecture and validation; current guide is
`openspec/docs/current-baseline/project-reporting.md`.

## Decision And Scope

On 2026-11-02 the user explicitly asked to integrate as early as possible because
the Base counterpart has delivered its synthetic integration prerequisites.
The former all-W3 -> all-W4 -> W5 ordering is not a necessary dependency for
one honest business integration slice.

W5.JOIN depends on C0.R, W1/W2, W3.ARCHIVE and W3.GATEWAY/CAPTURE.
It does not wait for spreadsheet approval/CLI, attachment bodies, external
dependency grants, HSD live qualification, full delta/import or report rendering.
Those requirements remain open under their original leaf tasks.

The first slice is an internal application API, not a new public web endpoint:

1. Read one complete, consistent, first captured work item from the real archive.
2. Build the strict explicit input with real Project/Stage/source identities.
3. Persist an immutable attempt and exact HTTP payload before any dispatch.
4. Call the installed a2 Python SDK against a real loopback Base Task/Run server.
5. Keep original RunSnapshot/RunResult, content and hashes; validate then accept
   under the application's source/owner/accepted-revision CAS.
6. Reuse the accepted summary without an SDK call when every retained source
   version since its baseline is unchanged.

Non-goals: production model qualification, provider reauthorization, final
report publication, automatic worker recovery, cross-process observation workers,
full cancellation UX, full incremental analysis, unlimited source chains and
fragment/merge. An unsupported case returns a typed refusal, not truncated input.
W5.JOIN is not W4, W5 or the complete project reporting feature.

## Actual Counterpart And Fixture Boundary

The frozen design SHA remains
`ff7899333c8ed8f0717b47fc7c1d6a6e5928db575a15553d2501045f123719da`.
SDK a2 SHA is
`32e54c5f443e39daa55190c4de142ac6c12478204d8fba6bf9909149c3b365f9`;
manifest SHA is
`e7386f82d2bf3963feccc28cfbfda732b9eddb829831d5ba660b50554e5f81c4`.
The exact counterpart paths and its qualification limits remain in
execution-handoff.md section7 and its linked delivery receipt.

The published launcher compares the complete input to a review fixture containing
`project-alpha`, `release-1`, `capture-2` and an all-ones rule hash. Dashboard
cannot produce that fixture from its UUID-based catalog and real archive.
Do not rewrite application identities or source hashes to make it pass.

The Base already provides the explicit synthetic composition API:

```text
app.task_run_candidate.create_task_run_candidate(
    data_directory, registrations, credential_secrets, profiles, grants,
    backend: SyntheticExecutor, limits=None, clock=None) -> FastAPI
SyntheticExecutor.execution_mode = "synthetic"
SyntheticExecutor.backend_id: str
SyntheticExecutor.execute(compiled) -> str
```

A Dashboard-owned integration harness may use this unchanged factory with
the hash-verified a2 profile, an exact UUID-derived scope grant, a generated
synthetic service-account identity and an explicit input/output test vector.
The executor accepts only that vector and counts invocations. It is a test
fixture, never an application summarizer or replacement Run service.
No Base source, pack, a1 environment or real credential is modified.
Report this as the Dashboard-owned joint fixture, not the peer's default launcher.
Use the delivered source snapshot or verify its exact source hashes before launch;
record the actual candidate and do not inherit unexecuted peer qualification.

If the factory no longer supports the documented explicit seam, stop the joined
run and request a versioned fixture-registration entry from Base. Do not monkeypatch
its executor, bypass schema/auth, or claim SDK MockTransport is business integration.

## Exact Application APIs

`project_management/app/domain/summary_contracts.py`:

```text
AnalysisError(code)                         # safe English message
AiBackendTarget(base_url, source_app_id, run_store_id, scope_key,
                grant_revision, limit_policy_revision)
PreparedAnalysis(source_key, target_capture_id, source_hash,
                 expected_revision, base_summary_id, input_content, input_hash)
AnalysisAttempt(attempt_id, project_id, stage_id, source_key,
                backend, prepared, request, dispatched)
AcceptedSummary(summary_id, revision, target_capture_id, source_hash,
                profile_definition_hash, input_hash, candidate, run_result)
AnalysisPreparation(kind: ready | no_work, attempt | None, accepted | None)
AnalysisStep(state, attempt_id, accepted | None, error_code | None)
```

All nested persisted values are copied by canonical JSON serialization; no
credential/token/session enters these values. Source key is the existing
`SourceChainKey(provider_id,endpoint_id,stable_id,principal_id,rule_hash)`.
Profile is loaded from the exact pack by `AiTaskContract`, not an arbitrary HTTP
parameter. Its key is `project-reporting.summary`, revision `review-1`.
This profile is explicitly synthetic-only; enabling a live profile is later work.

`project_management/out/ai_task_contract.py`:

```text
AiTaskContract.load(pack_root: Path) -> AiTaskContract
  profile_ref -> {"key": str, "revision": str}
  definition_hash -> str
  output_schema_hash -> str
  validate_input(value: dict) -> None
  validate_snapshot(attempt: AnalysisAttempt, value: dict) -> None
  validate_result(attempt: AnalysisAttempt, snapshot: dict, value: dict) -> dict
```

Load checks the exact a2 manifest and all21 file hashes, uses only its local
schemaDocuments registry, and rejects external schema retrieval. The runtime
validates the actual SDK version as0.1.0a2. Missing optional AI dependencies fail
when this feature is selected, not while loading unrelated Dashboard pages.
Consumer dependencies go in `requirements-ai-task.txt`; existing requirements
and the separate C0/a1 environment do not change.

`project_management/app/api/summary_analysis.py` exports:

```text
SummaryAnalysisService(archive, contract, client_factory, clock=None)
  prepare(actor, project_id, stage_id, source_key, *,
          backend: AiBackendTarget, deadline_at) -> AnalysisPreparation
  async advance(actor, project_id, stage_id, attempt_id, *,
                backend: AiBackendTarget) -> AnalysisStep
```

`prepare` delegates to the archive-owned journal. It never calls the SDK.
`advance` reauthorizes the Project/Stage, loads the persisted attempt and checks
the exact backend/store before invoking client_factory(target).
The factory supplies the private token out of band and returns the installed
SDK async context manager. There is no shell invocation or raw HTTP substitute.
One advance performs at most one submit/by-key request and one result request.
Polling is an explicit caller decision, bounded by the original deadline.
The synthetic join driver permits at most 8 advances and a 600-second total
window including setup/cleanup; it never starts a second identical experiment.

`CaptureArchiveService` receives one cohesive journal mixin, in
`project_management/services/summary_journal.py`:

```text
prepare_analysis(actor, project_id, stage_id, source_key, contract, backend,
                 deadline_at) -> AnalysisPreparation
read_analysis_attempt(actor, project_id, stage_id, attempt_id) -> AnalysisAttempt
claim_analysis_dispatch(actor, project_id, stage_id, attempt_id) -> bool
record_analysis_observation(actor, project_id, stage_id, attempt_id,
                            observation: dict) -> None
accept_analysis(actor, project_id, stage_id, attempt_id,
                snapshot: dict, result: dict, contract) -> AcceptedSummary
```

The implementation reuses the existing repository, root+stage locks, owner checks,
growth admission, immutable append, Git update-ref CAS and authoritative reads.
No second SQLite attempt/accepted authority is introduced. W7 must consume these
same attempts. No public arbitrary-file or callback mutation API is added.

## Input And Acceptance Rules

Preparation reads the authoritative complete source chain at one Git head.
At most 100 versions and 64 evidence records are accepted by this first profile;
oversize input is refused without slicing. An initial summary requires exactly
one complete captured version. Multiple changed historical versions require
W4.DELTA and are refused as `ANALYSIS_DELTA_REQUIRED`.

The target must be a current member in a complete membership observation, have
consistent facts/comments/history and no requested attachment/dependency bodies
that this slice cannot consume. The fields, every comment and every history
record form the input evidence; none are selected by UI or a guessed tag.
Keep original Unicode and values. Evidence pointers address the documented
`fields/comments/history` input projection; each source_hash is computed from
the exact projected value. Capture ID plus original snapshot source hash remain
bound separately in the durable attempt.

The latest capture itself must be complete in this first slice. Attachment and
dependency parts may be not_requested or confirmed empty complete collections;
partial, unsupported, access_lost, or positive uncaptured counts are refused even
when their body maps are empty. The original snapshot hash excludes coverage:
one shared source-readiness predicate is used by preparation and no-work reuse,
and every retained version is checked independently of its raw-data hash.

First-baseline input has null summary/capture/text, accepted_revision0 and all
comment IDs in added_ids. The schema-required fixture_version is `review-1`;
it is a profile wire version, not a fabricated catalog identity.
Input uses compact sorted UTF-8 JSON with no NaN/Infinity or duplicate keys.
Logical algorithm is `dashboard-json-review-1`; transport and logical hashes
are recorded separately even when these canonical bytes make them equal.

No-work requires the same profile definition and complete, consistent source
hash/coverage for *every* retained version after the accepted baseline. A->B->A
does not count as unchanged. Missing baseline/history, changed data, partial
coverage or access loss refuses reuse. A repeated source hash never grants access.

Before accepting, validate the full delivered RunSnapshot and RunResult schemas,
contract/store/app/scope/key/run/profile/definition/input/logical hashes, terminal
succeeded state, available result, effective-input agreement, output-schema hash,
media type and SHA-256 of the original UTF-8 content. Require synthetic receipt
mode and preserve unknown cost/token values; never coerce them to zero.

Then validate strict output, binding/profile/base/target/English marker, evidence
membership and value hashes, exact narrative quotes and grounded owner identity.
Owner confirmations remain false. Unknown owners require null identity/quote;
explicit owners need an exact cited quote and a source-backed identity. Reject
uncited or mismatched statements at the enforceable reference/quote boundary;
do not claim a deterministic check can prove arbitrary prose true.
Only after these checks bind local candidate.input_hash; retain original content.

For this application's review-1 projection, blockers and limitations contain
evidence-reference IDs, not free-form narratives; every listed ID must resolve
in the supplied evidence. This is an application validation rule, not a change
to the frozen generic Base schema. Rich blocker text belongs to the later full
W5 profile. Explicit next-owner quotes are supported from comments and current
summary/description/environment fields. Field history stays in the input and can
support context or a suggested owner, but an old field value alone is not an
explicit current next-action request. Do not broaden that source rule merely to
accept an arbitrary historical string.

Accepted CAS compares current source target/hash, scope/principal identity,
profile definition, base summary ID and accepted revision under the same archive
lock. Owner/source/accepted changes leave accepted state unchanged. Replaying the
same accepted attempt returns the original accepted record.

`backend.scope_key` must be exactly
`projects.<actual-project-uuid>.stages.<actual-stage-uuid>`, and is checked before
persisting/sending. The deployment/harness supplies expected grant and limit-policy
revisions explicitly; neither is inferred from an arbitrary response.
RunSnapshot must match the persisted `grant_revision`, `limit_policy_revision`,
original deadline instant, requested byte/token limits and minimum retention.
The delivered synthetic candidate uses limit policy `base-b-cancel-synthetic-1`;
the joint fixture registers `grantRevision=dashboard-join-1`.
RunResult lacks app/key/grant/limit/deadline fields, so those are validated on the
same run's full persisted snapshot, never fabricated as result properties.

## Persistence And Recovery

Namespace allowlist extends only with `analysis_attempts` and `accepted_summaries`.
Files use validated UUID/hash/numeric components:

```text
analysis_attempts/<attempt-uuid>/intent.json
analysis_attempts/<attempt-uuid>/dispatch.json
analysis_attempts/<attempt-uuid>/observations/<8-digit-sequence>.json
accepted_summaries/<source-key-sha256>/<8-digit-revision>.json
```

Attempt ID is UUID5(stage UUID, logical input hash). Its immutable intent stores
the exact submit payload, original deadline/limits, endpoint/app/store, profile
hashes, source and baseline. Same logical attempt with another store/endpoint
fails; another prepare deadline does not renew an existing attempt.
Creating an attempt also checks for an unresolved attempt for the same source.
Only a durable dispatch claim permits the single initial submit.
After a claim, all subsequent advances query the original clientRunKey, including
after a missing response or process exit. A 404 after an uncertain dispatch does
not authorize automatic re-submit. Persist typed unknown/error observations.

No lock is held across network I/O. A failed archive append prevents its following
side effect. A failed result/accept write does not create a new Run; observe the
old key and retry the application acceptance. Wrong store, expired deadline,
canceled/failed/timed_out/indeterminate or unavailable result never advances
accepted state. Base cancel support remains available for later integration;
this slice does not claim remote abort or unknown reconciliation.
All journal writes use existing growth quotas, never volume-free-space checks.

New submit deadlines use exact UTC milliseconds (`YYYY-MM-DDTHH:MM:SS.sssZ`),
truncated rather than extended. The application validates this before persistence
and dispatch because the delivered a2 JSON schema omits the server's validator
constraint. Existing persisted attempts are never reformatted in place.
Definite request rejection retains the Base error code, HTTP status and recovery
instruction; `rejected` describes the request, not a refund or proof about all
prior execution. Transport uncertainty stays unknown. Neither outcome silently
creates another key. Cross-application feedback is in [w5-base-feedback](w5-base-feedback.md).

Every call to `append_record` has a distinct, Windows-safe record UUID, not a
shared attempt ID. UUID5 inputs are exact UTF-8 strings:

| Event | `record_id` | `record_fingerprint` |
| --- | --- | --- |
| attempt intent | `uuid5(UUID(attempt_id), "intent")` | SHA256(canonical event envelope) |
| dispatch claim | `uuid5(UUID(attempt_id), "dispatch")` | SHA256(canonical event envelope) |
| observation N | `uuid5(UUID(attempt_id), "observation:" + 8-digit N)` | SHA256(canonical event envelope) |
| accepted revision N | `uuid5(UUID(stage_id), "accepted:" + source-key hash + ":" + 8-digit N)` | SHA256(canonical accepted envelope) |

The envelope contains schema_version1, kind, attempt_id and the exact payload;
accepted envelopes also bind source-key hash and revision. Its canonical bytes
are the corresponding file bytes. Observation sequence is allocated under the
existing lock, contiguous from1, at most16records per attempt in this slice.
Different phases therefore cannot collide in finalize/<namespace>/<record_id>.
Committed identical replay is recognized before another append; mismatched bytes
or an unrelated pending finalize remains a conflict, never an overwritten record.

## Owned Files And Source Reuse

New production files:
`project_management/app/domain/{summary_contracts,summary_input,summary_validation}.py`,
`project_management/app/api/summary_analysis.py`,
`project_management/services/{summary_analysis,summary_journal,summary_journal_reads}.py`,
`project_management/out/ai_task_contract.py`.
Existing files: `services/capture_archive.py` mixin wiring,
`storage/repository.py` namespace/path allowlist; optional requirements for installed SDK
consumer dependencies. No UI, provider adapter, Base source or scope editor edits.

New tests:
`project_management/tests/{summary_fixtures,test_summary_input,test_summary_acceptance,`
`test_summary_analysis,test_summary_journal}.py`.
Joint harness belongs under `scripts/validation/`, not the application runtime.
The unchanged a2 pack is vendored under
`project_management/ai_bundle/strict-summary/task-run-contract-0.1.0a2/` so the
offline validators and tests do not depend on another agent's mutable checkout.
This is a versioned dependency artifact, not completion of the future live app bundle.

Reuse existing Dashboard catalog, capture, Git admission/commit/locks and the
installed Base SDK. Semantic ports from donor commit
`3d06b7a4a25434ee2fa133c9b4bef5f9c7c1366d` are the complete-source/retained-version
guard in `domain/delta.py`, evidence identity/hash checks in `domain/evidence.py`,
and exact narrative/owner rules in `analysis_ownership.py`.
Do not claim those whole donor modules or W4.DELTA have migrated. Record exact
donor blob IDs and mapped tests in the implementation evidence.
The fixed mapping and Base source identity are in [early-ai-source.json](early-ai-source.json).

## Validation Matrix And Order

| ID / level | Input or event | Required result / wrong implementation rejected |
| --- | --- | --- |
| EJ01 L1 | first complete source, 3 comments including Unicode and >12k body | all original values/hashes/UUIDs preserved; no fixed review binding |
| EJ02 L1 | partial history, 65 references, changed multi-capture history | typed refusal before attempt/SDK, no truncation |
| EJ03 L1 | accepted baseline then unchanged / A->B->A / missing baseline | only complete unchanged chain gives no_work |
| EJ04 L1 | wrong binding/input/store/profile/schema/content hash, invented reference/owner | candidate rejected without accepted advance |
| EJ05 L1 | explicit source-backed quote and unknown owner | valid English candidate accepted locally; original content remains unchanged |
| EJ06 L1/L2 | persist failure before claim; repeated/uncertain dispatch | zero initial send on failure; one POST then original-key GET only |
| EJ07 L2 | real temporary Git journal, recreated service, expired/new deadline | same attempt/key/payload/store and original deadline, no renewed attempt |
| EJ08 L2 | wrong owner, archived project, changed latest capture or accepted revision | no side effect or failed CAS; original accepted record remains |
| EJ09 L2 | original result accepted twice; mutation of fetched JSON | one immutable accepted revision; no caller-owned mutable alias |
| EJ10 L3 | real catalog+capture+journal -> installed SDK -> Base loopback -> accept | UUID-derived scope/input, one synthetic execution, original result and accepted Git record |
| EJ11 L3 | recreate application service then no-work/replay | durable accepted summary, zero additional executor invocations |
| EJ12 L3 | fixture exit, exact source/artifact checks | own listener/process stopped, no tokens in receipt; no live/model claim |

Order: independent packet review -> input/validation RED/GREEN -> journal/client
RED/GREEN -> one real Git integration -> one joined loopback run -> scoped review.
Do not run Base's 574 tests or repeat the unaffected Ego/UI matrix.

Exact commands from the Dashboard root:

```powershell
.venv/Scripts/python.exe -m pytest project_management/tests/test_summary_input.py project_management/tests/test_summary_acceptance.py project_management/tests/test_summary_analysis.py --ds=provider_sync.tests.connection_test_settings -q
.venv/Scripts/python.exe -m pytest project_management/tests/test_summary_journal.py --ds=provider_sync.tests.connection_test_settings -q
.venv/Scripts/python.exe scripts/validation/project_summary_join.py --work-root D:/AIGC/scrum_dashboard/.tmp/task-run-w5 --data-root D:/AIGC/scrum_dashboard_validation/w5-join --base-python D:/AIGC/Report_creater_agent/.venv/Scripts/python.exe --base-source D:/AIGC/scrum_dashboard/.tmp/task-run-w5/base-source --pack-root D:/AIGC/scrum_dashboard/.tmp/task-run-w5/artifacts/contract-pack
```

`project_summary_join.py` creates an exclusive UUID evidence directory below
work-root and a matching owned run directory under the explicit external data-root.
Catalog DB, capture Git, vector, synthetic identity and Base Run DB stay outside
all code repositories. A root owner marker rejects an existing unowned directory;
the production archive path guard remains unchanged. The temporary Django
configuration explicitly registers project_management, bug_metrics, jira_history,
jira_sync and provider_sync, without importing the user's .env. The bootstrap
and data-root tests must pass before another full joined run.
It launches `project_summary_base_fixture.py` using base-python on the
fixed source copy, listens on127.0.0.1/OS-selected port and returns that descriptor.
It must not read the user's .env or default database. Finally creates the exact
stopFile, waits15seconds, then records any ownership-bound forced cleanup as a
failure. One child only; no listening service may remain after the command.
Both helpers, project_summary_support.py and their local import/settings/root
safety test are part of this packet. Failure artifacts retain safe traceback
frame names/lines, never exception locals, tokens or credential-bearing messages.

The Base snapshot must include the full fixed Git commit plus the verified delivery
overlay, not only services/app-service: its import closure reads root config files.
The driver verifies844 source files and performs a private-environment, outbound-
blocked Base factory import probe before collecting or loading application data.

`--resume-source <owned-data-root>/<source-run-uuid>` reuses only a complete
single-capture checkpoint with no committed analysis_attempts namespace. It
revalidates owner/catalog/archive/input and the original vector; it does not
recapture or rewrite source data. A new fixture store is forbidden once an
application attempt exists. This is validation-checkpoint reuse, not W7 native
Run recovery.

On Windows, the venv redirector PID can differ from the Python worker PID.
Readiness verifies the worker's OS-reported parent and full fixture argv before
accepting that distinction. The exact scope/stop path remains checked. Normal
cleanup signals the unique stop file, waits for the owned launcher, then verifies
worker exit using the existing lifecycle engine's process inspection. Forced
cleanup targets only the still-owned launcher tree and is reported as failure.

First RED: test_summary_input builds a first captured item through the planned
public preparation contract and expects its actual IDs plus all three comments.
Missing production API is the initial gap. The final report distinguishes
implemented slice, remaining full-wave requirements and actual test scope.
