"""Process identity and relevance rules for Windows performance observation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from ai_host.exit_processes import living_children
from scripts.validation.windows_host_process_window import (
    owner_registrations_by_instance,
    registration_key,
    ProcessWindowCapture,
    native_process_rows_by_pid,
    terminal_resolution_fact,
)
from scripts.validation.windows_qualification_inputs import QualificationError


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
RELEVANCE_WORKLOAD = {
    "metrics_runtime": True, "performance_validation": True, "sensor_unresolved": True,
    "git_write": True, "git_unknown": True, "git_read": False, "tooling_unrelated": False,
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
    return _normalize_parts(_split_command(command_line))


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
    values = {"-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
    switches = {"--no-optional-locks", "--no-pager", "--paginate", "--literal-pathspecs", "--no-replace-objects"}
    index = 1
    while index < len(parts):
        part = parts[index]
        if part in values:
            if index + 1 >= len(parts) or not parts[index + 1]:
                return "git_unknown", True
            index += 2
        elif "=" in part and part.partition("=")[0] in values - {"-c"}:
            if not part.partition("=")[2]:
                return "git_unknown", True
            index += 1
        elif part in switches:
            index += 1
        else:
            if part in GIT_READ_COMMANDS:
                return "git_read", False
            if part in GIT_WRITE_COMMANDS:
                return "git_write", True
            return "git_unknown", True
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


def classify_process_observations(records, *, owned_identities, owned_process_facts=None, current_run_id=None):
    processes, blockers = [], []
    resolution_facts = []
    registrations = owner_registrations_by_instance(owned_process_facts, current_run_id)
    for row in records:
        relevant = row.get('metrics_workload') is True
        identity = row.get('identity')
        if relevant and identity in owned_identities:
            classification = 'owned_measurement'
        elif relevant and identity:
            classification = 'foreign_relevant'
        elif relevant:
            registration = registrations.get(registration_key(row.get("pid"), (row.get("process_window") or {}).get("native_creation")))
            terminal_fact = terminal_resolution_fact(row, registration, _command_fingerprint) if registration else None
            if terminal_fact is not None:
                classification = 'owned_terminal'
                resolution_facts.append(terminal_fact)
            else:
                classification = 'unresolved_relevant'
        else:
            classification = 'tooling_unrelated'
        item = {
            'pid': row.get('pid'),
            'identity': identity,
            'relevance': row.get('relevance'),
            'classification': classification,
            'command_fingerprint': (
                _command_fingerprint(row["command"]) if row.get("command") is not None
                else row.get("command_fingerprint")
            ),
        }
        processes.append(item)
        if classification in {'foreign_relevant', 'unresolved_relevant'}:
            blockers.append(f'{classification}:{row.get("pid")}')
    return {'processes': processes, 'certification_blockers': blockers, 'process_resolution_facts': resolution_facts}


def sanitize_process_rows(records):
    allowed = {
        "pid", "parent_pid", "name", "threads", "identity", "metrics_workload",
        "relevance", "sensor_error", "process_window",
    }
    return [
        {**{key: row[key] for key in allowed if key in row},
         "command_fingerprint": _command_fingerprint(row.get("command"))}
        for row in records
    ]


def _registration_from_retained_native(pid, ops, platform_ops, *, role, expected_native_creation=None, expected_marker=None):
    pid = int(pid)
    row = native_process_rows_by_pid([pid]).get(pid)
    if not row:
        return None, None, None
    command_line, created, marker = "", "", None
    with ProcessWindowCapture([row]) as capture:
        native = capture.facts().get(pid, {})
        command_line = ops.process_command_line(pid)
        created = platform_ops.get_process_created_at(pid)
        if role == "service_root":
            marker = ops.process_start_marker(pid)
            if not expected_marker or marker != expected_marker:
                return None, None, None
    if expected_native_creation is not None and str(native.get("native_creation")) != str(expected_native_creation):
        return None, None, None
    sensor_identity = process_identity(pid, created, command_line)
    fingerprint = _command_fingerprint(_split_command(command_line))
    if (not fingerprint or not sensor_identity or native.get("handle_opened") is not True
            or native.get("native_creation") in (None, "")
            or native.get("parent_pid") is None or not native.get("image_name")):
        return None, sensor_identity, marker
    return {
        "schema_version": 1,
        "pid": pid,
        "parent_pid": native.get("parent_pid"),
        "image_name": native.get("image_name"),
        "native_creation": native.get("native_creation"),
        "command_fingerprint": fingerprint,
        "sensor_identity": sensor_identity,
        "role": role,
    }, sensor_identity, marker


def owned_process_identity_facts_from_state(state, ops):
    from scripts.service_lifecycle_engine import platform_ops

    facts = {
        "identities": set(), "sensor_identity": None, "sle_marker": None,
        "listener_identity": None, "descendant_identities": [], "registrations": [],
    }
    provenance = state.get("provenance") if isinstance(state, dict) else None
    if not isinstance(provenance, dict) or not provenance.get("process_start_marker"):
        return facts
    try:
        pid = int(state["pid"])
        root, sensor_identity, marker = _registration_from_retained_native(
            pid, ops, platform_ops, role="service_root", expected_marker=provenance["process_start_marker"],
        )
        if root is None:
            return facts
        facts.update(sensor_identity=sensor_identity, sle_marker=marker)
        facts["identities"].update((sensor_identity, marker))
        facts["registrations"].append(root)
        child_rows = living_children(root_pid=pid)
    except QualificationError:
        raise
    except Exception:
        return facts
    for child in child_rows:
        child_pid = int(child["pid"])
        child_identity = None
        try:
            registration, child_identity, _ = _registration_from_retained_native(
                child_pid, ops, platform_ops, role="descendant", expected_native_creation=child["created"],
            )
            if registration is not None and registration["parent_pid"] == child.get("parent_pid"):
                facts["identities"].add(child_identity)
                facts["registrations"].append(registration)
            else:
                child_identity = None
        except QualificationError:
            raise
        except Exception:
            pass
        facts["descendant_identities"].append({
            **child, "sensor_identity": child_identity,
        })
    listener_pid = provenance.get("listener_pid")
    for registration in facts["registrations"]:
        if registration["pid"] == listener_pid:
            facts["listener_identity"] = registration["sensor_identity"]
    return facts


def owned_process_identities_from_state(state, ops):
    return owned_process_identity_facts_from_state(state, ops)["identities"]


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
    return {"identities": identities, "matches": matched}
