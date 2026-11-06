# AI Authoring Delivery

Date: 2026-11-06. Scope: `W6.AUTHOR.ASSIST` and its replan.
State remains in [tasks.md](tasks.md); exact implementation/API contracts are in
[assist-execution.md](assist-execution.md). Source base is Dashboard main `4cb995b`.
This receipt does not close exports, the original full week, live qualification,
or the complete provider-neutral application.

## Delivered Behavior

The existing rich-text editor can explicitly request, preview, apply, reject and
observe AI candidates. Targets remain server-derived and bound to saved content.
An independently pinned authoring profile uses the installed SDK and existing Base
Task API; the summary profile/pack is unchanged. Apply is local/undoable; Save
verifies the server candidate under revision/hash CAS. Finalize remains explicit.

Text, paint, selection, draft revision and editor lifecycle guards prevent stale
replacement. Same-text acceptance is still dirty. Accepted receipts are retired
after Save, with current note hashes returned for a subsequent save containing newer
local edits. Reopening a stored candidate uses GET, not another generation.
Manual editing remains available when the authoring profile or service is unavailable.

The two backend review findings were corrected: eager profile loading no longer
breaks manual editing, and definite failures are distinguished from unresolved
execution. Cancellation remains observable by the original key; a pre-I/O exchange
claim bounds observations without refreshing key/deadline/budget. Malformed stored
state/pointer values produce controlled errors. Summary uses the unchanged settlement
rules through a shared pure helper.

## Validation

Evidence root: `.tmp/dashboard-assist-20261106/`.
Each failed attempt is preserved separately; later passes do not explain it away.

| Evidence | Result and scope |
| --- | --- |
| `assist-consumers-01.xml` | 52 passed, 8 subtests; profile/target, service/recovery, HTTP/CSRF/owner, eight mounted AI stories, and existing editor lifecycle consumers |
| `authoring-http-final-01.xml` | 4 passed; final SDK/Base/data-Git/next-day chain, profile selection, two malformed stored state types |
| `ui_web/tests/report_editor_test.mjs` | 10 Node tests passed; fragment codec, paint, selection/bookmark, undo delegation, continuity controller |
| `target-families-01.xml` | 1 passed; one four-target service transaction covers narrative, AI-optional slot, persistent note and AR body without changing source status/AR owner/tracking state |
| `save-races-red-01/02.xml` and `save-races-green-01.xml` | Same-text acceptance and delayed Save were falsified, corrected, then verified |
| `backend-review-01.md` -> `backend-review-02.md` | Two P1 findings closed; changed backend boundaries READY |
| `ui-review-01.md` | Bounded editor/view/API review READY; final execution evidence bound by coordinator |
| `final-review.md` | Final storage guards, API/current-doc alignment, XML and normal native cleanup READY |

Final mobile inspection also exposed a pre-existing unbroken revision hash in the
report header. The report-only stylesheet wraps this metadata without changing
shared CSS or authored text; `header-fit-red.xml` records the original clipping.
`header-fit-green.xml` passes the mounted Save/provenance story and desktop/mobile
header, popup, contrast and action-hit checks after the report-only CSS fix.

The scoped file-size gate checked 34 files; whitespace and strict OpenSpec validation
passed. Isolated Django `check` reported no issues and migration dry-run no changes.
The 13 excluded file hashes were verified unchanged before staging.
The staged candidate contained 51 allowlisted paths. Its clean archive, tree
`8e0b68e660923d265feafe5652e68fd5b338af84`, passed 10 profile/target tests in
`candidate-tests.xml`; both authoring JSON files matched their exact staged bytes.
Only this receipt was subsequently updated. This is a source-packaging check, not
a new-install or production-runtime qualification.

The final native run is
`http-d668d03b-f46e-4cd5-816f-1f1a037eb852/`:

- Installed SDK: `0.2.0a1`, original a2 `task-run/1` pack.
- Profile: `project-reporting.authoring@1`.
- Profile definition SHA-256:
  `31ef07605350544cf5c67ad7624921c0cfa2dacd3fdefb096d7b57d585cca2b2`.
- Output schema SHA-256:
  `829067bdb9e1045e97f7cb7b38c6ef3596abf2f0b6b5bf87d5e622d7419c7e54`.
- Fixed Base source: commit `2332d549ab69a7e927865acd0e3db2a19295c609`,
  844 files verified against its delivered fingerprint.
- One synthetic Base dispatch; no real provider/model invocation.
- Publication: `7b9a4116-f8ff-5959-81c7-087d2d3122af`.
- Data-Git commit: `a3943bb3d8d0e3a4b3a84a960570cd6feae83c8b`.
- Original six publication file hashes and AI-result reference are in `result.json`.
- Cleanup: exit 0, launcher/worker stopped normally, `forced=false`.

The native chain accepted an AI daily note, saved a later human text/color edit,
preserved AI provenance, finalized to real data Git, and inherited the exact effective
fragment/provenance on the next day. It is complementary to the already qualified
changed-source DELTA chain, not a substitute for it.

## Release Boundary

One explicit source allowlist excludes the 13 pre-existing Scope UI/spec/main.css/
model-default paths recorded by the previous source closure. Evidence and temporary
data are local; no data-Git remote or production service is activated by the source
push. The old 8017 service and legacy venv remain untouched.

Human docs now describe the actual AI controls, disabled default factory, APIs,
provenance and failure behavior. The approved root contract uses bounded independent
packet reviews; no extra exact-pass task ledger or model-config rewrite was introduced.

## Next Gate

ASSIST.REPLAN retains the original dependency order: representative export/clipboard
sample, then 2026-10-26..30 plus 2026-11-02 with three independent tickets. The full
week must use the actual daily preparation/editor/save/finalization path, original
source statuses, varied human paint/notes, restart and preserved evidence.
Markdown/Excel capability still needs its own declared projection and acceptance;
this packet's successful HTML and provenance checks do not qualify those exports.
Real Jira/HSD-ES, real model, Outlook, deployment and scheduling remain separately
authorized qualification boundaries.
