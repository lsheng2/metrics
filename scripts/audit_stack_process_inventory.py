from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


ALLOWED_GRAFANA_PLUGIN_NAMES = (
    "gpx_infinity_windows_amd64.exe",
    "gpx_grafana-prometheus-datasource_windows_amd64.exe",
)


@dataclass(slots=True, frozen=True)
class ProcessInfo:
    process_id: int
    parent_process_id: int
    name: str
    command_line: str


@dataclass(slots=True, frozen=True)
class ProcessFinding:
    severity: str
    process: ProcessInfo
    message: str


@dataclass(slots=True, frozen=True)
class ExpectedRuntime:
    dashboard_workspace: Path
    ai_base_workspace: Path | None
    dashboard_django_pid: int
    dashboard_grafana_pid: int
    ai_base_root_pids: tuple[int, ...]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    runtime = read_expected_runtime(args)
    processes = read_processes(args.process_snapshot_json)
    findings = inspect_processes(runtime, processes)
    inventory = summarize_inventory(runtime, processes)
    phase_text = f" phase={args.phase}" if args.phase else ""

    print(f"Process inventory audit{phase_text}: scanned {len(processes)} process(es).")
    print(
        "Process inventory summary: "
        f"dashboard_django={inventory['dashboard_django']} "
        f"dashboard_grafana={inventory['dashboard_grafana']} "
        f"grafana_plugins={inventory['grafana_plugins']} "
        f"ai_base={inventory['ai_base']}"
    )
    if findings:
        print(f"Process inventory audit failed: {len(findings)} issue(s).")
        for finding in findings[:20]:
            print(
                f"  [{finding.severity}] PID {finding.process.process_id} "
                f"{finding.process.name}: {finding.message}"
            )
            print(f"      {finding.process.command_line[:500]}")
        remaining = len(findings) - 20
        if remaining > 0:
            print(f"  ... {remaining} more issue(s) omitted")
        return 1

    print("Process inventory audit passed: no stale demo process windows detected.")
    return 0


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the Dashboard + AI Base demo process inventory.")
    parser.add_argument("--dashboard-workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--ai-base-workspace", default="")
    parser.add_argument("--dashboard-state", default="")
    parser.add_argument("--ai-base-state", default="")
    parser.add_argument("--process-snapshot-json", default="")
    parser.add_argument("--phase", default="")
    return parser.parse_args(argv)


def read_expected_runtime(args: argparse.Namespace) -> ExpectedRuntime:
    dashboard_workspace = Path(args.dashboard_workspace).resolve()
    ai_base_workspace = Path(args.ai_base_workspace).resolve() if args.ai_base_workspace else None
    dashboard_state_path = Path(args.dashboard_state) if args.dashboard_state else default_dashboard_state_path(dashboard_workspace)
    ai_base_state_path = (
        Path(args.ai_base_state)
        if args.ai_base_state
        else default_ai_base_state_path(ai_base_workspace)
    )
    dashboard_state = read_json_file(dashboard_state_path)
    ai_base_state = read_json_file(ai_base_state_path) if ai_base_state_path else {}
    dashboard_services = dashboard_state.get("services", {})
    django_service = dashboard_services.get("django", {})
    grafana_service = dashboard_services.get("grafana", {})

    return ExpectedRuntime(
        dashboard_workspace=dashboard_workspace,
        ai_base_workspace=ai_base_workspace,
        dashboard_django_pid=as_int(django_service.get("pid")),
        dashboard_grafana_pid=as_int(grafana_service.get("pid")),
        ai_base_root_pids=tuple(
            as_int(process.get("pid"))
            for process in ai_base_state.get("processes", [])
            if isinstance(process, dict) and as_int(process.get("pid")) > 0
        ),
    )


def read_processes(process_snapshot_json: str) -> tuple[ProcessInfo, ...]:
    if process_snapshot_json:
        payload = json.loads(Path(process_snapshot_json).read_text(encoding="utf-8"))
    elif sys.platform == "win32":
        payload = read_windows_process_snapshot()
    else:
        payload = read_posix_process_snapshot()
    if isinstance(payload, dict):
        payload = [payload]
    return tuple(process_from_payload(item) for item in payload if isinstance(item, dict))


def read_windows_process_snapshot() -> object:
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | "
        "ConvertTo-Json -Depth 4"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Could not query Win32_Process.")
    return json.loads(completed.stdout or "[]")


def read_posix_process_snapshot() -> object:
    completed = subprocess.run(
        ["ps", "-eo", "pid=,ppid=,comm=,args="],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Could not query process list.")
    rows = []
    for line in completed.stdout.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 3:
            continue
        rows.append(
            {
                "ProcessId": parts[0],
                "ParentProcessId": parts[1],
                "Name": parts[2],
                "CommandLine": parts[3] if len(parts) > 3 else parts[2],
            }
        )
    return rows


def process_from_payload(item: dict[str, object]) -> ProcessInfo:
    return ProcessInfo(
        process_id=as_int(item.get("ProcessId")),
        parent_process_id=as_int(item.get("ParentProcessId")),
        name=str(item.get("Name") or ""),
        command_line=str(item.get("CommandLine") or ""),
    )


def inspect_processes(runtime: ExpectedRuntime, processes: Sequence[ProcessInfo]) -> list[ProcessFinding]:
    process_by_pid = {process.process_id: process for process in processes}
    dashboard_django_tree = descendants(process_by_pid, (runtime.dashboard_django_pid,))
    dashboard_grafana_tree = descendants(process_by_pid, (runtime.dashboard_grafana_pid,))
    ai_base_tree = descendants(process_by_pid, runtime.ai_base_root_pids)
    findings: list[ProcessFinding] = []
    findings.extend(inspect_expected_dashboard_processes(runtime, process_by_pid))

    for process in processes:
        normalized = normalize(process.command_line)
        process_name = process.name.casefold()
        if process_name == "grafana.exe" and "grafana-e2e-" in normalized and process.process_id not in dashboard_grafana_tree:
            findings.append(ProcessFinding("error", process, "stale Grafana E2E process is still running."))
        elif is_dashboard_runserver(runtime.dashboard_workspace, normalized) and process.process_id not in dashboard_django_tree:
            findings.append(ProcessFinding("error", process, "stale Dashboard Django runserver is still running."))
        elif "sample_agent" in normalized:
            findings.append(ProcessFinding("error", process, "stale AI Base sample_agent profile is still running."))
        elif process_name.startswith("gpx_"):
            findings.extend(inspect_grafana_plugin(process, dashboard_grafana_tree))
        elif is_ai_base_visible_window_process(runtime, process, normalized, ai_base_tree):
            findings.append(ProcessFinding("error", process, "AI Base dev service is running in visible -NoExit window mode."))

    return findings


def inspect_expected_dashboard_processes(
    runtime: ExpectedRuntime,
    process_by_pid: dict[int, ProcessInfo],
) -> list[ProcessFinding]:
    findings: list[ProcessFinding] = []
    if runtime.dashboard_django_pid > 0:
        django_process = process_by_pid.get(runtime.dashboard_django_pid)
        if django_process is None:
            findings.append(
                missing_process_finding(runtime.dashboard_django_pid, "expected Dashboard Django lifecycle process is not running.")
            )
        elif not is_dashboard_runserver(runtime.dashboard_workspace, normalize(django_process.command_line)):
            findings.append(
                ProcessFinding("error", django_process, "Dashboard lifecycle PID no longer belongs to the current Django runserver.")
            )
    if runtime.dashboard_grafana_pid > 0:
        grafana_process = process_by_pid.get(runtime.dashboard_grafana_pid)
        if grafana_process is None:
            findings.append(
                missing_process_finding(runtime.dashboard_grafana_pid, "expected Dashboard Grafana lifecycle process is not running.")
            )
        elif not is_current_dashboard_grafana(runtime.dashboard_workspace, normalize(grafana_process.command_line), grafana_process.name):
            findings.append(
                ProcessFinding("error", grafana_process, "Dashboard lifecycle PID no longer belongs to the current Grafana runtime.")
            )
    return findings


def missing_process_finding(process_id: int, message: str) -> ProcessFinding:
    return ProcessFinding(
        "error",
        ProcessInfo(process_id=process_id, parent_process_id=0, name="<missing>", command_line=""),
        message,
    )


def inspect_grafana_plugin(process: ProcessInfo, dashboard_grafana_tree: set[int]) -> list[ProcessFinding]:
    if process.parent_process_id not in dashboard_grafana_tree:
        return [ProcessFinding("error", process, "Grafana plugin backend is not owned by the current Grafana demo process.")]
    if process.name.casefold() not in ALLOWED_GRAFANA_PLUGIN_NAMES:
        return [ProcessFinding("error", process, "unneeded Grafana bundled datasource backend is still running.")]
    return []


def summarize_inventory(runtime: ExpectedRuntime, processes: Sequence[ProcessInfo]) -> dict[str, int]:
    process_by_pid = {process.process_id: process for process in processes}
    dashboard_django_tree = descendants(process_by_pid, (runtime.dashboard_django_pid,))
    dashboard_grafana_tree = descendants(process_by_pid, (runtime.dashboard_grafana_pid,))
    ai_base_tree = descendants(process_by_pid, runtime.ai_base_root_pids)
    return {
        "dashboard_django": count_named(processes, dashboard_django_tree, ("python.exe", "python")),
        "dashboard_grafana": count_named(processes, dashboard_grafana_tree, ("grafana.exe", "grafana")),
        "grafana_plugins": count_prefixed(processes, dashboard_grafana_tree, "gpx_"),
        "ai_base": len(ai_base_tree),
    }


def is_dashboard_runserver(dashboard_workspace: Path, normalized_command: str) -> bool:
    normalized_workspace = normalize(str(dashboard_workspace))
    workspace_parent = normalize(str(dashboard_workspace.parent))
    return (
        ("manage.py" in normalized_command)
        and ("runserver 127.0.0.1:80" in normalized_command)
        and (normalized_workspace in normalized_command or workspace_parent in normalized_command)
    )


def is_current_dashboard_grafana(dashboard_workspace: Path, normalized_command: str, process_name: str) -> bool:
    normalized_workspace = normalize(str(dashboard_workspace))
    return (
        process_name.casefold() in {"grafana.exe", "grafana"}
        and "grafana-e2e-" in normalized_command
        and normalized_workspace in normalized_command
        and "\\.worktrees\\" not in normalized_command
    )


def is_ai_base_visible_window_process(
    runtime: ExpectedRuntime,
    process: ProcessInfo,
    normalized_command: str,
    ai_base_tree: set[int],
) -> bool:
    if runtime.ai_base_workspace is None:
        return False
    if process.process_id not in ai_base_tree:
        return False
    if "-noexit" not in normalized_command:
        return False
    normalized_workspace = normalize(str(runtime.ai_base_workspace))
    return normalized_workspace in normalized_command or "dashboard_query_agent" in normalized_command


def descendants(process_by_pid: dict[int, ProcessInfo], root_process_ids: Iterable[int]) -> set[int]:
    roots = [process_id for process_id in root_process_ids if process_id > 0]
    children_by_parent: dict[int, list[int]] = {}
    for process in process_by_pid.values():
        children_by_parent.setdefault(process.parent_process_id, []).append(process.process_id)
    seen: set[int] = set()
    stack = list(roots)
    while stack:
        process_id = stack.pop()
        if process_id in seen:
            continue
        seen.add(process_id)
        stack.extend(children_by_parent.get(process_id, ()))
    return seen


def count_named(processes: Sequence[ProcessInfo], allowed_ids: set[int], names: tuple[str, ...]) -> int:
    allowed_names = {name.casefold() for name in names}
    return sum(1 for process in processes if process.process_id in allowed_ids and process.name.casefold() in allowed_names)


def count_prefixed(processes: Sequence[ProcessInfo], allowed_ids: set[int], prefix: str) -> int:
    normalized_prefix = prefix.casefold()
    return sum(
        1
        for process in processes
        if process.process_id in allowed_ids and process.name.casefold().startswith(normalized_prefix)
    )


def read_json_file(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize(value: str) -> str:
    return value.replace("/", "\\").casefold()


def default_dashboard_state_path(workspace: Path) -> Path:
    return workspace / "state" / "e2e" / "service-lifecycle-engine" / "metrics-bug-trend-default.json"


def default_ai_base_state_path(workspace: Path | None) -> Path | None:
    if workspace is None:
        return None
    return workspace / ".tmp-validation" / "runtime" / "dev-stack-state.dashboard_query_agent.json"


if __name__ == "__main__":
    sys.exit(main())
