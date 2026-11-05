# Closure Verification Policy

Status: active BKM.

Use this before claiming a class of work is complete, review-ready, or fully covered.

## Contract Registry

| id | Contract | Disconfirming Check |
| --- | --- | --- |
| `CLOSURE-1` | A class of changes is complete only after the class was enumerated by search or made unrepresentable by API shape. | Show the query output, or narrow the claim to "sites I found". |
| `CLOSURE-2` | A boundary fix must name both producer and consumer. | List the producer path and consumer path for each changed value. |
| `CLOSURE-3` | Fixing a callee does not close the boundary if callers still derive unsafe values before calling it. | List callers and show they no longer bypass the owner path. |
| `CLOSURE-4` | A gate that checked zero files is a failure, not a pass. | The command must report a nonzero checked count or fail. |
| `GUARD-1` | One failing mutation proves necessity, not sufficiency. | Describe a second wrong implementation that the guard would reject. |
| `CLAIM-1` | Numeric claims must be measured on the code and scope being described. | Include command, scope, and output. |
| `MECH-1` | Use the repository's declared gate, not a convenient substitute. | Run the focused pytest, `manage.py check`, file-size gate, or diff gate named by this repo. |
| `MECH-2` | After multi-hunk edits, validate resulting structure, not only syntax. | Inspect definitions/imports or run the focused test that imports the edited owner. |

## Required Use

1. For nontrivial code waves, run `python scripts/check_file_size_limits.py --include-untracked` and `python scripts/check_diff_whitespace.py --include-untracked` before requesting review.
2. For Django settings, URL, view, template, or container changes, run `python manage.py check` unless blocked.
3. For behavior changes, run the focused test that exercises the owner path; broad tests may supplement but should not replace it.
4. If validation cannot run, state the blocker and residual risk.

## Scope And Evidence

Follow the selected environment and risk-based layers in `AI_CONTRACT.md`.
Reporting tests always name explicit paths; default pytest discovery misses the reporting modules.
Do not run product or browser suites solely because documentation changed.
For a dirty worktree use the declared packet's size/whitespace selection and inspect staged bytes;
unrelated failures remain visible but are not permission to edit or stage another owner's work.

One business invariant may need several assertions or complementary layer checks.
HTTP ownership/CSRF, templates, schema boundaries and actual container wiring require tests
where they enforce a contract. Never omit them because an old guide called them presentation.
Expected pending evidence is a readiness state; it is not automatically a new product defect.
Review source, relevant evidence and next-wave readiness together where this avoids duplicate review.
