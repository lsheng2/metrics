# Authoring Source Closure

Date: 2026-11-06. Status: source packaging qualified.
State: [tasks.md](tasks.md), `W6.AUTHOR.SOURCE`.
This is the source-publication prerequisite after DELTA.CORE.REPLAN, not a new feature wave.

## Scope

Publish the complete existing CONTENT, EDIT, REFERENCES, TEMPLATES, HISTORY, DAILY
and bounded DELTA implementation together with required migrations, public API/factories,
local Milkdown assets, build inputs, provider reference adapters and tests.

Exclude 13 unrelated paths: Scope metadata UI/spec/tests, their `main.css` changes,
and `.github/skills/lsheng2-coding/config.json`. The concrete allowlist and excluded
hashes are in `.tmp/authoring-source-20261106/{allowlist,excluded}.json`.
No credentials/runtime data, SDK release bytes, global settings or real provider work
are part of the source packet.

235 initially selected paths matched exact prior review-manifest hashes. Matching
bytes permit reuse of those scoped reviews; they do not imply the whole application
is complete. The remaining changed files receive bounded review or are covered by
the current DAILY/delta receipts. Human docs are synchronized to the current behavior.

## Checks

1. Stage only the explicit allowlist and verify staged paths and whitespace.
2. Verify local editor bundle/package/lock/metafile hashes against its asset manifest.
3. Materialize the staged Git tree into a separate candidate directory using Git archive.
   No hidden untracked source from the development checkout may satisfy its imports.
4. In the candidate, run the existing no-dotenv test entry with explicit module paths:
   collection verifies packaging, selected actual tests verify behavior. Collection
   alone is not reported as product acceptance.
5. Run isolated Django check and migration-drift check against the candidate. Do not
   migrate the user's database or switch the retained 8017 service.
6. Review the bounded source scope and remaining evidence; publish on main under
   the standing user authorization, then verify the remote SHA and 13 excluded hashes.

The current spec/test contract intentionally leaves ASSIST unavailable until its own
profile/candidate/save qualification. Full-workweek, external provider/Outlook and
deployment acceptance remain separate. This source closure does not enable scheduling,
sending, credentials or real model use.

## Receipt

Candidate tree: `aad094cf5a321065a165b6f9bd0794756f4bc1e0`.
Extracted from the staged Git tree into `.tmp/authoring-source-20261106/candidate-final/`.
Current receipt/status documentation is the only subsequent source-packet change.

- 1530 tests collected successfully across project_management/provider_sync/ui_web.
  This is packaging evidence, not 1530 executed tests.
- 33 selected tests and 14 subtests passed in the isolated candidate, including
  delta values/recovery, material integrity, DAILY forms and template corrections.
- 11 Node tests passed for editor codec/undo/stale selection and report JS.
- Django check passed with zero silenced issues. `makemigrations project_management
  --check --dry-run` reported no changes; no user database was migrated.
- Four bundle/package/lock/metafile hashes matched the editor asset manifest.
  Configured file-size gate checked 196 files; staged whitespace passed after
  removing only trailing empty lines in eight existing files.
- 13 excluded file hashes remained identical. The separate ASSIST planning appendix
  is not included in this source packet.
- Independent `.tmp/authoring-source-20261106/review.md`: READY.

The selected environment is SDK0.2.0a1 with the unchanged a2 pack. This proves source
completeness under that environment, not a fresh dependency installation or deployment.
