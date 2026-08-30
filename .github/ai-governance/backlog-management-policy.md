# Backlog Management Policy

This policy defines the lightweight backlog process for AI-assisted work in this repository. It is not a replacement for issue tracking. It is the local BKM for preserving deferred ideas, deciding when they are ready to plan, and preventing AI agents from silently turning future work into active implementation.

All project backlog records live in `openspec/docs/backlog/`. Future backlog items must be created there as one Markdown file per item and added to `openspec/docs/backlog/README.md`.

## Purpose

Use the backlog when a useful idea, risk, follow-up, or architecture improvement is real but not ready to implement in the current task.

A good backlog item answers three questions:

1. What problem or opportunity should not be lost?
2. What evidence or trigger would make it worth starting?
3. What validation would prove the work is actually done?

## When To Create An Item

Create or update a backlog item when any of these happens:

- A review finds valid work that is outside the current change scope.
- A design decision is deferred with a concrete trigger.
- A useful improvement depends on missing data, owner approval, or a later milestone.
- A runtime issue is mitigated but a broader architectural fix remains.
- A new AI-generated artifact pattern needs governance before implementation.

Do not create backlog items for vague reminders, personal notes, or work that should be done immediately in the current change.

## Required Item Fields

Each backlog item should contain these fields, either as YAML front matter or as a short Markdown table:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier, using `BLG-YYYYMMDD-short-name` unless an external tracker id exists |
| `title` | Plain-language title |
| `status` | One of the lifecycle states below |
| `source` | Link to the originating doc, review, bug, PR, or conversation summary |
| `problem` | The issue or opportunity in business/domain language |
| `user_value` | Why this matters to a dashboard user, maintainer, reviewer, or operator |
| `owner_paths` | Files, modules, or docs likely to own the work |
| `authority` | Contract, API, data model, BKM, or architecture rule affected |
| `risk` | `low`, `medium`, or `high`, with one sentence of rationale |
| `trigger_to_start` | Concrete condition that promotes this from backlog to planning |
| `non_goals` | What this item explicitly must not include |
| `dependencies` | Required decisions, data, tickets, or completed work |
| `validation_gates` | Commands, tests, reviews, or evidence needed for closure |
| `review_gate` | Whether architecture, validation, or coding review is required before implementation |
| `last_reviewed` | Date and short note from the latest triage |

## Status Lifecycle

Use these states consistently:

- `candidate`: Captured but not yet accepted as project backlog.
- `accepted`: Worth preserving, but not ready for planning.
- `ready-for-plan`: Trigger and owner paths are clear enough to create a DAG plan.
- `planned`: Covered by an approved plan or implementation handoff.
- `in-progress`: Active work is underway.
- `blocked`: Cannot proceed until a named dependency is resolved.
- `done`: Implemented and validated through the listed gates.
- `retired`: No longer needed, superseded, or explicitly rejected.

## AI Handling Rules

AI agents may propose and draft backlog items, but must not silently begin implementation from a backlog item.

Before starting implementation, an AI agent must confirm that the item is `ready-for-plan` or `planned`, and that the `trigger_to_start`, `owner_paths`, and `validation_gates` are concrete enough to test. If they are not, the correct action is to refine the backlog item, not to write production code.

When deferring work, write `deferred-with-trigger` instead of a generic TODO. The trigger must be observable, such as a user request, missing data arriving, a failing validation gate, or a named milestone starting.

When closing an item, cite the validation evidence. Do not mark `done` from memory or intent.

## Promotion To DAG Planning

A backlog item may become a DAG-backed plan only when all of these are true:

- The item has a concrete `trigger_to_start` that has occurred or has been accepted by the user.
- The owning modules, docs, or contracts are named.
- The validation gates can fail if the implementation is incomplete.
- The work has a bounded non-goal list.
- The required review gate is known.

Once promoted, follow the DAG planning skill and keep the backlog item linked to the plan or handoff.

## Triage Rhythm

Review accepted backlog before starting nontrivial architecture or implementation work in the same area. During triage, either keep the item as-is, refine missing fields, promote it, block it with a named dependency, retire it with a reason, or split it if it contains multiple independent outcomes.

Do not use backlog size as progress evidence. Progress is validated delivery or a clearer decision state.
