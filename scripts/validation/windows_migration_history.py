"""Hash-bound read roots for retained historical migration inputs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.validation import windows_qualification_inputs as common
from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_qualification_inputs import QualificationError


@dataclass(frozen=True, slots=True)
class HistoricalInputs:
    root: Path
    repository: str
    marker: Path
    marker_sha256: str

    def file(self, value: str | Path, owned_root: Path, label: str) -> Path:
        path = common.canonical(value, must_exist=True)
        if _inside_file_root(path, owned_root) or _inside_file_root(path, self.root):
            return path
        raise QualificationError(f"{label} is outside owned root or historical inputs")


def _inside_file_root(path: Path, root: Path) -> bool:
    return path != root and path.is_relative_to(root)


def from_migration(migration: dict, *, current_repo: Path, owned_root: Path) -> HistoricalInputs | None:
    if "historical_inputs" not in migration:
        return None
    value = migration["historical_inputs"]
    if not isinstance(value, dict):
        raise QualificationError("historical inputs declaration must be an object")
    marker = value.get("marker")
    if not isinstance(marker, dict):
        raise QualificationError("historical inputs marker must be an object")
    root = common.canonical(value.get("root", ""), must_exist=True)
    if not root.is_dir():
        raise QualificationError("historical inputs root must be a directory")
    current_repo = common.canonical(current_repo, must_exist=True)
    owned_root = common.canonical(owned_root, must_exist=True)
    if root == Path(root.anchor):
        raise QualificationError("historical inputs root must not be a filesystem anchor")
    if common.overlaps(root, current_repo) or common.overlaps(root, owned_root):
        raise QualificationError("historical inputs overlap current source or owned root")
    marker_path = common.canonical(marker.get("path", ""), must_exist=True)
    marker_sha256 = marker.get("sha256")
    if marker_path != root / "owner.json":
        raise QualificationError("historical inputs marker path mismatch")
    if not isinstance(marker_sha256, str):
        raise QualificationError("historical inputs marker hash is missing")
    common.require_hash(marker_path, marker_sha256, "historical inputs marker")
    repository = value.get("repository")
    if not isinstance(repository, str) or not repository:
        raise QualificationError("historical inputs repository label is missing")
    payload = read_json(marker_path)
    if not isinstance(payload, dict):
        raise QualificationError("historical inputs owner marker must be an object")
    if (type(payload.get("schema_version")) is not int
            or payload.get("schema_version") != 1
            or payload.get("owner") != common.OWNER):
        raise QualificationError("historical inputs owner marker is invalid")
    if common.canonical(payload.get("root", ""), must_exist=True) != root:
        raise QualificationError("historical inputs root marker mismatch")
    if payload.get("repository") != repository:
        raise QualificationError("historical inputs repository marker mismatch")
    if (payload.get("real_user_data_allowed") is not False
            or payload.get("external_provider_model_calls_allowed") is not False):
        raise QualificationError("historical inputs marker allows real data or provider calls")
    return HistoricalInputs(root=root, repository=repository, marker=marker_path, marker_sha256=marker_sha256)


def input_file(value: str | Path, owned_root: Path, label: str, historical: HistoricalInputs | None) -> Path:
    if historical is None:
        return common.owned_file(value, owned_root)
    return historical.file(value, owned_root, label)
