# SDK 0.2 Integration Contract

> Superseded on 2026-11-11 by [MDB-2](../embed-ai-base-runtime-in-process/proposal.md); historical evidence only, defines no remaining work.

Date: 2026-11-05. Owner: Dashboard; AI Base remains the public SDK/API owner.
Status: accepted scope for specification, scoped publication and pre-integration execution.
Execution state belongs only to [tasks.md](tasks.md).
profile_source: repo-local. agent_routing_mode: single-agent implementation with bounded independent review.

This appendix and [post-integration execution](sdk-020-post-integration.md) refine the existing
reporting change. They do not create a second plan, replace task-run/1, reopen FZ-01, or authorize
live providers/models. The pre-integration stop at `IP-SDK020-READY` was reached and explicitly
released by the user on 2026-11-05; the restrictions below remain the pre-IP contract, not a
prohibition on the separately authorized JOIN.

## 1. Stop Boundary And Ownership

`IP-SDK020-READY` is the handoff from separately developed SDK/application consumers to joined
integration development. Reaching it means the application accepts the selected SDK/pack pair,
its installed-client and domain rejection tests pass in an isolated process, and the next joined
work packet has concrete interfaces, fixtures and exit criteria.

It does not mean an AI Base HTTP service was started, a joined run passed, the main environment
was upgraded, or DAILY/ASSIST/the full week was completed. Application networking, including
loopback HTTP/direct connections, is forbidden. Windows Python's standard-library socketpair
uses a loopback self-pipe for asyncio; that runtime-only IPC is scoped and counted separately,
not treated as application networking or permission to connect to a Base server.

| Boundary | AI Base owner | Dashboard owner |
| --- | --- | --- |
| SDK release | Own SDK/API implementation, package contents, safe errors, receipt and compatibility statement | Verify exact delivered bytes and consume public methods |
| App preparation | No Dashboard edits; frozen artifacts remain available | Version gate, dependency selection, domain validation, isolated installed-client tests |
| IP-SDK020-READY | SDK artifact side ready; support concrete contract questions | Stop and provide source/test/artifact receipt; do not start JOIN automatically |
| Joined integration after release of the stop | Fix SDK/service defects in Base only, publish changed artifacts explicitly | Own joined fixture/driver, app state, acceptance and report journey |
| Later business work | No requirement to build editor, Jira scope or reporting history | DAILY, ASSIST, exports, week simulation and source/summary/editorial invariants |

Missing optional loader/events/TestKit capabilities do not block this integration.
An actual public contract defect is recorded with the original failing request shape and
sanitized evidence. The 2026-11-05 integration authorization permits necessary small fixes in
the Base owner's checkout, with focused regression tests and a separately identified candidate.
It does not permit mutating released wheels, old source snapshots, receipts or results; a
changed package/source must be explicitly versioned and selected before joined qualification.
Larger contract changes require owner coordination.

## 2. Exact Supported Combination

| Artifact/contract | Selected value |
| --- | --- |
| Python distribution | `ai-base-application-sdk==0.2.0a1` |
| Wheel filename | `ai_base_application_sdk-0.2.0a1-py3-none-any.whl` |
| Wheel SHA-256 | `1ab6c7aa7255abeb4637734f65613827d39593ff72b7ef9d630885922c2dd134` |
| HTTP contract | `task-run/1` |
| Existing contract pack | `0.1.0a2`, all 21 files unchanged |
| Pack manifest SHA-256 | `e7386f82d2bf3963feccc28cfbfda732b9eddb829831d5ba660b50554e5f81c4` |
| Summary profile | `project-reporting.summary@review-1` |
| Qualification | `synthetic_only`; no promotion to provider execution |
| TS package | `0.2.0` delivered, not adopted by this Python migration |
| TS tarball SHA-256 | `29b03a0f969cad503a45f88ced9d1d6831ec024a1d38067240c9e6d256eb1276` |

Source receipt is Base's `openspec/changes/refine-public-application-sdk/delivery.json`.
Final artifacts are under its `.tmp-validation/public-sdk-020/release/`, not earlier candidate
directories. Program Git carries the version/hash selection, not private runtime stores or tokens.

Runtime code does not read OpenSpec files. `requirements-ai-task.txt` and
`project_management/out/ai_task_contract.py` express the same exact supported combination.
The application continues reading its bundled
`project_management/ai_bundle/strict-summary/task-run-contract-0.1.0a2/`.
Unknown SDK versions, a different pack digest or changed profile bytes are rejected with
`ANALYSIS_CONTRACT_INVALID`; there is no wildcard, minimum-version range or automatic fallback.

SDK version, HTTP version, pack version, profile revision and provider qualification remain
separate. New SDK support does not make old unsupported source coverage or live execution valid.
Existing a1/a2 release artifacts and prior verification receipts remain untouched.

## 3. Public SDK API Consumed By The App

The following signatures are from the delivered Python SDK, not new Base requirements:

```text
TaskRunClient(*, base_url, source_app_id, credential_ref, token,
    run_store_id=None, timeout=30, transport=None)
await client.submit(request) -> RunSnapshot
await client.get_by_client_key(scope_key, client_run_key) -> RunSnapshot
await client.get_run(scope_key, run_id) -> RunSnapshot
await client.get_result(scope_key, run_id) -> RunResult
await client.cancel(scope_key, run_id) -> CancelResponse
await client.get_capabilities() -> CapabilitySnapshot
client.run_ref(scope_key, client_run_key, *, run_id=None, deadline_at=None) -> RunRef
await client.wait(ref, *, timeout, poll_interval=0.1) -> RunObservation
```

`request` is a Mapping matching RunSubmit; returned transport records are typed dictionaries.
`transport` is an optional httpx AsyncBaseTransport. The client is an async context manager.
`RunRef` contains service_url, source_app_id, run_store_id, scope_key, client_run_key,
optional run_id and deadline_at; it contains neither credentials nor a second journal.
`RunObservation={ref,snapshot,wait_timed_out}`; snapshot can be absent before the first response.
Local waiting timeout is not the server's `timed_out` state. `indeterminate` is not success.

For this migration, `SummaryAnalysisService` keeps its existing durable-claim/advance/cancel
orchestration and public submit/by-key/result/cancel calls. Merely having a new wait helper is not
a reason to replace its business deadline, observation limit or journal.
Future ASSIST may use bounded public reads, but still owns persistent intent and candidate acceptance.

SDK errors keep code, recovery, status, client_run_key, run_id and available request_id.
The app retains its safe AnalysisError mapping. `query_by_client_key` means observe the original
request, never invent a new key. A failed digest/identity check cannot be downgraded to an accepted
manual result. No automatic SDK POST retry or redirect is introduced.

Discovery without a pinned store is read-only. Run operations require the configured/retained
store, and capability discovery must not silently select a different store for an existing attempt.

## 4. App API And Authority Remain Stable

```text
AiTaskContract.load(pack_root) -> AiTaskContract
contract.validate_input(value)
contract.validate_request(request)
contract.validate_snapshot(attempt, snapshot)
contract.validate_result(attempt, snapshot, result) -> validated domain candidate
contract.validate_cancel(attempt, cancel_response, *, expected_run_id) -> snapshot

SummaryAnalysisService.prepare(actor, project_id, stage_id, source_key, *,
    backend, deadline_at, cancel_requested=None) -> AnalysisPreparation
await SummaryAnalysisService.advance(actor, project_id, stage_id, attempt_id, *,
    backend, cancel_requested=None) -> AnalysisStep
await SummaryAnalysisService.cancel(actor, project_id, stage_id, attempt_id, *,
    backend, timeout_seconds=None) -> AnalysisCancellation
```

Only the admitted SDK version changes before IP. The original request, metadata comparison,
output JSON Schema, evidence and owner validation remain in the application.
An SDK-validated result is not `AcceptedSummary`, a saved user edit, or a publication.
Original capture/source hashes, accepted-summary revisions, Run keys, deadlines and data-Git bytes
are not migrated or rewritten by installing the client.

| Contract / risk | Producer | Consumers | Required negative evidence |
| --- | --- | --- | --- |
| SDK020-COMBINATION / high | dependency pin and AiTaskContract.load | summary source reader, SummaryAnalysisService, future ASSIST-specific loader | supported exact pair works; old/unapproved version or tampered pack refuses |
| SDK020-RESULT / high | Base Run envelope and SDK decoder | AiTaskContract.validate_result, SummaryJournal.accept_analysis | wrong store/profile/input/hash/schema/evidence cannot become accepted |
| SDK020-RECOVERY / high | persisted application attempt | SummaryAnalysisService.advance/cancel | lost submit uses original key with one POST; original deadline and cancel fences survive |
| SDK020-ISOLATION / high | pre-integration runner and target install | selected tests and receipt reader | SDK outside owned target, changed wheel or real socket attempt refuses |
| SDK020-STOP / high | tasks user authorization boundary | coordinator, joined driver, future worker/UI qualification | pre-run receipt reports joined_http_started=false; next joined action requires release of IP |
| SDK020-POST / high | this contract and post appendix | DAILY, ASSIST, JOIN, final review | each later task names actual interfaces, fixtures, preservation assertions and remaining qualifiers |

Consumer inventory: public SDK/application API and services apply; UI/exports/CLI/background
workers consume the same application contract after IP. Persistence and migration apply only
as rejection/preservation checks before IP, not as production DB/data migration. Existing
source-search/cache code is unaffected. SDK artifacts, docs, test doubles and validation entry
apply. Live source/model, formal scheduler and Outlook remain separately qualified.

## 5. Pre-Integration Work Packet

Use Dashboard `main` per the user. Base is read-only. Existing authoring source WIP,
Scope/config/main.css changes and the existing 8017 service are not part of this packet.
No Git worktree reset, global dependency change or existing-service restart is allowed.

### SDK020.ARTIFACT

Create one owned `.tmp/sdk-020-preintegration-20261105/` evidence directory.
Copy the final wheel and owner receipt without modifying their source; verify the wheel,
bundled manifest and 21 content hashes. Check the retained synthetic Base source dependency
needed after IP exists; no Base module import or service start is part of this step.

Install with the existing Dashboard Python into this directory's separate `sdk-site`:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --no-deps --target .tmp/sdk-020-preintegration-20261105/sdk-site .tmp/sdk-020-preintegration-20261105/artifacts/ai_base_application_sdk-0.2.0a1-py3-none-any.whl
```

The target must be new/owned and empty before installation; do not use `--upgrade` to overwrite
an unknown target. Reuse exact installed httpx/jsonschema dependencies from the documented host
interpreter. Record their versions separately. This is a separate SDK installation and isolated
consumer process, not a claim that the main `.venv` or the running 8017 service was upgraded.

### SDK020.APP

Owner paths before IP:

- `requirements-ai-task.txt`
- `project_management/out/ai_task_contract.py`
- `project_management/tests/test_sdk_020_compatibility.py`
- `scripts/validation/run_project_sdk_preintegration.py`
- `scripts/validation/run_report_authoring_tests.py` as the explicit shared isolation-mode dependency
- directly necessary test fixtures only if the real SDK reveals a genuine protocol mismatch

Write the failing compatibility tests first. The supported SDK must be the real installed wheel,
not a monkeypatched implementation. Metadata injection is allowed only for the refusal cases.
Keep the original manifest/profile validators and semantic acceptance code intact.

Minimal production change:

```python
SDK_VERSION = '0.2.0a1'
if version('ai-base-application-sdk') != SDK_VERSION or sha256_bytes(manifest_bytes) != MANIFEST_SHA:
    raise ValueError
```

Do not reuse this summary-specific loader for authoring. Do not modify library internals or add
an SDK journal/schema loader. The tests must reject missing/unapproved package versions and
changed manifest/profile bytes, not just search for a new string in source.

### SDK020.PRE

`run_project_sdk_preintegration.py` is a bounded adapter around the existing no-dotenv authoring
test entry, not a second test framework. The shared entry will expose:

```text
run_tests(arguments, *, allow_loopback=True, network_attempts=None, runtime_ipc_attempts=None) -> int
```

Its ordinary CLI keeps the existing loopback-only policy. The pre-integration caller passes
`allow_loopback=False` and separate application/runtime counter lists; the same innermost guards cover connect, connect_ex,
create_connection and getaddrinfo before settings setup and during pytest. Every refusal appends
only an operation label, not a URL/credential. An outer monkeypatch alone is insufficient because
the existing runner installs its own socket guards. Guard tests prove both the unchanged ordinary
loopback policy and strict refusal/counter behavior using fake underlying callables, not real TCP.

Implementation discovery: Python3.13 on Windows creates an asyncio self-pipe through the
standard-library socketpair fallback. The first strict run refused that internal connection.
Use a context-local allowance only while the captured standard-library socketpair function
creates its own connected peers; only its numeric loopback connect is allowed and recorded as
`socketpair.connect`. DNS, arbitrary loopback HTTP and all other connects still fail.
The allowance resets on return/error and cannot leak to another thread/context.
This is test instrumentation, not a hostile-code sandbox. Preserve the original failed receipt;
do not relabel its refused IPC attempts as a successful qualification.

The new wrapper:

1. Validates the explicitly selected wheel hash and target SDK path under its owned work root.
2. Inserts only that installed SDK target before ordinary site-packages, verifies package and
   metadata origins, and compares package source bytes with the wheel.
3. Adds the current Dashboard source root, not Base source, and calls the shared
   `run_tests(..., allow_loopback=False, network_attempts=attempts)` for isolated Django settings.
4. Forbids application socket connections/DNS lookups, including localhost; SDK transport is
   explicit MockTransport. Only the separately counted standard-library socketpair IPC above
   is permitted. It does not import Base, create an HTTP server, or alter user settings.
5. Selects only the three files below, writes unique JUnit/receipt files and propagates failures.
   `passed` requires nonzero tests, no failures/errors/skips and zero real network attempts.

Exact selected tests:

```text
project_management/tests/test_sdk_020_compatibility.py
project_management/tests/test_summary_analysis.py
project_management/tests/test_summary_input.py
```

Command:

```powershell
.\.venv\Scripts\python.exe -I scripts/validation/run_project_sdk_preintegration.py --work-root .tmp/sdk-020-preintegration-20261105
```

First RED is expected to refuse the real installed 0.2.0a1 at the old exact version gate.
After the app change the same selection must pass. `SummaryScenario.setUp` builds domain values
without initializing Git; these tests must not pay for a whole browser/report fixture.
Existing summary transport cases exercise real SummaryAnalysisService and SDK with a memory
journal boundary; they do not claim actual Git persistence or Base HTTP integration.

### Pre-Integration Case Map

| ID | Test/behavior | Wrong behavior rejected |
| --- | --- | --- |
| S020-01 | load real installed 0.2.0a1 with unchanged bundled a2 pack | version gate still rejects delivered SDK |
| S020-02 | unapproved/missing SDK versions | permissive range or silent legacy fallback |
| S020-03 | changed manifest and profile bytes | disabling pack/definition trust to enable migration |
| S020-04 | existing lost-submit recovery test | a second POST, new key or lost accepted input binding |
| S020-05 | existing claim-failure/cancel/deadline tests | network before claim or acceptance after cancel |
| S020-06 | existing input/evidence and coverage tests | truncation, changed identity or incomplete source accepted |
| S020-07 | runner negative path and wheel checks | wrong installed package or an early real network call |
| S020-08 | per-run JUnit/receipt and unchanged main SDK/service | empty/failed tests called ready, or implicit deployment |

## 6. IP Receipt And Stop

At IP, record a unique JSON receipt under the owned work root with:

```text
schema_version=1, status=IP-SDK020-READY, created_at,
source_commit, source_files[{path,sha256}],
sdk_version, sdk_wheel_sha256, sdk_module_path, dependency_versions,
pack_version, pack_manifest_sha256, pack_files_checked,
test_selection[], junit_path, tests, failures, errors, skipped, exit_code,
network_policy_revision=2, network_attempts=0, runtime_ipc_socketpair_attempts,
joined_http_started=false, main_environment_modified=false,
base_owner_change, base_receipt_sha256, next_node=SDK020.JOIN
```

Record source WIP separately from the committed plan baseline; do not invent a commit containing
uncommitted code. A failed qualification still writes its real failure receipt and never READY.
No receipt is permission to start the next node automatically.
The receipt's test counters come from JUnit and may include unittest subtests; report the
top-level pytest summary separately rather than presenting their sum as independent test cases.

Before stopping: all owned commands must exit, unrelated dirty files remain unchanged, and the
current tasks section must say `waiting at IP-SDK020-READY`. Provide the exact first joined action
and remaining preconditions from the post appendix. No percentage or completion-time estimate.

## 7. Evidence And Publication Scope

Specification publication includes this change's connected authoring spec documents and the new
SDK integration guide. Existing authoring source WIP is deliberately excluded and identified as
local uncommitted implementation, not a remotely published feature.
Do not stage unrelated Scope/config/CSS, the entire workspace, runtime archives, package binaries
or credentials. Verify staged paths/content and the remote SHA after a normal push.

The later SDK preparation code may form its own bounded commit after targeted tests pass;
its receipt and excluded-file comparison remain explicit. No unrelated pending authoring work is
made complete by that commit. Integration after IP follows the existing tasks and the next appendix.
