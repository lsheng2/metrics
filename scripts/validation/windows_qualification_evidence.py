"""Evidence validation for Windows runtime qualification."""
from __future__ import annotations

from pathlib import Path
import hashlib
import re
import xml.etree.ElementTree as ET

from scripts.validation.project_full_stack_support import read_json
from scripts.validation.windows_qualification_inputs import (
    QualificationError,
    canonical,
    digest_file,
    path_in_allowed_roots,
    require_hash,
)
from scripts.validation.windows_qualification_profiles import (
    clause_evidence_keys,
    require_profile,
    validate_canonical_census,
)


MODULE_LANES = [
    "ai_host/tests",
    "metrics/tests",
    "bug_metrics/tests",
    "jira_sync/tests",
    "ui_web/tests",
    "project_management/tests",
    "scripts/tests",
]
SELF_PRODUCED_TASKS = {"5.11", "10.2"}
NON_PASS_CLAUSES = {("5.10", "asgi-nonapplicability")}
FORBIDDEN_ARGV = {"--collect-only", "--setup-only", "--lf", "--failed-first", "-k"}
FORBIDDEN_PREFIXES = ("--timeout",)
REQUIREMENT_DIGEST_POLICY = "Original row text excluding its mutable checkbox; this is the initial census generation."
TASKS_PATH = "openspec/changes/embed-ai-base-runtime-in-process/tasks.md"
NATIVE_CONFORMANCE_KIND = "windows-host-conformance"
PERFORMANCE_KIND = "windows-host-performance"
NATIVE_CONFORMANCE_KEYS = {
    "clause:10.4:B1-native-second-signal:functional",
    "clause:10.4:B4-disconnect-leaks:functional",
    "clause:10.4:B5-stream-stop:functional",
}


def is_performance_evidence_key(key: str) -> bool:
    return key == "task:10.4" or key.endswith(":performance")


def validate_argv(argv: list[str]) -> None:
    if any(item in FORBIDDEN_ARGV or item.startswith(FORBIDDEN_PREFIXES) for item in argv):
        raise QualificationError("forbidden evidence command option")
    if any(item in {";", "&&", "||", "|", ">", "<"} for item in argv):
        raise QualificationError("shell operators are not evidence")


def case_id(case: ET.Element) -> str:
    classname = case.attrib.get("classname", "")
    name = case.attrib.get("name", "")
    if not classname or not name:
        raise QualificationError("JUnit testcase inventory is unnamed")
    return f"{classname}::{name}"


def validate_junit(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise QualificationError("malformed JUnit XML") from error
    if root.tag == "testsuite":
        suites = [root]
    elif root.tag == "testsuites":
        suites = [child for child in root if child.tag == "testsuite"]
    else:
        raise QualificationError("malformed JUnit root")
    if not suites:
        raise QualificationError("missing JUnit testsuite")
    cases = [case for suite in suites for case in suite.iter("testcase")]
    totals = {name: sum(int(suite.attrib.get(name, "0") or 0) for suite in suites) for name in ("tests", "failures", "errors", "skipped")}
    actual = {
        "tests": len(cases),
        "failures": sum(len(case.findall("failure")) for case in cases),
        "errors": sum(len(case.findall("error")) for case in cases),
        "skipped": sum(len(case.findall("skipped")) for case in cases),
    }
    if totals != actual:
        raise QualificationError("JUnit aggregate and testcase inventory disagree")
    if actual["tests"] <= 0:
        raise QualificationError("empty test selection")
    if actual["failures"] or actual["errors"] or actual["skipped"]:
        raise QualificationError("JUnit failures, errors or skips present")
    ids = [case_id(case) for case in cases]
    if len(ids) != len(set(ids)):
        raise QualificationError("duplicate JUnit testcase inventory")
    return {**actual, "cases": ids, "sha256": digest_file(path)}


def binding_identity(binding: dict, source: dict, candidate: dict, fixtures: dict) -> None:
    if binding.get("source_commit") != source["commit"]:
        raise QualificationError("stale source evidence")
    if binding.get("candidate_wheel_sha256") != candidate["wheel_sha256"]:
        raise QualificationError("mixed candidate evidence")
    if binding.get("fixture_vector_sha256") != fixtures.get("fixture_vector_sha256"):
        raise QualificationError("stale fixture evidence")
    if binding.get("fresh") is True:
        return
    reuse = binding.get("reuse", {})
    if reuse.get("dependency_scope_unchanged") is not True or not reuse.get("scope"):
        raise QualificationError("reused evidence lacks unchanged dependency scope")


def validate_junit_binding(key: str, path: Path, binding: dict) -> dict:
    mapped = binding.get("cases") or []
    if not mapped:
        raise QualificationError("Junit evidence binding lacks concrete cases")
    junit = validate_junit(path)
    missing = sorted(set(mapped) - set(junit["cases"]))
    if missing:
        raise QualificationError(f"mapped testcase missing from JUnit: {missing[0]}")
    return {**junit, "mapped_cases": mapped, "kind": "junit"}


def validate_binding(key: str, binding: dict, request: dict, roots: tuple[Path, ...]) -> dict:
    if key not in (binding.get("covers") or []):
        raise QualificationError(f"{key} is not covered by its evidence binding")
    if "argv" in binding:
        validate_argv([str(item) for item in binding["argv"]])
    path = canonical(binding["path"], must_exist=True)
    if not path_in_allowed_roots(path, roots):
        raise QualificationError(f"{key} evidence is outside allowed roots")
    require_hash(path, binding["sha256"], f"{key} evidence")
    binding_identity(binding, request["source"], request["candidate"], request["fixtures"])
    kind = binding.get("kind")
    if request.get("native_conformance") and key in NATIVE_CONFORMANCE_KEYS and kind not in {NATIVE_CONFORMANCE_KIND, "native"}:
        raise QualificationError("native conformance evidence requires the owned semantic checker")
    if is_performance_evidence_key(key) and kind != PERFORMANCE_KIND:
        raise QualificationError("performance requires producer-owned native measurement evidence")
    if is_performance_evidence_key(key):
        from scripts.validation.windows_host_performance_contract import validate_performance_contract
        validate_performance_contract(request, roots, mode=request.get("performance", {}).get("mode"))
        from scripts.validation.windows_host_performance_evidence import validate_bound_receipt
        return validate_bound_receipt(key, path, request)
    if kind in {NATIVE_CONFORMANCE_KIND, "native"}:
        from scripts.validation.windows_host_conformance_evidence import validate_bound_receipt
        return validate_bound_receipt(key, path, request)
    if kind == "junit":
        return validate_junit_binding(key, path, binding)
    if kind == "windows-migration-rehearsal":
        from scripts.validation.windows_migration_evidence import validate_bound_receipt
        return validate_bound_receipt(key, path, request)
    if kind in {"receipt", "native"}:
        raise QualificationError(f"{kind} evidence kind is unsupported until its owned semantic checker is implemented")
    raise QualificationError(f"{key} has unsupported evidence kind")


def required_evidence_keys(coverage: dict, *, profile: str) -> list[str]:
    require_profile(profile)
    task_groups = coverage.get("task_groups")
    clauses = coverage.get("clauses")
    digests = coverage.get("source_requirement_digests")
    if not isinstance(task_groups, list) or not task_groups:
        raise QualificationError("coverage task_groups are empty")
    if not isinstance(clauses, list) or not clauses:
        raise QualificationError("coverage clauses are empty")
    if not isinstance(digests, dict) or not digests:
        raise QualificationError("coverage source requirement digests are empty")
    if coverage.get("requirement_digest_policy") != REQUIREMENT_DIGEST_POLICY:
        raise QualificationError("missing or unsupported requirement digest policy")
    required: set[str] = set()
    for row in task_groups:
        task_ids = row.get("task_ids") or []
        if not task_ids:
            raise QualificationError("coverage task row lacks task ids")
        for task_id in task_ids:
            if task_id not in digests:
                raise QualificationError(f"coverage digest missing for {task_id}")
            if task_id == "10.4" and profile == "functional":
                continue
            if not str(row.get("classification", "")).startswith("deferred") and task_id not in SELF_PRODUCED_TASKS:
                required.add(f"task:{task_id}")
    for row in clauses:
        task_id = row.get("task_id")
        clause_id = row.get("clause_id")
        if not task_id or not clause_id:
            raise QualificationError("coverage clause row lacks identity")
        if task_id not in digests:
            raise QualificationError(f"coverage digest missing for {task_id}")
        if (task_id, clause_id) not in NON_PASS_CLAUSES and not str(row.get("classification", "")).startswith("deferred"):
            required.update(clause_evidence_keys(task_id, clause_id, profile=profile))
    if not required:
        raise QualificationError("coverage has no mandatory evidence rows")
    return sorted(required)


def validate_coverage(request: dict, coverage_path: Path, roots: tuple[Path, ...]) -> dict:
    coverage = read_json(coverage_path)
    validate_canonical_census(coverage, roots[0])
    profile = require_profile(request["acceptance_profile"])
    required = required_evidence_keys(coverage, profile=profile)
    validate_requirement_digests(coverage, roots[0] / TASKS_PATH)
    bindings = request["checks"].get("evidence_bindings", {})
    missing = [key for key in required if key not in bindings]
    if missing:
        raise QualificationError(f"missing evidence binding: {missing[0]}")
    return {
        "required_input_evidence": required,
        "deferred_input_evidence": sorted(set(required_evidence_keys(coverage, profile="full")) - set(required)),
        "scope_deferrals": [row for row in coverage["task_groups"] if str(row.get("classification", "")).startswith("deferred")],
        "validated": {key: validate_binding(key, bindings[key], request, roots) for key in required},
        "coverage_sha256": digest_file(coverage_path),
    }


def validate_requirement_digests(coverage: dict, tasks_path: Path) -> None:
    if coverage.get("requirement_digest_policy") != REQUIREMENT_DIGEST_POLICY:
        raise QualificationError("missing or unsupported requirement digest policy")
    actual = {}
    text = tasks_path.read_text(encoding="utf-8")
    _, separator, original = text.partition("## Original Requirements And Evidence")
    if not separator:
        raise QualificationError("original requirement section is missing")
    for match in re.finditer(r"(?m)^- \[[ x]\] (([A-Z0-9][A-Z0-9.]*\.[A-Z0-9.]+) .*)$", original):
        row, task_id = match.groups()
        if task_id in actual:
            raise QualificationError("duplicate original task identity")
        actual[task_id] = hashlib.sha256(row.encode("utf-8")).hexdigest()
    if not actual or coverage.get("source_requirement_digests") != actual:
        raise QualificationError("original requirement digest mismatch")
    census_ids = [task_id for row in coverage["task_groups"] for task_id in row["task_ids"]]
    if len(census_ids) != len(set(census_ids)) or set(census_ids) != set(actual):
        raise QualificationError("original task census is incomplete or duplicated")
