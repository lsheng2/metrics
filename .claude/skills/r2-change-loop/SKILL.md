---
name: r2-change-loop
description: Use when executing an approved R2 OpenSpec change (public contract, data migration, security, cross-repo, or multi-session work) - opening a session, running verified milestones, handing off, and closing with archive. Replaces openspec-apply-change. Not for R0 bug fixes or R1 small changes; those follow the repository contract alone.
---

# R2 Change Loop

Run one approved OpenSpec change to done in small, verified, committed milestones.
Done means `scripts/compute_done.py` exits 0 on fresh JUnit plus human acceptance, never prose.
"The repository contract" below is AGENTS.md and the documents it links; it names the test
commands and pre-commit gates. Use the `openspec` CLI directly; this loop needs no other skill.

## Preconditions

- `openspec/changes/<id>/` has `proposal.md`, `specs/`, `tasks.md` and `feature_list.json`.
  An in-flight change adopts this loop by adding `feature_list.json` before its next milestone.
- Checkpoint 1 passed: a human approved the proposal and its acceptance examples.
- Acceptance examples or non-goals missing or vague: stop and pressure-test the request
  first (grilling skill). Never invent acceptance criteria.

`feature_list.json` belongs to the acceptance owner and has no status field; status is computed:

    {"change": "<id>", "features": [{"id": "EXP-1", "behavior": "<one observable behavior>",
      "spec": "openspec/specs/<capability>/spec.md", "scenario": "<scenario name>",
      "acceptance_tests": ["<pytest node id, or classname::name for other runners>"]}]}

## Open a session

1. Run `git status --short` and `git log --oneline -20`. Leave changes you did not make alone.
2. Read `tasks.md` > Now / Next / Blockers. It is the only session state. Do not create
   another plan or ledger file (for example `plan.md` or `docs/superpowers/**`).
3. Run `openspec instructions apply --change "<id>" --json` for the task list and context files.
4. Run the focused smoke check the repository contract names. If it is red before you start,
   report that first instead of building on it.

## Milestone loop

One milestone = one verified increment = one green commit.

1. Take the next unchecked milestone in `tasks.md`. If it spans more than one module
   boundary or more than one acceptance id, split it before coding.
2. Acceptance tests come from their owner. Never edit the tests listed in
   `feature_list.json` or `feature_list.json` itself.
   For behavior you add, write the focused failing test first.
3. Implement the smallest change that turns those tests green.
4. Verify, in this order:
   - focused tests for the touched modules, with the commands the repository contract names;
   - `openspec validate "<id>" --strict`;
   - the repository's pre-commit gates (for example size and whitespace checks);
   - the acceptance tests with `--junitxml=<junit.xml>`, then
     `python scripts/compute_done.py openspec/changes/<id>/feature_list.json <junit.xml>`
     to see which acceptance ids are still open.
5. Green: commit (message names the milestone and the test ids), tick the milestone,
   overwrite Now / Next / Blockers.
6. Red: fix forward. The same hypothesis may fail at most twice; then go to Recovery.

## Recovery

- Return to the last green commit by restoring only the files you changed since it
  (`git restore -- <your files>`). Never stash, reset or restore work you did not create.
- Change the hypothesis or split the milestone, then re-enter the loop.
- Still stuck: hand off with the blocker stated.

## Hand off

Hand off at about 60% context use, at the end of a session, or when blocked.
Overwrite this section of `tasks.md` (at most 15 lines):

    ## Now / Next / Blockers
    Now: <milestone> committed (<sha>); <ids> green, <ids> red (<reason>)
    Next: <one concrete next step>
    Blockers: <blocker, or "none">
    Assumptions: <decisions taken alone; list each one in the PR>
    Files: <files touched this session>

Durable decisions go to `tasks.md` > Decisions (one line with the commit sha) or to an
ADR / `design.md`. History stays in git, not in `tasks.md`.

## Stop and ask when

- acceptance criteria must change;
- a public contract outside the plan must change;
- two consecutive milestones overrun;
- an irreversible or destructive action is needed (running a data migration, force push,
  deleting work you did not create, writing to external systems).

## Review

Before human acceptance, request one review from a model of a different vendor when one is
available. Give it only the spec delta, the diff and the test results. The reviewer reruns
the focused tests itself and reports blocking findings only. Fix blocking findings; record
the rest as follow-ups in the PR.

## Close

1. `scripts/compute_done.py` exits 0 on the change's `feature_list.json` with fresh JUnit from
   all its acceptance tests: in CI where the repository has one, otherwise locally with the
   command and its summary line recorded in the PR or commit.
2. Human acceptance (checkpoint 2).
3. `openspec archive "<id>" --yes` merges the delta into `openspec/specs/` (truth sync).
   Archive within 7 days of acceptance; `openspec list --json` shows changes whose tasks are
   all complete but which are not archived yet.
4. Delete process-only scratch files (notes, temporary logs) unless the repository contract
   keeps them as evidence.

## End every session with

    done: <acceptance ids or test ids now green>
    not done: <remaining milestones or ids>
    blockers: <blockers, or "none">
