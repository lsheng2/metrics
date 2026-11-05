# SDK 0.2 Integration Status And Use

The selected Dashboard consumer combination is Python SDK `0.2.0a1`,
HTTP `task-run/1`, and the unchanged `0.1.0a2` summary contract pack.
The Base owner has delivered local artifacts; registry publication and real execution are not implied.

Current execution status belongs to
[the reporting tasks](../../changes/add-provider-neutral-project-reporting/tasks.md).
The pre-integration window reached `IP-SDK020-READY`. On 2026-11-05 the user
released that stop and authorized joined integration, including necessary small Base fixes.
Real provider/model execution and formal deployment remain excluded.
The isolated consumer selection passed 25 tests and 19 unittest subtests on 2026-11-05.
It verified the installed wheel's six package files, the original pack's 21 files, and
zero application network attempts. Windows asyncio made seven separately counted standard-library
socketpair IPC connections; this is not Base HTTP or an application-network qualification.

Use the [exact SDK/pack contract](../../changes/add-provider-neutral-project-reporting/sdk-020-integration.md)
for package hashes, public methods, failure rules, the isolated target installation and the readiness receipt.
Use [execution after IP](../../changes/add-provider-neutral-project-reporting/sdk-020-post-integration.md)
for the concrete joined consumer, DAILY, ASSIST, week simulation and export sequence.

The main `.venv` and existing 8017 service are not upgraded. A separate installed SDK
target and a short-lived isolated test process established pre-integration compatibility.
Joined execution uses `.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe`:
SDK0.2.0a1 is installed in that venv; an explicit `site.addsitedir` entry shares
the existing host dependencies and processes pywin32's Windows setup. A plain
directory-only `.pth` entry is insufficient for those native dependencies.
Module and distribution resolution must select the new local SDK, not the shared old SDK.
The fixture's `sdk-selection.json` fixes the SDK/wheel/pack identity; the launcher
checks package bytes and metadata and refuses cross-version relocation of retained runs.
All Dashboard server/worker and validation commands use the selected interpreter.
Application `AiTaskContract` still checks its trusted pack/profile/schema and business result;
removing those guards is not a supported migration method.

SDK wait and cancellation remain distinct. Chat stream abort can affect its turn; it is not the
same contract as read-only Run waiting. TS SDK `0.2.0` provides optional widget/reporting entries
and `{response, observationErrors}` for a completed stream, but this Python migration does not
adopt TS or claim that the server's report endpoints were split.

Editor/template/history implementation currently includes local uncommitted authoring WIP.
Publishing these specifications is not publication of that code or proof of the complete authoring journey.
The existing accepted feature requirements remain; only the dependency integration is being staged.
Generic loader, durable events and standalone TestKit remain deferred and are not prerequisites.

The current test receipt is under
`.tmp/sdk-020-preintegration-20261105/runs/dafa6bd9-de70-4069-83e3-059865f07d42/receipt.json`.
JUnit counts 44 entries including the 19 subtests; it is not 44 independent top-level cases.
The exact source hashes and retained RED receipts are in the same owned work root.
That receipt alone does not prove joined HTTP, DAILY closure, ASSIST, a full-week run or live qualification.
The subsequent joined candidate passed J020-01..06 over actual local Base HTTP and
Dashboard services on 2026-11-05. The first request was submitted through Dashboard
HTTP and processed by its worker into an accepted summary and renderable draft.
Lost-response recovery retained one POST/original identity; invalid store/hash/evidence
and late canceled results were refused. An unchanged second capture used no new inference.
Normal stop/reopen preserved the original store/Run/draft/accepted bytes; both stops were normal.
The six synthetic executor dispatches are separate scenarios, not real model calls.
See the [delivery receipt](../../changes/add-provider-neutral-project-reporting/sdk-020-join-delivery.json)
for exact source, artifact, test and native evidence references.

This qualifies SDK consumption, not the entire authoring workflow. DAILY's actual
next-day inherited-reference edit, the separately qualified ASSIST profile/Apply/Save,
the full-week simulation and declared export/Outlook gates remain in the reporting plan.
The temporary joined services are stopped; the existing 8017 service is unchanged.
The main SDK source fingerprints and separately checked package version are unchanged.
This is not a complete inventory audit of every file in the main virtual environment.
