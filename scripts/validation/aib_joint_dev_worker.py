"""Child process guard for AIB source and private-wheel development runs."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def validate_module_origin(stage: str, expected_root: Path, observed: Path) -> dict:
    expected = expected_root.resolve()
    origin = observed.resolve()
    if stage == "source":
        package_root = expected / "ai_base_runtime"
        expected_init = package_root / "__init__.py"
        if origin != expected_init or not origin.is_relative_to(expected):
            raise ValueError("source import origin mismatch")
    elif stage == "wheel":
        if not origin.is_relative_to(expected) or "site-packages" not in {part.lower() for part in origin.parts}:
            raise ValueError("wheel import origin mismatch")
    else:
        raise ValueError("unknown import origin stage")
    return {"stage": stage, "expected_root": str(expected), "origin": str(origin)}


def write_module_origin(stage: str, expected_root: Path, output: Path) -> dict:
    module = sys.modules.get("ai_base_runtime")
    if module is None or not getattr(module, "__file__", None):
        raise ValueError("ai_base_runtime was not imported by the selected tests")
    payload = validate_module_origin(stage, expected_root, Path(module.__file__))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_installed_package_files(manifest: dict, site_root: Path | None = None) -> dict:
    package_files = manifest.get("packageFiles")
    if not isinstance(package_files, dict) or not package_files:
        raise ValueError("package manifest is empty")
    if site_root is None:
        dist = metadata.distribution(manifest["distribution"])
        roots = [Path(dist.locate_file("")).resolve()]
        version = metadata.version(manifest["distribution"])
    else:
        dist = None
        roots = [site_root.resolve()]
        version = manifest.get("version")
    if not roots:
        roots.append(Path(dist.locate_file("")).resolve())
    checked = {}
    for relative, expected in package_files.items():
        installed = Path(dist.locate_file(relative)).resolve() if dist is not None else roots[0] / relative
        if not installed.is_file() or not any(installed.is_relative_to(root) for root in roots):
            raise ValueError("package file is outside installed root")
        actual = hashlib.sha256(installed.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("package file hash mismatch")
        checked[relative] = actual
    return {"distribution": manifest["distribution"], "version": version, "files": checked}


def run_pytest_stage(args: argparse.Namespace) -> int:
    dashboard = args.dashboard_root.resolve()
    sys.path.insert(0, str(dashboard))
    if args.stage == "source":
        sys.path.insert(0, str(args.aib_src.resolve()))
        expected_root = args.aib_src.resolve()
        tests = [dashboard / "ai_host/tests/conformance_backpressure_cases.py"]
    else:
        expected_root = Path(sys.prefix).resolve()
        tests = [
            dashboard / "ai_host/tests/test_serve_process.py",
            dashboard / "ai_host/tests/conformance_backpressure_cases.py",
        ]
    from scripts.validation.run_report_authoring_tests import run_tests

    pytest_args = [
        *(str(path) for path in tests),
        "-p",
        "ai_base_runtime.testkit.pytest_plugin",
        "-p",
        "ai_host.tests.conformance_fixtures",
        "-o",
        "ai_host_modes=blocking_wsgi",
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "-o",
        "asyncio_default_fixture_loop_scope=function",
        "--basetemp",
        str(args.basetemp),
        "--junitxml",
        str(args.junitxml),
    ]
    code = run_tests(pytest_args)
    write_module_origin(args.stage, expected_root, args.origin_output)
    return code


def probe_package(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(args.dashboard_root.resolve()))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    payload = verify_installed_package_files(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="stage", required=True)
    for name in ("source", "wheel"):
        stage = subparsers.add_parser(name)
        stage.add_argument("--dashboard-root", type=Path, required=True)
        stage.add_argument("--origin-output", type=Path, required=True)
        stage.add_argument("--junitxml", type=Path, required=True)
        stage.add_argument("--basetemp", type=Path, required=True)
        if name == "source":
            stage.add_argument("--aib-src", type=Path, required=True)
        stage.set_defaults(func=run_pytest_stage)
    probe = subparsers.add_parser("probe-package")
    probe.add_argument("--dashboard-root", type=Path, required=True)
    probe.add_argument("--manifest", type=Path, required=True)
    probe.add_argument("--output", type=Path, required=True)
    probe.set_defaults(func=probe_package)
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
