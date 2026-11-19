from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path(sys.executable)
sys.path.insert(0, str(ROOT))


def _env(tmp_path: Path) -> dict[str, str]:
    temp = tmp_path / "env-temp"
    temp.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["TEMP"] = str(temp)
    env["TMP"] = str(temp)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    return env


def _run_pytest_fixture(tmp_path: Path, body: str, *, name: str = "test_sample.py") -> dict:
    root = tmp_path / "synthetic-not-qualification"
    root.mkdir()
    test_path = root / name
    test_path.write_text(body, encoding="utf-8")
    raw = root / "raw.xml"
    inventory = root / "inventory.json"
    basetemp = tmp_path / "basetemp"
    args = [
        str(test_path),
        "-p",
        "scripts.validation.pytest_execution_inventory",
        "--execution-inventory",
        str(inventory),
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(basetemp),
        "--junitxml",
        str(raw),
    ]
    completed = subprocess.run(
        [str(PYTHON), "-m", "pytest", *args],
        cwd=root,
        env=_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return {
        "root": root,
        "args": args,
        "raw": raw,
        "inventory": inventory,
        "completed": completed,
    }


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _suite_totals(path: Path) -> tuple[int, int]:
    root = ET.parse(path).getroot()
    suite = next(root.iter("testsuite"))
    return int(suite.attrib["tests"]), len(list(suite.iter("testcase")))


def _element_signature(element: ET.Element):
    return (
        element.tag,
        tuple(element.attrib.items()),
        element.text,
        element.tail,
        tuple(_element_signature(child) for child in list(element)),
    )


def _case_signatures(path: Path) -> list:
    root = ET.parse(path).getroot()
    return [_element_signature(case) for case in root.iter("testcase")]


def _mutated_xml(source: Path, target: Path, mutator) -> Path:
    root = ET.parse(source).getroot()
    mutator(root)
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
    return target


@pytest.fixture()
def passing_subtest_run(tmp_path: Path) -> dict:
    run = _run_pytest_fixture(
        tmp_path,
        """
def test_plain_parent():
    assert True

def test_parent_with_two_passed_subtests(subtests):
    for value in (1, 2):
        with subtests.test("synthetic", value=value):
            assert value > 0
""",
    )
    assert run["completed"].returncode == 0, run["completed"].stderr
    assert _suite_totals(run["raw"]) == (4, 2)
    inventory = _load(run["inventory"])
    assert sum(inventory["subtests"].values()) == 2
    return run


def test_reconciles_actual_pytest_subtest_aggregate_bug_without_touching_raw(passing_subtest_run: dict) -> None:
    from scripts.validation.pytest_junit_reconciliation import reconcile_junit, validate_reconciled_junit

    output = passing_subtest_run["root"] / "derived.xml"
    before = passing_subtest_run["raw"].read_bytes()
    record = reconcile_junit(
        passing_subtest_run["raw"],
        passing_subtest_run["inventory"],
        output,
        pytest_args=passing_subtest_run["args"],
        repo_root=passing_subtest_run["root"],
    )

    assert passing_subtest_run["raw"].read_bytes() == before
    assert _suite_totals(output) == (2, 2)
    assert _case_signatures(output) == _case_signatures(passing_subtest_run["raw"])
    assert record["kind"] == "pytest-junit-reconciliation"
    assert record["scope"] == "pytest-junit-parent-subtest-reconciliation"
    assert record["status"] == "PASS"
    assert record["no_new_test_execution"] is True
    assert record["proof"]["raw_total_accepted_as"] == "parents_plus_passed_subtests"
    checked = validate_reconciled_junit(record, pytest_args=passing_subtest_run["args"], repo_root=passing_subtest_run["root"])
    assert checked["tests"] == 2


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("import pytest\n\ndef test_skip():\n    pytest.skip('synthetic skip')\n", "nonpass"),
        ("import pytest\n\n@pytest.mark.xfail(reason='synthetic')\ndef test_xfail():\n    assert False\n", "nonpass"),
        ("def test_failure():\n    assert False\n", "exit"),
    ],
)
def test_rejects_actual_pytest_nonpass_inventories(tmp_path: Path, body: str, message: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    run = _run_pytest_fixture(tmp_path, body)
    assert run["inventory"].is_file()
    with pytest.raises(ReconciliationError, match=message):
        reconcile_junit(
            run["raw"],
            run["inventory"],
            run["root"] / "derived.xml",
            pytest_args=run["args"],
            repo_root=run["root"],
        )


@pytest.mark.parametrize("tests_total", [1, 5])
def test_rejects_forged_raw_test_totals(passing_subtest_run: dict, tmp_path: Path, tests_total: int) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    raw = _mutated_xml(
        passing_subtest_run["raw"],
        tmp_path / f"raw-{tests_total}.xml",
        lambda root: next(root.iter("testsuite")).set("tests", str(tests_total)),
    )
    with pytest.raises(ReconciliationError, match="raw tests total"):
        reconcile_junit(raw, passing_subtest_run["inventory"], tmp_path / "derived.xml", pytest_args=passing_subtest_run["args"], repo_root=passing_subtest_run["root"])


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_rejects_missing_or_duplicate_testcase_nodes(passing_subtest_run: dict, tmp_path: Path, mutation: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    if mutation == "missing":
        def mutate(root: ET.Element) -> None:
            suite = next(root.iter("testsuite"))
            suite.remove(next(suite.iter("testcase")))
            suite.set("tests", "1")
    else:
        def mutate(root: ET.Element) -> None:
            suite = next(root.iter("testsuite"))
            suite.append(ET.fromstring(ET.tostring(next(suite.iter("testcase")), encoding="unicode")))
            suite.set("tests", "3")
    raw = _mutated_xml(passing_subtest_run["raw"], tmp_path / f"{mutation}.xml", mutate)
    with pytest.raises(ReconciliationError, match="testcase identity"):
        reconcile_junit(raw, passing_subtest_run["inventory"], tmp_path / "derived.xml", pytest_args=passing_subtest_run["args"], repo_root=passing_subtest_run["root"])


@pytest.mark.parametrize("mutation", ["missing-tests", "negative-tests", "float-tests", "missing-failures"])
def test_rejects_malformed_junit_totals(passing_subtest_run: dict, tmp_path: Path, mutation: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    def mutate(root: ET.Element) -> None:
        suite = next(root.iter("testsuite"))
        if mutation == "missing-tests":
            suite.attrib.pop("tests")
        elif mutation == "negative-tests":
            suite.set("tests", "-1")
        elif mutation == "float-tests":
            suite.set("tests", "4.0")
        else:
            suite.attrib.pop("failures")

    raw = _mutated_xml(passing_subtest_run["raw"], tmp_path / f"{mutation}.xml", mutate)
    with pytest.raises(ReconciliationError, match="JUnit .* total"):
        reconcile_junit(raw, passing_subtest_run["inventory"], tmp_path / "derived.xml", pytest_args=passing_subtest_run["args"], repo_root=passing_subtest_run["root"])


@pytest.mark.parametrize("mutation", ["missing-primary", "duplicate-primary", "unknown-subtest"])
def test_rejects_primary_and_subtest_inventory_mutations(passing_subtest_run: dict, tmp_path: Path, mutation: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    inventory = _load(passing_subtest_run["inventory"])
    first = next(iter(inventory["collected"]))
    if mutation == "missing-primary":
        inventory["primary"].pop(first)
    elif mutation == "duplicate-primary":
        inventory["primary"][first] = 2
    else:
        inventory["subtests"]["test_unknown.py::test_unknown"] = 1
    path = tmp_path / f"{mutation}.json"
    inventory["inventory_path"] = str(path)
    _write(path, inventory)
    with pytest.raises(ReconciliationError, match="primary|unknown"):
        reconcile_junit(passing_subtest_run["raw"], path, tmp_path / "derived.xml", pytest_args=passing_subtest_run["args"], repo_root=passing_subtest_run["root"])


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong-kind",
        "wrong-schema",
        "missing-required",
        "legacy-rejected",
        "false-exitstatus",
        "true-primary",
        "wrong-inventory-path",
    ],
)
def test_rejects_strict_inventory_schema_mutations(passing_subtest_run: dict, tmp_path: Path, mutation: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    inventory = _load(passing_subtest_run["inventory"])
    first = next(iter(inventory["primary"]))
    if mutation == "wrong-kind":
        inventory["kind"] = "pytest-execution-inventory-prototype"
    elif mutation == "wrong-schema":
        inventory["schema_version"] = "1"
    elif mutation == "missing-required":
        inventory.pop("collected_order")
    elif mutation == "legacy-rejected":
        inventory["rejected"] = []
    elif mutation == "false-exitstatus":
        inventory["exitstatus"] = False
    elif mutation == "true-primary":
        inventory["primary"][first] = True
    else:
        inventory["inventory_path"] = str(tmp_path / "other.json")
    path = tmp_path / f"{mutation}.json"
    if mutation != "wrong-inventory-path":
        inventory["inventory_path"] = str(path)
    _write(path, inventory)
    with pytest.raises(ReconciliationError, match="inventory|schema|kind|exit|primary"):
        reconcile_junit(passing_subtest_run["raw"], path, tmp_path / "derived.xml", pytest_args=passing_subtest_run["args"], repo_root=passing_subtest_run["root"])


@pytest.mark.parametrize("mutation", ["nonpass", "deselected"])
def test_rejects_nonpass_and_deselection_inventory_flags(passing_subtest_run: dict, tmp_path: Path, mutation: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    inventory = _load(passing_subtest_run["inventory"])
    first = next(iter(inventory["collected"]))
    if mutation == "nonpass":
        inventory["nonpass_reports"] = [{"nodeid": first, "when": "call", "outcome": "skipped"}]
    else:
        inventory["deselected"] = [first]
    path = tmp_path / f"{mutation}.json"
    inventory["inventory_path"] = str(path)
    _write(path, inventory)
    with pytest.raises(ReconciliationError, match=mutation):
        reconcile_junit(passing_subtest_run["raw"], path, tmp_path / "derived.xml", pytest_args=passing_subtest_run["args"], repo_root=passing_subtest_run["root"])


@pytest.mark.parametrize("field", ["args", "root"])
def test_rejects_wrong_invocation_provenance(passing_subtest_run: dict, tmp_path: Path, field: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    args = [*passing_subtest_run["args"], "-k", "other"] if field == "args" else passing_subtest_run["args"]
    root = tmp_path if field == "root" else passing_subtest_run["root"]
    with pytest.raises(ReconciliationError, match="pytest args|rootdir"):
        reconcile_junit(passing_subtest_run["raw"], passing_subtest_run["inventory"], tmp_path / "derived.xml", pytest_args=args, repo_root=root)


def test_requires_fresh_output_path(passing_subtest_run: dict) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    output = passing_subtest_run["root"] / "already-exists.xml"
    output.write_text("occupied", encoding="utf-8")
    with pytest.raises(ReconciliationError, match="fresh"):
        reconcile_junit(passing_subtest_run["raw"], passing_subtest_run["inventory"], output, pytest_args=passing_subtest_run["args"], repo_root=passing_subtest_run["root"])


@pytest.fixture()
def reconciliation_record(passing_subtest_run: dict) -> dict:
    from scripts.validation.pytest_junit_reconciliation import reconcile_junit

    return reconcile_junit(
        passing_subtest_run["raw"],
        passing_subtest_run["inventory"],
        passing_subtest_run["root"] / "derived.xml",
        pytest_args=passing_subtest_run["args"],
        repo_root=passing_subtest_run["root"],
    )


@pytest.mark.parametrize("target", ["raw", "inventory", "derived", "manifest-derived-hash"])
def test_replay_rejects_hash_and_output_tampering(reconciliation_record: dict, tmp_path: Path, target: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, validate_reconciled_junit

    record = json.loads(json.dumps(reconciliation_record))
    if target == "raw":
        Path(record["sources"]["raw_junit"]["path"]).write_text("<testsuites />", encoding="utf-8")
    elif target == "inventory":
        inventory = _load(Path(record["sources"]["execution_inventory"]["path"]))
        inventory["exitstatus"] = 1
        _write(Path(record["sources"]["execution_inventory"]["path"]), inventory)
    elif target == "derived":
        Path(record["derived"]["junit"]["path"]).write_text("<testsuites />", encoding="utf-8")
    else:
        record["derived"]["junit"]["sha256"] = "0" * 64

    with pytest.raises(ReconciliationError, match="hash|derived|exit"):
        validate_reconciled_junit(record, pytest_args=record["pytest"]["args"], repo_root=record["pytest"]["rootdir"])


@pytest.mark.parametrize("field", ["schema_version", "kind", "scope", "status", "no_new_test_execution"])
def test_replay_rejects_record_identity_mutations(reconciliation_record: dict, field: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, validate_reconciled_junit

    record = json.loads(json.dumps(reconciliation_record))
    if field == "schema_version":
        record[field] = "1"
    elif field == "kind":
        record[field] = "pytest-junit-reconciliation-prototype"
    elif field == "scope":
        record[field] = "other"
    elif field == "status":
        record[field] = "FAIL"
    else:
        record[field] = False
    with pytest.raises(ReconciliationError, match="record|replay"):
        validate_reconciled_junit(record, pytest_args=record["pytest"]["args"], repo_root=record["pytest"]["rootdir"])


def test_replay_does_not_write_outputs(reconciliation_record: dict) -> None:
    from scripts.validation.pytest_junit_reconciliation import validate_reconciled_junit

    output = Path(reconciliation_record["derived"]["junit"]["path"])
    before = output.read_bytes()
    checked = validate_reconciled_junit(
        reconciliation_record,
        pytest_args=reconciliation_record["pytest"]["args"],
        repo_root=reconciliation_record["pytest"]["rootdir"],
    )
    assert output.read_bytes() == before
    assert checked["sha256"] == reconciliation_record["derived"]["junit"]["sha256"]


def test_rejects_coherently_renamed_collection_node(passing_subtest_run: dict) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    run = passing_subtest_run
    inventory = _load(run["inventory"])
    original = inventory["collected_order"][0]
    replacement = "test_uncollected.py::test_other"
    inventory["collected"][replacement] = inventory["collected"].pop(original)
    inventory["collected_order"][0] = replacement
    inventory["primary"][replacement] = inventory["primary"].pop(original)
    if original in inventory["subtests"]:
        inventory["subtests"][replacement] = inventory["subtests"].pop(original)
    _write(run["inventory"], inventory)
    with pytest.raises(ReconciliationError, match="identity mapping"):
        reconcile_junit(run["raw"], run["inventory"], run["root"] / "derived.xml",
                        pytest_args=run["args"], repo_root=run["root"])


@pytest.mark.parametrize("which", ["raw", "inventory"])
def test_rejects_unbound_command_output_paths(passing_subtest_run: dict, which: str) -> None:
    from scripts.validation.pytest_junit_reconciliation import ReconciliationError, reconcile_junit

    run = passing_subtest_run
    copied = run["root"] / ("unbound.xml" if which == "raw" else "unbound.json")
    copied.write_bytes(run[which].read_bytes())
    if which == "inventory":
        inventory = _load(copied)
        inventory["inventory_path"] = str(copied)
        _write(copied, inventory)
    with pytest.raises(ReconciliationError, match="output paths"):
        reconcile_junit(copied if which == "raw" else run["raw"],
                        copied if which == "inventory" else run["inventory"],
                        run["root"] / "derived.xml", pytest_args=run["args"], repo_root=run["root"])
