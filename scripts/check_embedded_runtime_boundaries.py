"""AST import ownership and scoped event-loop boundary checks."""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.runtime_check_support import classify, cli, inventory, read_text, violation

LOOP_OWNERS = {
    "project_management/services/report_assists.py",
    "project_management/services/project_run_worker.py",
}


def module_matches(name, prefix):
    return name == prefix or name.startswith(prefix + ".")


def imported_names(node, relative):
    if isinstance(node, ast.Import):
        return [item.name for item in node.names]
    module = node.module or ""
    if node.level:
        package = relative.with_suffix("").parts[:-1]
        parent = package[:max(0, len(package) - node.level + 1)]
        module = ".".join((*parent, *module.split("."))).strip(".")
    return [module, *(f"{module}.{item.name}".strip(".") for item in node.names)]


def dotted(node, aliases):
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = dotted(node.value, aliases)
        return f"{parent}.{node.attr}" if parent else ""
    return ""


def check(root):
    root, paths, problems, excluded = inventory(root)
    counts = Counter()
    checked = 0
    for path in paths:
        if path.suffix != ".py" or classify(path) in {"history", "specification", "process-artifact"}:
            continue
        text = read_text(root, path, problems)
        if text is None:
            continue
        checked += 1
        role = classify(path)
        counts[role] += 1
        relative = path.as_posix()
        try:
            tree = ast.parse(text, filename=relative)
        except SyntaxError as error:
            problems.append(violation(relative, "invalid_python", error.lineno or 0))
            continue
        aliases = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            names = imported_names(node, path)
            for item in node.names:
                if isinstance(node, ast.Import):
                    aliases[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
                else:
                    aliases[item.asname or item.name] = names[0] + "." + item.name
            rules = set()
            for name in names:
                if module_matches(name, "ai_base_runtime._internal"):
                    rules.add("private_runtime")
                if module_matches(name, "app"):
                    rules.add("base_app_import")
                if role in {"test", "validation", "documentation"}:
                    continue
                if path.parts[0] != "ai_host" and any(module_matches(name, prefix) for prefix in ("ai_base_runtime", "waitress")):
                    rules.add("runtime_owner")
                if path.parts[0] == "project_management" and module_matches(name, "ai_host"):
                    rules.add("host_dependency")
                if "app/domain/" in relative and any(module_matches(name, prefix) for prefix in ("django", "asgiref", "ai_base_runtime")):
                    rules.add("domain_framework")
            problems.extend(violation(relative, rule, node.lineno) for rule in sorted(rules))
        loop_scoped = role == "production" and (path.parts[0] == "ai_host" or relative in LOOP_OWNERS)
        if loop_scoped:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and dotted(node.func, aliases) == "asyncio.run":
                    problems.append(violation(relative, "loop_runner", node.lineno))
    if not checked:
        problems.append(violation(".", "zero_python_scan"))
    return {
        "schema_version": 1, "passed": not problems, "root": str(root),
        "checked_files": checked, "classified": dict(sorted(counts.items())),
        "violations": problems, "excluded": excluded,
    }


if __name__ == "__main__":
    raise SystemExit(cli(check))
