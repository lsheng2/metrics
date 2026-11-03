# Full-Stack Qualification Packet

Scope: W7.E2E.QUALIFY after HOST implementation/review.
Parent: [manual-host-packet](manual-host-packet.md) QUALIFY section and
[manual-full-stack](manual-full-stack.md) FS08-10. Only tasks.md stores status.
This is an executable synthetic qualification and local demo, not live rollout.

2026-11-03 user split: qualify the non-editor workflow first. Do not exercise or
extend the transitional textarea editor; WYSIWYG and copy/Outlook integration
wait for the separate editor Agent's [handoff](rich-text-editor-handoff.md).
Capture, accepted summary, saved HTML/download, explicit Git publication,
unchanged reuse and normal service stop remain this lane's exit conditions.

## Commands And Files

New CLI: `scripts/validation/project_full_stack.py`.

```text
prepare --data-root <absolute-root> [--base-python <python>]
        [--work-root <prepared-w5-root>]
start --run-dir <owned-run-dir> [--port <available-port>]
      [--lifetime-seconds 1800]
status --run-dir <owned-run-dir>
restart-app --run-dir <owned-run-dir>
stop --run-dir <owned-run-dir>
relocate-work-root --run-dir <owned-run-dir> --work-root <approved-clean-root>
```

Use argparse subcommands. Default data root is
`D:/AIGC/scrum_dashboard_validation/full-stack`; override must be absolute,
outside code repositories, regular/non-reparse and explicitly owner-marked.
Work-root default is this checkout's `.tmp/task-run-w5`; Base source and pack
must be its already verified `base-source` and `artifacts/contract-pack`.
The sole additional qualification alias is
`.tmp/task-run-w5-clean-merged-20261103`, reconstructed once from the same
pinned full archive and overlay with844exact files. Original polluted/partial
copies are retained. No arbitrary path or extra source inventory is allowed.
A recorded location-only relocation preserves the previous manifest and all
business IDs, original store identity, vector, SDK and contract/source hashes;
it does not prepare another run or change earlier evidence.
The default Base interpreter may resolve the known sibling
`Report_creater_agent/.venv/Scripts/python.exe`, but the explicit option is
supported and its existence/origin is recorded.

Supporting files:
`project_full_stack_settings.py` (isolated Django settings),
`project_full_stack_fixture.py` (actual app services and synthetic source),
`project_full_stack_base.py` (fixed Base factory plus exact dynamic vector),
`project_full_stack_support.py` (small ownership/manifest/SLE helpers if needed).
Split only along these responsibilities to meet existing size gates.
Do not copy another platform or modify the fixed Base source.
Lifecycle/provenance/exit helpers may be split into
`project_full_stack_lifecycle.py` and `project_full_stack_identity.py` when
needed; they remain fixture helpers over SLE, not another process manager.

Tests:
`project_management/tests/test_project_full_stack_fixture.py` for exact-vector
and fixture isolation negatives; `test_project_full_stack_lifecycle.py` for
the parent's semantic SLE stop tests. Ordinary tests use explicit synthetic
settings and controlled external SPIs, not real servers.

## Preparation

`prepare` creates a fresh UUID child, never reuses a prior W2/W5 run in place.
Its owner marker binds schema version, owner `dashboard-manual-fullstack`,
canonical repository/data-root/run-directory and UUID. Existing nonempty
unowned roots are refused. `start/status/restart-app/stop` require that marker
and must not create a replacement owner.

Owned layout:

```text
<run-dir>/
  owner.json
  runtime-manifest.json
  catalog.sqlite3
  archive/
  fixture-vector.json
  base/
  environment/
  lifecycle/
  logs/
  evidence/
```

Preparation records pinned Base/pack/SDK hashes using existing
`project_summary_support.verify_base_source/verify_installed_sdk` and profile
loader helpers. No source tree byte is modified or pycache written into it.
It migrates only catalog.sqlite3 under this marker, creates a real scope/provider
binding and project/stage through the existing public APIs, and adds a second
owner/project for isolation checks. It does not capture, analyze, create an
accepted record/draft, initialize stage Git, or start a server.

Use the bootstrap/registry pattern identified in manual-host-packet, not W2's
settings/guard CLI. The profile endpoint is exactly
`https://tracker.example.test/jira`; the rule may be a simple approved synthetic
JQL. Keep actual DashboardScopeCatalog/ORM ownership and immutable stage hash.
The trusted validation runtime factory binds only the prepared main project/
stage to the registered synthetic provider and Base grant.

runtime-manifest.json contains identity, safe source/runtime paths, Base
interpreter/pack references, project/stage/scope IDs, fixture-vector hash,
synthetic browser usernames/passwords, cookie names and execution mode.
It contains no real credential. Generated Base service-account token remains
only in the owned Base connection file, never in printed CLI output, archive,
report or code Git.

## Exact Source And Model Fixture

Reuse the actual `provider_sync.tests.capture_gateway_fixtures.JiraFixture`
with actual Project API installed in both `provider.project_api` and
`provider.service.project_api`, as the earlier W5 join did.
It uses ProviderAccessService/JiraCaptureAdapter/BoundCaptureReader and records
requests while its HTTP adapter returns only exact registered synthetic data.
The descriptor profile ID can vary; its endpoint must keep the `/jira` path
that this fixture's responder expects.

Wrap its HTTP adapter with a qualification-specific strict request guard.
Before recording/delegating, require GET, the exact registered HTTPS host/base
path, no credentials/redirect, and no duplicate/extra query keys. Frozen JQL
must match exactly. Allowed requests for the page_size=2 fixture are:

| Request | Exact query |
| --- | --- |
| `/jira/rest/api/2/myself` | empty |
| `/jira/rest/api/2/search` validation | jql=frozen rule, validateQuery=true, startAt=0, maxResults=0, fields=id |
| `/jira/rest/api/2/search` membership/recheck | jql=frozen rule, validateQuery=true, startAt=0, maxResults=2, fields=id,key,summary,updated,status,assignee,resolution,issuelinks |
| `/jira/rest/api/2/issue/101` | fields=*all, expand=changelog,names,schema |
| `/jira/rest/api/2/issue/101/comment` | startAt=0 or2, maxResults=2 |

The exact one-ticket rule has no saved filter dependencies. Refuse any other
issue/comment/filter identity, field set, JQL or pagination without a fabricated
response. Keep a method/path/query/response-digest transcript per capture,
excluding headers/tokens. Negative fixture tests mutate each boundary so the
permissive generic JiraFixture responder cannot hide an integration bug.

One ticket: stable ID101, keyALPHA-101, statusFixed, summary
Intermittent validation failure, assignee dev-a/Alice, reporter qa-b/Bob.
Use the existing issue()/comment() builders for their complete raw structure.
Comments201/202/203 contain Failure observed; retained log text including
Unicode and a long body; and the exact explicit request
`Bob (qa-b), please rerun validation on build r8.`.
History/attachments/links are empty with truthful complete/not-requested
coverage, not omitted source requirements.

Base must use the untouched fixed factory `create_task_run_candidate`,
installed a2 profile and per-app signed synthetic credential plus exact scope
grant. No live backend or actual model is configured. The executor checks
the input schema and complete known input, not only selected identifiers.

The application input's only run-varying source fields are:

```text
target_capture_id
delta.to_capture_id
evidence[*].capture_id
```

Every one must be the same canonical UUID. Normalize only these known fields
to a fixed placeholder for comparison with the prepared exact input template.
All binding, baseline, profile revision, required parts, coverage, delta IDs,
evidence IDs/pointers/values/source hashes must equal the registered template.
Reject missing/extra evidence, changed B text, another project/stage/principal,
or unregistered ticket data. Do not strip arbitrary fields or accept arbitrary
real text. Per-evidence source hashes are calculated from the registered
synthetic values independently of submitted content.

The output is the known English W5 expected summary/actions adapted only to the
validated actual capture ID and binding. The model output does not generate
input_hash. Append actual executor observations with input/effective hashes and
execution_mode=synthetic so the test can prove one dispatch.

This input-template generation uses known fixture values and public pure
serialization/schema helpers; it must not precapture a real run or alter the
application's prepared input to fit the fixture.

## Startup And Ownership

Every actual process start receives a fresh canonical `launch_id` and an
immutable descriptor under `lifecycle/launches/<launch_id>/launch.json`.
It binds run UUID, service name, launch ID, command/source identity and the
exact owned `stop.handle` and `exit.json` paths in that directory.
SLE remains PID/provenance/termination authority. These descriptors bind
signals and evidence; they do not independently adopt or kill a process.
Never reuse an existing stop handle for a replacement process.

Pass launch ID and exit-receipt path to the app/Base entry wrappers. In finally
they write an exclusive per-launch receipt containing schema_version=1,
service, launch_id, actual pid, exit_code and UTC finished_at.
Record nonzero for SystemExit failure or any unhandled failure; cleanup must
not turn a failing command into zero. The app wrapper still calls the actual
project_serve command. A receipt is evidence only after matching the owned
launch and actual SLE wrapper/listener relationship.

`start` verifies all owned inputs and uses existing ServiceLifecycleEngine for
both dedicated processes. Allocate/check unused explicit loopback ports; never
adopt/stop another listener by port. Bound source/SDK verification and readiness,
and persist SLE process provenance plus stop handles before returning success.
Use hidden Windows processes and sanitized per-child environments. The app
uses project_serve with no autoreloader and the trusted fixture settings factory.

SLE starts from `os.environ.copy()`, so passing a small spec.env alone is not
sanitization. Before every SLE start call, the dedicated launcher enters an
allowlisted base environment using the existing child_environment contract,
then restores only its own prior process environment afterwards. Allowed base
keys: PATH, SYSTEMROOT, WINDIR, COMSPEC, PATHEXT, HOME, USERPROFILE, TEMP, TMP,
NO_PROXY. Add only the explicit fixture settings/run-directory and owned
pycache controls required by that child. Never carry an inherited provider/
model/Python-path secret or modify the user's persistent environment.
Record sorted allowed keys and a canonical environment digest, not secret
values. A launcher test injects unrelated provider/model credential canaries
and verifies they do not reach the SLE platform start_process boundary.

The isolated settings ignore dotenv, point DB/cache/archive/state into this
run directory, use unique session/CSRF/language cookie names, and register only
fixture profiles. Block real outbound connect/connect_ex/DNS; permit only the
registered Base loopback address for the app. Synthetic provider traffic stays
in its explicit transport. Base outbound connections remain forbidden.
Set `METRICS_PROJECT_CAPTURE_PAGE_SIZE=2` in these dedicated settings so the
actual runtime's persisted CaptureLimits match the strict provider vector.
Test this through runtime assembly, not only through JiraFixture.context().
Never amend an already persisted operation's request limits to match a fixture.

The Base publishes a bounded owned connection file containing exact store/app/
scope/credential identity, endpoint, process identity and stop handle. Validate
it against the SLE provenance and fixture registration before starting the app.
Do not turn an arbitrary connection file into trusted configuration.

After SLE port readiness, wait at most20seconds for the current launch's atomic
connection file, checking owned process liveness. An old launch's file is not
readiness. Validate execution/qualification, contractVersion, packVersion,
sourceAppId, credentialRef/token presence, scope/store/grant/limit revisions,
exact127.0.0.1 URL/selected port and current launch stop/exit paths.
Use W5 checked_connection semantics with SLE's proven listener/worker relation
when Windows venv wrapper PID differs; do not relax to any PID on that port.
When SLE can only provide registered_process with listener_pid=null, resolve
the live relation using the existing W5 `worker_matches_process`/
`worker_record_matches` checks: current worker parent equals the registered
live wrapper, interpreter is Python and the complete command arguments match
the exact per-launch command. Persist that validated worker binding as
per-launch process-proof.json, bound to launch ID and command fingerprint.
Re-use the proof for app/Base exit receipt PID matching; an exit receipt names
the actual Python worker, not necessarily the venv wrapper. Do not infer a
missing historical relation after the process has exited. Include the explicit
registered-process-only Windows case in the focused tests before native retry.
For an already recorded store, require its original ID; no replacement store
on recovery. Invalid current-launch identity is a hard failure, not a retry
with a different scope or endpoint.
The Base entry accepts an existing `base/store` only after validating the
registered run/launch and exact canonical store path, with no reparse alias.
Reopen it through the existing Base factory, preserving store identity and
contents. Do not use unconditional exist_ok=False for a known retained store,
delete it, or change run IDs to conceal the failure. An unrelated/unowned
existing store remains a refusal. Include a no-server retained-store identity
check before retrying native startup.

Track services actually started by each start invocation. If connection
validation/app startup/readiness fails, preserve the failure and stop those
newly started owned services in reverse order. Do not stop a pre-existing
matching Base merely because a later app start failed. Preserve cleanup
outcomes and fail; do not leave an unreported partial start running.

Before start/status/restart validate the manifest's schema/mode, actual pinned
source/pack/SDK identity, vector digest, catalog UUIDs/scope and the recorded
Django route relation, not only directory strings. Interpreters must match the
explicitly approved path and executable, not merely any file in Scripts/.
Stop must still be able to clean up an already proven owned launch after a
source-validation failure, without trusting arbitrary replacement commands.

Each service has the recorded bounded interactive lifetime (default1800s).
Every application operation still has its original at-most600-second deadline.
Do not renew operations, grants or tokens implicitly when reporting status.
An already running matching start replays its safe connection information;
it does not create a second store or project.

`restart-app` gracefully stops and restarts only the app on the same DB/archive,
while the original owned Base/store/grant stays active. Refuse if that dependency
is no longer usable; do not silently replace it with another store.
With the shared SLE state, use app-scoped
`stop_service(app_name, graceful_timeout_seconds=620)` and then
`start_service(app_spec, original_app_port)`. Do not use restart_services,
prepare_startup or stop_all for restart-app: they can stop the registered Base.
Before/after, record that Base process identity, runStoreId, grant revision and
executor dispatch count are unchanged. A controlled lifecycle test must reject
an implementation that invokes a Base stop or creates another store.
SLE reopens a same-name/port stdout log with truncation on start. Preserve the
closed app stdout/stderr and its structured stop observation in a unique
evidence/restart directory before starting the replacement app. Never overwrite
the first process's qualification evidence with the second process's log.
`stop` uses the original SLE authority and stop commands with the parent's
620-second safe maximum grace. Normal qualification requires actual worker
exit plus process exit; forced/terminated/missing stop evidence is abnormal.
Before stopping, record current launch identity and stdout byte offset.
Accept only the newly appended matching structured worker stop event plus the
current launch's zero exit receipt and actual wrapper/listener exit. Require
the SLE stop-command path, not terminated/killed fallback or an old event.
Apply this classification before restart-app; on abnormal/missing evidence,
preserve everything and refuse replacement. Add controlled tests for delayed
connection publication, valid wrapper/listener split, wrong identity fields,
partial-start cleanup, stale handles/receipts, nonzero exit and abnormal restart.
Status is read-only and never starts services or advances a run.

## Evidence And Browser Flow

Commands print only a safe JSON result: run directory, execution mode, URL,
registered process/service state and next safe action. Store full diagnostics
under evidence/ without real secrets. Error output is a fixed safe category
plus owned log location, not a raw credential-bearing traceback.

One stable-candidate FS08/09 run follows the seven parent browser steps.
Capture actual source/SDK/Base/app hashes, real process identities, operation/
capture/attempt/draft/publication IDs, original HTML/plain artifact digests,
Base dispatch counts before/after unchanged repeat and normal restart receipts.
Verify old W2/W5 selected data fingerprints remain untouched as specified.
A source fix invalidates its dependent evidence, not all earlier unaffected
source/module tests. Never overwrite a failed run's evidence.

Use Ego (approved Chrome equivalent), the current owned task space and1440x900.
Validate a real user-gesture copy promise, then paste only the resulting known
synthetic clipboard content into a dedicated editable test sink and inspect its
tables/text. If copy failed, do not paste the user's previous clipboard.
Screenshot failure is a separate environment issue, not proof of visual
correctness; use a supported alternative capture after identifying the cause.
Never repeat identical failed screenshot attempts.

FS10 remains actual blank Outlook HTML-mode draft paste without recipients or
send. Record unsupported native UI/permission limits precisely. Do not read
other messages or retain mailbox/session identifiers.

After qualification, write an immutable evidence receipt and update the current
guide with the tested commands/URL/lifetime and explicit synthetic/live limits.
An interactive demo may remain running only with its recorded ownership and
expiry; final output must state its lifetime and a reproducible restart command.
