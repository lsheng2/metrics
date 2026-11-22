from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


def init_git_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True, timeout=15)
    return root


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# synthetic python\n", encoding="utf-8")
    return path


def runtime_source(root: Path) -> Path:
    package = root / "packages/runtime/src/ai_base_runtime"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 'source'\n", encoding="utf-8")
    (root / "packages/runtime/pyproject.toml").write_text(
        "[build-system]\nrequires=[]\nbuild-backend='setuptools.build_meta'\n"
        "[project]\nname='ai-base-runtime'\nversion='0.1.1.dev8'\n",
        encoding="utf-8",
    )
    return root


def dashboard_source(root: Path) -> Path:
    (root / "ai_host").mkdir(parents=True)
    write_json(
        root / "ai_host/runtime_artifact.json",
        {
            "schemaVersion": 1,
            "distribution": "ai-base-runtime",
            "version": "0.1.1.dev8",
            "wheelSha256": "0" * 64,
            "genericCapabilities": [],
            "packageFiles": {"ai_base_runtime/__init__.py": "0" * 64},
            "sourceCommit": "release-commit",
            "sourceTree": "release-tree",
        },
    )
    (root / "requirements.txt").write_text("ai-base-runtime==0.1.1.dev8\n", encoding="utf-8")
    return root


def locked_wheelhouse(root: Path) -> tuple[Path, Path, str]:
    wheelhouse = root / "wheels"
    wheelhouse.mkdir(parents=True)
    wheel = wheelhouse / "django-6.0.7-py3-none-any.whl"
    wheel.write_bytes(b"dependency")
    lock = root / "inputs/wheelhouse-lock.json"
    lock_sha = write_json(
        lock,
        {
            "schema_version": 1,
            "kind": "windows-wheelhouse-lock",
            "files": {wheel.name: sha256(wheel)},
        },
    )
    return wheelhouse, lock, sha256(lock_sha)


def runtime_wheel(path: Path, *, payload: bytes = b"VALUE = 'wheel'\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ai_base_runtime/__init__.py", payload)
        archive.writestr(
            "ai_base_runtime-0.1.1.dev8.dist-info/METADATA",
            "Metadata-Version: 2.3\nName: ai-base-runtime\nVersion: 0.1.1.dev8\n",
        )
    return path


def formal_input_with_development_receipt(root: Path, receipt: Path) -> Path:
    wheel = runtime_wheel(root / "owned/wheels/ai_base_runtime-0.1.1.dev8-py3-none-any.whl")
    fixture = write_json(root / "owned/fixtures/fixture.json", {"fixture": "stable"})
    vector = write_json(
        root / "owned/fixtures/vector.json",
        {"files": [{"path": str(fixture), "sha256": sha256(fixture)}]},
    )
    coverage = write_json(root / "owned/coverage.json", {"task_groups": [], "source_requirement_digests": {}})
    return write_json(
        root / "owned/inputs.json",
        {
            "schema_version": 1,
            "acceptance_profile": "functional",
            "source": {
                "kind": "working-tree",
                "repository": str(root / "dashboard"),
                "files": [{"path": "frozen.py", "sha256": "0" * 64}],
            },
            "candidate": {"version": "0.1.1.dev8", "wheel": str(wheel), "wheel_sha256": sha256(wheel)},
            "python": {"candidate": sys.executable, "version": "3.13.0"},
            "owned_root": {"path": str(root / "owned"), "marker": str(root / "owned/owner.json")},
            "fixtures": {
                "fixture_vector": {"path": str(vector), "sha256": sha256(vector)},
                "fixture_vector_sha256": sha256(vector),
                "files": [{"path": str(fixture), "sha256": sha256(fixture)}],
            },
            "checks": {
                "coverage": {"path": str(coverage), "sha256": sha256(coverage)},
                "evidence_bindings": {
                    "task:1.1": {
                        "kind": "aib-joint-development-run",
                        "path": str(receipt),
                        "sha256": sha256(receipt),
                    },
                },
            },
        },
    )
