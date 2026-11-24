# Windows Concurrent Saturated Page Policy

Date: 2026-11-24. Status: owner-authorized reassessment; prospective r3 freeze.
Docs impact: operations/validation; current guide:
`docs/development/reporting-delivery.md`.
`profile_source=repo-local`; `agent_routing_mode=multiagent-configured`.

The owner chose to keep the existing implementation and reassess this scenario's
KPI. This amendment continues the existing PERF.KPI, PERF.OPTIMIZE and review
nodes, with `tasks.md` as the only execution ledger. It does not authorize a
response-wrapper, file-handoff, runtime, SDK, authentication or quota change.

## Decision And Rationale

The ordinary regression question and the combined concurrency/saturation
question have different budgets. Define the stressed class exclusively by
`mode=c4` AND `arm=candidate_saturated`: four concurrent page clients while
four AI streams are held. Apply it to every prescribed page in both development
and production. Never select it by page name, observed duration or prior failure.

| Class | Required page-plus-assets nearest-rank P95 |
| --- | --- |
| All other candidate cells, including sequential saturated and ordinary c4 | At most 1.2 times the matched baseline |
| Concurrent saturated class | At most 1.25 times the matched baseline AND at most 800 ms |

These numbers are an engineering budget, not statistically inferred confidence
bounds or an industry-mandated threshold. The ordinary 20% regression allowance
is retained. Combined stress gets five additional percentage points of relative
allowance, while a new absolute ceiling prevents a slow baseline from allowing
arbitrarily slow candidate pages. The 800 ms ceiling is a deliberately
sub-second service-side page-plus-assets budget, not browser LCP, render time,
end-user telemetry or a claim about every request. Both comparisons are
inclusive; neither can compensate for failure of the other.

Alternatives considered:

- Keep 1.2 everywhere: valid conservative policy, but it leaves the last formal
  failure open and cannot justify an implementation change without causal proof.
- Set a single-page exception or round 1.21978 up to 1.22: rejected as fitted to
  the observed failing cell rather than a reusable workload class.
- Raise all page limits or use only an absolute limit: rejected because either
  can hide ordinary regressions or materially penalize fast baseline pages.
- Use the class-specific dual limit above: selected after independent planning
  review. It preserves ordinary sensitivity and adds an absolute stress bound.

Google's [SLO implementation guidance](https://sre.google/workbook/implementing-slos/)
supports choosing objectives around critical user workflows and multiple latency
thresholds. It does not supply our 1.25 or 800 ms values. The local benchmark
executes HTML plus its referenced assets serially within each page sample;
it is a reproducible synthetic regression instrument, not a browser UX metric.

## Evidence And Limits

The original r2 full certificate remains FAIL, COMPLETE, and ineligible:
`D:/AIGC/d9-1122/runs/certify-final-r2-1124b.json`, SHA256
`51449f4f8aca990612c9d8f4421dd8be46701fe8a0991813e7fa36a81cf52d92`.
It collected 11,520 pages with normal cleanup and no collection errors.
Its only violation was production/c4/draft_edit/candidate_saturated:
baseline P95 560.371900 ms, candidate 683.531100 ms, ratio 1.2197811847.
The 1.2 bound was missed by 11.084820 ms. Block ratios were 1.40186, 1.32277,
1.05006 and 1.11049; these are not four independent certifications.

The same ordinary c4 cell was 1.12359; sequential ordinary/saturated ratios
were approximately 0.99782/0.99923. An earlier uninstrumented full diagnostic
measured the stressed cell at 1.05504, but also retained a sequential ordinary
failure of 1.58434. That ordinary failure would still fail the new policy.
The instrumented 480-page C4 diagnostic did not reproduce the stressed ratio.
Different run families are not pooled, and no green subset replaces a full run.

The real file-buffer characterization establishes that `TrackedResponse` hides
Waitress's native buffer type, not its causal share or an optimization benefit.
Restoring that path changes close/handoff ownership. The owner-selected
no-runtime-change decision avoids that unproved lifecycle intervention.
No root cause, speedup or statistical equivalence is claimed by this decision.

## Unchanged Requirements

- Full recipe: six pages, two settings phases, seq/c4, three arms, ten warmups,
  four alternating blocks and forty measured samples per block.
- Nearest-rank P95, all samples, complete identical asset sets and authentication.
- P1 streaming: first event <=200 ms and inter-arrival P95 <=150 ms.
- P4: each short/direct-asset kind and each phase independently needs P99<100 ms
  and maximum<=200 ms; statuses, hashes, cadence, four held streams and excess
  503/Retry-After2 are still mandatory.
- Real-leak checks, production-stop budgets, normal cleanup, source/fixture/wheel
  identity and exclusive collection remain hard gates.
- Dev9 stays admitted; AIB payload, app features, Windows environment and the
  Linux/other-App/global-release exclusions do not change.

## Authority And Tests

| Contract / Risk | Owner and producers | Consumers and required negative checks |
| --- | --- | --- |
| PERF-RECIPE / high | r3 canonical policy; `windows_host_samples.py` | Benchmark, conformance and standalone/aggregate replay: all six stressed pages accept exact 1.25/800 boundaries, reject either excess; all other cells reject >1.2 |
| PERF-IDENTITY / high | `windows_host_performance_contract.py`; new recipe and policy hash | Input builder, resolved inputs and semantic replay reject r1/r2, stale path/hash, mixed fields, reduced recipe and caller-selected limits |
| PERF-CLAIM / high | Existing raw receipt/window/witness/cleanup owners | Aggregate qualifier rejects forged summary, diagnostic/pilot promotion, missing samples and invalid cleanup regardless of page policy |

Applies: internal validation facade, exported validation report, diagnostic
events, validation scripts, immutable external evidence, CLI, operator docs and
test fixtures. Public runtime API, product UI, user-data schema/migration,
background scheduling and cache/search are not applicable: none is changed.
Runtime lifecycle work is deferred only if future evidence establishes a
separately authorized owner-scoped defect or optimization.

The parent owns policy/docs and integration. An isolated Architect Planner
Reviewer owns policy preflight and final code/claim review. Focused validation
uses the existing no-dotenv runner and candidate interpreter; the main agent
owns this small enforcement edit. No additional implementation/debug agent is
needed because product code and diagnosis are out of scope.

## Prospective Execution

1. Record the approved direction and independent policy recommendation. Keep
   every old policy, input and receipt immutable.
2. Add failing tests for class boundaries, ordinary-load negatives, stale
   identities and standalone/aggregate false-PASS attempts. Change only the
   owning evaluator, policy admission, active fixtures and current docs.
3. Run focused producer/replay/aggregate tests, size/whitespace, strict OpenSpec,
   refreeze preflight and an independent integrated review before publication.
4. Publish a scoped clean mainline source, then create a fresh input family.
   The source and combined fixture vector change, so use current-family native,
   migration and mapped functional proof; never relabel older receipts.
5. After agents and tests settle, run one uninstrumented full r3 certification
   through the reviewed bounded quiet coordinator. Preserve any failure.
   Do not repeat unchanged runs to choose a pass or automatically relax again.
6. Only an actually eligible certificate can feed the 121-key full qualifier.
   Complete CLOSE.R, WIN.ACCEPT, scoped publication and requirement-level audit.

Old policy r2 is historical once r3 is published. The P4 decision in
[the tail amendment](windows-tail-policy-amendment.md) remains active, but its
instruction to retain a universal page ratio is superseded by this amendment.
The earlier task wording and S0/S0b records are historical evidence, not a
second current numerical authority. No acceptance is granted by a policy freeze.

## Source Inventory Correction

The first r3 mapped-functional run stopped after42 passes with
`unreadable_source` for a `.zvec-grep` reader lock. That file was absent on
reinspection; the original low-level read exception was not retained.
The regression fixture reproduces disappearance between inventory and read.
The failed proof is retained under
`D:/AIGC/d9-1122/mapped-proof-runs/80ef1d8f-67d9-4fb8-beee-8ad0b0d4e372/`.
This is a shared source-inventory defect, not a product or numerical failure.
Under existing W1.RETIRE ownership, exclude only the root tool-metadata
directory before traversal. Near-miss/nested names and unreadable application
source still fail both checkers; Git-ignored business code remains scanned.
The r3 policy, application/SDK and all budgets remain unchanged. Preserve the
ee92276 native/migration/conformance results under their original identity,
then freeze a fresh source/input family for the corrected validation source.
