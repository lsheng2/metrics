# Report Performance Delivery

Date: 2026-11-07. Status: scoped performance qualification complete;
`W6.PERF.ACCEPT.R` passed with independent final evidence review READY.
Machine-readable evidence: [performance-delivery.json](performance-delivery.json).
One execution ledger: [tasks.md](tasks.md).

## Results

Backend steady-state values below use 20 serial requests and nearest-rank p95.
The actual Ego language roundtrip uses ten serial switches and the same quantile.
Failed earlier samples remain in the evidence directories; they were not excluded
from their original receipts or combined with passing candidates.

| Scenario | Observed | Gate |
| --- | --- | --- |
| Language POST | 0.010s p95; zero archive Git calls | <=0.150s |
| Actual Ego Apply through target language and all lists | 3.101s p95; 10/10 complete | <=3.5s |
| S0 workbench first process request | 3.860s | <=5s |
| S0 workbench steady state | 2.876s p95 | <=3s |
| S0 baseline preview | 2.573s p95 | <=3s |
| S0 preparation detail | 1.448s p95 | <=3s |
| S1 workbench, page 20 | 4.105s p95 | <=5s |
| Save, revisions 24 through 43 | 1.839s p95; all saved and reopened | <=2s |

S0 is a fingerprinted clone of the retained synthetic week. The same frozen
input measured 31.602s and 169 Git processes before implementation. S1 contains
100 captures, 100 drafts, 100 publications, five revisions per draft and three
real captured synthetic tickets per snapshot. All 600 publication files were
validated through the normal reader after fixture construction.
These local synthetic results are not a production SLA or live provider/model qualification.

## Implemented Boundaries

- One authorized, fixed-head `ArchiveReadView` per query, bounded native Git
  batches, strict binary/object/hash validation and a shared ten-second budget.
- Request-only byte and pure-validation reuse, bounded four-worker local reads,
  ordered results and owned worker/process cleanup. No global permission cache.
- A workbench-specific publication DTO retains full six-file validation but
  omits the unused checkout diagnostic. Old publication APIs and visible capture
  checkout state keep their original meaning and validation.
- Baseline, preparation and optional operation reads reuse a checked scope;
  foreign root/owner/stage/hash, closed scopes and borrowing for writes are refused.
- Preview/prepare/reprepare/detail use narrow controls. Successful commands and
  JSON requests do not prebuild unrelated history. Error pages preserve original
  commands, dates, baseline selections, gap acknowledgments and user input.
- Authored Save performs syntax validation without a redundant draft preload.
  The original locked service still validates current revision/hash, targets,
  reference and AI receipts. Save does not finalize or advance the editorial baseline.
- Storage timeout/unsupported capability is retryable HTTP 503, not a false
  corrupt-artifact or invalid-input result. Corrupt bytes remain rejected.

## Validation

The JSON receipt binds exact XML hashes and source files. Key checks include:

- Binary batch/limits, real Git history and provenance, dirty checkout,
  hardlinks/reparse paths and process/worker cleanup.
- Full publication validation reuse, original bytes, scope movement, two readers
  interleaved with one writer, stale Save and borrowed-scope authorization.
- Source-reader, runtime recovery, period, skipped-meeting and preparation guards.
- HTTP auth/CSRF, replay, malformed/forged input, preserved error forms and
  correct 503 responses.
- Mounted-browser English/Chinese, lean preview/prepare, rich-text Save/reopen,
  desktop/mobile screenshots, Finalize and exact original HTML download.
- Actual Ego manual note, red/strong/highlight preservation, formatted copy and
  HTML download. A failed authentication probe is retained and attributed to
  browser-round authentication setup, not hidden as application success.

The two prior source-review findings were fixed with RED/GREEN evidence:
unsupported Git capability diagnostics and stage-hash recheck for absent archives.
The projection and final Save/detail changes received bounded independent review.
No Base SDK, real credentials/provider/model, production database, scheduler or
original week data was modified. The 13 pre-existing unrelated dirty files retain
their original SHA256 values.

## Final Browser Acceptance

The user authorized one new Ego validation space after the previous space
disappeared. On unchanged implementation commit
`60d791bac13078583de847740247768a35bd366d`, ten actual alternating en/zh-hans
switches passed. The timer starts at the real Apply click and finishes after
navigation, the target language and two animation frames with all five tables
rendered. Every response was HTTP 200 and every table-body count was
`[8, 8, 2, 9, 7]` for operations, captures, series, drafts and publications.

Ordered seconds: `3.1011, 2.7626, 2.8158, 2.7122, 2.6077, 2.6939, 2.6308,
2.6339, 2.7092, 2.7947`. Nearest-rank p95 for ten samples is the maximum,
`3.1011s`, below the unchanged `3.5s` gate. No final sample was discarded.
The two older preflight samples, including the approximately 3.52s sample,
remain historical diagnostics and are not included in this final ten-sample set.

The receipt binds all ten screenshots, the full page snapshot, collection
scripts, runtime/environment identity and unchanged frozen fixture fingerprints.
Screenshots confirm English/Chinese rendering and the lower draft/publication
lists. The observed final desktop viewport was 2560x1351 at DPR 1.5; this is the
actual Ego desktop, not a claimed 1280x900 emulation. The prior mobile check
remains separate and is not replaced by this desktop timing run.

An unsupported Ego `Browser.getVersion` query failed before navigation or
sampling; that setup diagnostic is retained, and page user-agent metadata was
used in the same authorized space. It was not an application request failure.
The owned task space and loopback-only test server exited normally; the server
recorded zero outbound connection attempts. No new week or S1 fixture was built.
The bounded independent review confirmed the timer/quantile, all 29 bound
artifacts, source/fixture stability and cleanup with no blocking finding.
It also rechecked all six earlier performance receipts, 16 XML receipts,
46 runtime-file hashes and 13 protected unrelated files. These earlier tests
were reused after identity checks, not represented as rerun in this closure.
OpenSpec strict validation, 106 relative documentation links, the applicable
file-size rule and whitespace checks passed. This closes only `W6.PERF.*`;
broader authoring, live provider/model and deployment gates remain separate.

## Reuse And Rollback

Current behavior is documented in the
[reporting guide](../../docs/current-baseline/project-reporting.md) and
[validation guide](../../../docs/development/reporting-delivery.md).
The JSON records why unaffected baseline/S1/period evidence remains applicable
after narrow POST or absent-archive changes.

Rollback is a code deployment rollback and normal service restart. No schema
migration, publication rewrite or baseline reset is required. Final deployment,
real providers/models and scheduling retain their separate authorization.
