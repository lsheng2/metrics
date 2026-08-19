---
name: dag-based-planning
description: "Use when creating, reviewing, or executing DAG-backed plans, dependency graphs, implementation checklists, invariant contracts, multi-agent handoffs, or machine-checkable task DAGs for the Metrics dashboard."
argument-hint: "feature/fix scope, source spec, or plan file"
---

# DAG-Based Planning

Use this skill when work needs dependency-aware planning, wave execution, independent review gates, or machine-checkable closure.

Do not use this skill for trivial one-file fixes with one obvious validation command. Use a short checklist instead.

## Must Load

1. User request or source spec.
2. `CLAUDE.md`.
3. `.github/skills/dag-based-planning/templates/project-profile.md`.
4. Target module code and nearby tests.

## Workflow

1. Decide whether a DAG is warranted.
2. Build a plan-level Contract Registry. Each entry has a stable id such as `INV-*`, `PRED-*`, `ADV-*`, or `SYNC-*`, one authoritative owner, consumers, and an executable disconfirming check.
3. Identify nodes with stable ids, dependencies, `owner_paths`, contract references, validation, and exit criteria.
4. Record scope baseline: `git rev-parse HEAD` and current dirty paths from `git status --porcelain=v1 --untracked-files=all`.
5. Assess code-doc truth sync before implementation: architecture docs, README, `CLAUDE.md`, `.github` customization, tests, and configuration docs.
6. Create a human-readable execution ledger with one Markdown checkbox line per DAG node, for example `- [ ] W0.N1 - Add facade contract`.
7. Run plan preflight before review: the Contract Registry, node table, Mermaid graph if any, checkbox ledger, validation commands, and owner paths must agree.
8. Use independent review gates for nontrivial plans:
   - `PLAN.R` before implementation starts.
   - `W*.VA` validation architecture signoff before risky implementation waves.
   - `W*.R` behavior review after focused validation.
   - `CLOSE.R` before final closure.
9. Execute one node or slice at a time unless the plan marks nodes parallel-safe and they do not touch the same owner files.
10. Update checkbox status when a node completes, reopens, or is deferred.

## Mechanical Gates

| Gate | Question | Enforcement |
| --- | --- | --- |
| Scope | Did a file change outside every declared node `owner_paths`? | Always for DAG plans |
| Producer/consumer | Does every changed contract name both producer and consumer? | Always for contracts |
| Wiring | Does every new symbol have at least one production call site? | Per new symbol |
| Orphan | Do zero production importers of a replaced owner remain? | When replacing owners |
| Registration | Is every new status/filter/API/display value registered in all owners? | When adding values |
| Code-doc sync | Did current docs and AI customization reflect changed stable behavior? | Code, contract, config, UI, or validation changes |
| File-size | Do changed source files stay under configured limits? | Nontrivial code waves |

## Evidence Rules

1. A green test suite is evidence, not proof. Name the exact behavior it falsifies.
2. A gate that checked zero files is a failure.
3. A structural checker cannot prove missing requirements. The plan must name the owner layers.
4. Do not verify a subtree that no implementation node produces.
5. For every boundary, name producer and consumer. Produced but never consumed and consumed but never produced are both defects.

## Node Template

```markdown
| Field | Value |
| --- | --- |
| id | W0.N1 |
| depends_on | [] |
| owner_paths |  |
| authority_boundary |  |
| contracts |  |
| validation |  |
| exit_criteria |  |
| parallel_policy | serial |
```
