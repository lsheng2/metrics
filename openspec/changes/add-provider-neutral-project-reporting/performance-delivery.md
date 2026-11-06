# Report Performance Delivery

Date: 2026-11-07. Status: implementation and backend qualification complete;
final `W6.PERF.ACCEPT.R` remains open for the authorized Ego browser rerun.
Machine-readable evidence: [performance-delivery.json](performance-delivery.json).
One execution ledger: [tasks.md](tasks.md).

## Results

All steady-state values below use 20 serial requests and nearest-rank p95.
Failed earlier samples remain in the evidence directories; they were not excluded
from their original receipts or combined with passing candidates.

| Scenario | Observed | Gate |
| --- | --- | --- |
| Language POST | 0.010s p95; zero archive Git calls | <=0.150s |
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

## Remaining Gate

The last Ego browser task space disappeared before the ten final language
roundtrips. Inventory then contained only user-owned spaces. The agent stopped
that surface and asked permission to create a new validation task space instead
of claiming or modifying the user's tabs.

Only two earlier language preflight roundtrips exist, approximately 3.52s and
3.30s. They are not a ten-sample pass and are not substituted for the required
click-to-target-language-and-all-lists gate of p95 <=3.5s.
`W6.PERF.ACCEPT.R` must stay unchecked until that gate and the final evidence
review are complete.

After authorization, resume with the existing frozen S0 data and the same final
code; do not rebuild a week or S1. Record ten real language changes, screenshots,
row counts and all timings. If a runtime change is needed, rerun only the
affected performance/consumer checks before closing this gate.

## Reuse And Rollback

Current behavior is documented in the
[reporting guide](../../docs/current-baseline/project-reporting.md) and
[validation guide](../../../docs/development/reporting-delivery.md).
The JSON records why unaffected baseline/S1/period evidence remains applicable
after narrow POST or absent-archive changes.

Rollback is a code deployment rollback and normal service restart. No schema
migration, publication rewrite or baseline reset is required. Final deployment,
real providers/models and scheduling retain their separate authorization.
