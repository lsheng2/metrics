# HTML Report Validation

Status: planned acceptance cases; none of these new product tests has run.
Design: [HTML report authoring](html-report-authoring.md).
Task status: [tasks](tasks.md), W6.HTML.* and the existing W4/W6/W7 leaves.

2026-11-03 user-directed split: retain backend draft/render/finalize evidence,
but stop expanding tests for the transitional textarea editor. WYSIWYG
component tests are owned by the separate editor Agent. HT28/29/30 and the
editing/copy portion of FS08 are deferred to its delivery and the joined
[editor integration gate](rich-text-editor-handoff.md). The workflow-only
HTML/download/Git/unchanged-repeat run is a separate scoped result.
No second implementation ledger or permanent validation service.

## 1. Selection And Escalation

- L0: OpenSpec, document links, fixed template/options schema and fixture shape.
- L1: pure projection/render/edit rules, exact output fields, hostile literals.
- L2: real temporary draft storage, existing archive and Django request boundaries.
- L3: real Git/ref recovery, installed resources, desktop Chrome/Ego clipboard and
  receiving-email-client paste. Use synthetic data and no sent message.
- L4: real provider/model qualifications stay with their own existing leaves;
  template changes alone do not trigger another paid or live run.

Start with the direct negative case for the changed boundary. Run affected
consumers next, then one representative real-storage/browser flow on the stable
candidate. Do not rerun Base's full suite or all old T12 tests for report-only work.
Record source/template/test hashes, command, selected cases, duration and actual
environment. Browser clipboard success and receiving-client paste are separate.

## 2. Synthetic Fixture

Use two distinct arbitrary projects, Alpha and Beta, with stable source identities,
different owners and exact source hashes. No real ticket text, tokens or recipients.
For daily semantic tests create three retained captures/publications:

- D1: DEMO-101 Open, Alice, action "Provide logs"; DEMO-102 already exists.
- D2: DEMO-101 Fixed, verification pending; DEMO-102 newly enters the scope but
  its source creation time is before D1.
- D3: DEMO-101 Reopened; DEMO-102 has no source change and an unfinished action.
- Retain a separate intra-day Closed -> Reopened sequence and a missing-capture
  day. Include a pending summary and permission-loss branch.

Renderer fixtures are verified input examples, not a substitute for the actual
source adapter. The authoring integration starts from a real W5.JOIN accepted
record in isolated stage Git, preserving its original result content/hash.
No fixture may bypass the source/owner/evidence validator or pretend new SDK
calls occurred. Existing successful W5.JOIN artifacts are read-only.

## 3. Cases

| ID / layer | Test file and case | Input/action -> required observation |
| --- | --- | --- |
| HT01 L1 | `project_management/tests/test_report_templates.py::test_template_switch_preserves_source` | Same snapshot + daily/weekly -> same source/summary IDs and coverage; zero network/model/Git dependency |
| HT02 L1 | same, `test_unknown_template_or_option_is_rejected` | Unknown version/path/raw CSS/prompt option -> typed refusal, no fallback or write |
| HT03 L1 | `test_report_timeline.py::test_status_history_and_open_actions_are_retained` | D1/D2/D3 -> Fixed then Reopened visible; pending retest and unchanged open action remain |
| HT04 L1 | same, `test_scope_entry_is_not_issue_creation` | Existing DEMO-102 joins at D2 -> entered-scope, not new-created |
| HT05 L1 | same, `test_missing_or_partial_day_is_not_unchanged` | No capture, incomplete membership, stale summary -> explicit unknown/pending; no zero-change inference |
| HT06 L1 | same, `test_report_and_analysis_baselines_are_independent` | Unaccepted D2 update + published D2 partial -> D3 analysis still retains unaccepted delta; display includes pending |
| HT07 L1 | same, `test_local_dates_and_multiple_editions_preserve_cutoff` | Two same-day editions and UTC/local date boundary -> explicit IDs, original cutoff/timezone; no double event counts |
| HT08 L1 | same, `test_intermediate_events_and_policy_mismatch_are_not_hidden` | Closed -> Reopened, A -> B -> A, changed mapping -> retain events or refuse comparison, not no-change |
| HT09 L1 | `test_report_html.py::test_literal_content_cannot_create_active_markup` | Script/event/style/image/iframe/form, formula prefixes, Unicode, quotes, ampersands -> literal safe text, no active nodes or external request |
| HT10 L1 | same, `test_email_fragment_is_self_contained` | Every section/row/link/note -> complete table wrappers + inline style, no app classes required, scripts/editor fields/localhost assets absent |
| HT11 L1 | same, `test_output_matches_independent_expected_fields` | Independently parse final HTML -> exact counts, actions, provenance, dates, evidence and long-text segments; no missing/extra/shifted issue text |
| HT12 L1 | same, `test_limits_refuse_without_truncation` | Text/snapshot/HTML/clipboard at bound and bound+1 -> allowed or specific failure; clipboard-only excess still permits full within-limit HTML |
| HT13 L2 | `test_report_source_reader.py::test_pinned_public_read_returns_original_acceptance` | Real W5.JOIN source -> original source/candidate/result hashes, correct owner and cutoff; zero prepare/advance calls |
| HT14 L2 | same, `test_foreign_or_unverified_source_is_refused` | Wrong project/stage/principal, corrupted evidence, incomplete membership or incompatible accepted result -> refusal, no draft/HTML leakage |
| HT15 L2 | `test_report_drafts.py::test_save_note_preserves_machine_original` | Save a note/narrative override -> new local revision + author/time; raw/candidate/result/Git HEAD unchanged |
| HT16 L2 | same, `test_stale_save_and_command_replay` | Two tabs at rev1; first saves -> second conflicts; repeat original command replays original rev2 even after rev3; changed payload conflicts |
| HT17 L2 | same, `test_human_owner_note_does_not_change_source_owner` | Human next-owner edit -> human proposal in output; Jira assignee/owner_confirmed and AI baseline unchanged |
| HT18 L2 | same, `test_source_drift_does_not_rebase_saved_notes` | Source advances after draft -> current finalization refuses; original draft/notes preserved; explicit new draft/historical selection required |
| HT19 L2 | same, `test_draft_save_failure_is_recoverable` | Failure after command intent/revision before head -> original data remains; same command repairs once; no skip/revision overwrite |
| HT20 L3 | `test_report_publication.py::test_only_confirmation_commits_exact_selected_revision` | Save/preview/copy/download -> zero commits; finalize first retains six exact payloads and intent, then one publication; manifest excludes its own hash/commit, returned receipt verifies actual commit and chosen notes |
| HT21 L3 | same, `test_duplicate_finalize_and_crash_replay_retained_packet` | Duplicate/concurrent command or crash after finalization intent before append_record, after commit before ref, or after ref before response -> use original retained bytes and publication ID, same commit where a candidate exists; zero rerender/provider/model calls |
| HT22 L3 | same, `test_commit_failure_does_not_advance_publication` | Git/CAS/quota/checkout failure or missing/corrupt retained finalization byte -> preserve intent/draft/old history, no false final state; pre-intent partial packet cannot count as approval; committed+checkout-stale distinguished |
| HT23 L3 | same, `test_amendment_and_history_download_preserve_old_bytes` | New note on a published edition -> linked new draft/publication; original download unchanged, template upgrade cannot rewrite it |
| HT24 L2/L3 | `test_report_publication_security.py` | Wrong owner, archived project write, path/link/reparse/hostile Git config, arbitrary repo/remote -> refuse; no push and no touched code/unrelated files |
| HT25 L2 | `ui_web/tests/test_project_report_views.py` | Auth/CSRF/method checks across every route -> 401/403/404/405 as appropriate; no business mutation or false empty report |
| HT26 L2 | same, `test_clipboard_payload_uses_saved_revision_only` | Unsaved editor or preview revision mismatch -> Copy disabled; endpoint explicit revision returns matching fragment/plain hashes with private/no-store |
| HT27 L2 | same, `test_ui_language_does_not_modify_report_data` | en/zh switch -> UI labels only; English generated report, literal human/source text, no source/hash/model change |
| HT28 L3 | desktop Chrome/Ego authoring journey | Open accepted-source draft -> edit/save -> preview/copy/download -> finalization -> exact committed download; no clipping/hidden rows or controls in export |
| HT29 L3 | clipboard failure journey | Denied/unavailable clipboard -> visible failure, no success toast; saved HTML still downloadable; no permission bypass |
| HT30 L3 | user-selected Windows Outlook | Copy then paste into a blank HTML-mode draft with no recipients -> headings/table rows/borders/status labels/notes/links readable without manual reformat; no Send |
| HT31 L2/L3 | `test_report_publication.py::test_draft_copy_and_historical_export_do_not_advance_baseline` | Copied uncommitted draft or historical-purpose commit -> default meeting baseline unchanged; actual standup receipt advances per-item display only |
| HT32 L1/L3 | `test_report_html.py::test_independent_parser_detects_mutated_output` | Deliberately remove a row, exchange owner cells, alter literal note or unsafe URL -> semantic validator rejects despite a well-formed document |

HT03-08 production-adapter coverage depends on W4.DELTA/EVIDENCE; pure rendering
fixtures do not satisfy those dependencies. The initial HTML lane can qualify
first-baseline and same-source authoring without claiming multi-day operation.

HT30 target is confirmed by the user's 2026-11-02 About Outlook screenshot:

| Component | User-observed version |
| --- | --- |
| Microsoft Outlook for Windows | `1.2026.1020.100` |
| Client | `20261023003.06` |
| WebView2 | `156.0.4314.50 (Stable)` |

The screenshot establishes the environment only, not HTML compose mode or paste
compatibility. Do not copy its Session ID into evidence. HT30 records actual
versions and compose mode at execution, Chrome/Ego version, synthetic screenshot
evidence and any automatic formatting differences. If Outlook has updated,
record and test the actual version without downgrading or silently attributing
results to the screenshot's version. Classic Outlook and other mail clients are
not an added first-release matrix. HT30 is pending implementation/execution,
not pending client identification; unrelated local work need not wait for it.
Do not access mailboxes, existing drafts or recipients just to discover it.

## 4. Commands And Resource Ownership

These are planned commands after their named files exist, not tests run now:

```powershell
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_report_templates.py project_management/tests/test_report_html.py -q
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_report_source_reader.py project_management/tests/test_report_drafts.py -q
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_report_publication.py project_management/tests/test_report_publication_security.py -q
.\.venv\Scripts\python.exe -m pytest ui_web/tests/test_project_report_views.py -q
```

Use a fresh synthetic data root under
`D:/AIGC/scrum_dashboard_validation/html-reports/<run-id>/`, never inside the code
Git repository and never the user's existing W2 demo DB or W5.JOIN evidence root.
Reuse existing fixture ownership/settings/path guards and lifecycle handling.
Do not start the legacy all-services launcher, real Jira/HSD, Base or Grafana for
HTML-only validation. Required test sessions terminate before reporting closure.
Any user-requested preview server is separately identified and left running only
with a usable URL and explicit ownership.

Before a browser/native run fix a source candidate, test list, expected output,
log path, owned process cleanup and one question it will answer. Unknown failure
twice with no distinguishing evidence changes the experiment, not the retry count.
No cosmetic/mobile/multi-browser matrix or invented performance target gates
this desktop functional slice.
