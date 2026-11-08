# Retirement Validation Cases

This gate qualifies directory retirement, not the complete reporting product.
One real capture and one scoped consumer run are sufficient absent new failures.

| ID | Layer | Exact scenario and required observation |
| --- | --- | --- |
| RET-01 | L1 maintenance | Synthetic Git repo with two commits, tracked edit, untracked and ignored secret/binary, empty directory; snapshot matches all bytes and bundle clone recovers refs; no source change |
| RET-02 | L1 maintenance | Replace/delete/add a payload file after capture; Verify fails and original receipt is unchanged |
| RET-03 | L1 maintenance | Modify original after capture; Verify with SourceRoot fails, archive-only Verify remains valid |
| RET-04 | L0/path + L1 | Existing target, relative path, nested source/target, Git-contained target or reparse ancestor; refuse without modifying source or target |
| RET-05 | L1 filesystem | Internal and external junctions; inventory records targets, snapshot has no live link, external secret marker is never copied |
| RET-06 | L1 security | Current user/SYSTEM-only archive ACL; secret inherits that policy, output omits secret; broad payload/evidence ACL or an unexpected top-level entry makes Verify fail |
| RET-07 | L1 integrity | Edited inventory or missing/changed bundle; Verify fails rather than trusting counts |
| RET-08 | L1 real data | All actual ordinary files hash-identical, every link accounted for, dirty/untracked/ignored files included; zero truncation/exclusion of ordinary files |
| RET-09 | L1 Git recovery | Clone `history.bundle`; recovered HEAD/all refs match source, `git fsck --full` succeeds; raw snapshot retains Git index and reflogs |
| RET-10 | L2 app | Existing no-dotenv runner, installed SDK0.2, old-root open/list/chdir/subprocess access forbidden; selected source-observation/publication/recovery tests pass |
| RET-11 | configuration | No active source import, editable/.pth pointer, secret reader, service/task or owned launcher requires old root; historical literals classified separately |
| RET-12 | L0 governance | Current links resolve, provenance unchanged, 13 unrelated files unchanged, scoped OpenSpec/size/whitespace pass |
| RET-13 | independent review | Review exact changed files and capture/dependency receipts; no unresolved loss, exposure or false completion finding |

RET-10 uses existing tests in
`project_management/tests/test_report_source_observation_publication.py`,
`project_management/tests/test_report_user_workflow_publication.py`,
`project_management/tests/test_report_recovery.py`, and
`ui_web/tests/test_report_recovery_views.py`.
Select the final node list after collection; use a fresh evidence XML.
The filesystem guard rejects the old root in Python file/directory operations,
imports and subprocess command/cwd arguments. It is not OS-wide instrumentation.

Do not run the whole week, S1 performance campaign, all Base tests, browser editor
matrix or a live provider/model for a maintenance-only change. Existing product
qualification gaps remain explicitly outside this retirement receipt.

Run capture/verification with no source writers. If a source differs, retain the
failed archive, identify that writer and use a new capture; never silently
refresh a frozen archive or weaken the equality check.
