# HTML Source Projection Packet

Status: implementation detail for W6.HTML.SOURCE; actual state only in tasks.md.
Goal: an owner can read exact accepted report material without running capture,
analysis, writing a draft or modifying Git.
Parent: [HTML authoring](html-report-authoring.md).
This packet freezes the first code leaf, not all reporting or deployment.

## Source And Reuse

Dashboard checkout HEAD is `12f7ac285d1bba7f125b947a11a3deaa2fd5d330`.
The already reviewed W5.JOIN code is uncommitted and the exact source bytes
below, rather than HEAD alone, identify this input.

| Existing input | SHA-256 before this leaf | Use |
| --- | --- | --- |
| `project_management/services/archive_reads.py` | `798c155c9d86fbcff6fd228ace55b21dfc743504bbf34c4b5e6901b4cc763f87` | authorized manifest/chain queries |
| `project_management/services/summary_journal.py` | `8c014676eacd0263ba6e2db95c8c51e350981b7ff34907c3708b6f51abb13a3d` | reference for actual acceptance and locks, not a new writer |
| `project_management/services/summary_journal_reads.py` | `aeb1b88bffbde932b93b2130a07fedf82f2656ea82975ecd32af2eed5bba40fe` | envelope/attempt/accepted validation, use commit-pinned wrapper |
| `project_management/services/capture_archive.py` | `2a4fbf70d56bda54edc493e8f48bc67fc66c845c1075c5843238f66e074956aa` | extend existing service with ReportArchiveReads mixin |
| `project_management/app/domain/summary_input.py` | `0eac3eee141bd6b321e924cb4738c38f4e495df94a77176dd077c3409034719f` | completeness, unchanged chain and original initial-input rebuild |
| `project_management/out/ai_task_contract.py` | `edd440f8f73eafe1c7578e7210e6ce5633bc05fb5cf45844981f032fe8acefd3` | existing pure original snapshot/result/candidate check |
| `project_management/app/domain/capture_values.py` | `8a9a822f3b7b7010c738d64a2a875f783a2678b5fd2b6c9b70be1a21a1852ea8` | canonical JSON and immutable value hash |
| `project_management/tests/summary_fixtures.py` | `88454c5e4d8b4bba13f9a3e398a57e5d9221c29301b86069965a4f1bbed4015c` | original review-1 output and synthetic actor/source |
| `project_management/tests/test_summary_journal.py` | `d3c9a3203435d97bc01cc2d625d7facb3b1f3b7061557f317cd833d63b01ff6d` | behavior source; do not inherit its test class to duplicate execution |

This leaf adds an adapter over already ported code, not a fresh port of the
donor runtime. MIG-12 future rendering references remain pinned to donor
`3d06b7a4a25434ee2fa133c9b4bef5f9c7c1366d`:
`src/standup/report_data.py` blob `6027eb22869e8fc37f79517a836389868b1a2549`,
`report_rendering.py` blob `9644090e515e6bec4d9d2f5eb01a312a19181a86`,
`report_validation.py` blob `d1e3cbbb13d549b5b3239d4a29217f11d47f196a`,
`report_row_validation.py` blob `f7bd2b6b65410722465164243f316d0049a546ad`,
`reports.py` blob `30ad369405082dd5196e932f51bdf51abb881506`.
No donor code is copied by SOURCE; no runtime/import dependency on its path.

## Exact API

```text
ReportSourceReader(archive, contract, limits: ReportLimits | None = None)
  .read(actor, project_id, stage_id, selection: ReportSelection) -> ReportSourceSnapshot

CaptureArchiveService.read_report_material(actor, project_id, stage_id,
    selection, *, contract, limits) -> ReportSourceSnapshot
```

The contract is an already loaded AiTaskContract; reading never creates an SDK
client. Keep archive's existing constructor and capture/analysis APIs compatible.
`ReportSelection(capture_id, baseline_publication_id=None,
parent_publication_id=None, purpose="standup", timezone="UTC")`.
Validate exact UUIDs, supported purpose and valid ZoneInfo key before reading;
other-owner authorization precedes filesystem access. No ambient timezone.

New frozen slots DTOs use the fields in html-report-authoring section4.
Add project_name/stage_name for presentation, derived from the authorized catalog,
not caller input. Collection fields are tuples; JSON evidence/coverage maps are
deep-copied through canonical serialization before return so callers cannot
mutate archive values. Nested values may use Mapping at this boundary.
`ReportRow.source_hash` may be null for a member without a captured detail.
`ReportRow.source_url` is a nullable safe presentation link. Build Jira links
only from the trusted HTTPS stage endpoint and validated display key, preserving
the configured context path. Reject userinfo/query/fragment/unsafe key; do not
emit a link for unsupported HSD UI mapping. Never alter source hashes for this
derived field or treat an endpoint ID as a URL.
`summary_as_of` is the retained Base snapshot terminalAt, or null; it is not
rewritten to now or substituted for source_as_of.

`ReportLimits` defaults: max_snapshot_bytes=8388608, max_members=500,
max_captures=100; these are bounded-read guards, not truncation or retention.
Violation is REPORT_LIMIT, preserving all archive files.
`ReportError` contains a fixed safe English code/message from the parent list.

## Read Algorithm And Refusals

1. Resolve actor/project/stage through the same public catalog and archive
   identity checks. A read must not create lock directories, bootstrap, indexes,
   files or reservations; use immutable commit-pinned reads and final recheck.
2. Pin repository HEAD. Use a small internal read facade whose head/read_file/
   list_files/commit_for_path use that exact commit and retain the original
   repository project/stage identity. Existing summary helpers read through it.
   No process-global cache. The wrapper exposes read methods only.
3. Bound capture manifest count before decoding them, then read the requested
   committed capture. Refuse incomplete membership, cross-stage identity,
   provider/endpoint/rule/principal mismatch or a future/unrelated capture.
4. SOURCE supports the current captured selection and first-baseline report.
   Non-null baseline/parent IDs return REPORT_COMPARISON_UNAVAILABLE until the
   publication leaf installs its verified reference resolver. A requested older
   capture returns REPORT_SOURCE_CHANGED in this leaf. This explicit refusal
   is temporary capability scope, not an excuse to silently ignore selection.
5. Iterate every member, stable identity order. No detail means a pending row
   with unknown facts/summary; source incomplete means pending, not a complete
   summary. Preserve all part coverage even when hashes are equal.
6. For an available accepted record: read original attempt, dispatch, accepted
   envelope, original RunSnapshot and RunResult. Check record/source identity,
   summary revision/ID, profile hash, expected base revision, original result
   hash, and `contract.validate_result`. Its returned local candidate must equal
   the stored candidate; do not merely trust a stored candidate's shape.
7. Rebuild the accepted initial input from its original captured source with the
   existing build_initial_input and verify input hash/content against the stored
   attempt. Missing/corrupt history refuses, not "pending". For equal newer
   captures verify every intermediate hash and complete coverage with
   unchanged_since; A -> B -> A must not reuse the old summary as current.
   For changed/incomplete source keep current facts and an explicit pending row;
   do not claim a stale summary is current or erase it from Git.
8. Evidence for exposed prose/actions comes from the verified original input;
   preserve IDs, pointer/hash, capture and literal value. Blockers/limitations
   reference this evidence. No secret or backend URL/token is added to output.
9. Derive coverage totals and deterministic key messages. Initial comparison has
   zero inferred events, comparison_state=initial_baseline; days=().
   No global status mapping or model-generated executive message in this leaf.
10. Check canonical output size, current catalog ownership/stage/source identity
    and HEAD again. Drift fails REPORT_SOURCE_CHANGED rather than mixing versions.
    Missing config/files/corruption keeps existing safe archive errors.

The result contains every member even when all analysis is pending; only a
validated usable accepted record contributes to accepted_count.
Coverage fields: membership (PartCoverage mapping), members_count,
accepted_count, pending_count, complete (membership complete and pending_count=0),
comparison_state, plus each row's original CaptureCoverage mapping.
No new remote authorization or provider calls are implied by local evidence
inspection. A current scope/profile change is reported/refused, not ignored.

## Files And TDD

Create `app/domain/report_contracts.py`, `app/domain/report_values.py`,
`app/api/reports.py`, `services/report_sources.py`,
`services/report_archive_reads.py`, `services/report_source_values.py`,
`tests/report_source_fixtures.py`, `tests/test_report_source_reader.py`.
Modify only the mixin import/base list in services/capture_archive.py and public
re-exports if needed. No provider, SDK, config, ORM, Git-writer or UI change.
Keep production files <=400lines, tests <=600. Small source projection helpers
may be split inside these owner files; no generic new persistence framework.

First RED:

```powershell
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_report_source_reader.py -q
```

Test the missing public read with `assert callable(getattr(archive,
"read_report_material", None))` in its initial behavior test, then the actual
returned original hashes/rows after implementation. The useful GREEN assertion
is the returned content and zero filesystem/Git mutations, not symbol existence.

HT13/14 precise cases, using the existing SummaryScenario and actual temporary
Git for the representative consumer:

| Case | Required result |
| --- | --- |
| Original accepted result | exact source/input/result IDs/hashes, 3 comments and explicit qa-b action preserved; no archive writes or SDK calls |
| Wrong owner/stage | refusal before repository reads, no new directories |
| Wrong result/candidate/hash | refuse inconsistent committed record; use an intentionally corrupt committed synthetic fixture, not a mock success |
| Missing detail / missing summary | every member retained as pending; no invented narrative |
| Incomplete membership | refuse register; no partially successful omission |
| Same source recaptured | original summary time/ref retained with newer source cutoff |
| Equal hash but partial coverage | summary not current; pending and original coverage |
| A -> B -> A chain | no false no-work reuse |
| Invalid/timezone/limits/unsupported baseline | typed safe refusal, no write |
| HEAD/catalog changes during query | no mixed-version successful snapshot |

Use lightweight in-memory read-store SPI tests for corruption/drift branches,
and one real-Git original-accepted integration fixture reused read-only across
parameterized query scenarios where appropriate. Do not recreate a full capture
for every pure value test. Test fixtures must never inherit another TestCase and
accidentally rerun its expensive suite.

Affected consumer check after narrow GREEN:

```powershell
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_summary_analysis.py project_management/tests/test_summary_input.py -q
```

Do not rerun the joined Base server for this read-only leaf. It consumes the
unchanged installed a2 contract; new source/fixture checks are its evidence.
