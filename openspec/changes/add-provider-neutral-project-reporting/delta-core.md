# Bounded Cumulative Summary Delivery

Date: 2026-11-05. Qualified: 2026-11-06. Status: bounded CORE qualified.
Spec: [delivery-sequence.md](delivery-sequence.md), section 5.
Execution state belongs only to [tasks.md](tasks.md).
profile_source: repo-local. agent_routing_mode: multiagent-configured.
One implementation writer; one bounded independent plan/behavior reviewer.
Plan review: `.tmp/dashboard-delta-20261105/plan-review.md`, GPT-5.5/xhigh.

## Outcome And Scope

After accepted capture A, captures B and C can be summarized as one cumulative
input even if B's analysis failed. Acceptance advances revision 1 to 2, and the
real report reader consumes revision 2. Recapturing unchanged data then uses
the original accepted result without another model request.

Reuse SDK `0.2.0a1`, the immutable a2 `task-run/1` pack, capture archive, existing
analysis journal, and CAS. No second task engine, schema registry or source
index is introduced. The existing pack already permits baseline summary text,
delta identifiers and evidence from individually named captures.

Limits remain 100 retained versions, 64 evidence records and 65536 input bytes.
Every version in the admitted segment must be complete for facts/comments/history.
Nonempty attachments/dependencies, missing intermediate versions or partial source
still refuse. This is the bounded DELTA.CORE lane, not complete W4/W5 capability.

## Interfaces

New pure owner: `project_management/app/domain/summary_delta.py`.

```python
def build_analysis_input(project_id, stage, source_key, chain, snapshots,
                         profile_revision, baseline=None) -> PreparedAnalysis:
    ...
```

`chain` and `snapshots` are aligned, ordered retained versions of one
`SourceChainKey(provider_id, endpoint_id, stable_id, principal_id, rule_hash)`.
The source reader/journal verify each stored source hash and actual identity.
The builder independently rejects duplicate capture IDs, gaps, identity/rule
mismatches, unsupported/incomplete segment material and exceeded limits.

For no baseline and exactly one version, delegate to unchanged `build_initial_input`.
Its old serializer/hash, ref IDs, raw comments, quotes and language rules stay intact.
For multiple versions, segment starts at the verified accepted target, inclusive;
without a baseline it starts at the first complete version. Missing baseline
capture/hash, wrong binding or nonpositive accepted revision rejects.

Wire format remains the strict review-1 schema:

- `baseline` contains accepted ID, revision, target capture and canonical JSON of
  the accepted candidate in `text`; initial values remain null/0.
- Evidence is ordered by capture sequence, then fields/comments/history, with
  each collection ordered by source ID. Every admitted version has a fields row,
  even when its body is unchanged, preserving the capture sequence in the input.
- Target evidence keeps `fields`, `comment:<id>` and `history:<id>`.
  Prior evidence uses `archived:<capture-uuid>:<target-ref-id>`, with the actual
  old capture ID, source pointer/value/hash. It is not relabeled as current.
- `delta` is the union of changes across adjacent versions, not just A versus C.
  Namespaced IDs are `fields`, `comment:<id>`, `history:<id>`. A temporary comment
  may occur in both added and deleted sets; its actual old content remains evidence.
  Empty collections are represented by absence within their capture's complete
  evidence group. Initial single-capture added IDs keep their legacy raw form.
- No new synthetic event object is disguised as provider evidence. No truncation.

`validate_candidate` permits these historical records only with the canonical
historical ref/capture association; current IDs still bind to the target capture.
Every value hash, cited ref, quotation, language and owner rule is retained.
Final authorization depends on recomputing the exact input from retained sources,
not trusting the candidate's hashes or schema alone.

## Shared Accepted Material

New service helper: `project_management/services/summary_material.py`.

```python
def verified_accepted_material(archive, repository, source_key, contract,
                               chain, snapshots=None) -> tuple:
    """Return ordered verified accepted material, one entry per revision."""
```

Each entry contains the accepted summary, attempt, recorded snapshot and rebuilt
input. Add `_analysis_accepted_history` to `SummaryJournalReads` to read bounded
consecutive accepted records once; keep `_analysis_accepted` for latest callers.

For every revision, verify owner/project/stage/source key, original attempt,
profile/schema/request identity, dispatch claim, result and business validation,
accepted UUID derived from attempt, predecessor ID/revision and target source.
Rebuild against only the source prefix ending at that accepted target. Iterate
oldest to newest, using the already verified predecessor; do not recursively
reload all Git records. Cache only within this function invocation.

Consumers:

1. `SummaryJournal.prepare_analysis`: verify accepted material before no-work or
   baseline use; preserve exact existing-input request/key/deadline replay.
2. `accept_analysis`: verify current predecessor under the existing writer lock,
   check original revision/base ID and current target, recompute identical input,
   write `expected_revision + 1`. Replaying any already accepted attempt returns
   its own original accepted record, not the newest unrelated result.
3. `ReportSourceReader._accepted_material`: verify the same chain; retain the
   existing complete/no-change checks after the accepted target. Return pending
   for genuinely stale summaries, not an invented new analysis.

## Attempt Admission

New pure owner: `project_management/app/domain/summary_attempts.py`.

```python
def attempt_blocks_new_input(attempt, observations, contract, *,
                             accepted_attempt_ids, target_capture_id) -> bool:
    ...
```

- Verified accepted attempt IDs are settled regardless of which is newest.
- Undispatched attempts for an older target are safe to supersede: the existing
  claim fence rejects stale source before dispatch. Other undispatched attempts
  stay pending, unless they are the exact input replay.
- Validate retained snapshot/cancel identity before terminal classification.
  `succeeded/failed/canceled/timed_out` is settled only with `terminalAt`, no
  unresolved exposure and definite response/not-dispatched knowledge or confirmed
  remote stop. Inconsistent, malformed and wrong-store records fail closed.
- Submission rejection is settled only for a recorded actual submit operation,
  `recovery=correct_request` and status 400/413/422. Legacy unqualified error rows
  are not automatically upgraded to safe terminal proof.
- `indeterminate`, possible dispatch, transport timeout, expiration and cancel
  requested without remote proof do not authorize another dispatch.
- Extend `SummaryAnalysisService` error observations with operation provenance
  (`submit`, `observe`, `result`); no old bytes are rewritten.
- Same input always recovers its original intent, even after a terminal failure.
  A newly captured different input may proceed only after old exposure is settled.
  New input does not refund old cost or reset old request/deadline.

## Ownership And Tests

| Contract / high risk | Owners and consumers | Required disconfirming cases |
| --- | --- | --- |
| DELTA-INPUT | summary_delta -> summary_journal, summary_material, summary_validation | A-B-A revert, transient add/delete, historical quote, partial/gap/oversize refusal, initial byte compatibility |
| DELTA-ACCEPT | summary_material and journal -> ReportSourceReader, CLI/worker summary API | revision2 reader, original replay, tampered predecessor/result/source, wrong owner/principal, stale target/CAS |
| DELTA-ADMIT | summary_attempts, summary_analysis -> prepare/advance through existing worker | prior accepted1 does not block3; verified failure permits C; unknown B blocks; wrong identity cannot release |
| DELTA-REUSE | verified material -> prepare, worker, report reader | post-revision2 unchanged capture causes no new intent or inference |

Additional owner paths: `services/summary_journal{,_reads}.py`, `report_sources.py`,
`services/summary_analysis.py`, `app/domain/summary_validation.py`, their new and
affected tests, this appendix/tasks/delivery sequence, and current reporting docs.
No schema/ORM migration, frontend, SDK release, runtime config, global hooks or
provider transport changes in CORE. Public API signatures stay compatible.

Consumer universe: public API, services, report/export, immutable journal/audit,
worker/CLI, validation fixtures and current docs apply. UI consumes unchanged
report DTOs; mounted editor is not rerun for pure delta. New scheduler, migration,
cache/index, external data export and deployment are deferred to their old nodes.

Validation uses the selected interpreter and existing no-dotenv runner:

```powershell
.\.tmp\sdk-020-join-20261105\app-venv\Scripts\python.exe -I scripts/validation/run_report_authoring_tests.py project_management/tests/test_summary_delta.py project_management/tests/test_summary_attempt_admission.py -q --tb=short
.\.tmp\sdk-020-join-20261105\app-venv\Scripts\python.exe -I scripts/validation/run_report_authoring_tests.py project_management/tests/test_summary_delta_journal.py -q --tb=short
```

Execution steps:

1. L0: fail `build_analysis_input` tests with literal A/B/C fixtures and literal
   change/evidence expectations; implement full bounded serialization and refusals.
2. L0: fail admission cases across terminal/unknown/accepted identities; implement
   pure classification and prove result-fetch rejection cannot release unknown work.
3. L1: fail real archive revision2/failed-B/unknown-B/read-report cases; implement
   shared verification, prepare/accept/reader and error-operation recording together.
4. Run affected `test_summary_input.py`, `test_summary_acceptance.py`,
   `test_summary_journal.py`, `test_summary_analysis.py` and `test_report_source_reader.py`.
   Run explicit selected cases, not global discovery. Bind any retained evidence.
5. One installed-SDK/local-HTTP cumulative fixture, using existing joined service
   lifecycle helpers and synthetic execution only; preserve normal cleanup evidence.
6. Bounded behavior review plus CORE.REPLAN. Publish a complete scoped source packet,
   or state the exact pre-existing source-closure dependency. Do not falsely mark
   the parent W4/W5 nodes or live qualification complete.

First counterexamples should be subsecond pure values, before Git/HTTP work.
Use a unique `.tmp/dashboard-delta-20261105/` evidence directory, no timed native
stack sampler, and no equivalent retries without new evidence. Long fixture latency
is measured separately; performance conclusions require their own reproducible probe.

## Delivery Evidence

Evidence root: `.tmp/dashboard-delta-20261105/`.
The directory date identifies the start, not the completion date.

- `shared-contract-green.xml`: 32 tests, 53 subtests; cumulative values,
  initial compatibility, request recovery, evidence and owner validation.
- `delta-journal-green-01.xml`: 5 real-Git tests, 920.10 seconds; revision2/3
  report reads, failed-B cumulative changes, unknown-B admission, unchanged reuse
  and original journal negative cases. This candidate predates the final narrow
  replay/type/read guards; it is not their verification.
- `material-integrity-green.xml` and `report-reader-final-green.xml`: direct
  guards for boolean revision, corrupted replay and duplicate source reads;
  affected report/source cases passed.
- `delta-http-01.xml`: 1 passed, 146.48 seconds on the final runtime candidate.
  Installed SDK0.2 plus the verified 844-file Base copy accepted one cumulative
  delta via actual loopback HTTP; the report consumed revision 2, no-change reused
  it, and the owned Base launcher/worker exited normally without forced stop.
  Native evidence: `http-1d7ae92e-3488-4fe8-9eec-a9bdf93b6ca6/`.
- Independent `review-01/review.md` found two material guards; both were corrected
  with RED/GREEN cases. `review-fix/review.md` is READY for those fixes and the
  repeated-read mitigation. Final native evidence is bound by the coordinator.

CORE.REPLAN: continue to authoring source closure and ASSIST. No SDK/Base source
change is required for this slice. Full evidence index/import/unbounded chunking,
provider breadth and live qualification remain open. The one-query source read
count reduced from three to one; no broad latency improvement is claimed.
