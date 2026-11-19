"""Reconcile pytest JUnit XML against an execution inventory."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

from scripts.validation.project_full_stack_support import digest_file, read_json
from scripts.validation.windows_qualification_evidence import case_id, validate_junit
from scripts.validation.windows_qualification_inputs import QualificationError, canonical
from scripts.validation.pytest_execution_inventory import junit_identity, output_paths_match


INVENTORY_KIND = "pytest-execution-inventory"
RECONCILIATION_KIND = "pytest-junit-reconciliation"
RECONCILIATION_SCOPE = "pytest-junit-parent-subtest-reconciliation"
TOTAL_ATTRS = ("tests", "failures", "errors", "skipped")
INVENTORY_KEYS = {
    "schema_version", "kind", "exitstatus", "pytest_args", "rootdir", "inventory_path",
    "collected", "collected_order", "primary", "subtests",
    "nonpass_reports", "collection_reports", "deselected",
}


class ReconciliationError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise ReconciliationError(message)


def _path(value: str | Path, *, must_exist: bool, label: str) -> Path:
    try:
        return canonical(value, must_exist=must_exist)
    except Exception as error:
        raise ReconciliationError(f"{label} path is not canonical") from error


def _hash_ref(path: Path) -> dict:
    return {"path": str(path), "sha256": digest_file(path)}


def _require_hash(ref: dict, label: str) -> Path:
    path = _path(ref.get("path", ""), must_exist=True, label=label)
    if digest_file(path) != ref.get("sha256"):
        _fail(f"{label} hash mismatch")
    return path


def _expected_args(values) -> list[str]:
    return [str(item) for item in values]


def _require_dict(value, label: str) -> dict:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return value


def _require_str_list(value, label: str) -> list[str]:
    if type(value) is not list or any(type(item) is not str for item in value):
        _fail(f"{label} must be a string list")
    return value


def _require_report_list(value, label: str) -> list[dict]:
    if type(value) is not list or any(type(item) is not dict for item in value):
        _fail(f"{label} must be a report object list")
    return value


def _require_str_map(value, label: str) -> dict[str, str]:
    if type(value) is not dict or any(type(k) is not str or type(v) is not str for k, v in value.items()):
        _fail(f"{label} must be a string map")
    return value


def _require_int(value, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be an integer")
    return value


def _validate_inventory(inventory: dict, inventory_path: Path, *, pytest_args, repo_root: Path) -> dict:
    inventory = _require_dict(inventory, "inventory")
    if set(inventory) != INVENTORY_KEYS:
        _fail("inventory schema mismatch")
    if _require_int(inventory["schema_version"], "inventory schema_version") != 1:
        _fail("inventory schema_version mismatch")
    if inventory["kind"] != INVENTORY_KIND:
        _fail("inventory kind mismatch")
    if _require_int(inventory["exitstatus"], "inventory exitstatus") != 0:
        _fail("pytest exit status was not zero")
    if _require_str_list(inventory["pytest_args"], "pytest_args") != _expected_args(pytest_args):
        _fail("pytest args mismatch")
    if _path(inventory["rootdir"], must_exist=True, label="rootdir") != repo_root:
        _fail("rootdir mismatch")
    if _path(inventory["inventory_path"], must_exist=True, label="inventory_path") != inventory_path:
        _fail("inventory path mismatch")

    collected = _require_str_map(inventory["collected"], "collected")
    order = _require_str_list(inventory["collected_order"], "collected_order")
    if not collected:
        _fail("empty collected inventory")
    if len(order) != len(collected) or set(order) != set(collected):
        _fail("collected order mismatch")
    identities = [collected[nodeid] for nodeid in order]
    if any(not nodeid or junit_identity(nodeid) != collected[nodeid] for nodeid in order):
        _fail("collected JUnit identity mapping mismatch")
    if len(identities) != len(set(identities)):
        _fail("duplicate collected JUnit identity")

    nonpass = _require_report_list(inventory["nonpass_reports"], "nonpass_reports")
    collection = _require_report_list(inventory["collection_reports"], "collection_reports")
    deselected = _require_str_list(inventory["deselected"], "deselected")
    if nonpass or collection:
        _fail("nonpass reports present")
    if deselected:
        _fail("deselected tests present")

    primary = _require_dict(inventory["primary"], "primary")
    subtests = _require_dict(inventory["subtests"], "subtests")
    if any(type(k) is not str or _require_int(v, "primary count") != 1 for k, v in primary.items()):
        _fail("primary pass inventory mismatch")
    if any(type(k) is not str or _require_int(v, "subtest count") <= 0 for k, v in subtests.items()):
        _fail("subtest pass inventory mismatch")
    unknown = (set(primary) | set(subtests)) - set(collected)
    if unknown:
        _fail("unknown parent/subtest node in inventory")
    if set(primary) != set(collected):
        _fail("primary pass inventory mismatch")
    return {"identities": identities, "parent_count": len(identities), "passed_subtest_count": sum(subtests.values())}


def _one_suite(root: ET.Element) -> ET.Element:
    if root.tag == "testsuite":
        suites = [root]
    elif root.tag == "testsuites":
        suites = [child for child in root if child.tag == "testsuite"]
    else:
        _fail("malformed JUnit root")
    if len(suites) != 1:
        _fail("exactly one JUnit testsuite is supported")
    return suites[0]


def _total_attr(suite: ET.Element, name: str) -> int:
    if name not in suite.attrib:
        _fail(f"JUnit {name} total is missing")
    text = suite.attrib[name]
    if not text.isascii() or not text.isdecimal():
        _fail(f"JUnit {name} total is not a nonnegative integer")
    return int(text)


def _signature(element: ET.Element):
    return (
        element.tag,
        tuple(element.attrib.items()),
        element.text,
        element.tail,
        tuple(_signature(child) for child in list(element)),
    )


def _case_signatures(root: ET.Element) -> list:
    return [_signature(case) for case in _one_suite(root).iter("testcase")]


def _parse_junit(raw_path: Path, identities: list[str]) -> dict:
    try:
        root = ET.parse(raw_path).getroot()
    except ET.ParseError as error:
        raise ReconciliationError("malformed JUnit XML") from error
    suite = _one_suite(root)
    cases = [case for case in suite.iter("testcase")]
    totals = {name: _total_attr(suite, name) for name in TOTAL_ATTRS}
    actual = {
        "tests": len(cases),
        "failures": sum(len(case.findall("failure")) for case in cases),
        "errors": sum(len(case.findall("error")) for case in cases),
        "skipped": sum(len(case.findall("skipped")) for case in cases),
    }
    if any(totals[name] or actual[name] for name in ("failures", "errors", "skipped")):
        _fail("JUnit failures/errors/skips are not zero")
    ids = [case_id(case) for case in cases]
    if ids != identities:
        _fail("JUnit testcase identity inventory mismatch")
    if len(ids) != len(set(ids)):
        _fail("duplicate JUnit testcase identity")
    return {"root": root, "totals": totals, "actual": actual, "cases": ids}


def _derived_bytes(junit: dict) -> bytes:
    root = junit["root"]
    derived = deepcopy(root)
    _one_suite(derived).set("tests", str(junit["actual"]["tests"]))
    if _case_signatures(root) != _case_signatures(derived):
        _fail("derived testcase subtrees changed")
    return ET.tostring(derived, encoding="utf-8", xml_declaration=True)


def _check(raw_path: Path, inventory_path: Path, *, pytest_args, repo_root: Path) -> tuple[dict, bytes]:
    inv = _validate_inventory(read_json(inventory_path), inventory_path, pytest_args=pytest_args, repo_root=repo_root)
    junit = _parse_junit(raw_path, inv["identities"])
    parent_count = inv["parent_count"]
    subtest_count = inv["passed_subtest_count"]
    raw_total = junit["totals"]["tests"]
    if raw_total == parent_count:
        accepted = "parents"
    elif raw_total == parent_count + subtest_count and subtest_count:
        accepted = "parents_plus_passed_subtests"
    else:
        _fail("raw tests total is not an accepted parent/subtest aggregate")
    if not output_paths_match(_expected_args(pytest_args), raw_path, inventory_path):
        _fail("pytest output paths mismatch")
    return {
        "raw_total_accepted_as": accepted,
        "raw_tests_total": raw_total,
        "collected_parent_count": parent_count,
        "passed_subtest_count": subtest_count,
        "derived_tests_total": junit["actual"]["tests"],
        "cases": junit["cases"],
    }, _derived_bytes(junit)


def reconcile_junit(raw_path: str | Path, inventory_path: str | Path, output_path: str | Path, *, pytest_args, repo_root) -> dict:
    repo = _path(repo_root, must_exist=True, label="repo_root")
    raw = _path(raw_path, must_exist=True, label="raw JUnit")
    inventory = _path(inventory_path, must_exist=True, label="execution inventory")
    output = _path(output_path, must_exist=False, label="output")
    if output.exists():
        _fail("output path must be fresh")
    sources = {"raw_junit": _hash_ref(raw), "execution_inventory": _hash_ref(inventory)}
    proof, data = _check(raw, inventory, pytest_args=pytest_args, repo_root=repo)
    _require_hash(sources["raw_junit"], "raw JUnit")
    _require_hash(sources["execution_inventory"], "execution inventory")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as stream:
            stream.write(data)
    except FileExistsError as error:
        raise ReconciliationError("output path must be fresh") from error
    try:
        checked = validate_junit(output)
    except QualificationError as error:
        raise ReconciliationError(str(error)) from error
    record = {
        "schema_version": 1,
        "kind": RECONCILIATION_KIND,
        "scope": RECONCILIATION_SCOPE,
        "status": "PASS",
        "no_new_test_execution": True,
        "pytest": {"args": _expected_args(pytest_args), "rootdir": str(repo)},
        "sources": sources,
        "derived": {"junit": {**_hash_ref(output), "tests": checked["tests"], "cases": checked["cases"]}},
        "proof": proof,
    }
    validate_reconciled_junit(record, pytest_args=pytest_args, repo_root=repo)
    _require_hash(sources["raw_junit"], "raw JUnit")
    _require_hash(sources["execution_inventory"], "execution inventory")
    return record


def validate_reconciled_junit(record: dict, *, pytest_args, repo_root) -> dict:
    record = _require_dict(record, "reconciliation record")
    if _require_int(record.get("schema_version"), "record schema_version") != 1:
        _fail("reconciliation record schema_version mismatch")
    if record.get("kind") != RECONCILIATION_KIND or record.get("scope") != RECONCILIATION_SCOPE:
        _fail("reconciliation record identity mismatch")
    if record.get("status") != "PASS":
        _fail("reconciliation record status mismatch")
    if record.get("no_new_test_execution") is not True:
        _fail("reconciliation replay must not execute tests")
    repo = _path(repo_root, must_exist=True, label="repo_root")
    if record.get("pytest") != {"args": _expected_args(pytest_args), "rootdir": str(repo)}:
        _fail("pytest provenance mismatch")
    raw = _require_hash(record["sources"]["raw_junit"], "raw JUnit")
    inventory = _require_hash(record["sources"]["execution_inventory"], "execution inventory")
    output = _require_hash(record["derived"]["junit"], "derived JUnit")
    proof, data = _check(raw, inventory, pytest_args=pytest_args, repo_root=repo)
    if output.read_bytes() != data:
        _fail("derived output mismatch")
    if proof != record.get("proof"):
        _fail("reconciliation proof mismatch")
    try:
        checked = validate_junit(output)
    except QualificationError as error:
        raise ReconciliationError(str(error)) from error
    derived = record.get("derived", {}).get("junit", {})
    if checked["sha256"] != derived.get("sha256") or checked["cases"] != derived.get("cases"):
        _fail("derived JUnit binding mismatch")
    _require_hash(record["sources"]["raw_junit"], "raw JUnit")
    _require_hash(record["sources"]["execution_inventory"], "execution inventory")
    _require_hash(record["derived"]["junit"], "derived JUnit")
    return checked
