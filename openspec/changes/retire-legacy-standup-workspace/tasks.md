# Legacy Workspace Retirement Execution Plan

> Execute this one ledger with Superpowers planning, TDD and completion checks.
> The user authorized reversible migration through deletion readiness on 2026-11-08.

Goal: remove the legacy checkout as a dependency without losing its useful bytes.
Architecture: active Dashboard plus a private immutable donor archive, not two apps.
Tech stack: PowerShell 7, Git, Robocopy, SHA-256, existing pytest/SDK environment.
Spec: [design](design.md) and [requirements](specs/workspace-retirement/spec.md).

## Global Constraints

- Source read-only; preserve all ordinary files, including dirty/ignored data.
- Never follow links, delete the source, check free disk space, or export data.
- Existing 13 unrelated Dashboard paths stay unchanged.
- No real Jira/model calls, production database writes or task activation.
- Product backlog status stays in the provider-neutral reporting ledger.

## R1: Inventory And Plan

Files: this change; `docs/migration/legacy-workspace-retirement.md`.
Consumes: actual two-repository state, source filesystem and process inventory.
Produces: fixed archive policy, mapping, failure criteria and validation cases.

- [x] Read both contracts/current guides and verify old HEAD, remote gap and dirty files.
- [x] Inspect ordinary files, reparse targets, Git store boundaries and current runtime references.
- [x] Specify exact maintenance interface, archive ownership and no-feature-parity claim.
- [x] Run scoped OpenSpec structure check; final link check remains in R4.

## R2: Protected Capture And Recovery

Files: `scripts/maintenance/archive_workspace.ps1`,
`scripts/tests/test_workspace_archive.py`; private archive outside the code repo.
Consumes: explicit absolute source/archive roots.
Produces: verified `workspace-retirement/1` snapshot, bundle and inventory.

- [x] Write synthetic tests for complete capture, private ACL, corruption/extra-file,
  source drift, containment/existing-target refusal and non-followed links.
- [x] Run the scoped archive tests and observe RED (maintenance command absent).
- [x] Implement the two-action maintenance command; final suite: 17 passed.
- [x] Capture the real source once; 128752 files / 2059470928 bytes, all ordinary bytes matched.
- [x] Clone the bundle into a separate private recovery directory: exact HEAD, 2 refs,
  85 commits and `git fsck --full` passed; 7 file samples recovered without the source.

## R3: Remove Active Dependencies

Files: migration guide, reporting `migration-catalog.md`, `execution-history.md`,
current README navigation, small relocation/delivery receipt.
Consumes: verified archive identity and source inventory.
Produces: current and future development no longer needs the old checkout path.

- [x] Map all MIG families and unique dirty/research material to the planned snapshot paths.
- [x] Replace active cross-directory links with the relocation guide; retain immutable provenance.
- [x] Inspect config/installed-package pointers, services/tasks and owned launchers.
- [x] Verify no active consumer requires the old source or its secret-file path:
  current runtime/config/database/environment/launcher scopes have zero matches.

## R4: Independent Dashboard And Final Gate

Consumes: R2 successful capture, R3 locator and current reporting SDK interpreter.
Produces: original-preservation, independent-runtime and deletion-readiness evidence.

- [x] Run selected capture/publication/recovery consumers with old-root access denied,
  no dotenv and networking disabled: 17 passed, 2 guard counterexamples passed,
  zero actual legacy-path or network attempts.
- [x] Read representative original report/source/credential bytes from recovery, not the source path.
- [x] Verify the complete archive again with repaired tool; source metadata unchanged,
  13 protected paths and 4 frozen manifests unchanged; 61 local links and scoped size/parser checks pass.
- [x] Obtain an independent bounded review and address actual findings; final receipt/data gate approved.
- [x] Write delivery receipt/current guide with counts, evidence and deletion prerequisites.
- [ ] Publish only allowlisted non-sensitive maintenance/docs/test changes if existing origin authorization applies.

Stop after the directory is deletion-ready. Do not delete it or resume other work.

## Evidence Frontier

Archive: `D:\AIGC\retired_workspaces\chiplet_programmgr-20261108`.
The original capture used tool hash `7ff0923bcaff42e8184cd707ed36f2ce7af8210e7d4ad9cc0b062dbb14fa142b`.
One independent P1 found missing evidence-directory ACL coverage; two real RED
counterexamples preceded the fix, the targeted 3-case run passed, and the final
17-case suite passed. Independent recheck closed P1 without new findings.
The fixed tool completed final full archive verification in 128.18 seconds; no
recopy or business rerun was needed because the preserved payload algorithm did not change.
Raw evidence is private under `evidence/retirement-validation/`; the final
delivery receipt links the exact files and distinguishes capture from final verification.
The independent receipt/data review accepted deletion readiness with no P0-P3 blockers.
All technical migration work is complete. The source remains in place by design;
no product import, feature parity, off-machine backup or live qualification is claimed.
