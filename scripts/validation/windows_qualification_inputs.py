"""Input and identity validation for Windows runtime qualification."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from scripts.validation import windows_install_smoke as install_smoke
from scripts.validation.project_full_stack_support import read_json, reject_reparse_components


ROOT = Path(__file__).resolve().parents[2]
OWNER = "mdb2-windows-closure"


class QualificationError(RuntimeError):
    pass


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def canonical(value: str | Path, *, must_exist: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise QualificationError("path must be absolute")
    reject_reparse_components(path)
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as error:
        raise QualificationError("path cannot be resolved") from error
    if resolved != path.absolute():
        raise QualificationError("path must be canonical")
    return resolved


def within(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def path_in_allowed_roots(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(within(path, root) for root in roots)


def overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def owned_file(value: str | Path, root: Path, *, must_exist: bool = True) -> Path:
    path = canonical(value, must_exist=must_exist)
    if path == root or not path.is_relative_to(root):
        raise QualificationError("path is outside the owned root")
    return path


def require_hash(path: Path, expected: str, label: str) -> None:
    if digest_file(path) != expected:
        raise QualificationError(f"{label} hash mismatch")


def validate_owner(root: Path, marker: Path, repo: Path) -> None:
    if marker != root / "owner.json":
        raise QualificationError("unexpected owner marker")
    payload = read_json(marker)
    if payload.get("owner") != OWNER:
        raise QualificationError("wrong owner")
    if canonical(payload.get("root", ""), must_exist=True) != root:
        raise QualificationError("owner root mismatch")
    if canonical(payload.get("repository", ""), must_exist=True) != repo:
        raise QualificationError("owner repository mismatch")


def validate_runtime_wheel(wheel: Path, source: dict, candidate: dict) -> None:
    try:
        install_smoke.validate_wheel(wheel, candidate)
    except Exception as error:
        raise QualificationError(str(error)) from error
    manifest = read_json(ROOT / "ai_host" / "runtime_artifact.json")
    if candidate.get("source_commit") != manifest.get("sourceCommit"):
        raise QualificationError("candidate source commit mismatch")


def source_file_path(repo: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        result = canonical(path, must_exist=True)
        if not result.is_relative_to(repo):
            raise QualificationError("source file is outside repository")
        return result
    if any(part in {"", ".", ".."} for part in path.parts):
        raise QualificationError("invalid source file path")
    return canonical(repo / path, must_exist=True)


def validate_frozen_hashes(repo: Path, source: dict, fixtures: dict, roots: tuple[Path, ...]) -> None:
    source_files = source.get("files") or []
    fixture_files = fixtures.get("files") or []
    if not source_files:
        raise QualificationError("source files must be bound")
    if not fixture_files:
        raise QualificationError("fixture files must be bound")
    vector = fixtures.get("fixture_vector") or {}
    vector_path = canonical(vector.get("path", ""), must_exist=True)
    if not path_in_allowed_roots(vector_path, roots):
        raise QualificationError("fixture vector is outside allowed roots")
    require_hash(vector_path, vector.get("sha256", ""), "fixture vector")
    if fixtures.get("fixture_vector_sha256") != vector.get("sha256"):
        raise QualificationError("fixture vector hash mismatch")
    for item in source_files:
        require_hash(source_file_path(repo, item["path"]), item["sha256"], "source file")
    for item in fixture_files:
        path = canonical(item["path"], must_exist=True)
        if not path_in_allowed_roots(path, roots):
            raise QualificationError("fixture file is outside allowed roots")
        require_hash(path, item["sha256"], "fixture file")


def load_request(input_arg: str | Path, output_arg: str | Path, *, profile: str) -> dict:
    repo = ROOT.resolve()
    inputs = canonical(input_arg, must_exist=True)
    data = read_json(inputs)
    if data.get("schema_version") != 1:
        raise QualificationError("unsupported input schema")
    if data.get("acceptance_profile") != profile:
        raise QualificationError("input acceptance profile mismatch")
    if data["source"].get("kind") != "commit":
        raise QualificationError("final qualification requires source.kind=commit")
    if canonical(data["source"]["repository"], must_exist=True) != repo:
        raise QualificationError("input source mismatch")
    owned_root = canonical(data["owned_root"]["path"], must_exist=True)
    if overlaps(owned_root, repo):
        raise QualificationError("owned root overlaps source")
    marker = canonical(data["owned_root"]["marker"], must_exist=True)
    validate_owner(owned_root, marker, repo)
    if not path_in_allowed_roots(inputs, (repo, owned_root)):
        raise QualificationError("input manifest is outside source and owned roots")
    output = canonical(output_arg, must_exist=False)
    if output.exists() or not output.is_relative_to(owned_root) or output == owned_root:
        raise QualificationError("requested output must be new and inside owned root")
    python = owned_file(data["python"]["candidate"], owned_root)
    if not python.is_file():
        raise QualificationError("candidate interpreter is missing")
    wheel = owned_file(data["candidate"]["wheel"], owned_root)
    validate_runtime_wheel(wheel, data["source"], data["candidate"])
    coverage_path = canonical(data["checks"]["coverage"]["path"], must_exist=True)
    if not path_in_allowed_roots(coverage_path, (repo, owned_root)):
        raise QualificationError("coverage is outside allowed roots")
    require_hash(coverage_path, data["checks"]["coverage"]["sha256"], "coverage")
    validate_frozen_hashes(repo, data["source"], data["fixtures"], (repo, owned_root))
    for path in (inputs, wheel, coverage_path, python):
        if overlaps(output, path):
            raise QualificationError("requested output overlaps an input")
    data["_paths"] = {"inputs": inputs, "output": output, "owned_root": owned_root, "python": python, "coverage": coverage_path}
    return data
