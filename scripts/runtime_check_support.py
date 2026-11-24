"""Shared source inventory and report output for the embedded-runtime gates."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.validation.project_full_stack_support import reject_reparse_components, write_json

REQUIRED_ROOTS = ("ai_host", "project_management", "metrics", "ui_web", "scripts")
APP_ROOTS = {
    *REQUIRED_ROOTS, "provider_sync", "tasks", "forecast", "velocity",
    "pull_requests", "jira_sync", "jira_history", "bug_metrics",
}
ROOT_EXCLUSIONS = {
    ".git", ".tmp", ".venv", ".venv-embedded", "venv", ".zvec-grep",
    "state", "tmp_ui_validation", "screenshots",
}
CACHE_DIRS = {"__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
VENDOR_ROOTS = (
    "ui_web/static/vendor/", "ui_web/static/js/report_editor/vendor/",
    "provider_sync/out/_jql/",
)
PROCESS_ARTIFACTS = {
    ".github/skills/lsheng2-coding/config.runs.json",
    ".github/skills/lsheng2-coding/config.receipts.json",
}


def violation(path, rule, line=0, detail=""):
    return {"path": str(path), "rule": rule, "line": line, "detail": detail}


def classify(path):
    parts = Path(path).parts
    text = Path(path).as_posix()
    # Document build outputs contain captured historical source and UI text.
    if text in PROCESS_ARTIFACTS or text.startswith("docs/_build/"):
        return "process-artifact"
    if text in {".vscode/tasks.json", ".vscode/launch.json"}:
        return "editor-entrypoint"
    if (len(parts) > 1 and parts[0] in APP_ROOTS and parts[1] == "tests"
            or parts[0] == "tests" or parts[-1] == "conftest.py"):
        return "test"
    if text.startswith("docs/case_study/"):
        return "history"
    if text.startswith("openspec/") and not text.startswith("openspec/docs/current-baseline/"):
        return "specification"
    if text.startswith("scripts/validation/"):
        return "validation"
    if (text in {"README.md", "AI_CONTRACT.md", "AGENTS.md", "CLAUDE.md"}
            or text.startswith((".github/", ".agents/", "docs/", "openspec/docs/current-baseline/"))):
        return "documentation"
    return "production"


def inventory(root):
    root = Path(root)
    problems, paths, excluded = [], [], []
    try:
        reject_reparse_components(root)
        root = root.resolve()
        if not root.is_dir() or any(not (root / name).is_dir() for name in REQUIRED_ROOTS):
            return root, [], [violation(".", "invalid_root", detail="Required project roots are missing")], []
        for directory, dirs, files in os.walk(root, followlinks=False):
            base = Path(directory)
            for name in tuple(dirs):
                relative = (base / name).relative_to(root).as_posix()
                if (name in CACHE_DIRS or relative.split("/")[0] in ROOT_EXCLUSIONS
                        or relative.split("/")[0].startswith(".venv")
                        or any((relative + "/").startswith(prefix) for prefix in VENDOR_ROOTS)):
                    dirs.remove(name)
                    excluded.append(relative)
                    continue
                try:
                    reject_reparse_components(base / name)
                except ValueError:
                    dirs.remove(name)
                    problems.append(violation(relative, "reparse_source"))
            for name in files:
                relative = (base / name).relative_to(root)
                if relative.parts[0] == ".vscode" and relative.as_posix() not in {".vscode/tasks.json", ".vscode/launch.json"}:
                    excluded.append(relative.as_posix())
                    continue
                if name.startswith(".env") and name != ".env.example":
                    excluded.append(relative.as_posix())
                    continue
                try:
                    reject_reparse_components(base / name)
                except ValueError:
                    problems.append(violation(relative.as_posix(), "reparse_source"))
                    continue
                paths.append(relative)
    except (OSError, ValueError):
        problems.append(violation(".", "unreadable_root"))
    return root, sorted(paths), problems, sorted(excluded)


def read_text(root, path, problems):
    try:
        return (root / path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        problems.append(violation(path.as_posix(), "unreadable_source"))
        return None


def cli(check, *, platform=False):
    parser = argparse.ArgumentParser(description="Validate current embedded-runtime source boundaries.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    if platform:
        parser.add_argument("--platform", choices=("windows", "all"), required=True)
    args = parser.parse_args()
    try:
        reject_reparse_components(args.output)
        if args.output.suffix != ".json" or args.output.exists():
            raise ValueError("A new JSON output path is required")
        result = check(args.root, platform=args.platform) if platform else check(args.root)
        write_json(args.output, result)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps({
        "passed": result["passed"], "checked_files": result["checked_files"],
        "violations": len(result["violations"]), "output": str(args.output),
    }))
    return 0 if result["passed"] else 1
