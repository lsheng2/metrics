from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


HARD_PATTERNS = (
    re.compile(r"\blevel=(error|fatal|panic)\b", re.IGNORECASE),
    re.compile(r"\b(CRITICAL|FATAL|ERROR)\b"),
    re.compile(r"\bCommandError\b"),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"\bexception\b", re.IGNORECASE),
    re.compile(r"\bfailed\b", re.IGNORECASE),
    re.compile(r"\bforbidden by access permissions\b", re.IGNORECASE),
    re.compile(r"\baccess is denied\b", re.IGNORECASE),
    re.compile(r"\baddress already in use\b", re.IGNORECASE),
    re.compile(r"\bEADDRINUSE\b", re.IGNORECASE),
    re.compile(r"\bfailed to open listener\b", re.IGNORECASE),
)
WARNING_PATTERNS = (
    re.compile(r"\blevel=warn(ing)?\b", re.IGNORECASE),
    re.compile(r"warn(ing)?", re.IGNORECASE),
)
WARNING_PREFIXES = ("warning:", "warn:")
IGNORED_LINE_PATTERNS = (
    re.compile(r"CommandError:\s+A sync is already running for this scope\.", re.IGNORECASE),
    re.compile(r'\blevel=error\b.*msg="Request error".*error="net/http:\s+abort Handler"', re.IGNORECASE),
    re.compile(r'\blevel=error\b.*msg="Partial data response error".*pluginId=yesoreyeram-infinity-datasource.*status code\s+:\s+400 Bad Request', re.IGNORECASE),
    re.compile(r'\blevel=error\b.*msg="Plugin Request Completed".*pluginId=yesoreyeram-infinity-datasource.*statusSource=downstream.*status=error', re.IGNORECASE),
    re.compile(r'\blevel=warn\b.*msg="SQLite database file has broader permissions than it should"', re.IGNORECASE),
    re.compile(r'\blevel=warn\b.*msg="skipped registering status sub-resource that does not support dual writing"', re.IGNORECASE),
)
MAX_FINDINGS_PER_SEVERITY = 20


@dataclass(slots=True, frozen=True)
class BootFinding:
    severity: str
    path: Path
    line_number: int
    line: str


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    since_timestamp = parse_since_timestamp(args.since_utc)
    dashboard_workspace = Path(args.dashboard_workspace).resolve()
    ai_base_workspace = Path(args.ai_base_workspace).resolve() if args.ai_base_workspace else None
    log_paths = collect_log_paths(
        dashboard_workspace=dashboard_workspace,
        ai_base_workspace=ai_base_workspace,
        dashboard_state_path=Path(args.dashboard_state) if args.dashboard_state else default_dashboard_state_path(dashboard_workspace),
        ai_base_state_path=Path(args.ai_base_state) if args.ai_base_state else default_ai_base_state_path(ai_base_workspace),
        stack_log_directory=Path(args.stack_log_directory) if args.stack_log_directory else None,
        explicit_log_files=tuple(Path(path) for path in args.log_file),
        since_timestamp=since_timestamp,
        include_ai_base_logs=args.require_ai_base_state,
    )
    findings = []
    state_findings = inspect_state_files(
        dashboard_state_path=Path(args.dashboard_state) if args.dashboard_state else default_dashboard_state_path(dashboard_workspace),
        ai_base_state_path=Path(args.ai_base_state) if args.ai_base_state else default_ai_base_state_path(ai_base_workspace),
        require_dashboard_state=args.require_dashboard_state,
        require_ai_base_state=args.require_ai_base_state,
    )
    findings.extend(state_findings)
    for log_path in log_paths:
        findings.extend(scan_log_file(log_path))

    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]
    phase_text = f" phase={args.phase}" if args.phase else ""
    print(f"Boot log audit{phase_text}: scanned {len(log_paths)} log file(s).")
    if errors:
        print(f"Boot log audit failed: {len(errors)} error finding(s).")
        print_findings(errors)
    if warnings:
        print(f"Boot log audit warnings: {len(warnings)} warning finding(s).")
        print_findings(warnings)
    if not errors and not warnings:
        print("Boot log audit passed: no actionable errors or warnings found.")
    return 1 if errors else 0


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit stack boot logs for errors and warnings.")
    parser.add_argument("--dashboard-workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--ai-base-workspace", default="")
    parser.add_argument("--dashboard-state", default="")
    parser.add_argument("--ai-base-state", default="")
    parser.add_argument("--stack-log-directory", default="")
    parser.add_argument("--since-utc", default="")
    parser.add_argument("--phase", default="")
    parser.add_argument("--require-dashboard-state", action="store_true")
    parser.add_argument("--require-ai-base-state", action="store_true")
    parser.add_argument("--log-file", action="append", default=[])
    return parser.parse_args(argv)


def collect_log_paths(
    dashboard_workspace: Path,
    ai_base_workspace: Path | None,
    dashboard_state_path: Path,
    ai_base_state_path: Path | None,
    stack_log_directory: Path | None,
    explicit_log_files: Sequence[Path],
    since_timestamp: float | None,
    include_ai_base_logs: bool,
) -> tuple[Path, ...]:
    paths: list[Path] = []
    paths.extend(explicit_log_files)
    paths.extend(log_paths_from_dashboard_state(dashboard_state_path))
    paths.extend(recent_logs(dashboard_workspace / "state" / "e2e" / "port-lifecycle" / "logs", since_timestamp))
    if stack_log_directory is not None:
        paths.extend(recent_logs(stack_log_directory, since_timestamp))
    if ai_base_workspace is not None and include_ai_base_logs:
        paths.extend(recent_logs(ai_base_workspace / ".tmp-validation" / "runtime", since_timestamp))
        paths.extend(recent_logs(ai_base_workspace / ".tmp-validation" / "runtime" / "logs", since_timestamp))
    if ai_base_state_path is not None and ai_base_state_path.exists():
        paths.append(ai_base_state_path)
    return tuple(unique_existing_paths(paths))


def inspect_state_files(
    dashboard_state_path: Path,
    ai_base_state_path: Path | None,
    require_dashboard_state: bool,
    require_ai_base_state: bool,
) -> list[BootFinding]:
    findings: list[BootFinding] = []
    if require_dashboard_state and not dashboard_state_path.exists():
        findings.append(BootFinding("error", dashboard_state_path, 1, "Dashboard lifecycle state file is missing."))
    if ai_base_state_path is None:
        return findings
    if require_ai_base_state and not ai_base_state_path.exists():
        findings.append(BootFinding("error", ai_base_state_path, 1, "AI Base dev-stack state file is missing."))
        return findings
    if not ai_base_state_path.exists():
        return findings
    try:
        state = json.loads(read_text(ai_base_state_path))
    except (OSError, json.JSONDecodeError) as error:
        findings.append(BootFinding("error", ai_base_state_path, 1, f"AI Base dev-stack state could not be read: {error}"))
        return findings
    startup = state.get("startup", {})
    startup_state = str(startup.get("state") or "")
    last_error = startup.get("lastError")
    if startup_state.lower() == "failed":
        findings.append(BootFinding("error", ai_base_state_path, 1, f"AI Base startup state is failed: {last_error or 'no lastError recorded'}"))
    elif last_error:
        findings.append(BootFinding("error", ai_base_state_path, 1, f"AI Base startup recorded lastError: {last_error}"))
    return findings


def log_paths_from_dashboard_state(state_path: Path) -> tuple[Path, ...]:
    if not state_path.exists():
        return ()
    try:
        payload = json.loads(read_text(state_path))
    except (OSError, json.JSONDecodeError):
        return ()
    paths: list[Path] = []
    for service in payload.get("services", {}).values():
        if not isinstance(service, dict):
            continue
        for key in ("stdout_log", "stderr_log"):
            value = service.get(key)
            if value:
                paths.append(Path(str(value)))
    return tuple(paths)


def recent_logs(directory: Path, since_timestamp: float | None) -> tuple[Path, ...]:
    if not directory.exists():
        return ()
    paths = []
    for pattern in ("*.log", "*.out", "*.err"):
        for path in directory.glob(pattern):
            if since_timestamp is not None and path.stat().st_mtime < since_timestamp:
                continue
            paths.append(path)
    return tuple(paths)


def scan_log_file(path: Path) -> list[BootFinding]:
    findings: list[BootFinding] = []
    try:
        lines = read_text(path).splitlines()
    except OSError as error:
        return [BootFinding("error", path, 1, f"Boot log could not be read: {error}")]
    has_ignored_powershell_command = any(any(pattern.search(line) for pattern in IGNORED_LINE_PATTERNS) for line in lines)
    ignored_line_numbers = windows_proactor_client_reset_line_numbers(lines)
    for line_number, line in enumerate(lines, start=1):
        if line_number in ignored_line_numbers:
            continue
        severity = classify_line(line, has_ignored_powershell_command=has_ignored_powershell_command)
        if severity:
            findings.append(BootFinding(severity, path, line_number, line.strip()))
    return findings


def classify_line(line: str, has_ignored_powershell_command: bool = False) -> str:
    normalized = line.strip().lower()
    if has_ignored_powershell_command and is_powershell_error_metadata(line):
        return ""
    if any(pattern.search(line) for pattern in IGNORED_LINE_PATTERNS):
        return ""
    if any(pattern.search(line) for pattern in WARNING_PATTERNS) or normalized.startswith(WARNING_PREFIXES):
        if not any(pattern.search(line) for pattern in HARD_PATTERNS[:5]) and "access is denied" not in normalized and "forbidden by access permissions" not in normalized:
            return "warning"
    if any(pattern.search(line) for pattern in HARD_PATTERNS):
        return "error"
    return ""


def is_powershell_error_metadata(line: str) -> bool:
    stripped = line.strip()
    return (
        stripped.startswith("At ")
        or stripped.startswith("+")
        or stripped.startswith("~")
        or stripped.startswith("+ CategoryInfo")
        or stripped.startswith("+ FullyQualifiedErrorId")
    )


def windows_proactor_client_reset_line_numbers(lines: Sequence[str]) -> set[int]:
    ignored: set[int] = set()
    for index, line in enumerate(lines):
        if "_ProactorBasePipeTransport._call_connection_lost" not in line:
            continue
        stop_index = min(len(lines), index + 12)
        for candidate_index in range(index + 1, stop_index):
            candidate = lines[candidate_index]
            if "ConnectionResetError:" in candidate and "[WinError 10054]" in candidate:
                ignored.update(range(index + 1, candidate_index + 2))
                break
    return ignored


def print_findings(findings: Sequence[BootFinding]) -> None:
    for finding in findings[:MAX_FINDINGS_PER_SEVERITY]:
        print(f"  [{finding.severity}] {finding.path}:{finding.line_number}: {finding.line}")
    remaining = len(findings) - MAX_FINDINGS_PER_SEVERITY
    if remaining > 0:
        print(f"  ... {remaining} more finding(s) omitted")


def unique_existing_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    unique: dict[str, Path] = {}
    for path in paths:
        resolved = path.resolve()
        if resolved.exists() and resolved.is_file():
            unique[str(resolved).lower()] = resolved
    return tuple(unique[key] for key in sorted(unique))


def read_text(path: Path) -> str:
    content = path.read_bytes()
    if content.startswith(b"\xff\xfe") or content.startswith(b"\xfe\xff"):
        return content.decode("utf-16", errors="replace")
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig", errors="replace")
    return content.decode("utf-8", errors="replace")


def default_dashboard_state_path(workspace: Path) -> Path:
    return workspace / "state" / "e2e" / "port-lifecycle" / "metrics-bug-trend-default.json"


def default_ai_base_state_path(workspace: Path | None) -> Path | None:
    if workspace is None:
        return None
    return workspace / ".tmp-validation" / "runtime" / "dev-stack-state.dashboard_query_agent.json"


def parse_since_timestamp(value: str) -> float | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized).astimezone(timezone.utc).timestamp()


if __name__ == "__main__":
    sys.exit(main())
