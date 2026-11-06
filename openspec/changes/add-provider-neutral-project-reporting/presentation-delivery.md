# Concise Standup Presentation Delivery

Date: 2026-11-06. Source base: `9dff849018c259ff861c421f895aa64d85fb2df9`.
Scope: `W6.PRESENT.*`; task status remains in [tasks.md](tasks.md).
Contract: [standup-presentation.md](standup-presentation.md).
User approved concise business output plus a separate complete audit attachment.

## Delivered Behavior

New concise daily and weekly starter actions appear first in the template library.
Users can add fixed content and editable slots; template Save retains the explicit
`standup/1` profile. Its pinned renderer is `template-document/2`.
Existing actions/templates retain `template-document/1`; no old template, report,
schema, source hash, accepted summary or editorial baseline is rewritten.

The body is a compact `Ticket / Updates / AR` table. It includes cumulative
effective notes with provider-status date prefixes, paint/links, persistent context
and unresolved actions. Deleted text is not recovered from raw AI prose.
Missing source URL remains plain ID; unsafe links fail the existing validator.
Coverage still states partial/pending, missing reports and acknowledged draft gaps.
Legacy original source-action state and raw evidence are not appended as
competing business content.

Publication exports now offer `Audit bundle (ZIP)`, independently of Markdown/Excel.
One owner-checked public read validates all original publication bytes from the same
commit. The attachment includes the exact six original files, an escaped readable
`audit.html` and `audit-manifest.json` with file hashes, commit and generator version.
No renderer, provider, model, Save or Finalize is called by audit download.
The attachment has fixed ZIP metadata, a `report-audit/1` revision and a 32 MiB
aggregate/final-output bound; missing/tampered/oversized content fails explicitly.

## Validation

Selected environment: SDK0.2.0a1 reporting venv and the existing no-dotenv,
external-network-denying runner. No full-week re-execution or Base task was needed.
Evidence root: `.tmp/dashboard-presentation-20261106/`.

| Evidence | Observed result |
| --- | --- |
| `standup-red.xml` | New-profile behavior failed before implementation |
| `profile-guard-red.xml` | Unknown/misrouted pinned renderer was incorrectly accepted by generic fallback |
| `compatibility.xml` | 39 passed: profile/body/audit/old template rendering, migration, retained packet and corrupt snapshot checks |
| `consumer-guards.xml` | 1 passed: rehashed unknown renderer rejected through actual Get/render/Save/Finalize with no publication |
| `publication-02.xml` | 1 passed, 37.41s: real-Git legacy day then explicit series-policy switch to concise day, human history retained, old bytes/head unchanged, export works with renderer/source/finalize poisoned |
| `ui-green.xml` | 5 passed: actual forms, export/auth/method/query boundaries, draft audit refusal and original exports |
| `browser-02.xml` | 1 passed, 22.39s: actual template creation/edit/Save, profile preserved, mounted report paint/Save/reopen/Finalize, HTML/Markdown/Excel/audit downloads, desktop and 390px output |
| `coverage-red.xml`, `coverage-green.xml` | Missing-report/gap display counterexample, then 19 focused standup/audit tests passed |
| Node `report_exports_test.mjs` | 4 passed, including publication-only audit and original dirty-state guards |
| Isolated Django check | No issues using synthetic retained-run settings |
| `final-scoped.xml` | 47 passed, 20.46s: final pure/compatibility/corruption/HTTP/localized-label selection |

The first browser attempt called sync ORM inside Playwright's active async context;
it was a test-assembly failure. Setup now leaves browser context before ORM use.
The first two-day fixture selected a new template without explicitly revising the
series policy; the service correctly refused it. The test now uses the existing
policy-CAS API. Those attempts remain retained and are not product-failure proof.
No checks were skipped or converted into passing claims.

Final bounded independent review found no blocking issue in the declared
presentation/reporting contracts and code. Selected size gate checked 26 files;
88 local documentation links and OpenSpec strict passed. The unrelated Scope
tests exceeded their own size limits in an all-dirty check and were left untouched;
the scoped presentation check passed without relaxing any limit.

The final coverage change only adds explicit missing-day/gap warnings. Earlier
real-Git/browser samples had no missing days or acknowledged gaps, so their output
and affected contracts remain unchanged. The browser helper's later indentation
cleanup changes no statements or assertions.

## Retained Week Comparison

The new public read API re-read the seven prior week publications and all 42
original file hashes remained identical. Evidence:
`retained-preview/readback.json`. Read-only previews for 2026-10-30 and 2026-11-02
were generated from those exact source/editorial contexts with the new compiler.
They are clearly separate `*-preview.html` files, not newly finalized editions.

`retained-preview/2026-10-30-preview.png` and `2026-11-02-preview.png` were inspected
in Ego. The three independent tickets, original daily prefixes, bold/highlight,
red/blue/green text, open ARs and cross-week seed are visible without the long audit
tables. Original audit ZIPs retain the old publications, not the new previews.
The temporary read-only Ego TaskSpace was finished.

The mounted new-publication sample is separately retained in
`browser-67926814-0584-4f79-9348-64faa35d34c9/`; its audit ZIP includes the exact
newly published concise `report.html`. This is the actual save/finalization proof.

## Remaining Work

The earlier 53-77s preparation/view waits still need a bounded critical-path
profile. This presentation change does not claim to fix them. Full provider/import
capabilities, deployment, real Jira/HSD/model qualification, Outlook/native-client
paste and optional scheduling retain their independent task/authorization gates.
The original week and existing SDK/AI/continuity qualifications are reused only
within their unchanged source/contract boundaries.

Do not treat this scoped presentation delivery as complete product release.
Code publication must use the explicit allowlist and leave unrelated Scope/config/
global-style edits intact.
