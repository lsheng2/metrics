from __future__ import annotations

import argparse
import json
from pathlib import Path

from service_lifecycle_engine import ServiceLifecycleEngine, load_project_name, load_service_specs


def main() -> None:
    parser = argparse.ArgumentParser(description="Service lifecycle diagnostics.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="Inspect lifecycle state, listeners, and health for declared services.")
    doctor.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    doctor.add_argument("--service-config", required=True)
    doctor.add_argument("--instance", default="default")
    doctor.add_argument("--state-directory", default="")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--fail-on-problem", action="store_true")
    args = parser.parse_args()

    if args.command == "doctor":
        run_doctor(args)


def run_doctor(args: argparse.Namespace) -> None:
    workspace = Path(args.workspace).resolve()
    service_config = resolve_workspace_path(workspace, args.service_config)
    state_directory = resolve_workspace_path(workspace, args.state_directory) if args.state_directory else workspace / "state" / "service-lifecycle-engine"
    lifecycle = ServiceLifecycleEngine(
        project_name=load_project_name(service_config, "service-lifecycle-engine"),
        workspace=workspace,
        instance_name=args.instance,
        state_directory=state_directory,
    )
    diagnostics = lifecycle.diagnose_services(tuple(load_service_specs(service_config, workspace).values()))
    if args.json:
        print(json.dumps(diagnostics, indent=2, sort_keys=True))
    else:
        print_human_diagnostics(diagnostics)
    if args.fail_on_problem and any(item["status"] != "ok" for item in diagnostics):
        raise SystemExit(1)


def resolve_workspace_path(workspace: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (workspace / path).resolve()


def print_human_diagnostics(diagnostics: list[dict[str, object]]) -> None:
    if not diagnostics:
        print("No services declared.")
        return
    for item in diagnostics:
        listeners = ", ".join(f"{port}:{pids}" for port, pids in item["listener_pids_by_port"].items())
        print(
            f"{item['service']} status={item['status']} "
            f"registered={item['registered']} pid={item['registered_pid']} port={item['registered_port']} "
            f"running={item['process_running']} health={item['health_reachable']} listeners={listeners}"
        )


if __name__ == "__main__":
    main()
