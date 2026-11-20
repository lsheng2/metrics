"""Process identity and relevance rules for Windows performance observation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from ai_host.exit_processes import living_children


PERFORMANCE_TEST_MARKERS = (
    "ai_host/tests/conformance_performance_cases.py",
    "ai_host\\tests\\conformance_performance_cases.py",
    "scripts/tests/test_windows_performance",
    "scripts\\tests\\test_windows_performance",
    "scripts/tests/test_windows_host_qualification.py",
    "scripts\\tests\\test_windows_host_qualification.py",
)
PERFORMANCE_VALIDATION_MARKERS = (
    "scripts/validation/windows_host_qualification.py",
    "scripts\\validation\\windows_host_qualification.py",
    "scripts/validation/windows_host_performance.py",
    "scripts\\validation\\windows_host_performance.py",
    "scripts/validation/run_report_authoring_tests.py",
    "scripts\\validation\\run_report_authoring_tests.py",
)
GIT_READ_COMMANDS = {"status", "rev-parse", "diff", "show", "log", "ls-files", "ls-tree", "cat-file", "merge-base"}
GIT_WRITE_COMMANDS = {
    "add", "am", "apply", "branch", "checkout", "cherry-pick", "clean", "commit",
    "merge", "mv", "pull", "push", "rebase", "reset", "restore", "rm", "switch", "tag", "worktree",
}


def _creation_identity_value(created):
    text = str(created or "").strip()
    for pattern in ("%A, %B %d, %Y %I:%M:%S %p", "%m/%d/%Y %I:%M:%S %p"):
        try:
            return datetime.strptime(text, pattern).isoformat()
        except ValueError:
            pass
    return text


def process_identity(pid, created, command_line):
    if not pid or not created or not command_line:
        return None
    return hashlib.sha256(f"{int(pid)}:{_creation_identity_value(created)}:{command_line}".encode("utf-8")).hexdigest()


def _split_command(command_line):
    if not command_line:
        return None
    from scripts.service_lifecycle_engine import platform_ops

    return list(platform_ops.split_command_line(command_line))


def _normalized_text(*parts):
    return " ".join(str(part or "").replace("\\", "/").casefold() for part in parts)


def _command_parts(command_line):
    return [str(part).casefold() for part in (_split_command(command_line) or [])]


def _normalize_parts(command):
    return [str(part).strip().strip('"').replace("\\", "/").casefold() for part in command or ()]


def _python_like(row):
    name = str(row.get("name") or "").casefold()
    executable = str(row.get("executable_path") or "").replace("\\", "/").casefold()
    return name.startswith("python") or name == "py.exe" or "/python" in executable


def _git_like(row, command_line):
    name = str(row.get("name") or "").casefold()
    first = (_command_parts(command_line) or [""])[0]
    return name == "git.exe" or Path(first).name.casefold() in {"git", "git.exe"}


def _git_relevance(command_line):
    parts = _command_parts(command_line)
    for part in parts[1:]:
        value = part.lstrip("-")
        if value in GIT_READ_COMMANDS:
            return "git_read", False
        if value in GIT_WRITE_COMMANDS:
            return "git_write", True
    return "git_unknown", True


def _metrics_relevance(row, *, source_root, owned_root):
    command_line = str(row.get("command_line") or "")
    if command_line and _git_like(row, command_line):
        return _git_relevance(command_line)
    if not command_line:
        if row.get("sensor_error") and (_python_like(row) or _git_like(row, command_line)):
            return "sensor_unresolved", True
        return "tooling_unrelated", False
    text = _normalized_text(command_line, row.get("executable_path"))
    source = _normalized_text(source_root)
    owned = _normalized_text(owned_root)
    if source and source in text:
        if "windows_perf_entry.py" in text or "manage.py" in text:
            return "metrics_runtime", True
        if any(_normalized_text(marker) in text for marker in PERFORMANCE_VALIDATION_MARKERS):
            return "performance_validation", True
        if "pytest" in text and (
            any(_normalized_text(marker) in text for marker in PERFORMANCE_TEST_MARKERS)
            or "scripts/tests" in text
            or "ai_host/tests" in text
        ):
            return "performance_validation", True
    if owned and owned in text and "windows_perf_entry.py" in text:
        return "metrics_runtime", True
    return "tooling_unrelated", False


def enrich_process_observations(records, details_by_pid, *, source_root, owned_root):
    enriched = []
    for row in records:
        item = dict(row)
        details = dict(details_by_pid.get(int(item.get("pid", -1)), {}) or {})
        command_line = details.get("command_line") or item.get("command_line") or ""
        created = details.get("creation_date") or details.get("created") or item.get("created") or ""
        item.update({key: value for key, value in details.items() if value not in (None, "")})
        if command_line:
            item["command_line"] = command_line
            item["command"] = item.get("command") or _split_command(command_line)
        identity = item.get("identity") or process_identity(item.get("pid"), created, command_line)
        if identity:
            item["identity"] = identity
        relevance, is_relevant = _metrics_relevance(item, source_root=source_root, owned_root=owned_root)
        item.setdefault("relevance", relevance)
        if "metrics_workload" not in item:
            item["metrics_workload"] = is_relevant
        enriched.append(item)
    return enriched


def _command_fingerprint(command):
    if command is None:
        return None
    sanitized = [Path(str(command[0])).name] if command else []
    if len(command) > 1:
        sanitized.append(f'argc={len(command)}')
    digest = hashlib.sha256(json.dumps([str(part) for part in command], sort_keys=True).encode()).hexdigest()
    return {'display': ' '.join(sanitized), 'sha256': digest}


def classify_process_observations(records, *, owned_identities):
    processes, blockers = [], []
    for row in records:
        relevant = row.get('metrics_workload') is True
        identity = row.get('identity')
        if relevant and identity in owned_identities:
            classification = 'owned_measurement'
        elif relevant and identity:
            classification = 'foreign_relevant'
        elif relevant:
            classification = 'unresolved_relevant'
        else:
            classification = 'tooling_unrelated'
        item = {
            'pid': row.get('pid'),
            'identity': identity,
            'relevance': row.get('relevance'),
            'classification': classification,
            'command_fingerprint': _command_fingerprint(row.get('command')),
        }
        processes.append(item)
        if classification in {'foreign_relevant', 'unresolved_relevant'}:
            blockers.append(f'{classification}:{row.get("pid")}')
    return {'processes': processes, 'certification_blockers': blockers}


def sanitize_process_rows(records):
    allowed = {"pid", "parent_pid", "name", "threads", "identity", "metrics_workload", "relevance", "sensor_error"}
    return [{key: row[key] for key in allowed if key in row} for row in records]


def owned_process_identity_facts_from_state(state, ops):
    from scripts.service_lifecycle_engine import platform_ops

    identities = set()
    descendants = []
    provenance = state.get('provenance') if isinstance(state, dict) else None
    sle_marker = None
    pid = None
    if isinstance(provenance, dict):
        sle_marker = provenance.get('process_start_marker') or None
        if sle_marker:
            identities.add(str(sle_marker))
    sensor_identity = None
    try:
        pid = int(state.get('pid'))
        command_line = ops.process_command_line(pid)
        created = platform_ops.get_process_created_at(pid)
        sensor_identity = process_identity(pid, created, command_line)
        if sensor_identity:
            identities.add(sensor_identity)
        marker = ops.process_start_marker(pid)
        if marker:
            sle_marker = sle_marker or marker
            identities.add(str(marker))
    except Exception:
        pass
    if pid is not None:
        try:
            child_rows = living_children(root_pid=pid)
        except Exception:
            child_rows = ()
        for child in child_rows:
            child_identity = None
            child_pid = int(child["pid"])
            try:
                child_command = ops.process_command_line(child_pid)
                child_created = platform_ops.get_process_created_at(child_pid)
                child_identity = process_identity(child_pid, child_created, child_command)
                if child_identity:
                    identities.add(child_identity)
            except Exception:
                pass
            descendants.append({
                "pid": child_pid,
                "parent_pid": child.get("parent_pid"),
                "created": child.get("created"),
                "sensor_identity": child_identity,
            })
    listener_identity = None
    if isinstance(provenance, dict):
        listener_pid = provenance.get('listener_pid')
        try:
            if listener_pid is not None:
                marker = ops.process_start_marker(int(listener_pid))
                if marker:
                    listener_identity = marker
                    identities.add(str(marker))
        except Exception:
            pass
    return {
        "identities": identities,
        "sensor_identity": sensor_identity,
        "sle_marker": sle_marker,
        "listener_identity": listener_identity,
        "descendant_identities": descendants,
    }


def owned_process_identities_from_state(state, ops):
    return owned_process_identity_facts_from_state(state, ops)["identities"]


def _load_lifecycle_services(run_root):
    run_root = Path(run_root)
    services = []
    for state_file in run_root.glob("raw/*/lifecycle/*.json"):
        try:
            payload = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        value = payload.get("services")
        if isinstance(value, dict):
            services.extend((state_file, row) for row in value.values() if isinstance(row, dict))
    return services


def _command_is_bound_to_run_root(command, run_root):
    parts = list(command or ())
    if parts.count("--root") != 1:
        return False
    try:
        root = Path(str(parts[parts.index("--root") + 1]).strip('"'))
        return root.is_absolute() and root.resolve().is_relative_to(Path(run_root).resolve())
    except (IndexError, OSError, ValueError):
        return False


def _commands_match(left, right):
    return _normalize_parts(left) == _normalize_parts(right)


def _descendant_pids(root_pid, rows):
    parents = {}
    for row in rows:
        try:
            parents[int(row["pid"])] = int(row.get("parent_pid"))
        except (TypeError, ValueError):
            continue
    owned = {int(root_pid)}
    changed = True
    while changed:
        changed = False
        for pid, parent in parents.items():
            if pid not in owned and parent in owned:
                owned.add(pid)
                changed = True
    return owned


def driver_process_identities(process_rows, driver_pid):
    by_pid = {row["pid"]: row for row in process_rows if type(row.get("pid")) is int}
    row = by_pid.get(driver_pid)
    identities, visited = set(), set()
    while row and row.get("identity") and row["pid"] not in visited:
        visited.add(row["pid"])
        identities.add(row["identity"])
        parent = by_pid.get(row.get("parent_pid"))
        if not row.get("command") or not parent or not _commands_match(row["command"], parent.get("command")):
            break
        row = parent
    return identities


def startup_owned_identities_from_run(run_root, process_rows, *, pending_launches=()):
    rows = []
    by_pid = {}
    for row in process_rows:
        try:
            pid = int(row.get("pid"))
        except (TypeError, ValueError):
            continue
        by_pid[pid] = row
        rows.append(row)
    identities = set()
    matched = []
    for launch in pending_launches:
        command = launch["command"]
        if not _command_is_bound_to_run_root(command, run_root):
            continue
        roots = [
            row for row in rows
            if row.get("parent_pid") == launch["parent_pid"]
            and _commands_match(row.get("command"), command)
        ]
        if len(roots) != 1:
            continue
        for pid in _descendant_pids(roots[0]["pid"], rows):
            identity = by_pid[pid].get("identity")
            if identity:
                identities.add(identity)
                matched.append({"state": "predeclared_launch", "pid": pid})
    for state_file, service in _load_lifecycle_services(run_root):
        if str(service.get("lifecycle_state")) not in {"prepared", "ready"}:
            continue
        command = service.get("command")
        if not isinstance(command, list) or not _command_is_bound_to_run_root(command, run_root):
            continue
        try:
            root_pid = int(service.get("pid"))
        except (TypeError, ValueError):
            continue
        root_row = by_pid.get(root_pid)
        if root_row is None or not _commands_match(root_row.get("command"), command):
            continue
        for pid in _descendant_pids(root_pid, rows):
            identity = by_pid.get(pid, {}).get("identity")
            if identity:
                identities.add(identity)
                matched.append({"state": str(state_file), "service": service.get("name"), "pid": pid})
    return {"identities": identities, "matches": matched}
