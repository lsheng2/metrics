# Dashboard C0 SDK Intake Implementation Plan

> For agentic workers: use the current OpenSpec tasks ledger and bounded validation.
> This packet is a development qualification task, not production W5 implementation.

Goal: install and exercise the delivered SDK in a Dashboard-owned isolated environment with no server/model access.
Architecture: installed wheel + explicit httpx.MockTransport + immutable contract pack.
Tech stack: Dashboard Python 3.13, stdlib unittest, httpx declared by the delivered wheel, jsonschema for pack checks.
Spec: [project-reporting](specs/project-reporting/spec.md), [application integration](application-integration.md).
profile_source: repo-local. agent_routing_mode: multiagent-configured.
Status/check boxes: only [tasks](tasks.md); this appendix has no separate execution ledger.

## 1. Scope And Readiness

This is the next bounded packet that can run without W1.R or BASE-B. It does not bypass their gates.
The original missing-httpx prerequisite is now resolved in the dedicated C0 environment only.
2026-11-01 readiness preparation created `.tmp/task-run-c0/preparation.json`, copied verified artifacts,
installed dependencies and passed a bounded installed-SDK probe. The main Dashboard environment is unchanged.
The formal 12-case test script is implemented; C0.N1 and C0.R are complete for the pinned candidate.
Current source/command evidence is in tasks.md, not an assumption that product integration is complete.
The 0.1.0a1 wheel is synthetic-only; no cancellation/provider/native recovery claim is permitted.

| Node | depends_on | owner_paths | Exit |
| --- | --- | --- | --- |
| C0.PLAN.R | delivered BASE-A pack/wheel and this packet | current change docs only | independent plan/validation review; no missing consumer/unsafe command |
| C0.N1 | C0.PLAN.R | `scripts/validation/test_task_run_sdk_intake.py`; owned `.tmp/task-run-c0/` artifacts; current tasks evidence | installed wheel imported without repo/server, declared cases pass |
| C0.R | C0.N1 | same scoped evidence/docs | review real commands/results and explicitly unproved behavior |

C0.R feeds W4.REPLAN, which still owns the precise application attempt/accepted boundaries before W5.
Implementation remains one writer. A single Architect Planner Reviewer covers C0.PLAN.R and the validation design;
no separate debugger or implementation subagent is needed for this small dev-only packet.

Do not edit `.env`, normal `db.sqlite3`, app settings, production requirements, other agents' scope tests,
base source/pack/wheel, or old chiplet data. Do not call `manage.py` or import Django app settings for C0.
`.tmp/` is already ignored. No recursive delete is required; preserve receipts and refuse unknown existing work roots.

## 2. Inputs And Public API

Delivered immutable inputs, relative to `D:/AIGC/Report_creater_agent`:

| Input | Expected identity |
| --- | --- |
| `packages/task-run-contract/manifest.json` | SHA-256 `08f081745ce956df13474de15063ec66849aef7a0454b3f0bd8fb4c56ee9bbca` |
| `.tmp-validation/task-run-base-a/wheels/ai_base_application_sdk-0.1.0a1-py3-none-any.whl` | SHA-256 `de223668e49dc9ed145f6ec3bc5084d453a5611cee5f4f41987dd70a4474179f` |
| FZ-01 design | SHA-256 `ff7899333c8ed8f0717b47fc7c1d6a6e5928db575a15553d2501045f123719da` |

Before copying/installing, verify all manifest file targets remain inside the pack root and all 19 hashes match.
Copy only the declared pack files/manifest and wheel to the owned work root; no symlink/source/PYTHONPATH dependency.
Copies retain original bytes. Recheck hashes of copies before import; failed hashes stop without network/model calls.
Future package versions use a new receipt/input selection; do not silently accept different bytes under this packet.

Consume the installed package's actual API:

```text
TaskRunClient(
    *, base_url: str, source_app_id: str, credential_ref: str,
    token: str, run_store_id: str, timeout: float = 30,
    transport: httpx.AsyncBaseTransport | None = None,
)
await client.submit(request: Mapping[str, object]) -> dict[str, object]
await client.get_by_client_key(scope_key: str, client_run_key: str) -> dict[str, object]
await client.get_result(scope_key: str, run_id: str) -> dict[str, object]
```

Errors expose `code`, `recovery`, `status`, `client_run_key`, `run_id`.
No C0 test calls absent cancel/events/native recovery methods or loads `app.task_run_candidate`.
There is no new production wrapper/Run state machine in C0.

## 3. Environment And Commands

All commands below run from Dashboard root only during C0 execution.
Use the prepared `.tmp/task-run-c0/` after validating its preparation.json owner, wheel/manifest hashes,
interpreter and installed package identity. Do not blindly recreate its venv or reinstall mutable dependency ranges.
For a new run, use a fresh owned directory. If nonempty without a matching C0 receipt, stop and select
a new explicit task-specific directory; never delete/merge unknown contents or reuse the base environment.

1. Record Dashboard HEAD/dirty, Python path/version, five FZ-01 fixture hashes and delivered artifact hashes.
2. Create the owned environment from Dashboard's interpreter:

```powershell
.\.venv\Scripts\python.exe -m venv .tmp/task-run-c0/venv
```

3. Copy verified artifacts into `.tmp/task-run-c0/artifacts/`. Standard file-copy APIs are sufficient;
   resolved sources and destinations must stay in the explicit input/work roots.
4. Install the copied wheel and test dependencies into that environment, never globally:

```powershell
.\.tmp\task-run-c0\venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-input --timeout 30 --retries 0 --report .tmp/task-run-c0/pip-install-report.json .tmp/task-run-c0/artifacts/ai_base_application_sdk-0.1.0a1-py3-none-any.whl "jsonschema>=4,<5"
.\.tmp\task-run-c0\venv\Scripts\python.exe -m pip check
.\.tmp\task-run-c0\venv\Scripts\python.exe -m pip list --format=json
```

The wheel declares httpx>=0.28,<1. Use the already approved/configured package source; do not change global
proxy/index/credentials. Dependency download is separate from the network-denied SDK tests.
If dependency resolution is unavailable, record setup failure, do not splice another repo's site-packages.
Capture resolved versions from pip list and `download_info.archive_info.hashes` from the UTF-8 pip report;
ranges above are not a reproducibility lock. Keep the raw report only in the ignored owned work root,
and export names/versions/hashes without credential-bearing source URLs or local source paths.
If a source omits hashes, record the gap and obtain the exact artifact in the owned wheelhouse to hash;
functional tests may continue, but do not close the reproducibility part of C0.R as pinned until resolved.

5. Implement the named unittest file with actual SDK imports and MockTransport. Run it by absolute/script path
   under isolated Python; no pytest/Django conftest loading:

```powershell
.\.tmp\task-run-c0\venv\Scripts\python.exe -I scripts/validation/test_task_run_sdk_intake.py --pack-root .tmp/task-run-c0/artifacts/contract-pack
```

`--pack-root` is the sole custom argument; the script removes it before `unittest.main`.
It accepts a local directory only, validates the manifest/hash first and never scans arbitrary home/config paths.
All HTTP cases use MockTransport and synthetic identities. Guard socket connect/connect_ex/create_connection so
an accidental transport omission fails locally, and report zero real connections rather than trusting an .invalid hostname.
Test failure/empty selection is nonzero. Do not catch assertion failures to print PASS.
6. Run scoped size/whitespace checks on the new test file. Record known whole-worktree failures separately;
   C0 is not a declaration that W1/global hygiene passed.
7. Save command/exit/count/dependency/hash evidence in the original tasks entry and an ignored work-root receipt.
   Do not log Authorization or synthetic token values; record only non-secret identifiers.

## 4. Concrete Test Cases

Test class must be `class SdkIntakeTests(unittest.IsolatedAsyncioTestCase)`, not unittest.TestCase.
Prefix methods with `test_`; every async SDK method is awaited. Record per-test MockTransport method/path/call
counts, not only unittest totals. Unawaited-coroutine warnings or a zero-call HTTP test are failures.
L0/L1 are this packet's scope; no server, DB, provider or native restart tests are part of C0.

| ID / layer | Exact test name | Input / observation | Pass / failure criterion |
| --- | --- | --- | --- |
| C0-01 L0 | test_installed_package_is_independent | imported module paths and sys.modules | SDK from C0 venv/site-packages, no `app`/`template_runtime`, no base source path |
| C0-02 L0 | test_pack_identity_and_profile_hash_domains | copied manifest/19 files and two profiles | exact bytes; FZ-01 source hashes separate from runtime outputSchemaSha256 |
| C0-03 L1 | test_submit_transport_failure_keeps_original_key | valid fixture-based RunSubmit; transport raises ReadTimeout | one call; transport_outcome_unknown/query_by_client_key; original key; no retry |
| C0-04 L1 | test_lookup_is_explicit_and_does_not_resubmit | within this test perform one failed POST, then explicit get_by_client_key; return frozen 404 envelope | exactly POST then GET with original scope/key; association preserved, no second POST; no dependence on another test's state |
| C0-05 L1 | test_wrong_store_is_rejected | 200 response with correct protocol but another runStoreId | run_store_mismatch/stop; no auto-discovery or second request |
| C0-06 L1 | test_unknown_contract_is_rejected | response contractVersion=task-run/unsupported | contract_unsupported/stop; no fallback to Chat |
| C0-07 L1 | test_incomplete_success_is_not_accepted | right protocol/store but missing required RunSnapshot fields | invalid_response/stop; no success-shaped result |
| C0-08 L1 | test_redirect_is_not_followed | empty-body 307, Location=http://other.example.invalid/redirected | invalid_response/query_by_client_key/status 307, original key and exactly one request; no forwarded auth |
| C0-09 L1 | test_credentials_are_not_in_public_error | fault with synthetic token canary | str(error) contains code only, not token/header; don't print canary |
| C0-10 L0 | test_strict_model_output_and_local_binding | copied raw output, input and strict schemas | raw output excludes input_hash; local validated hash binding reconstructs fixture candidate; not product CAS proof |
| C0-11 L0 | test_no_unqualified_feature_is_claimed | manifest operations/notQualified | exactly current operation set; synthetic_only retained; no fabricated cancel/provider method |
| C0-12 L1 | test_valid_submit_lookup_and_result_are_accepted | schema-valid 201 RunSnapshot, 200 by-key snapshot, 200 RunResult from helper below | all three public methods awaited; exactly POST/GET/GET; returned identity/profile/hash/content equal the fixtures |

Build RunSubmit from `manifest.profiles["project-reporting.summary@review-1"]` input content, not whole fixture.
Use fixed test scope/store/key, a declared synthetic UTC deadline, null token limits for this synthetic lane,
positive byte limits and retained window. These values are fixture values, not production defaults.
Generate error responses in the frozen ErrorEnvelope shape; always provide protocol version.

The concrete payload builder is:

```python
def fixture_submit(pack_root):
    manifest = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))
    selected = manifest["profiles"]["project-reporting.summary@review-1"]
    content = (pack_root / selected["input"]).read_bytes().decode("utf-8")
    canonical = json.dumps(
        json.loads(content), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "clientRunKey": "intake-key",
        "scopeKey": "projects.alpha.stages.one",
        "profile": {"key": "project-reporting.summary", "revision": "review-1"},
        "input": {
            "mediaType": "application/json",
            "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        },
        "logicalInputHash": {
            "algorithm": "dashboard-json-review-1",
            "digest": hashlib.sha256(canonical).hexdigest(),
        },
        "deadlineAt": "2030-01-01T00:01:00.000Z",
        "limits": {
            "maxInputBytes": len(content.encode("utf-8")),
            "maxOutputBytes": 65536,
            "maxInputTokens": None,
            "maxOutputTokens": None,
        },
        "minimumResultRetentionSeconds": 60,
    }
```

Imports for this helper are stdlib json/hashlib; pack_root is the already hash-verified local Path.
The 2030 timestamp is an inert transport fixture, not a deadline for a real submitted task.

Construct C0-12 responses without a server import; validate these dictionaries against the copied
RunSnapshot.json/RunResult.json before using them. The effective hash is synthetic fixture data,
not evidence of a real compiler or provider:

```python
def fixture_responses(pack_root, request):
    manifest = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))
    selected = manifest["profiles"]["project-reporting.summary@review-1"]
    content = (pack_root / selected["output"]).read_bytes().decode("utf-8")
    output_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    profile = dict(request["profile"], definitionSha256=selected["definitionSha256"])
    effective_hash = hashlib.sha256(b"synthetic compiled fixture").hexdigest()
    receipt = {
        "revision": 1, "executionMode": "synthetic", "backendId": "fixture",
        "modelName": None, "qualificationRef": None,
        "inputTokens": {"value": None, "certainty": "unknown"},
        "outputTokens": {"value": None, "certainty": "unknown"},
        "providerRequests": {"value": 0, "certainty": "known"},
        "cost": {"amountDecimal": None, "currency": None, "certainty": "unknown"},
    }
    common = {
        "contractVersion": "task-run/1", "runStoreId": "store-fixture",
        "runId": "run-fixture", "scopeKey": request["scopeKey"], "profile": profile,
        "inputSha256": request["input"]["sha256"],
        "logicalInputHash": request["logicalInputHash"],
        "effectiveInputSha256": effective_hash, "receipt": receipt,
    }
    result = dict(
        common, outputSchemaSha256=selected["outputSchemaSha256"],
        content=content, mediaType="application/json", sha256=output_hash,
    )
    snapshot = dict(
        common, sourceAppId="metrics-dashboard", clientRunKey=request["clientRunKey"],
        state="succeeded", lifecycleVersion=2, acceptedAt="2030-01-01T00:00:00.000Z",
        updatedAt="2030-01-01T00:00:30.000Z", terminalAt="2030-01-01T00:00:30.000Z",
        deadlineAt=request["deadlineAt"], grantRevision="fixture-grant-1",
        limitPolicyRevision="fixture-limits-1", acceptedLimits=request["limits"],
        resultRetentionSeconds=60, observationRetentionSeconds=120,
        observationExpiresAt="2030-01-01T00:02:30.000Z", unresolvedExposure=False,
        dispatch={"attemptCount": 1, "knowledge": "response_received", "remoteStop": "not_requested"},
        result={"availability": "available", "sha256": output_hash,
                "mediaType": "application/json", "expiresAt": "2030-01-01T00:01:30.000Z"},
        error=None,
    )
    return snapshot, result
```

The positive client test is:

```python
async def test_valid_submit_lookup_and_result_are_accepted(self):
    expected_snapshot, expected_result = fixture_responses(self.pack_root, self.submit_payload)
    calls = []

    def respond(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/api/runs":
            return httpx.Response(201, json=expected_snapshot)
        if request.method == "GET" and request.url.path == "/api/runs/by-client-key":
            return httpx.Response(200, json=expected_snapshot)
        if request.method == "GET" and request.url.path == "/api/runs/run-fixture/result":
            return httpx.Response(200, json=expected_result)
        raise AssertionError("Unexpected request")

    async with TaskRunClient(
        base_url="http://candidate.example.invalid", source_app_id="metrics-dashboard",
        credential_ref="fixture-ref", token=self.synthetic_token, run_store_id="store-fixture",
        transport=httpx.MockTransport(respond),
    ) as client:
        snapshot = await client.submit(self.submit_payload)
        replay = await client.get_by_client_key(self.submit_payload["scopeKey"], "intake-key")
        result = await client.get_result(self.submit_payload["scopeKey"], "run-fixture")

    self.assertEqual(snapshot, expected_snapshot)
    self.assertEqual(replay, expected_snapshot)
    self.assertEqual(result, expected_result)
    self.assertEqual(calls, [
        ("POST", "/api/runs"), ("GET", "/api/runs/by-client-key"),
        ("GET", "/api/runs/run-fixture/result"),
    ])
```

Transport behavior example for C0-03; the script implements the remaining rows against the same public SDK:

```python
async def test_submit_transport_failure_keeps_original_key(self):
    calls = []

    def fail(request):
        calls.append(request)
        raise httpx.ReadTimeout("offline fixture", request=request)

    async with TaskRunClient(
        base_url="http://candidate.example.invalid",
        source_app_id="metrics-dashboard",
        credential_ref="fixture-ref",
        token=self.synthetic_token,
        run_store_id="store-fixture",
        transport=httpx.MockTransport(fail),
    ) as client:
        with self.assertRaises(TaskRunClientError) as caught:
            await client.submit(self.submit_payload)

    self.assertEqual(caught.exception.code, "transport_outcome_unknown")
    self.assertEqual(caught.exception.recovery, "query_by_client_key")
    self.assertEqual(caught.exception.client_run_key, "intake-key")
    self.assertEqual(len(calls), 1)
```

`self.synthetic_token` is an in-memory test constant, never loaded from environment.
`self.submit_payload` uses the exact frozen RunSubmit fields described above; setup reads only verified pack files.
Where a negative case only needs to disprove unsafe SDK acceptance, a deliberately incomplete HTTP response is valid;
it is not a server simulator or proof that the whole HTTP lifecycle passed.
Tests must not claim C0-10 proves live permissions, source completeness, owner truth, durable attempt or CAS.

## 5. Review And Exit

Before C0.R: verify the test file actually ran all 12 named methods; include transport call counts
(C0-03 one; C0-04 two; C0-08 one; C0-12 three), no skips and no unawaited-coroutine warnings.
If an SDK mismatch appears, return its request/error and a synthetic repro to the base owner; do not patch
the installed wheel or weaken expected assertions. Unrelated warnings and known W1 gate failures stay recorded.

Acceptance: installed dependency closure works in the C0 environment, all selected checks pass,
no server/provider/network side effect occurs during tests, artifacts and environment are pinned,
and current docs distinguish C0 success from W5/BASE-B/product readiness.
Stop after this packet and update C0.R evidence. W1/W2-W7 still follow their original review/refreeze prerequisites.

C0 self-review and independent plan review cover artifact/version/permission boundaries only;
they do not silently grant live execution, global package changes, production data access or code commit/push.

## 6. C0 Contract Propagation And Consumer Census

| Contract / risk | Producer -> consumers | Disconfirming check |
| --- | --- | --- |
| PM-SDK-ARTIFACT / high | base wheel/manifest -> copied inputs -> installed SDK -> C0.R/W4.REPLAN | wrong hash/path escape/source import stops before request; C0-01/02 |
| PM-SDK-TRANSPORT / high | installed public client -> test script -> integration evidence | typed failure, wrong store/version, no retry/redirect and valid success; C0-03..09/12 |
| PM-SDK-QUALIFICATION / high | manifest/profile -> C0 receipt/current docs -> W4.REPLAN | synthetic-only and hash-domain distinction retained; C0-02/10/11 |

| Consumer category | C0 disposition |
| --- | --- |
| public API | applies: installed SDK methods only; no new application HTTP API |
| internal service/facade | not-applies: no production wrapper or app service |
| UI route/template/component | not-applies: no UI changes |
| export/report | not-applies: no business report |
| audit/log/event | applies: safe test/command receipt, not production audit |
| validation script | applies: named unittest script |
| migration/schema | applies to pack/schema validation; no database migration |
| background job/scheduler | not-applies: no server/worker/task |
| cache/index/search | not-applies: no cache/index use |
| external artifact | applies: verified wheel/pack/copy/environment |
| CLI/admin command | applies: development test runner only |
| docs/operator workflow | applies: tasks receipt and current integration guide |
| test double/fake/fixture | applies: MockTransport and delivered synthetic inputs |

This packet does not change the original business DAG. C0.PLAN.R -> C0.N1 -> C0.R is the new
bounded qualification lane; W4.REPLAN consumes C0.R before starting W5 production integration.
The base's BASE-B work and Dashboard W1 review remain independent. No C0 success reclassifies
unrelated file-size failures or closes the original project review.

## 7. Coding-Readiness Result

`READY_TO_CODE_C0_N1`: scope/API/12-case plan reviewed; copied 19 pack artifacts and wheel verified;
Python3.13.7/SDK0.1.0a1/httpx0.28.1/jsonschema4.26.0 available in the owned environment;
pip check passed and all 13 dependency install records contain artifact hashes.
The bounded probe used actual installed SDK with MockTransport: submit/by-key/result succeeded,
one timeout produced the typed unknown error with original key, zero real network connections and no app/server imports.
This is preparation evidence, not execution of the whole planned test suite or a formal C0.R review.

The planned script now exists at `scripts/validation/test_task_run_sdk_intake.py`; all 12 cases ran successfully.
It checks complete public responses and refusal paths, preserves each receipt and fails closed on wrong interpreter/path.
C0.R reviewed the actual source/receipt and passed; its evidence feeds W4.REPLAN, not product acceptance.
The SDK was already implemented by the base owner,
so no artificial SDK defect was introduced to manufacture a RED. Future behavior changes still need
a test that can distinguish the original gap.
