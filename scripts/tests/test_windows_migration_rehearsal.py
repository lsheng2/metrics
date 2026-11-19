from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest


OLD_COMMIT = "e" * 40
NEW_COMMIT = "4" * 40
RUN_UUID = "35db79d3-bf52-410f-856f-ead341e83615"
ARCHIVE_ROOT_ID = "11111111-1111-4111-8111-111111111111"
ARCHIVE_AUTHOR = "Synthetic Validation"
ARCHIVE_EMAIL = "synthetic.validation@example.test"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _identity(root: Path, *, commit=OLD_COMMIT, app="python.exe"):
    from scripts.validation.windows_migration_rehearsal import SourceIdentity

    return SourceIdentity(
        repository=root,
        commit=commit,
        app_python=root / "venv" / "Scripts" / app,
        base_python=root / "base-venv" / "Scripts" / "python.exe",
        base_source=root / ".tmp" / "base-source",
        pack_root=root / ".tmp" / "contract-pack",
    )


def _materialize_identity(identity) -> None:
    identity.app_python.parent.mkdir(parents=True, exist_ok=True)
    identity.app_python.write_text("# synthetic interpreter marker", encoding="utf-8")
    if identity.base_python is not None:
        identity.base_python.parent.mkdir(parents=True, exist_ok=True)
        identity.base_python.write_text("# synthetic base interpreter marker", encoding="utf-8")
    if identity.base_source is not None:
        identity.base_source.mkdir(parents=True, exist_ok=True)
    if identity.pack_root is not None:
        identity.pack_root.mkdir(parents=True, exist_ok=True)


def _service_state(run_dir: Path, *, lifecycle_state="stopped") -> None:
    payload = {
        "schema_version": 1,
        "project": "dashboard-full-stack",
        "instance": "qualify",
        "services": {
            "project-app": {
                "pid": 12345,
                "port": 8127,
                "lifecycle_state": lifecycle_state,
                "command": ["python", "serve.py"],
            }
        },
    }
    _write_json(run_dir / "lifecycle" / "dashboard-full-stack-qualify.json", payload)


def _write_archive_identity(run_dir: Path) -> None:
    from project_management.storage.git_safety import write_configuration

    archive_root = run_dir / "archive"
    stage_root = archive_root / "projects" / "p" / "stages" / "s"
    stage_archive = stage_root / "archive"
    stage_hooks = stage_root / "runtime" / "empty-hooks"
    stage_archive.joinpath(".git").mkdir(parents=True, exist_ok=True)
    stage_hooks.mkdir(parents=True, exist_ok=True)
    (stage_archive / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    _write_json(archive_root / "archive-root.json", {
        "schema_version": 1,
        "root_id": ARCHIVE_ROOT_ID,
        "canonical_root": str(archive_root),
        "author_name": ARCHIVE_AUTHOR,
        "author_email": ARCHIVE_EMAIL,
        "branch": "main",
    })
    write_configuration(stage_archive, stage_hooks, ARCHIVE_AUTHOR, ARCHIVE_EMAIL)


def _fixture(tmp_path: Path):
    old_repo = tmp_path / "old-repo"
    current_repo = tmp_path / "current-repo"
    old_repo.mkdir()
    current_repo.mkdir()
    old = _identity(old_repo)
    current = _identity(current_repo, commit=NEW_COMMIT, app="new-python.exe")
    _materialize_identity(old)
    _materialize_identity(current)
    data_root = tmp_path / "old-data"
    run_dir = data_root / RUN_UUID
    run_dir.mkdir(parents=True)
    _write_json(data_root / "owner.json", {
        "schema_version": 1,
        "owner": "dashboard-manual-fullstack-root",
        "repository": str(old_repo),
        "data_root": str(data_root),
    })
    _write_json(run_dir / "owner.json", {
        "schema_version": 1,
        "owner": "dashboard-manual-fullstack",
        "repository": str(old_repo),
        "data_root": str(data_root),
        "run_directory": str(run_dir),
        "run_uuid": RUN_UUID,
    })
    fixture_text = '{"fixture":"vector"}'
    fixture_sha = hashlib.sha256(fixture_text.encode("utf-8")).hexdigest()
    (run_dir / "fixture-vector.json").write_text(fixture_text, encoding="utf-8")
    (run_dir / "catalog.sqlite3").write_bytes(b"catalog")
    (run_dir / "catalog.sqlite3-wal").write_bytes(b"wal")
    (run_dir / "catalog.sqlite3-shm").write_bytes(b"shm")
    (run_dir / "environment" / "state").mkdir(parents=True)
    (run_dir / "environment" / "state" / "state.json").write_text("{}", encoding="utf-8")
    (run_dir / "environment" / "pycache-app").mkdir()
    (run_dir / "environment" / "pycache-app" / "x.pyc").write_bytes(b"pyc")
    _write_archive_identity(run_dir)
    (run_dir / "archive" / "publications").mkdir()
    (run_dir / "archive" / "publications" / "pub.json").write_text('{"publication":1}', encoding="utf-8")
    operations = run_dir / "archive" / "projects" / "p" / "stages" / "s" / "runtime" / "operations"
    operations.mkdir(parents=True)
    (operations / "live.json").write_text("{}", encoding="utf-8")
    (run_dir / "base" / "store").mkdir(parents=True)
    (run_dir / "base" / "store" / "task-runs.db").write_bytes(b"tasks")
    _write_json(run_dir / "base" / "store-owner.json", {
        "schema_version": 1,
        "owner": "dashboard-manual-fullstack-base-store",
        "repository": str(old_repo),
        "data_dir": str(run_dir / "base" / "store"),
        "run_uuid": RUN_UUID,
    })
    _write_json(run_dir / "base" / "connection.json", {"base_url": "http://127.0.0.1:1"})
    (run_dir / "model").mkdir()
    (run_dir / "model" / "connection.json").write_text("{}", encoding="utf-8")
    (run_dir / "logs").mkdir()
    (run_dir / "logs" / "app.log").write_text("old log", encoding="utf-8")
    _service_state(run_dir)
    _write_json(run_dir / "runtime-manifest.json", {
        "schema_version": 1,
        "repository": str(old_repo),
        "run_dir": str(run_dir),
        "app_python": str(old.app_python),
        "base_python": str(old.base_python),
        "base_source": str(old.base_source),
        "pack_root": str(old.pack_root),
        "execution_mode": "synthetic",
        "sdk_version": "0.2.0a1",
        "sdk_wheel_sha256": "a" * 64,
        "sdk_selection_sha256": "b" * 64,
        "contract_pack_manifest_sha256": "c" * 64,
        "base_run_store_id": "store_1",
        "scenario": "single",
        "catalog": {
            "project_id": "p",
            "stage_id": "s",
            "scope_key": "projects.p.stages.s",
            "fixture_vector_sha256": fixture_sha,
        },
        "auth": {"alice": {"username": "SYNTHETIC_ALICE", "password": "SYNTHETIC_ALICE_PASSWORD"}},
        "cookies": {"session": "s", "csrf": "c", "language": "l"},
        "routes": {"project_stage_reports": "/projects/p/stages/s/reports/"},
    })
    return old, current, data_root, run_dir


def test_snapshot_binds_old_source_and_hashes_complete_members(tmp_path):
    from scripts.validation.windows_migration_rehearsal import snapshot_source_run

    old, _, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    members = {item["path"] for item in snapshot.files}

    assert snapshot.run_uuid == RUN_UUID
    assert snapshot.source["commit"] == OLD_COMMIT
    assert "catalog.sqlite3" in members
    assert "catalog.sqlite3-wal" in members
    assert "catalog.sqlite3-shm" in members
    assert "fixture-vector.json" in members
    assert "archive/archive-root.json" in members
    assert "archive/projects/p/stages/s/archive/.git/config" in members
    assert "archive/projects/p/stages/s/runtime/empty-hooks" in snapshot.directories
    assert "archive/projects/p/stages/s/runtime/operations/live.json" in members
    assert "base/store-owner.json" in members
    assert "environment/state/state.json" in members
    assert "environment/pycache-app/x.pyc" not in members
    assert "archive" in snapshot.directories
    assert "environment/state" in snapshot.directories
    assert len({item["path"] for item in snapshot.files}) == len(snapshot.files)


def test_snapshot_rejects_wrong_source_marker(tmp_path):
    from scripts.validation.windows_migration_rehearsal import snapshot_source_run

    old, _, _, run_dir = _fixture(tmp_path)
    owner = json.loads((run_dir / "owner.json").read_text(encoding="utf-8"))
    owner["repository"] = str(tmp_path / "other")
    _write_json(run_dir / "owner.json", owner)

    with pytest.raises(ValueError, match="owner"):
        snapshot_source_run(run_dir, old)


@pytest.mark.parametrize(("matches", "message"), [(True, "live writer"), (False, "unknown ownership")])
def test_snapshot_uses_platform_observation_for_stopped_processes(tmp_path, matches, message):
    from scripts.service_lifecycle_engine import PlatformOperationSet
    from scripts.validation.windows_migration_rehearsal import snapshot_source_run

    old, _, _, run_dir = _fixture(tmp_path)
    _service_state(run_dir, lifecycle_state="ready")
    ops = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: matches,
    )

    with pytest.raises(ValueError, match=message):
        snapshot_source_run(run_dir, old, platform_ops=ops)


def test_snapshot_rejects_live_process_even_when_persisted_state_says_stopped(tmp_path):
    from scripts.service_lifecycle_engine import PlatformOperationSet
    from scripts.validation.windows_migration_rehearsal import snapshot_source_run

    old, _, _, run_dir = _fixture(tmp_path)
    ops = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
    )

    with pytest.raises(ValueError, match="live writer"):
        snapshot_source_run(run_dir, old, platform_ops=ops)


def test_snapshot_rejects_malformed_lifecycle_inventory(tmp_path):
    from scripts.validation.windows_migration_rehearsal import snapshot_source_run

    old, _, _, run_dir = _fixture(tmp_path)
    state_file = run_dir / "lifecycle" / "dashboard-full-stack-qualify.json"
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    payload.pop("schema_version")
    _write_json(state_file, payload)

    with pytest.raises(ValueError, match="lifecycle"):
        snapshot_source_run(run_dir, old)


def test_snapshot_rejects_missing_lifecycle_state_when_operational_records_exist(tmp_path):
    from scripts.validation.windows_migration_rehearsal import snapshot_source_run

    old, _, _, run_dir = _fixture(tmp_path)
    (run_dir / "lifecycle" / "dashboard-full-stack-qualify.json").unlink()
    (run_dir / "lifecycle" / "launches" / "stale").mkdir(parents=True)
    (run_dir / "lifecycle" / "launches" / "stale" / "launch.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="lifecycle"):
        snapshot_source_run(run_dir, old)


def test_new_copy_rebinds_schema2_and_quarantines_legacy_runtime(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, snapshot_source_run
    from project_management.storage.git_safety import validate_configuration

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    copied = copy_snapshot_for_new_host(
        snapshot,
        tmp_path / "new-data",
        current_identity=current,
        old_identity=old,
    )
    dest = Path(copied.destination_run)
    manifest = json.loads((dest / "runtime-manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 2
    assert manifest["repository"] == str(current.repository)
    assert manifest["run_dir"] == str(dest)
    assert manifest["app_python"] == str(current.app_python)
    for retired in ("execution_mode", "base_python", "base_source", "pack_root", "sdk_version",
                    "sdk_wheel_sha256", "sdk_selection_sha256", "contract_pack_manifest_sha256",
                    "base_run_store_id", "model"):
        assert retired not in manifest
    assert not (dest / "base").exists()
    assert not (dest / "archive" / "projects" / "p" / "stages" / "s" / "runtime" / "operations").exists()
    assert (dest / "environment" / "state" / "state.json").is_file()
    assert not (dest / "environment" / "pycache-app").exists()
    assert all(not any((dest / name).iterdir()) for name in ("model", "lifecycle", "logs"))
    backup = dest / "evidence" / "migration-backup" / snapshot.snapshot_id
    assert (backup / "base" / "store-owner.json").is_file()
    assert not (dest / "environment" / "pycache-app").exists()
    assert not (backup / "environment" / "pycache-app").exists()
    assert (backup / "archive" / "projects" / "p" / "stages" / "s" / "runtime" / "operations" / "live.json").is_file()
    archive_root = json.loads((dest / "archive" / "archive-root.json").read_text(encoding="utf-8"))
    assert archive_root == {
        "schema_version": 1,
        "root_id": ARCHIVE_ROOT_ID,
        "canonical_root": str(dest / "archive"),
        "author_name": ARCHIVE_AUTHOR,
        "author_email": ARCHIVE_EMAIL,
        "branch": "main",
    }
    validate_configuration(
        dest / "archive" / "projects" / "p" / "stages" / "s" / "archive",
        dest / "archive" / "projects" / "p" / "stages" / "s" / "runtime" / "empty-hooks",
        ARCHIVE_AUTHOR,
        ARCHIVE_EMAIL,
    )
    source_root = json.loads((run_dir / "archive" / "archive-root.json").read_text(encoding="utf-8"))
    assert source_root["canonical_root"] == str(run_dir / "archive")


def test_old_restore_keeps_schema1_and_rebinds_base_store(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_old_restore, snapshot_source_run
    from project_management.storage.git_safety import validate_configuration

    old, _, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    copied = copy_snapshot_for_old_restore(snapshot, tmp_path / "old-restore-data", old_identity=old)
    dest = Path(copied.destination_run)
    manifest = json.loads((dest / "runtime-manifest.json").read_text(encoding="utf-8"))
    store_owner = json.loads((dest / "base" / "store-owner.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["repository"] == str(old.repository)
    assert manifest["run_dir"] == str(dest)
    assert manifest["base_python"] == str(old.base_python)
    assert not (dest / "base" / "connection.json").exists()
    assert not (dest / "lifecycle").exists()
    assert not (dest / "logs").exists()
    assert not (dest / "model" / "connection.json").exists()
    assert (dest / "base" / "store" / "task-runs.db").is_file()
    assert (Path(copied.backup_root) / "base" / "connection.json").is_file()
    assert (Path(copied.backup_root) / "lifecycle" / "dashboard-full-stack-qualify.json").is_file()
    assert (Path(copied.backup_root) / "logs" / "app.log").is_file()
    assert store_owner == {
        "schema_version": 1,
        "owner": "dashboard-manual-fullstack-base-store",
        "repository": str(old.repository),
        "data_dir": str(dest / "base" / "store"),
        "run_uuid": RUN_UUID,
    }
    archive_root = json.loads((dest / "archive" / "archive-root.json").read_text(encoding="utf-8"))
    assert archive_root["canonical_root"] == str(dest / "archive")
    assert archive_root["root_id"] == ARCHIVE_ROOT_ID
    validate_configuration(
        dest / "archive" / "projects" / "p" / "stages" / "s" / "archive",
        dest / "archive" / "projects" / "p" / "stages" / "s" / "runtime" / "empty-hooks",
        ARCHIVE_AUTHOR,
        ARCHIVE_EMAIL,
    )


@pytest.mark.parametrize("mutation", ["root", "hooks"])
def test_snapshot_rejects_source_archive_root_or_hooks_mismatch(tmp_path, mutation):
    from project_management.storage.git_safety import write_configuration
    from scripts.validation.windows_migration_rehearsal import snapshot_source_run

    old, _, _, run_dir = _fixture(tmp_path)
    if mutation == "root":
        payload = json.loads((run_dir / "archive" / "archive-root.json").read_text(encoding="utf-8"))
        payload["canonical_root"] = str(tmp_path / "other-archive")
        _write_json(run_dir / "archive" / "archive-root.json", payload)
    else:
        stage = run_dir / "archive" / "projects" / "p" / "stages" / "s"
        wrong_hooks = stage / "runtime" / "wrong-hooks"
        wrong_hooks.mkdir()
        write_configuration(stage / "archive", wrong_hooks, ARCHIVE_AUTHOR, ARCHIVE_EMAIL)

    with pytest.raises(ValueError, match="archive"):
        snapshot_source_run(run_dir, old)


def test_copy_rejects_source_drift_and_invalid_inventory_paths(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, snapshot_source_run

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    (run_dir / "catalog.sqlite3").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        copy_snapshot_for_new_host(snapshot, tmp_path / "new-data", current_identity=current, old_identity=old)

    bad = replace(snapshot, files=tuple([*snapshot.files, {**snapshot.files[0], "path": "../escape"}]))
    with pytest.raises(ValueError, match="member path"):
        copy_snapshot_for_new_host(bad, tmp_path / "other-data", current_identity=current, old_identity=old)


def test_copy_rejects_removed_listed_publication(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, snapshot_source_run

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    (run_dir / "archive" / "publications" / "pub.json").unlink()

    with pytest.raises(ValueError, match="hash mismatch"):
        copy_snapshot_for_new_host(snapshot, tmp_path / "new-data", current_identity=current, old_identity=old)


def test_copy_rejects_added_source_member_after_snapshot(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, snapshot_source_run

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    (run_dir / "archive" / "publications" / "new.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="inventory"):
        copy_snapshot_for_new_host(snapshot, tmp_path / "new-data", current_identity=current, old_identity=old)


def test_copy_rejects_omitted_sqlite_sidecar_from_snapshot(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, snapshot_source_run

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    bad = replace(snapshot, files=tuple(item for item in snapshot.files if item["path"] != "catalog.sqlite3-wal"))

    with pytest.raises(ValueError, match="inventory"):
        copy_snapshot_for_new_host(bad, tmp_path / "new-data", current_identity=current, old_identity=old)


def test_copy_rejects_source_write_during_copy(tmp_path, monkeypatch):
    from scripts.validation import windows_migration_rehearsal as rehearsal

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = rehearsal.snapshot_source_run(run_dir, old)
    original = rehearsal.shutil.copy2
    calls = {"count": 0}

    def copy_and_mutate(source, target):
        calls["count"] += 1
        if calls["count"] == 1:
            (run_dir / "archive" / "publications" / "during-copy.json").write_text("{}", encoding="utf-8")
        return original(source, target)

    monkeypatch.setattr(rehearsal.shutil, "copy2", copy_and_mutate)
    with pytest.raises(ValueError, match="inventory"):
        rehearsal.copy_snapshot_for_new_host(snapshot, tmp_path / "new-data", current_identity=current, old_identity=old)


def test_copy_rejects_malformed_normalized_member_path(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, snapshot_source_run

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    replacement = []
    for item in snapshot.files:
        if item["path"] == "archive/projects/p/stages/s/archive/.git/config":
            replacement.append({**item, "path": "archive/projects/p/stages/s/archive/.git//config"})
        else:
            replacement.append(item)
    bad = replace(snapshot, files=tuple(replacement))

    with pytest.raises(ValueError, match="member path"):
        copy_snapshot_for_new_host(bad, tmp_path / "new-data", current_identity=current, old_identity=old)


def test_source_identity_requires_existing_app_python(tmp_path):
    from scripts.validation.windows_migration_rehearsal import SourceIdentity

    source = SourceIdentity(repository=tmp_path, commit=OLD_COMMIT, app_python=tmp_path / "missing.exe")

    with pytest.raises(ValueError, match="app_python"):
        source.as_record()


def test_source_identity_rejects_directory_as_interpreter(tmp_path):
    from scripts.validation.windows_migration_rehearsal import SourceIdentity

    source = SourceIdentity(repository=tmp_path, commit=OLD_COMMIT, app_python=tmp_path)
    with pytest.raises(ValueError, match="interpreter"):
        source.as_record()


def test_copy_rejects_nonempty_or_overlapping_output(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, snapshot_source_run

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "leftover.txt").write_text("not ours", encoding="utf-8")

    with pytest.raises(ValueError, match="nonempty"):
        copy_snapshot_for_new_host(snapshot, occupied, current_identity=current, old_identity=old)
    with pytest.raises(ValueError, match="overlap"):
        copy_snapshot_for_new_host(snapshot, current.repository / "inside", current_identity=current, old_identity=old)


def test_copy_rejects_snapshot_id_path_escape_before_creating_output(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_new_host, snapshot_source_run

    old, current, _, run_dir = _fixture(tmp_path)
    snapshot = snapshot_source_run(run_dir, old)
    forged = replace(
        snapshot, snapshot_id="../escape",
        files=tuple({**item, "snapshot_id": "../escape"} for item in snapshot.files),
    )
    target = tmp_path / "new-data"
    with pytest.raises(ValueError, match="snapshot identity"):
        copy_snapshot_for_new_host(forged, target, current_identity=current, old_identity=old)
    assert not target.exists()


def test_copy_rejects_writer_that_appears_before_post_copy_validation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scripts.validation import windows_migration_rehearsal as rehearsal

    old, current, _, run_dir = _fixture(tmp_path)
    live = [False]
    ops = SimpleNamespace(process_exists=lambda pid: live[0], process_matches_command=lambda pid, argv: True)
    snapshot = rehearsal.snapshot_source_run(run_dir, old, platform_ops=ops)
    original = rehearsal.shutil.copy2

    def copy_then_observe_writer(source, target):
        result = original(source, target)
        live[0] = True
        return result

    monkeypatch.setattr(rehearsal.shutil, "copy2", copy_then_observe_writer)
    with pytest.raises(ValueError, match="live writer"):
        rehearsal.copy_snapshot_for_new_host(
            snapshot, tmp_path / "new-data", current_identity=current, old_identity=old, platform_ops=ops,
        )


def test_old_restore_cannot_write_inside_another_git_checkout(tmp_path):
    from scripts.validation.windows_migration_rehearsal import copy_snapshot_for_old_restore, snapshot_source_run

    old, current, _, run_dir = _fixture(tmp_path)
    (current.repository / ".git").write_text("gitdir: synthetic-linked-worktree", encoding="utf-8")
    snapshot = snapshot_source_run(run_dir, old)
    target = current.repository / "restored-data"
    with pytest.raises(ValueError, match="Git worktree"):
        copy_snapshot_for_old_restore(snapshot, target, old_identity=old)
    assert not target.exists()


@pytest.mark.parametrize("role", ["new", "old"])
def test_preservation_check_covers_all_native_archive_payloads(tmp_path, role):
    from scripts.validation import windows_migration_inventory as inventory
    from scripts.validation import windows_migration_rehearsal as rehearsal

    old, current, _, run = _fixture(tmp_path)
    snapshot = rehearsal.snapshot_source_run(run, old)
    copied = (
        rehearsal.copy_snapshot_for_new_host(snapshot, tmp_path / "copy", current_identity=current, old_identity=old)
        if role == "new" else rehearsal.copy_snapshot_for_old_restore(snapshot, tmp_path / "copy", old_identity=old)
    )
    target = Path(copied.destination_run)
    assert inventory.verify_preserved_archive(target, snapshot, retire_operations=role == "new") > 0
    (target / "archive/publications/pub.json").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="archive"):
        inventory.verify_preserved_archive(target, snapshot, retire_operations=role == "new")
