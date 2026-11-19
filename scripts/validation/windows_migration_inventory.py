"""Source identity, liveness and inventory guards for migration rehearsal."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
import re
import uuid

from project_management.app.domain.captures import ArchiveError
from project_management.storage.git_safety import validate_configuration, write_configuration
from scripts.service_lifecycle_engine import FilesystemLifecycleStateStore, LifecycleStateStoreError, PlatformOperationSet
from scripts.validation.project_full_stack import INSTANCE, PROJECT_NAME
from scripts.validation.project_full_stack_support import (
    OWNER,
    ROOT_OWNER,
    UUID_TEXT,
    digest_file,
    is_reparse_or_symlink,
    read_json,
    reject_reparse_components,
)


SNAPSHOT_SCHEMA = 1
MANDATORY_FILES = ("owner.json", "runtime-manifest.json", "catalog.sqlite3", "fixture-vector.json")
SQLITE_SIDECARS = ("catalog.sqlite3-wal", "catalog.sqlite3-shm")
MANDATORY_DIRECTORIES = ("archive", "environment/state")
OPTIONAL_DIRECTORIES = ("base", "lifecycle", "logs", "model")
INVENTORY_ROOTS = ("environment/state", "archive", *OPTIONAL_DIRECTORIES)


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    repository: Path
    commit: str
    app_python: Path
    base_python: Path | None = None
    base_source: Path | None = None
    pack_root: Path | None = None
    environment_digest: str | None = None

    def as_record(self) -> dict:
        if not self.commit or len(self.commit) < 7:
            raise ValueError("source commit must be explicit")
        record = {
            "repository": str(canonical(self.repository, must_exist=True, label="repository")),
            "commit": self.commit,
            "app_python": str(canonical(self.app_python, must_exist=True, label="app_python")),
            "base_python": _optional_path(self.base_python, must_exist=True, label="base_python"),
            "base_source": _optional_path(self.base_source, must_exist=True, label="base_source"),
            "pack_root": _optional_path(self.pack_root, must_exist=True, label="pack_root"),
            "environment_digest": self.environment_digest,
            "source_commit_verification": "external_admission_required",
        }
        for key in ("app_python", "base_python"):
            if record[key] is not None and not Path(record[key]).is_file():
                raise ValueError(f"{key} interpreter must be a file")
        return record


@dataclass(frozen=True, slots=True)
class MigrationSnapshot:
    schema_version: int
    snapshot_id: str
    created_at: str
    source: dict
    data_root: str
    run_dir: str
    run_uuid: str
    files: tuple[dict, ...]
    directories: tuple[str, ...]


def snapshot_source_run(run_dir: Path | str, source_identity: SourceIdentity, *,
                        platform_ops: PlatformOperationSet | None = None) -> MigrationSnapshot:
    source = source_identity.as_record()
    run, data_root, manifest = validate_source_run(run_dir, source, platform_ops=platform_ops)
    snapshot_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    directories, paths = inventory_paths(run)
    files = tuple(file_entry(run, path, snapshot_id, created_at) for path in paths)
    snapshot = MigrationSnapshot(SNAPSHOT_SCHEMA, snapshot_id, created_at, source, str(data_root), str(run), run.name, files, directories)
    validate_snapshot(snapshot, source)
    if digest_file(run / "fixture-vector.json") != manifest["catalog"].get("fixture_vector_sha256"):
        raise ValueError("runtime manifest vector identity mismatch")
    return snapshot


def validate_source_run(run_dir: Path | str, identity: dict, *,
                        platform_ops: PlatformOperationSet | None = None) -> tuple[Path, Path, dict]:
    run = canonical(run_dir, must_exist=True, label="run_dir")
    data_root = validate_source_owner(run, identity)
    manifest = validate_source_manifest(run, identity)
    validate_archive_bindings(run)
    assert_no_live_writers(run, platform_ops or PlatformOperationSet())
    return run, data_root, manifest


def canonical(value: Path | str | None, *, must_exist: bool, label: str = "path") -> Path:
    if value is None:
        raise ValueError(f"{label} is required")
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    reject_reparse_components(path)
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as error:
        raise ValueError(f"{label} path cannot be resolved") from error
    if resolved != path.absolute():
        raise ValueError(f"{label} must be canonical")
    return resolved


def overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def root_owner(root: Path, identity: dict) -> dict:
    return {"schema_version": 1, "owner": ROOT_OWNER, "repository": identity["repository"], "data_root": str(root)}


def run_owner(run_dir: Path, data_root: Path, identity: dict) -> dict:
    return {
        "schema_version": 1,
        "owner": OWNER,
        "repository": identity["repository"],
        "data_root": str(data_root),
        "run_directory": str(run_dir),
        "run_uuid": run_dir.name,
    }


def validate_source_owner(run_dir: Path, identity: dict) -> Path:
    if UUID_TEXT.fullmatch(run_dir.name) is None:
        raise ValueError("source run path must end in a UUID")
    owner = read_json(run_dir / "owner.json")
    data_root = canonical(owner.get("data_root"), must_exist=True, label="data_root")
    if run_dir.parent != data_root or owner != run_owner(run_dir, data_root, identity):
        raise ValueError("source run owner does not match pinned source")
    marker = data_root / "owner.json"
    if not marker.is_file() or read_json(marker) != root_owner(data_root, identity):
        raise ValueError("source root owner marker is invalid")
    return data_root


def validate_source_manifest(run_dir: Path, identity: dict) -> dict:
    manifest = read_json(run_dir / "runtime-manifest.json")
    if manifest.get("repository") != identity["repository"] or manifest.get("run_dir") != str(run_dir):
        raise ValueError("runtime manifest source identity mismatch")
    if manifest.get("app_python") != identity["app_python"]:
        raise ValueError("runtime manifest app interpreter mismatch")
    for key in ("base_python", "base_source", "pack_root"):
        if identity.get(key) is not None and manifest.get(key) != identity[key]:
            raise ValueError(f"runtime manifest {key} mismatch")
    if not isinstance(manifest.get("catalog"), dict):
        raise ValueError("runtime manifest catalog is missing")
    return manifest


def assert_no_live_writers(run_dir: Path, platform_ops: PlatformOperationSet) -> None:
    state_dir = run_dir / "lifecycle"
    state_file = state_dir / f"{PROJECT_NAME}-{INSTANCE}.json"
    if not state_file.exists():
        if state_dir.exists() and any(state_dir.iterdir()):
            raise ValueError("lifecycle inventory is missing persisted service state")
        return
    try:
        payload = FilesystemLifecycleStateStore(state_dir).read_json(state_file)
    except LifecycleStateStoreError as error:
        raise ValueError("lifecycle inventory state is invalid") from error
    services = payload.get("services")
    if not isinstance(services, dict):
        raise ValueError("lifecycle inventory services payload is invalid")
    for service, state in services.items():
        if not isinstance(state, dict) or "pid" not in state or "lifecycle_state" not in state:
            raise ValueError(f"lifecycle inventory record is invalid for {service}")
        pid = int(state["pid"])
        if not platform_ops.process_exists(pid):
            continue
        command = tuple(str(part) for part in state.get("command", ()))
        if not command or not platform_ops.process_matches_command(pid, command):
            raise ValueError(f"unknown ownership for persisted service {service}")
        raise ValueError(f"live writer still owns persisted service {service}")


def inventory_paths(run_dir: Path) -> tuple[tuple[str, ...], tuple[Path, ...]]:
    for relative in (*MANDATORY_FILES, *MANDATORY_DIRECTORIES):
        if not (run_dir / relative).exists():
            raise ValueError(f"snapshot member is missing: {relative}")
    directories: set[str] = set()
    files: dict[str, Path] = {}
    for name in (*MANDATORY_FILES, *SQLITE_SIDECARS):
        path = run_dir / name
        if path.exists():
            add_file(run_dir, path, files)
    for name in INVENTORY_ROOTS:
        root = run_dir / name
        if root.exists():
            collect_tree(run_dir, root, directories, files)
    return tuple(sorted(directories)), tuple(files[key] for key in sorted(files))


def verify_snapshot_inventory(root: Path, snapshot: MigrationSnapshot) -> tuple[dict, ...]:
    expected = {member_key(item["path"]): item for item in snapshot.files}
    for item in snapshot.files:
        path = root / member_path(str(item["path"]))
        reject_member_path(path)
        if not path.is_file() or path.stat().st_size != int(item["size"]) or digest_file(path) != item["sha256"]:
            raise ValueError(f"hash mismatch for snapshot member {item['path']}")
    directories, paths = inventory_paths(root)
    current = tuple({"path": path.relative_to(root).as_posix(), "size": path.stat().st_size, "sha256": digest_file(path)}
                    for path in paths)
    observed = {member_key(item["path"]): item for item in current}
    if set(observed) != set(expected) or directories != snapshot.directories:
        raise ValueError("snapshot inventory mismatch")
    for key, item in observed.items():
        old = expected[key]
        if item["size"] != old["size"] or item["sha256"] != old["sha256"]:
            raise ValueError(f"hash mismatch for snapshot member {item['path']}")
    return current


def verify_preserved_archive(root: Path, snapshot: MigrationSnapshot, *, retire_operations: bool) -> int:
    checked = 0
    for item in snapshot.files:
        relative = item["path"]
        if not relative.startswith("archive/") or relative == "archive/archive-root.json":
            continue
        if re.fullmatch(r"archive/projects/[^/]+/stages/[^/]+/archive/\.git/config", relative):
            continue
        path = root / member_path(relative)
        reject_member_path(path)
        if retire_operations and "/runtime/operations/" in relative:
            if path.exists():
                raise ValueError("legacy archive operation remains active")
            continue
        if not path.is_file() or digest_file(path) != item["sha256"]:
            raise ValueError(f"native archive payload changed: {relative}")
        checked += 1
    if not checked:
        raise ValueError("no native archive payload was verified")
    return checked


def file_entry(run_dir: Path, path: Path, snapshot_id: str, created_at: str) -> dict:
    return {
        "path": path.relative_to(run_dir).as_posix(),
        "size": path.stat().st_size,
        "sha256": digest_file(path),
        "snapshot_id": snapshot_id,
        "snapshot_created_at": created_at,
    }


def validate_snapshot(snapshot: MigrationSnapshot, expected_source: dict) -> None:
    if not isinstance(snapshot.snapshot_id, str) or UUID_TEXT.fullmatch(snapshot.snapshot_id) is None:
        raise ValueError("snapshot identity must be a canonical UUID")
    if snapshot.schema_version != SNAPSHOT_SCHEMA or snapshot.source != expected_source:
        raise ValueError("snapshot source identity mismatch")
    if UUID_TEXT.fullmatch(snapshot.run_uuid) is None or Path(snapshot.run_dir).name != snapshot.run_uuid:
        raise ValueError("snapshot run identity is invalid")
    required = set(MANDATORY_FILES)
    for sidecar in SQLITE_SIDECARS:
        if Path(snapshot.run_dir, sidecar).exists():
            required.add(sidecar)
    members = {str(item.get("path")) for item in snapshot.files}
    if not required.issubset(members) or not set(MANDATORY_DIRECTORIES).issubset(snapshot.directories):
        raise ValueError("snapshot inventory is incomplete")
    seen: set[str] = set()
    for item in snapshot.files:
        key = member_key(str(item.get("path", "")))
        if key in seen:
            raise ValueError("duplicate snapshot member path")
        seen.add(key)
        if item.get("snapshot_id") != snapshot.snapshot_id or item.get("snapshot_created_at") != snapshot.created_at:
            raise ValueError("mixed snapshot inventory")
        if len(str(item.get("sha256", ""))) != 64:
            raise ValueError("snapshot hash is invalid")
    for directory in snapshot.directories:
        member_path(directory)


def validate_archive_bindings(run_dir: Path) -> dict:
    archive = run_dir / "archive"
    marker = archive / "archive-root.json"
    if not marker.is_file():
        raise ValueError("archive root marker is missing")
    payload = read_json(marker)
    if payload.get("schema_version") != 1 or payload.get("canonical_root") != str(archive):
        raise ValueError("archive root marker is invalid")
    if payload.get("branch") != "main" or not payload.get("author_name") or not payload.get("author_email"):
        raise ValueError("archive root marker is incomplete")
    try:
        uuid.UUID(str(payload.get("root_id")))
    except ValueError:
        raise ValueError("archive root marker id is invalid") from None
    configs = _stage_git_configs(archive)
    if not configs:
        raise ValueError("archive git configuration is missing")
    for stage_archive, hooks in configs:
        try:
            validate_configuration(stage_archive, hooks, payload["author_name"], payload["author_email"])
        except ArchiveError as error:
            raise ValueError("archive git configuration is invalid") from error
    return payload


def rebind_archive_copy(run_dir: Path) -> None:
    archive = run_dir / "archive"
    marker = archive / "archive-root.json"
    payload = read_json(marker)
    payload["canonical_root"] = str(archive)
    from scripts.validation.project_full_stack_support import write_json
    write_json(marker, payload, replace=True)
    for stage_archive, hooks in _stage_git_configs(archive):
        write_configuration(stage_archive, hooks, payload["author_name"], payload["author_email"])
    validate_archive_bindings(run_dir)


def member_path(value: str) -> Path:
    if not value or "\\" in value or ":" in value or "//" in value:
        raise ValueError("member path is invalid")
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("member path is invalid")
    return Path(*pure.parts)


def member_key(value: str) -> str:
    return member_path(value).as_posix().lower()


def reject_member_path(path: Path) -> None:
    reject_reparse_components(path)
    if is_reparse_or_symlink(path):
        raise ValueError("refusing reparse or symlink snapshot member")


def collect_tree(run_dir: Path, root: Path, directories: set[str], files: dict[str, Path]) -> None:
    reject_member_path(root)
    directories.add(root.relative_to(run_dir).as_posix())
    for path in root.rglob("*"):
        reject_member_path(path)
        if path.is_dir():
            directories.add(path.relative_to(run_dir).as_posix())
        elif path.is_file():
            add_file(run_dir, path, files)


def add_file(run_dir: Path, path: Path, files: dict[str, Path]) -> None:
    reject_member_path(path)
    key = member_key(path.relative_to(run_dir).as_posix())
    if key in files:
        raise ValueError("duplicate snapshot member path")
    files[key] = path


def _optional_path(value: Path | None, *, must_exist: bool, label: str) -> str | None:
    return str(canonical(value, must_exist=must_exist, label=label)) if value else None


def _stage_git_configs(archive_root: Path) -> tuple[tuple[Path, Path], ...]:
    result = []
    for config in sorted(archive_root.glob("projects/*/stages/*/archive/.git/config")):
        stage_root = config.parents[2]
        result.append((stage_root / "archive", stage_root / "runtime" / "empty-hooks"))
    return tuple(result)
