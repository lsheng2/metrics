# Source Observation And Summary Readiness

Date: 2026-11-07. Status: implemented and validated within this packet.
Docs impact: architecture, user, reference.
Current docs: `openspec/docs/current-baseline/project-reporting.md`,
`docs/development/reporting-delivery.md`.
Execution state lives only in [tasks.md](tasks.md), under `W6.OBS.*`.
This packet amends [continuity](report-continuity.md#current-day-without-new-source-content)
and [authoring requirements](specs/report-authoring/spec.md).

## Outcome And Boundary

After a finalized daily report, another complete capture of the same ticket
content SHALL yield `No source change`, including `analysis_mode=manual_only`
and cases where no accepted AI summary exists. Earlier human text, deletion,
paint, links, note dates and unresolved AR remain authoritative.

```text
ww45.1(In Analysis): Previous human note. AR: @owner follow up.
ww45.2(In Analysis): No source change
```

The second line is a system observation, not an authored DailyNote. The current
editor slot remains empty and accepts a human note. An explicitly saved empty
note is different from an untouched slot and must not resurrect old AI text.
Status always uses the selected provider capture, never AI or yesterday's status.
Equality describes the two selected captures, not unobserved time between them.
The existing complete-chain requirement for accepted-summary reuse is separate.

No live Jira, HSD-ES, model, SDK, scheduling, deployment or old-publication rewrite
is part of this packet. Reuse the qualified SDK environment. Do not rerun the
full-week or S1 performance fixtures. Preserve unrelated dirty Scope/CSS files.

## Producer Contract

`ReportSourceReader._row` already checks immutable source identity/hash and
`complete_source(source)` BEFORE considering accepted summaries:

| ReportRow evidence | Source meaning | Summary readiness |
| --- | --- | --- |
| `source_hash is None` / `source_missing` | unavailable | false |
| `pending_reason=source_incomplete` | incomplete, even if a hash exists | false |
| `summary_pending` | current source passed the complete-source gate | false |
| `summary_stale` | current source complete; old summary cannot cover it | false |
| usable `summary_ref`, no source/summary refusal | current source complete | true |

The continuity builder consumes this verified projection, not arbitrary provider
JSON. Do not create a second, weaker completeness parser from individual coverage
fields or make source equality depend on summary presence. Capture hashes,
required parts, unsupported-part policy and accepted-summary reuse remain owned
by the existing capture/analysis code.

## Independent Decisions

Keep `build_daily_authoring_context(...)` and the v1/v2 context wire shapes.
Extract summary-note eligibility from `_source_state(row, previous)`:

1. A current missing hash/source yields `unavailable`; a current incomplete
   source yields `incomplete`, regardless of accepted-summary metadata.
2. A complete source with no prior observation for the same stable issue is
   `initial`.
3. A previous unavailable/incomplete observation or missing source hash is not a
   comparable baseline. The complete current source yields `pending`, meaning
   comparison unavailable, not inference pending.
4. Otherwise compare only the per-ticket `source_hash`: equal is `unchanged`,
   unequal is `changed`. Capture UUID, capture time and summary identity do not
   affect source equality. Existing stable provider/endpoint/item identity and
   series/stage checks remain in force.

Summary-note eligibility is a separate pure decision:

```python
summary_ready = row.summary_ref is not None and row.pending_reason not in {
    "source_missing", "source_incomplete", "summary_pending", "summary_stale",
}
new_summary = summary_identity(current_ref) != summary_identity(previous_ref)
make_note = summary_ready and source_state not in {"incomplete", "unavailable"} and (
    source_state in {"initial", "changed"} or new_summary
)
```

`new_summary` deliberately preserves pending-to-accepted and revised-summary
materialization even when source equality is `unchanged`. Such a note is a new
accepted analysis, not evidence of changed provider data. An unchanged, already
used summary cannot copy itself into today's empty slot. Explicit AI assistance
continues through its existing candidate/Apply/Save contract.

## Compatibility

No new stored coverage/readiness field, enum value or context version is needed.
`accepted_summary_ref` continues to identify the accepted material; readiness
is decided from the verified current row at preparation, not reconstructed by
the renderer. Readers do not normalize, migrate or modify old canonical bytes.

For existing v1/v2 observations, `initial|changed|unchanged` and `pending` with a
non-null source hash were produced only after the complete-source gate.
Therefore legacy `pending` plus a hash is a complete observation for a NEW
comparison. Incomplete/unavailable/null-hash observations cannot qualify.
This is an explicit producer invariant, not a guess that every hash is complete.
A current complete capture after an uncomparable baseline can itself become the
next finalized comparison baseline. Old `pending` display remains conservative.

Keep context validators' exact keys, canonical hashes, preparation replay,
Save/CAS, six original publication files, weekly merging and read-only downloads
unchanged. Tests must demonstrate legacy v1/v2 round trips and old publication
bytes after a new report is published.

## Presentation Contract

One reporting helper owns canonical English observation labels for the concise
standup renderer, generic meeting-matrix renderer and editor view model.
The UI translates the labels through its existing EN/zh-Hans catalog.
Business report output remains English in either UI language.

| source_state | Label when no current authored note |
| --- | --- |
| initial | Initial source; note pending |
| changed | Source changed; note pending |
| unchanged | No source change |
| pending | Source comparison unavailable |
| incomplete | Source incomplete |
| unavailable | Source unavailable |

For initial/changed/unchanged, a saved current note replaces the observation
line, including an explicitly empty note. For pending/incomplete/unavailable,
retain the uncertainty warning even alongside a human note. Prior notes and AR
are never hidden by an uncertainty warning.

In the editor, place the read-only observation beneath the provider-status
prefix, outside the Milkdown region. Reuse existing paragraph/help styles;
no global CSS, new controls, alternate editor or layout redesign. Observation
text must have at least 4.5:1 contrast on the existing white table cell. In read-only
weekly cells, suppress duplicate current prefixes when a note already supplies
the prefix. A missing meeting is not an unchanged observation.

## Contracts And Consumers

profile_source: repo-local. agent_routing_mode: multiagent-configured.
Baseline: `ec9368b462e39ea7a2f0445b7e3c6d2f24dd4c57`, own `main`.
All 13 pre-existing dirty paths remain outside scope.
One coordinator writes; an independent reviewer owns plan/behavior gates.
No separate implementer or debugger is needed for this single bounded wave.

| Contract / risk | Producer -> concrete consumers | Disconfirming checks |
| --- | --- | --- |
| OBS-SOURCE high | `services/report_sources.py` -> `app/domain/report_continuity.py` -> existing seed/draft/period readers | complete manual same/different hashes; incomplete/missing cannot claim unchanged; legacy comparable/uncomparable baseline |
| OBS-NOTE high | continuity builder -> existing continuity edits, persistence and next-day builder | pending-to-accepted/revised-summary yields a new note without source change; same accepted summary cannot duplicate; human paint/deletion/AR survive |
| OBS-DISPLAY high | `reporting/observations.py` -> `reporting/standup.py`, `reporting/pinned.py`, `ui_web/report_continuity_view_model.py`, `pinned_blocks.html` | no current note versus saved empty note; uncertainty visible with human note; generic/concise/weekly and bilingual UI agree |
| OBS-IMMUTABLE high | existing v1/v2 context -> preparation/Save/publication/period/download | canonical context round trip; old six files byte-identical; no schema rewrite, model or provider call |

Consumer universe: public API applies through unchanged `app/api/reports.py`;
internal service applies through continuity/preparation; UI and exports apply as
above; audit applies via unchanged original context/artifact readback; validation
scripts apply through the existing no-dotenv runner and scoped gates; stored
schema applies with no format migration. Scheduler, cache/index and CLI are
not changed because none produces observation state. External artifacts apply
only to derived HTML/plain/Markdown/Excel from saved HTML. Docs and synthetic
fixtures apply. AI Base and provider adapters are explicit non-goals.

## Execution And Validation

| Node | Depends on | Owned files and exit |
| --- | --- | --- |
| W6.OBS.PLAN.R | user approval | this packet, continuity/spec amendment, tasks; independent compatibility/consumer review |
| W6.OBS.CORE | W6.OBS.PLAN.R | continuity builder; new reporting observation helper; standup/pinned renderers; editor view model/partial; zh-Hans po/mo; tests below; RED then GREEN |
| W6.OBS.ACCEPT.R | W6.OBS.CORE | current guide, development guide, this packet and tasks; bounded native/UI evidence, independent review, scoped gates and publication |

L0: `project_management/tests/test_report_source_observations.py`, plus the
same-hash pending-to-accepted regression in `test_report_history_core_review_regressions.py`.
Use the real builder/renderer/validator, literal expectations and no Git.
Cover both v1 and v2 context bytes, changed manual source, missing/incomplete
source, recovery from an uncomparable baseline, late/revised summaries, existing
human/empty notes and unresolved actions.

L1: `project_management/tests/test_report_source_observation_publication.py`
uses one real local-Git two-date prepare/edit/finalize chain, a manual source
boundary, original-byte rechecks and saved-HTML derived exports.
Reuse existing source-reader tests to pin the completeness-before-summary
producer invariant. No repeated five-day or SDK/Base fixture.

L2: `ui_web/tests/test_report_source_observation_ui.py` renders real view-model
and template output for labels, empty/read-only regions, uncertainty and English/
Chinese. Existing focused HTTP/history tests cover unchanged route/owner/CAS.
L3: `ui_web/tests/test_report_source_observation_browser.py` mounts Milkdown on
the real local HTTP editor, verifies the observation is outside editable content,
adds/saves/reopens a human note and captures desktop/390px bilingual evidence.

Resolve `{python}` to `.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe`.
Run `-I scripts/validation/run_report_authoring_tests.py` with the explicit
test paths above, `-q --tb=short --junitxml=<unique-evidence-file>`. Evidence stays
under `.tmp/dashboard-source-observation-20261107/`. Run isolated Django check,
OpenSpec strict validation and explicit-path size/whitespace gates before commit.
The existing runner denies external networking. Retain RED output separately.
Do not count collection, skips or unaffected historic evidence as new passes.

Stop at a reproducible contract ambiguity or two equivalent unexplained failures;
change the hypothesis/instrumentation rather than repeat the full stack. Closure
requires the named current docs and receipt, not merely a green unit suite.

## Delivery Receipt

The implementation is limited to independent decisions in
`app/domain/report_continuity.py`, shared `reporting/observations.py`, both report
renderers, the editor view model/partial and zh-Hans translations. No API,
context schema, source hash, SDK or original publication file format changed.
The current user and development guides linked above describe the behavior.

Evidence root: `.tmp/dashboard-source-observation-20261107/`.
Final runtime/fixture hashes and command results:
`validation-receipt-a7250749-9908-40c4-a32a-0d3c2f1bb35f.json`.

| Verification | Final result |
| --- | --- |
| `final-core-ui-01.xml` | 97 passed; source/summary, old contexts, both renderers, template and mounted editor |
| `source-producer-01.xml` | 4 passed; source completeness precedes summary readiness; unchanged-summary reuse |
| `period-http-01.xml` | 10 passed; weekly/missing/source-status projections and template HTTP consumers |
| `native-01.xml` | 1 passed; two native captures, manual worker preparation, two local-Git publications, original six bytes and Markdown/Excel |
| `django-check-01.xml` | 1 isolated environment/system check passed; SDK 0.2.0a1, Django 6.0.7 |
| OpenSpec strict / diff whitespace / scoped file size | passed; 10 scoped Python files checked |

These are 112 business tests plus one environment/system check, not a full
repository, full-week, S1, live provider/model or deployment qualification.
The native test took 105.72 seconds including its fixture; this is not a
production latency measurement. Its runtime dependencies were unchanged by
the later editor-only contrast correction, so it was not repeated.

Mounted screenshots and measurements:
`browser-ce033be4-e465-40ce-b999-a4595b6735a4/` contains EN/zh-Hans at 1440px
and 390px, plus the saved blue human note. Text fits, no page-level horizontal
overflow, and the observation contrast is 10.35:1. The prior human red note
survives; the system observation remains outside Milkdown and disappears after
the new human note is saved. Browser and owned test servers exited normally.

Preserved failures: `red-01.xml` reproduced conflated source/summary and missing
UI/render warnings; one new-test link fixture was corrected to the real fragment
shape. `native-red-01.xml` reproduced manual source marked pending.
`contrast-red-01.xml` measured 2.54:1 before the scoped paragraph-color fix.
These failures are retained, not relabeled as successful runs.

Independent plan review `01a1b675-97e4-7023-91ee-79e5b13ba9af` and final source/
evidence review `01a1b685-2ec8-74f3-9a7d-8e6b2eb40a7e` returned READY, with no
actionable P0-P3 findings. This is a bounded independent review, not automated
exact-pass certification. The full dirty-tree size check reports two pre-existing,
out-of-scope Scope tests at 650 and 624 lines; all 13 protected unrelated files
retain their prior hashes. No global gate setting or other owner's file was changed.
