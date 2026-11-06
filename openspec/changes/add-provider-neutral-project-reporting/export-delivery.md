# Saved Report Export Delivery

Date: 2026-11-06. Source base: `2759d461175215dbdc3c5920a3cf780bf2102ffc`.
Scope: `W6.AUTHOR.EXPORT.SAMPLE`. State stays in [tasks.md](tasks.md).
Exact APIs, bounds and ownership are in [export-execution.md](export-execution.md).

## Current Behavior

Saved drafts and publications expose Markdown and Excel derived downloads through
the public report API and authenticated GET routes. Published export reads verified
original `report.html`; it does not invoke the current renderer, source reader,
provider, Base client, Save, Finalize or Git writer. Original six-file publications
and HTML/plain downloads are unchanged.

Markdown preserves separate rows, links, literal markup and daily update breaks.
Excel exports literal text tables, full report text, links and an Information sheet.
Neither is a paint-restoration format; HTML/JSON retain full formatting. Unsupported
structure and excessive content fail explicitly. No formula interpretation, silent
cell truncation, export cache or new publication namespace is introduced.

The compact controls use existing saved revision/lifecycle signals. Dirty, saving,
failed-mount and uncertain states remove the export link; normal Save/reopen restores
the correct revision. Controls support English and Simplified Chinese.
Missing export dependencies do not disable original HTML/manual report operations.

## Evidence

Evidence root: `.tmp/dashboard-exports-20261106/`.

| Evidence | Observed result |
| --- | --- |
| `compiler-final-01.xml` | 17 passed; actual Markdown/Excel content, literal markup/formulas, limits, missing dependency, repeatability across controlled clocks |
| `service-green-01.xml` | 1 passed, 86.67s; real Git, three tickets/two days, original source hash/bytes/head unchanged, poisoned renderer/source/finalize not called |
| `views-green-01.xml` | 2 passed; actual files/hashes/private headers, owner, method, duplicate/unknown query and unavailable dependency |
| `browser-green-01.xml` | 2 passed, 20.94s; mounted human text/paint/link Save, real file downloads and publication export, browser clipboard HTML/plain readback, Chinese phone layout |
| `consumers-01.xml` | 28 passed; affected original report Save/view/lifecycle and initial compiler/view cases |
| `ui_web/tests/report_exports_test.mjs` | 3 passed; confirmed revision URL, each existing dirty lifecycle state, publication and same-origin boundary |
| `plan-review.md` | Bounded plan READY |
| `review-01.md` | One P2 Markdown line-limit omission; falsified by `line-limit-red.xml`, corrected and included in final compiler checks |
| `review-fix.md` | Changed-finding rereview BOUNDED READY; no open findings in the fix scope |

The final line guard changes no output below the limit. The retained real-Git and
browser samples are far below it; their source/format adapters remain unchanged.
The guard additionally counts in-cell `<br>` breaks, not only physical file lines.
Initial RED and harness-error evidence is retained, including overlong pytest
parameter IDs corrected for Windows without changing product bounds.

Browser evidence:
`browser-d37e859b-9de2-4cca-8920-abc66e5365a6/` contains actual `draft.md`,
`draft.xlsx`, `publication.md`, clipboard HTML/text and the result/screenshot.
`phone-5f7ddc3f-8656-43b4-a449-a3c8c2466005.png` and its XLSX record the Chinese
390px control. Clipboard proof is the browser Clipboard API, not Outlook or another
native receiving application's paste qualification.

Pinned dependencies: existing openpyxl3.1.5, bs4 4.15.0, Markdownify1.2.3.
Markdownify wheel SHA-256:
`a189a0bedfd14009030fde5f85bb6f77c56897cb839b5c25315dd7d4e3e290ba`.
It was installed only into the selected reporting environment; the legacy venv was
not changed. The source pins are in `requirements.txt`; export imports remain lazy.

Scoped file-size checks (17 selected files), whitespace, isolated Django `check`
and migration dry-run passed. Source publication uses an explicit allowlist and
preserves the same 13 unrelated Scope/config/style paths.

## Next Boundary

Proceed to the original `W6.AUTHOR.JOIN`: 2026-10-26..30 plus 2026-11-02, three
independent tickets, stable source values, daily human edits/paint, original-key
reuse, Save/reopen/Finalize, normal restart and retained per-day evidence.
The first accepted summaries must come through the installed SDK and real local
Base HTTP with a synthetic backend; a seeded accepted summary is not a replacement.
This export sample does not close the complete week, real provider/model, Outlook,
deployment or optional scheduler qualifications.
