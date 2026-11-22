"""Private AIB wheel construction and copied Dashboard preparation."""
from __future__ import annotations

from email.parser import BytesParser
import json
from pathlib import Path
import re
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validation.aib_joint_dev_inputs import (
    DevelopmentCommandError,
    WheelRequest,
    assert_inventory_unchanged,
    copy_inventory_files,
    run_development_command,
    source_inventory,
)
from scripts.validation.aib_joint_dev_worker import verify_installed_package_files
from scripts.validation.project_full_stack_support import digest_file, write_json
from scripts.validation.windows_install_wheelhouse import verify_wheelhouse_lock


class WheelRunError(RuntimeError):
    def __init__(self, message: str, context: dict):
        super().__init__(message)
        self.context = context


PHASES = ("setup", "snapshot", "build", "install", "test", "post_run_verification", "external_cleanup")


def build_development_manifest(wheel: Path, *, aib_inventory: dict, dashboard_inventory: dict) -> dict:
    metadata, files = wheel_package_files(wheel)
    return {
        "schemaVersion": 1,
        "kind": "aib-private-development-wheel",
        "classification": "dashboard-development-private-wheel",
        "distribution": metadata["name"],
        "version": metadata["version"],
        "wheelFile": wheel.name,
        "wheelSha256": digest_file(wheel),
        "packageFiles": files,
        "genericCapabilities": [],
        "fullAibQualification": False,
        "acceptanceEligible": False,
        "source": {
            "kind": "working-tree",
            "aib": {
                "root": aib_inventory.get("root"),
                "commit": aib_inventory.get("commit"),
                "dirty": aib_inventory.get("dirty"),
                "inventorySha256": aib_inventory.get("inventorySha256"),
            },
            "dashboard": {
                "root": dashboard_inventory.get("root"),
                "commit": dashboard_inventory.get("commit"),
                "dirty": dashboard_inventory.get("dirty"),
                "inventorySha256": dashboard_inventory.get("inventorySha256"),
            },
        },
    }


def wheel_package_files(wheel: Path) -> tuple[dict, dict[str, str]]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError("wheel metadata is ambiguous")
        info = BytesParser().parsebytes(archive.read(metadata_names[0]))
        if info["Name"] != "ai-base-runtime":
            raise ValueError("wheel distribution mismatch")
        files = {
            name: __import__("hashlib").sha256(archive.read(name)).hexdigest()
            for name in names
            if name.startswith("ai_base_runtime/") and not name.endswith("/")
        }
    if not files:
        raise ValueError("runtime wheel has no package files")
    return {"name": info["Name"], "version": info["Version"]}, dict(sorted(files.items()))


def copy_dashboard_snapshot(source: Path, target: Path, manifest: dict) -> Path:
    inventory = source_inventory(source)
    copy_inventory_files(source, target, inventory)
    write_json(target / "ai_host/runtime_artifact.json", manifest, replace=True)
    return target


def copy_runtime_snapshot(source_root: Path, target: Path, inventory: dict) -> Path:
    copy_inventory_files(source_root, target, inventory, strip_relative="packages/runtime")
    return target


def prepare_wheel_run(request: WheelRequest, run_dir: Path) -> dict:
    total_start = time.monotonic()
    timings = _timing_model()
    command_receipts = []
    context = {"commands": command_receipts, "timings": timings}
    try:
        setup_start = time.monotonic()
        dashboard_before = source_inventory(request.dashboard_root)
        aib_before = source_inventory(request.aib_root, "packages/runtime")
        _finish_phase(timings, "setup", setup_start)
        runtime_copy = run_dir / "copy/aib-runtime"
        dashboard_copy = run_dir / "copy/dashboard"
        runtime_copy_start = time.monotonic()
        copy_runtime_snapshot(request.aib_root, runtime_copy, aib_before)
        _add_segment(timings, "snapshot", "aib_runtime_copy", runtime_copy_start)

        built_dir = run_dir / "build/wheels"
        built_dir.mkdir(parents=True)
        build_start = time.monotonic()
        build_error = None
        try:
            _record_command(command_receipts,
                [request.build_python, "-I", "-B", "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                 "--no-index", "--wheel-dir", built_dir, runtime_copy],
                cwd=runtime_copy, label="build-wheel", run_dir=run_dir, timeout=600,
            )
        except Exception as error:
            build_error = error
            raise
        finally:
            _finish_phase(timings, "build", build_start, state="failed" if build_error else "measured")
        private_wheels = sorted(built_dir.glob("ai_base_runtime-*.whl"))
        if len(private_wheels) != 1:
            raise ValueError("private wheel build did not produce exactly one runtime wheel")
        private_wheel = private_wheels[0]

        manifest = build_development_manifest(private_wheel, aib_inventory=aib_before, dashboard_inventory=dashboard_before)
        dashboard_copy_start = time.monotonic()
        copy_dashboard_snapshot(request.dashboard_root, dashboard_copy, manifest)
        _add_segment(timings, "snapshot", "dashboard_copy_after_build", dashboard_copy_start)

        install_start = time.monotonic()
        env_root = run_dir / "env/private-wheel"
        install_error = None
        try:
            verify_wheelhouse_lock(request.wheelhouse)
            _record_command(command_receipts, [request.bootstrap_python, "-I", "-B", "-m", "venv", env_root],
                            cwd=dashboard_copy, label="create-venv", run_dir=run_dir, timeout=300)
            python = env_root / "Scripts/python.exe"
            pip = [python, "-I", "-B", "-m", "pip", "--isolated", "--disable-pip-version-check", "--no-cache-dir"]
            install = [*pip, "install", "--no-index", "--only-binary=:all:",
                       "--find-links", request.wheelhouse.wheelhouse, "--find-links", built_dir]
            _record_command(command_receipts, [*install, private_wheel], cwd=dashboard_copy,
                            label="install-private-wheel", run_dir=run_dir, timeout=600)
            _record_command(command_receipts, [*install, "-r", dashboard_copy / "requirements.txt"], cwd=dashboard_copy,
                            label="install-dashboard-requirements", run_dir=run_dir, timeout=600)
            verify_wheelhouse_lock(request.wheelhouse)
        except Exception as error:
            install_error = error
            raise
        finally:
            _finish_phase(timings, "install", install_start, state="failed" if install_error else "measured")

        probe = run_dir / "evidence/package-probe.json"
        test_start = time.monotonic()
        test_error = None
        try:
            _record_command(command_receipts, [python, "-I", "-B", dashboard_copy / "scripts/validation/aib_joint_dev_worker.py",
                                               "probe-package", "--dashboard-root", dashboard_copy,
                                               "--manifest", dashboard_copy / "ai_host/runtime_artifact.json",
                                               "--output", probe],
                            cwd=dashboard_copy, label="probe-package", run_dir=run_dir, timeout=60)
            junit = run_dir / "evidence/wheel-tests.xml"
            origin = run_dir / "evidence/wheel-origin.json"
            _record_command(command_receipts, [python, "-I", "-B", dashboard_copy / "scripts/validation/aib_joint_dev_worker.py",
                                               "wheel", "--dashboard-root", dashboard_copy, "--origin-output", origin,
                                               "--junitxml", junit, "--basetemp", run_dir / "tmp/pytest"],
                            cwd=dashboard_copy, label="wheel-tests", run_dir=run_dir, timeout=900)
        except Exception as error:
            test_error = error
        finally:
            _finish_phase(
                timings, "test", test_start,
                state="failed" if test_error else "measured", includes_fixture_cleanup=True,
            )

        post_start = time.monotonic()
        dashboard_after = assert_inventory_unchanged(request.dashboard_root, dashboard_before)
        aib_after = assert_inventory_unchanged(request.aib_root, aib_before, "packages/runtime")
        context["source_after"] = {"dashboard": dashboard_after, "aib": aib_after}
        verify_installed_package_files(manifest, env_root / "Lib/site-packages")
        _finish_phase(timings, "post_run_verification", post_start)
        if test_error is not None:
            raise test_error
        _finalize_timings(timings, total_start)
        return {
            "private_wheel": {"path": str(private_wheel), "sha256": digest_file(private_wheel)},
            "dashboard_copy": str(dashboard_copy),
            "runtime_copy": str(runtime_copy),
            "manifest": manifest,
            "module_origins": {"path": str(origin), "payload": json.loads(origin.read_text(encoding="utf-8"))},
            "junit": str(junit),
            "commands": command_receipts,
            "timings": timings,
            "source_after": context["source_after"],
            "package_probe": json.loads(probe.read_text(encoding="utf-8")),
        }
    except Exception as error:
        _finalize_timings(timings, total_start)
        context.setdefault("source_after", _safe_source_after(request))
        raise WheelRunError(str(error), context) from error


def _command(argv, *, cwd: Path, label: str, run_dir: Path, timeout: int) -> dict:
    return run_development_command(argv, cwd=cwd, run_dir=run_dir, label=label, timeout=timeout)


def _record_command(records: list[dict], argv, *, cwd: Path, label: str, run_dir: Path, timeout: int) -> dict:
    try:
        record = _command(argv, cwd=cwd, label=label, run_dir=run_dir, timeout=timeout)
    except DevelopmentCommandError as error:
        if error.receipt is not None:
            records.append(error.receipt)
        raise
    records.append(record)
    return record


def _safe_source_after(request: WheelRequest) -> dict | None:
    try:
        return {
            "dashboard": source_inventory(request.dashboard_root),
            "aib": source_inventory(request.aib_root, "packages/runtime"),
        }
    except Exception:
        return None


def _timing_model() -> dict:
    return {"schema_version": 1, "phases": {name: {"state": "not_started"} for name in PHASES}}


def _set_phase(timings: dict, name: str, state: str, **extra) -> None:
    timings["phases"][name] = {"state": state, **extra}


def _finish_phase(timings: dict, name: str, start: float, *, state: str = "measured", **extra) -> None:
    _set_phase(timings, name, state, seconds=time.monotonic() - start, **extra)


def _add_segment(timings: dict, phase: str, name: str, start: float) -> None:
    entry = timings["phases"].setdefault(phase, {"state": "measured", "segments": [], "seconds": 0.0})
    if entry["state"] == "not_started":
        entry.update(state="measured", segments=[], seconds=0.0)
    segment = {"name": name, "seconds": time.monotonic() - start}
    entry.setdefault("segments", []).append(segment)
    entry["seconds"] = sum(item["seconds"] for item in entry["segments"])


def _finalize_timings(timings: dict, total_start: float) -> None:
    timings["phases"]["external_cleanup"] = {"state": "not_performed", "measurement": "not_separately_measured"}
    for phase in timings["phases"].values():
        if phase["state"] == "not_started":
            phase["state"] = "not_performed"
    timings["total_seconds"] = time.monotonic() - total_start
    timings["non_overlapping_phase_seconds"] = sum(
        phase.get("seconds", 0.0) for phase in timings["phases"].values()
    )
