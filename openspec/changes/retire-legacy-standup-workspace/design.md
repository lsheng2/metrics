# Legacy Workspace Retirement Design

Status: implemented and independently reviewed on 2026-11-08.
Authority: [tasks](tasks.md); requirements: [spec](specs/workspace-retirement/spec.md).
Current operations: [guide](../../../docs/migration/legacy-workspace-retirement.md).

## 1. Decision And Boundaries

Use preservation plus selective relocation, not wholesale product reinstallation
or a claim of complete feature parity. Whole-product migration would reopen
unrelated backlog; a Git-only archive would lose dirty and ignored material.
The selected approach preserves everything while removing the old checkout as
a runtime/development prerequisite.

Source: `D:\AIGC\chiplet_programmgr`.
Active app: `D:\AIGC\scrum_dashboard`.
Archive parent: `D:\AIGC\retired_workspaces`.
Each archive is a new child directory with an immutable capture identity.
No code repository may contain the archive; no remote is configured for it.

```text
scrum_dashboard/
  scripts/maintenance/archive_workspace.ps1
  scripts/tests/test_workspace_archive.py
  docs/migration/legacy-workspace-retirement.md
  openspec/changes/retire-legacy-standup-workspace/
    proposal.md, design.md, tasks.md, validation.md, delivery.json

retired_workspaces/<capture-id>/          # current Windows user + SYSTEM only
  snapshot/                             # all ordinary files, including .git
  inventory.json                        # paths/bytes/SHA-256/directories/links
  capture.json                          # source/Git identity, private metadata
  history.bundle                        # all Git refs, no external prerequisites
  evidence/                             # copy/restore/dependency test receipts
```

The archive snapshot is frozen donor material, not a second live app or a
Dashboard archive/database. Source absolute paths inside historical receipts
remain historical identifiers. Internal link destinations are ordinary files
already captured; external shared-cache destinations remain external and are
not owned by this migration. Links are represented in the inventory, not
recreated as live pointers into the old directory.

## 2. Maintenance Interface

`pwsh -NoProfile -File scripts/maintenance/archive_workspace.ps1`

| Parameter | Contract |
| --- | --- |
| `-Action Capture` | Requires `-SourceRoot` and a nonexistent `-ArchiveRoot`; copy, verify, then write a successful receipt |
| `-Action Verify` | Requires existing archive; verify manifest, every payload file, directories, Git bundle and private ACL |
| `-SourceRoot <absolute path>` | Required for capture; optional on verify to compare the still-present original |
| `-ArchiveRoot <absolute path>` | Outside all Git roots; no source/archive containment or reparse ancestor |

Success prints bounded JSON with schema `workspace-retirement/1`, result,
file/byte/link counts and inventory/bundle hashes. Failure exits nonzero and
does not issue a successful capture receipt. It never deletes, overwrites an
existing archive, edits the source, reads credentials into output, starts an
application, or executes an archived hook. It does not inspect disk free space.

Capture requires a normal standalone `.git` directory, no alternate object
store, no linked-worktree common directory and no external `core.worktree`.
The original `.git` bytes preserve reflogs/index/config/unreachable objects;
the extra `git bundle --all` preserves portable reachable history and refs.
Bundle creation is not used as a substitute for preserving the dirty tree.

## 3. Integrity And Failure

1. Resolve and validate absolute roots and every existing ancestor before writes.
2. Reject an existing archive and any archive inside a Git working tree.
3. Create a private archive root before writing any payload or inventory.
4. Walk the source without following reparse points. Record every directory,
   file length/SHA-256 and each link's type/target. Verify that each file stayed
   unchanged while its hash was read.
5. Copy ordinary files with native Robocopy, excluding reparse points. Copy
   data/attributes/timestamps, never the source's broad inherited ACL.
6. Verify the copied file set and hashes against the manifest. Compare the
   original again before closing; source changes fail the capture.
7. Create/verify a self-contained bundle, compare all refs, and preserve Git
   status with optional Git index locking disabled.
8. Write `capture.json` last. A partial archive is retained for diagnosis but
   never considered deletion-ready. A later retry uses a new capture directory.

The receipt binds the inventory and bundle hashes. Verify refuses missing,
extra, altered or redirected payload files, unexpected top-level entries and a
modified manifest. Every archive file, including the recursively checked
`evidence` subtree, must remain private to the current user and SYSTEM.
Evidence can accumulate validation outputs but is not an immutable donor-data
authority; its files do not change the snapshot/inventory/bundle hashes. Hashes prove
consistency, not protection against an attacker controlling both the archive
and its receipt. Source/application histories and watermarks are not rewritten.

## 4. Consumer Relocation

The current migration guide provides the archive locator and maps MIG-01..19
to preserved source and existing Dashboard responsibilities. Current navigation
must not require `../chiplet_programmgr`. Frozen `*-source.json` files retain
their original `source_root` and commit, with the new guide as a relocation
index. Historical postmortems are preserved verbatim in the private snapshot;
current docs link through the relocation guide.

Pending code ports use `git show <frozen-commit>:<relative-path>` from the
recovered local Git repo or read the frozen snapshot. Dirty overlays remain
explicitly separate from the frozen commit. Runtime never imports `standup`
or adds the archive to `PYTHONPATH`.

## 5. Readiness And Rollback

The final gate requires source-to-snapshot equality, successful Git recovery,
representative historical report/credential byte checks, zero necessary legacy
runtime references, scoped Dashboard tests under an old-root access guard, and
unchanged unrelated working-tree hashes.

Old-path access is denied inside the isolated validation process because other
Codex sessions currently hold the old workspace. Do not rename underneath or
kill those agents. This is a bounded runtime proof, not a claim to monitor every
Windows process's filesystem calls. Inspect current service/task/shortcut and
environment references separately.

Deletion remains a user-controlled final action after switching/closing old
workspace sessions. A fresh `Verify -SourceRoot` must precede deletion if work
continued after the receipt. Rollback restores `snapshot` to a new protected
directory; recovering an executable legacy deployment is separate from reading
its history and must not silently reactivate old tasks or credentials.
