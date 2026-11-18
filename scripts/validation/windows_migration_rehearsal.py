"""Safe copy and rebind primitives for Windows migration rehearsal."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.service_lifecycle_engine import PlatformOperationSet
from scripts.validation.project_full_stack_support import validate_data_root, write_json
from scripts.validation.windows_migration_inventory import (
    MigrationSnapshot,
    SourceIdentity,
    canonical,
    member_path,
    overlaps,
    rebind_archive_copy,
    root_owner,
    run_owner,
    snapshot_source_run,
    validate_snapshot,
    validate_source_run,
    verify_snapshot_inventory,
)


BASE_STORE_OWNER = "dashboard-manual-fullstack-base-store"
COPY_SCHEMA = 1
NEW_MANIFEST_KEEP = ("scenario", "catalog", "auth", "cookies", "routes", "lifetime_seconds")
NEW_EMPTY_DIRS = ("model", "lifecycle", "logs")


@dataclass(frozen=True, slots=True)
class SnapshotCopyMap:
    schema_version: int
    snapshot_id: str
    mode: str
    source_run: str
    destination_data_root: str
    destination_run: str
    source_verified_before: tuple[dict, ...]
    source_verified_after: tuple[dict, ...]
    copied_files: tuple[dict, ...]
    backup_root: str | None


def copy_snapshot_for_new_host(snapshot: MigrationSnapshot, destination_data_root: Path | str, *,
                               current_identity: SourceIdentity, old_identity: SourceIdentity,
                               platform_ops: PlatformOperationSet | None = None) -> SnapshotCopyMap:
    current = current_identity.as_record()
    old = old_identity.as_record()
    return _copy_snapshot(snapshot, destination_data_root, mode="new", destination_identity=current,
                          old_identity=old, current_identity=current, platform_ops=platform_ops)


def copy_snapshot_for_old_restore(snapshot: MigrationSnapshot, destination_data_root: Path | str, *,
                                  old_identity: SourceIdentity,
                                  platform_ops: PlatformOperationSet | None = None) -> SnapshotCopyMap:
    old = old_identity.as_record()
    return _copy_snapshot(snapshot, destination_data_root, mode="old", destination_identity=old,
                          old_identity=old, current_identity=None, platform_ops=platform_ops)


def _copy_snapshot(snapshot: MigrationSnapshot, destination_data_root: Path | str, *, mode: str,
                   destination_identity: dict, old_identity: dict, current_identity: dict | None,
                   platform_ops: PlatformOperationSet | None) -> SnapshotCopyMap:
    validate_snapshot(snapshot, old_identity)
    source_run, _, _ = validate_source_run(snapshot.run_dir, old_identity, platform_ops=platform_ops)
    source_before = verify_snapshot_inventory(source_run, snapshot)
    data_root = _prepare_destination_root(destination_data_root, destination_identity, snapshot, current_identity)
    destination_run = data_root / snapshot.run_uuid
    if destination_run.exists():
        raise ValueError("destination run output already exists")
    destination_run.mkdir()
    _copy_members(source_run, destination_run, snapshot)
    copied = verify_snapshot_inventory(destination_run, snapshot)
    source_after = verify_snapshot_inventory(source_run, snapshot)
    validate_source_run(source_run, old_identity, platform_ops=platform_ops)
    if source_before != source_after:
        raise ValueError("source inventory changed during copy")
    backup = _rebind_new_copy(destination_run, data_root, snapshot, destination_identity) if mode == "new" else None
    if mode == "old":
        backup = _rebind_old_restore(destination_run, data_root, snapshot, destination_identity)
    if backup is None:
        raise ValueError("copy mode is invalid")
    return SnapshotCopyMap(COPY_SCHEMA, snapshot.snapshot_id, mode, snapshot.run_dir, str(data_root),
                           str(destination_run), source_before, source_after, copied, str(backup))


def _copy_members(source_run: Path, destination_run: Path, snapshot: MigrationSnapshot) -> None:
    for directory in snapshot.directories:
        (destination_run / member_path(directory)).mkdir(parents=True, exist_ok=True)
    for item in snapshot.files:
        source = source_run / member_path(item["path"])
        target = destination_run / member_path(item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _prepare_destination_root(destination_data_root: Path | str, destination_identity: dict,
                              snapshot: MigrationSnapshot, current_identity: dict | None) -> Path:
    root = canonical(destination_data_root, must_exist=False, label="destination_data_root")
    protected = [
        canonical(snapshot.run_dir, must_exist=True, label="snapshot_run"),
        canonical(snapshot.data_root, must_exist=True, label="snapshot_data_root"),
        canonical(snapshot.source["repository"], must_exist=True, label="snapshot_repository"),
        canonical(destination_identity["repository"], must_exist=True, label="destination_repository"),
    ]
    if current_identity is not None:
        protected.append(canonical(current_identity["repository"], must_exist=True, label="current_repository"))
    if any(overlaps(root, item) for item in protected):
        raise ValueError("destination output overlaps source or repository")
    validate_data_root(root)
    if root.exists():
        if not root.is_dir():
            raise ValueError("destination output is not a directory")
        if any(root.iterdir()):
            raise ValueError("destination output is nonempty")
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "owner.json", root_owner(root, destination_identity))
    return root


def _rebind_new_copy(run_dir: Path, data_root: Path, snapshot: MigrationSnapshot, identity: dict) -> Path:
    backup = _backup_root(run_dir, snapshot)
    for name in ("base", "model", "lifecycle", "logs"):
        _move_to_backup(run_dir, Path(name), backup)
    for operations in sorted((run_dir / "archive").glob("**/runtime/operations"), key=lambda item: len(item.parts), reverse=True):
        _move_to_backup(run_dir, operations.relative_to(run_dir), backup)
    for name in NEW_EMPTY_DIRS:
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    (run_dir / "environment").mkdir(exist_ok=True)
    rebind_archive_copy(run_dir)
    write_json(run_dir / "owner.json", run_owner(run_dir, data_root, identity), replace=True)
    old_manifest = _read_json(run_dir / "runtime-manifest.json")
    manifest = {key: old_manifest[key] for key in NEW_MANIFEST_KEEP if key in old_manifest}
    manifest.update({"schema_version": 2, "repository": identity["repository"],
                     "run_dir": str(run_dir), "app_python": identity["app_python"]})
    write_json(run_dir / "runtime-manifest.json", manifest, replace=True)
    return backup


def _rebind_old_restore(run_dir: Path, data_root: Path, snapshot: MigrationSnapshot, identity: dict) -> Path:
    backup = _backup_root(run_dir, snapshot)
    for relative in (Path("base") / "connection.json", Path("model"), Path("lifecycle"), Path("logs")):
        _move_to_backup(run_dir, relative, backup)
    rebind_archive_copy(run_dir)
    write_json(run_dir / "owner.json", run_owner(run_dir, data_root, identity), replace=True)
    manifest = _read_json(run_dir / "runtime-manifest.json")
    if manifest.get("schema_version") != 1:
        raise ValueError("old restore requires a schema-1 manifest")
    manifest.update({"repository": identity["repository"], "run_dir": str(run_dir), "app_python": identity["app_python"]})
    for key in ("base_python", "base_source", "pack_root"):
        if identity.get(key) is not None:
            manifest[key] = identity[key]
    write_json(run_dir / "runtime-manifest.json", manifest, replace=True)
    _rebind_base_store(run_dir, snapshot, identity)
    return backup


def _rebind_base_store(run_dir: Path, snapshot: MigrationSnapshot, identity: dict) -> None:
    store = run_dir / "base" / "store"
    marker = run_dir / "base" / "store-owner.json"
    if store.exists() and not marker.exists():
        raise ValueError("old restore Base store marker is missing")
    if marker.exists():
        write_json(marker, {"schema_version": 1, "owner": BASE_STORE_OWNER,
                            "repository": identity["repository"], "data_dir": str(store),
                            "run_uuid": snapshot.run_uuid}, replace=True)


def _backup_root(run_dir: Path, snapshot: MigrationSnapshot) -> Path:
    backup = run_dir / "evidence" / "migration-backup" / snapshot.snapshot_id
    backup.mkdir(parents=True, exist_ok=True)
    return backup


def _move_to_backup(run_dir: Path, relative: Path, backup: Path) -> None:
    source = run_dir / relative
    if not source.exists():
        return
    target = backup / relative
    source = canonical(source, must_exist=True, label="backup_source")
    target = canonical(target, must_exist=False, label="backup_destination")
    if not source.is_relative_to(run_dir.resolve()) or not target.is_relative_to(backup.resolve()):
        raise ValueError("backup move escapes owned copy")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


def _read_json(path: Path) -> dict:
    from scripts.validation.project_full_stack_support import read_json
    return read_json(path)


if __name__ == "__main__":
    from scripts.validation.windows_migration_driver import main
    raise SystemExit(main())
