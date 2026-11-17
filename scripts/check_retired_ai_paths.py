"""Inventory active legacy paths separately from test, history and Linux definitions."""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.runtime_check_support import classify, cli, inventory, read_text, violation

CODE_MARKERS = (
    "ai_base_application_sdk", "ai-base-application-sdk", "/api/ai-dashboard/",
    "connector_endpoint", "TaskRunClient", "AiBackendTarget", "execution_mode",
    "ai_bundle", "METRICS_AI_SIDECAR_ENABLED", "METRICS_AI_BASE_", "METRICS_PROJECT_AI_",
    "METRICS_PROJECT_RUNTIME_FACTORY", "METRICS_REPORT_ASSIST_FACTORY", "dry_run_proof_id",
    "ai-base.host-action", "frontend_url", "project_serve", "metrics.wsgi", "metrics.asgi",
    "uvicorn", "RCA_DASHBOARD_METRICS_BASE_URL", "DASHBOARD_METRICS_BASE_URL",
    "e2e_start_dashboard_ai_stack.ps1", "e2e_stop_dashboard_ai_stack.ps1", "e2e_restart_dashboard_ai_stack.ps1",
)
DOC_MARKERS = (
    "sidecar", "project_serve", "gunicorn", "metrics.wsgi", "metrics.asgi",
    "TaskRunClient", "ai_base_application_sdk",
    "e2e_start_dashboard_ai_stack.ps1", "e2e_stop_dashboard_ai_stack.ps1", "e2e_restart_dashboard_ai_stack.ps1",
)
DOC_PATTERNS = (
    r"installed[ -]SDK",
    r"e2e_bug_trend\.py[^\n]*--force-by-port",
    r"manage\.py\s+runserver",
)
CODE_SUFFIXES = {".py", ".ps1", ".js", ".ts", ".tsx", ".html", ".json", ".yaml", ".yml", ".toml", ".ini", ".txt"}
LINUX_DEFINITIONS = {"ops/docker/Dockerfile"}
POLICY_ASSIGNMENTS = {"CODE_MARKERS", "DOC_MARKERS", "DOC_PATTERNS", "INSTALLER_LITERALS", "ENTRY_MARKERS", "RETIRED_FILES"}
ENTRY_MARKERS = ("ForceByPort", "AiBaseWorkspace", "AiBaseBackendUrl", "AiBaseFrontendUrl", "FullAiChatSmoke")
RETIRED_FILES = {
    "metrics/wsgi.py", "metrics/asgi.py",
    "scripts/e2e_start_dashboard_ai_stack.ps1", "scripts/e2e_stop_dashboard_ai_stack.ps1",
    "scripts/e2e_restart_dashboard_ai_stack.ps1",
}
INSTALLER_ASSIGNMENTS = {"LEGACY_SDK_MODULES", "LEGACY_SDK_DISTRIBUTIONS"}
INSTALLER_LITERALS = {
    "ai_base_application_sdk", "ai_base_sdk", "ai-base-application-sdk", "ai-base-sdk",
}


def policy_spans(path, text):
    """Allow declared detector literals, not arbitrary code in a detector file."""
    if path not in {"scripts/check_retired_ai_paths.py", "scripts/validation/windows_install_smoke.py"}:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    allowed = []
    assignments = POLICY_ASSIGNMENTS if path == "scripts/check_retired_ai_paths.py" else INSTALLER_ASSIGNMENTS
    for node in ast.walk(tree):
        candidates = []
        if (isinstance(node, ast.Assign)
                and isinstance(node.value, (ast.List, ast.Tuple, ast.Set))
                and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in node.value.elts)
                and any(isinstance(target, ast.Name) and target.id in assignments for target in node.targets)):
            candidates = [node.value]
        if (path.endswith("windows_install_smoke.py") and isinstance(node, ast.Call)
                and ast.unparse(node.func) == "importlib.util.find_spec"):
            candidates += node.args
        for candidate in candidates:
            for item in ast.walk(candidate):
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    if path.endswith("windows_install_smoke.py") and item.value not in INSTALLER_LITERALS:
                        continue
                    start = len(lines[item.lineno - 1].encode("utf-8")[:item.col_offset].decode("utf-8"))
                    end = len(lines[item.end_lineno - 1].encode("utf-8")[:item.end_col_offset].decode("utf-8"))
                    allowed.append((offsets[item.lineno - 1] + start, offsets[item.end_lineno - 1] + end))
    return allowed


def check(root, *, platform="windows"):
    if platform not in {"windows", "all"}:
        raise ValueError("Unknown platform scope")
    root, paths, problems, excluded = inventory(root)
    counts = Counter()
    deferred, checked, code_count, docs_count = [], 0, 0, 0
    code_pattern = re.compile("|".join(re.escape(value) for value in sorted(CODE_MARKERS, key=len, reverse=True)))
    doc_pattern = re.compile("|".join([*(re.escape(value) for value in DOC_MARKERS), *DOC_PATTERNS]), re.IGNORECASE)
    entry_pattern = re.compile("|".join(re.escape(value) for value in (*CODE_MARKERS, *ENTRY_MARKERS)))
    for path in paths:
        relative = path.as_posix()
        role = classify(path)
        if relative in RETIRED_FILES:
            problems.append(violation(relative, "retired_entrypoint"))
        if role in {"test", "history", "specification", "process-artifact"}:
            counts[role] += 1
            continue
        document = role == "documentation"
        selected = path.suffix in CODE_SUFFIXES or path.name in {".gitattributes", ".env.example", "Dockerfile"}
        if document:
            selected = path.suffix in {".md", ".json", ".yaml", ".yml", ".py", ".ps1"}
        if not selected:
            continue
        text = read_text(root, path, problems)
        if text is None:
            continue
        checked += 1
        counts[role] += 1
        docs_count += int(document)
        code_count += int(not document)
        pattern = doc_pattern if document else entry_pattern if path.suffix == ".ps1" or role == "editor-entrypoint" else code_pattern
        allowed = policy_spans(relative, text)
        matches = []
        for match in pattern.finditer(text):
            if any(start <= match.start() < end for start, end in allowed):
                continue
            matches.append(violation(relative, "retired_document" if document else "retired_code",
                                     text.count("\n", 0, match.start()) + 1, match.group()))
        if relative in LINUX_DEFINITIONS and platform == "windows":
            deferred.append({"path": relative, "reason": "Owner-deferred Linux deployment definition", "matches": matches})
        else:
            problems.extend(matches)
    if not code_count:
        problems.append(violation(".", "zero_code_scan"))
    if not docs_count:
        problems.append(violation(".", "zero_document_scan"))
    return {
        "schema_version": 1, "passed": not problems, "platform": platform,
        "root": str(root), "checked_files": checked, "code_files": code_count,
        "document_files": docs_count, "classified": dict(sorted(counts.items())),
        "violations": problems, "deferred": deferred, "excluded": excluded,
    }


if __name__ == "__main__":
    raise SystemExit(cli(check, platform=True))
