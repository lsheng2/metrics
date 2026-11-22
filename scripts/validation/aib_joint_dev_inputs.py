"""Input identity, path safety and inventory helpers for AIB joint development."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validation.project_full_stack_support import (
    base_environment, digest_file, is_reparse_or_symlink, reject_reparse_components, write_json,
)
from scripts.validation.windows_install_wheelhouse import (
    WheelhouseLock,
    load_wheelhouse_lock,
)


DASHBOARD_ROOT = ROOT
OWNER = "aib-joint-development"
ROOT_OWNER = "aib-joint-development-root"
SCHEMA_VERSION = 1
INVENTORY_KIND = "aib-joint-source-inventory"
TEXT_SUFFIXES = {
    ".cfg", ".css", ".html", ".ini", ".js", ".json", ".lock", ".md", ".py", ".ps1", ".toml", ".txt", ".yaml", ".yml",
}
EXCLUDED_PARTS = {
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tmp", "cache", "caches", "node_modules",
    "test-results", "tmp_ui_validation", "user-data", "user_data", "userdata",
}


@dataclass(frozen=True, slots=True)
class SourceRequest:
    dashboard_root: Path
    aib_root: Path
    aib_src: Path
    python: Path
    data_root: Path


@dataclass(frozen=True, slots=True)
class WheelRequest:
    dashboard_root: Path
    aib_root: Path
    aib_runtime_root: Path
    bootstrap_python: Path
    build_python: Path
    wheelhouse: WheelhouseLock
    data_root: Path


class DevelopmentCommandError(RuntimeError):
    def __init__(self, message: str, receipt: dict | None = None):
        super().__init__(message)
        self.receipt = receipt


def canonical(value: str | Path, *, must_exist: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("path must be absolute")
    reject_reparse_components(path)
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as error:
        raise ValueError("path cannot be resolved") from error
    if resolved != path.absolute():
        raise ValueError("path must be canonical")
    return resolved


def overlaps(left: Path, right: Path) -> bool:
    left = left.resolve(strict=False)
    right = right.resolve(strict=False)
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def validate_interpreter(value: str | Path, forbidden_roots: tuple[Path, ...], label: str = "interpreter") -> Path:
    python = canonical(value)
    if not python.is_file() or python.name.lower() not in {"python.exe", "python"}:
        raise ValueError(f"{label} must be a Python executable")
    env_root = python_environment_root(python)
    if any(overlaps(env_root, root) or overlaps(python, root) for root in forbidden_roots):
        raise ValueError(f"{label} overlaps a source, wheelhouse or data root")
    return python


def python_environment_root(python: Path) -> Path:
    return python.parent.parent if python.parent.name.lower() == "scripts" else python.parent


def validate_source_request(
    aib_root: str | Path,
    python: str | Path,
    data_root: str | Path,
    *,
    dashboard_root: str | Path = DASHBOARD_ROOT,
    create_data_root: bool = False,
) -> SourceRequest:
    dashboard = _repository_root(dashboard_root, "Dashboard")
    aib = _repository_root(aib_root, "AIB")
    aib_src = canonical(aib / "packages/runtime/src")
    if not (aib_src / "ai_base_runtime/__init__.py").is_file():
        raise ValueError("AIB runtime source package is incomplete")
    root = validate_data_root(data_root, forbidden_roots=(dashboard, aib))
    interpreter = validate_interpreter(python, (dashboard, aib, root))
    if create_data_root:
        ensure_data_root(root, dashboard)
    return SourceRequest(dashboard, aib, aib_src, interpreter, root)


def validate_wheel_request(
    aib_root: str | Path,
    bootstrap_python: str | Path,
    build_python: str | Path,
    wheelhouse: str | Path,
    wheelhouse_lock: str | Path,
    wheelhouse_sha256: str,
    data_root: str | Path,
    *,
    dashboard_root: str | Path = DASHBOARD_ROOT,
    create_data_root: bool = False,
) -> WheelRequest:
    dashboard = _repository_root(dashboard_root, "Dashboard")
    aib = _repository_root(aib_root, "AIB")
    runtime_root = canonical(aib / "packages/runtime")
    lock_root = _wheelhouse_owner_root(wheelhouse, wheelhouse_lock)
    lock = load_wheelhouse_lock(wheelhouse, wheelhouse_lock, wheelhouse_sha256, lock_root)
    root = validate_data_root(data_root, forbidden_roots=(dashboard, aib, lock.root, lock.wheelhouse))
    bootstrap = validate_interpreter(bootstrap_python, (dashboard, aib, lock.root, root), "bootstrap interpreter")
    build = validate_interpreter(build_python, (dashboard, aib, lock.root, root), "build interpreter")
    if create_data_root:
        ensure_data_root(root, dashboard)
    return WheelRequest(dashboard, aib, runtime_root, bootstrap, build, lock, root)


def validate_data_root(value: str | Path, *, forbidden_roots: tuple[Path, ...]) -> Path:
    root = canonical(value, must_exist=False)
    if any(overlaps(root, forbidden) for forbidden in forbidden_roots):
        raise ValueError("data root must be outside source, interpreter and wheelhouse roots")
    for parent in (root, *root.parents):
        if (parent / ".git").exists():
            raise ValueError("data root must be outside Git repositories")
    marker = root / "owner.json"
    if root.exists():
        if not root.is_dir() or is_reparse_or_symlink(root):
            raise ValueError("data root is not a regular directory")
        if marker.exists():
            payload = json.loads(marker.read_text(encoding="utf-8"))
            if payload.get("owner") != ROOT_OWNER:
                raise ValueError("data root has another owner")
        elif any(root.iterdir()):
            raise ValueError("refusing existing nonempty unowned data root")
    return root


def ensure_data_root(root: Path, dashboard_root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "owner.json"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "owner": ROOT_OWNER,
        "repository": str(dashboard_root),
        "root": str(root),
    }
    if marker.exists():
        existing = json.loads(marker.read_text(encoding="utf-8"))
        if existing != payload:
            raise ValueError("data root has another owner")
    else:
        write_json(marker, payload)
    return root


def create_owned_run_dir(data_root: Path, dashboard_root: Path, stage: str) -> Path:
    ensure_data_root(data_root, dashboard_root)
    for _ in range(16):
        run_dir = data_root / str(uuid.uuid4())
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise RuntimeError("could not allocate unique run directory")
    for name in ("build", "copy", "env", "evidence", "logs", "tmp"):
        (run_dir / name).mkdir()
    write_json(
        run_dir / "owner.json",
        {
            "schema_version": SCHEMA_VERSION,
            "owner": OWNER,
            "stage": stage,
            "repository": str(dashboard_root),
            "data_root": str(data_root),
            "run_directory": str(run_dir),
        },
    )
    return run_dir


def source_inventory(root: str | Path, relative: str | None = None) -> dict:
    repo = _repository_root(root, "source")
    scope = _inventory_scope(repo, relative)
    paths = _git_paths(repo)
    files = []
    for rel in paths:
        if relative and not _is_under_relative(rel, relative):
            continue
        path = repo / rel
        if not path.is_file() or _excluded(rel):
            continue
        if (path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".gitignore", ".gitattributes"}
                and "ai_base_runtime/assets" not in rel.replace("\\", "/")):
            continue
        files.append({"path": rel.replace("\\", "/"), "sha256": digest_file(path), "bytes": path.stat().st_size})
    if not files:
        raise ValueError("source inventory is empty or incomplete")
    status = _git_output(repo, ["status", "--porcelain=v1", "--untracked-files=all"]).splitlines()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": INVENTORY_KIND,
        "root": str(repo),
        "relative": relative,
        "scope": str(scope),
        "commit": _git_output(repo, ["rev-parse", "HEAD"]).strip() or None,
        "dirty": bool(status),
        "status": status,
        "files": sorted(files, key=lambda item: item["path"]),
    }
    payload["inventorySha256"] = _inventory_digest(payload["files"])
    return payload


def assert_inventory_unchanged(root: str | Path, before: dict, relative: str | None = None) -> dict:
    after = source_inventory(root, relative if relative is not None else before.get("relative"))
    if after != before:
        raise ValueError("source inventory drift detected")
    return after


def copy_inventory_files(source_root: Path, target_root: Path, inventory: dict, *, strip_relative: str | None = None) -> None:
    if target_root.exists() and any(target_root.iterdir()):
        raise ValueError("copy target must be new or empty")
    copied = 0
    for item in inventory["files"]:
        relative = Path(item["path"])
        if strip_relative is not None:
            strip = Path(strip_relative)
            if not (relative == strip or relative.is_relative_to(strip)):
                continue
            relative = relative.relative_to(strip)
        source = source_root / item["path"]
        if is_reparse_or_symlink(source):
            raise ValueError("refusing reparse or symlink source entry")
        if digest_file(source) != item["sha256"]:
            raise ValueError("source inventory drift detected before copy")
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        if digest_file(target) != item["sha256"]:
            raise ValueError("copied source hash mismatch")
        copied += 1
    if copied == 0:
        raise ValueError("source inventory copy was empty")


def development_environment(directory: Path) -> dict[str, str]:
    env = base_environment(directory)
    env.update(PIP_CONFIG_FILE=os.devnull, PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONUTF8="1")
    return env


def run_development_command(argv, *, cwd: Path, run_dir: Path, label: str, timeout: int) -> dict:
    from scripts.validation import qualify_ai_runtime

    log_dir = run_dir / "logs"
    start = time.monotonic()
    try:
        record = qualify_ai_runtime.run_command(
            [str(part) for part in argv],
            cwd=cwd,
            log_dir=log_dir,
            label=label,
            timeout=timeout,
            env=development_environment(run_dir / "tmp" / label),
        )
        record["seconds"] = time.monotonic() - start
        write_json(Path(record["receipt"]), record, replace=True)
        return record
    except Exception as error:
        record = _read_command_receipt(log_dir, label)
        if record is not None:
            record["seconds"] = time.monotonic() - start
            write_json(log_dir / f"{label}.command.json", record, replace=True)
        raise DevelopmentCommandError(str(error), record) from error


def _read_command_receipt(log_dir: Path, label: str) -> dict | None:
    path = log_dir / f"{label}.command.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _repository_root(value: str | Path, label: str) -> Path:
    root = canonical(value)
    if not root.is_dir() or not (root / ".git").exists() or is_reparse_or_symlink(root):
        raise ValueError(f"{label} root must be a Git checkout")
    return root


def _inventory_scope(repo: Path, relative: str | None) -> Path:
    if relative is None:
        return repo
    rel = Path(relative)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError("inventory relative path is invalid")
    scope = canonical(repo / rel)
    if not scope.is_relative_to(repo):
        raise ValueError("inventory scope escapes repository")
    return scope


def _git_paths(repo: Path) -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
        timeout=30,
    ).stdout.decode("utf-8", errors="replace")
    return sorted(path for path in output.split("\0") if path)


def _git_output(repo: Path, args: list[str]) -> str:
    try:
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=30).stdout
    except subprocess.SubprocessError:
        return ""


def _excluded(relative: str) -> bool:
    parts = Path(relative).parts
    lowered = [part.lower() for part in parts]
    if any(part in EXCLUDED_PARTS for part in lowered):
        return True
    return any(part.startswith(".env") or "secret" in part or part in {"credentials", "cookies"} for part in lowered)


def _is_under_relative(relative_path: str, relative_root: str) -> bool:
    rel = Path(relative_path)
    root = Path(relative_root)
    return rel == root or rel.is_relative_to(root)


def _inventory_digest(files: list[dict]) -> str:
    data = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    from hashlib import sha256

    return sha256(data).hexdigest()


def _wheelhouse_owner_root(wheelhouse: str | Path, manifest: str | Path) -> Path:
    wheel_path = canonical(wheelhouse)
    manifest_path = canonical(manifest)
    common = Path(os.path.commonpath([str(wheel_path), str(manifest_path)])).resolve()
    if common in {wheel_path, manifest_path}:
        common = common.parent
    if not common.is_dir():
        raise ValueError("wheelhouse owner root is invalid")
    return common
