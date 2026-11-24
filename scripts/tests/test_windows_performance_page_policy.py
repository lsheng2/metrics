"""Prospective r3 page budgets must bind workload class, not prior failures."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.tests.test_qualify_ai_runtime import _sha, _write_json
from scripts.tests.test_windows_performance_inputs import performance_case
from scripts.tests.windows_performance_support import performance_measurement_payload
from scripts.validation.windows_host_samples import evaluate_pages, validate_pages
from scripts.validation.windows_qualification_inputs import QualificationError


PAGES = ("home", "projects", "project_detail", "stage_reports", "draft_edit", "bug_trend")


def timed_payload(*, mode, page, arm, baseline, candidate, production=False):
    payload = performance_measurement_payload()
    payload["production"] = production
    for index, block in enumerate(payload["blocks"]):
        block["started"] = 201 + index * 3
        block["ended"] = block["started"] + 2
        rows = payload["pages"][block["mode"]][block["page"]][block["arm"]]
        for row in rows:
            if row["block"] != block["block"]:
                continue
            if block["mode"] == mode and block["page"] == page:
                if block["arm"] == "baseline":
                    row["ms"] = baseline
                elif block["arm"] == arm:
                    row["ms"] = candidate
            row["started"] = block["started"] + row["sample"] * 0.001
            row["ended"] = row["started"] + row["ms"] / 1000
    payload["saturation"]["ended"] = payload["blocks"][-1]["ended"] + 1
    return payload


@pytest.mark.parametrize("production", [False, True], ids=["development", "production"])
@pytest.mark.parametrize("page", PAGES)
def test_concurrent_saturated_budget_accepts_joint_boundary_for_every_page(production, page):
    payload = timed_payload(
        mode="c4", page=page, arm="candidate_saturated",
        baseline=640, candidate=800, production=production,
    )
    assert evaluate_pages(payload)["violations"] == []
    assert len(validate_pages(payload)) == 24


@pytest.mark.parametrize("production", [False, True], ids=["development", "production"])
@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("baseline,candidate,metric,limit", [
    (400, 500.001, "page_ratio", 1.25),
    (800, 800.001, "page_p95_ms", 800),
])
def test_each_stress_limit_blocks_independently(production, page, baseline, candidate, metric, limit):
    payload = timed_payload(
        mode="c4", page=page, arm="candidate_saturated",
        baseline=baseline, candidate=candidate, production=production,
    )
    violations = evaluate_pages(payload)["violations"]
    assert len(violations) == 1
    assert violations[0]["metric"] == metric
    assert violations[0]["limit"] == limit
    assert violations[0]["page"] == page
    with pytest.raises(ValueError):
        validate_pages(payload)


@pytest.mark.parametrize("mode,arm", [
    ("seq", "candidate"), ("seq", "candidate_saturated"), ("c4", "candidate"),
])
@pytest.mark.parametrize("page", PAGES)
def test_normal_class_is_not_relaxed_by_page_name_or_one_stress_axis(mode, arm, page):
    payload = timed_payload(mode=mode, page=page, arm=arm, baseline=100, candidate=120)
    assert evaluate_pages(payload)["violations"] == []
    payload = timed_payload(mode=mode, page=page, arm=arm, baseline=100, candidate=120.001)
    result = evaluate_pages(payload)
    assert len(result["violations"]) == 1
    assert result["violations"][0]["metric"] == "page_ratio"
    assert result["violations"][0]["limit"] == 1.2


def test_historical_ordinary_regression_is_not_waived_by_new_class():
    payload = timed_payload(
        mode="seq", page="draft_edit", arm="candidate",
        baseline=227.5443, candidate=360.5075, production=True,
    )
    with pytest.raises(ValueError):
        validate_pages(payload)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "status", "asset", "nan"])
def test_numerical_stress_allowance_does_not_waive_raw_integrity(mutation):
    payload = timed_payload(
        mode="c4", page="home", arm="candidate_saturated", baseline=640, candidate=800,
    )
    rows = payload["pages"]["c4"]["home"]["candidate_saturated"]
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = deepcopy(rows[0])
    elif mutation == "status":
        rows[0]["status"] = 503
    elif mutation == "asset":
        rows[0]["assets"][0]["sha256"] = "f" * 64
    else:
        rows[0]["ms"] = float("nan")
    with pytest.raises(ValueError):
        evaluate_pages(payload)


@pytest.mark.parametrize("mutation", [
    {"page_ratio_max": 1.3}, {"p95_max_ms": 801}, {"mode": "seq"},
    {"arm": "candidate"}, {"page": "draft_edit"},
])
def test_canonical_policy_cannot_select_another_budget_or_single_page(tmp_path, monkeypatch, mutation):
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch)
    path = Path(case["manifest"]["performance"]["policy_ref"]["path"])
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["full_recipe"]["concurrent_saturated_page"] = {
        "mode": "c4", "arm": "candidate_saturated", "page_ratio_max": 1.25, "p95_max_ms": 800,
        **mutation,
    }
    _write_json(path, policy)
    case["manifest"]["performance"]["policy_ref"]["sha256"] = _sha(path)
    _write_json(case["inputs"], case["manifest"])
    with pytest.raises(QualificationError, match="performance policy recipe mismatch"):
        load_performance_request(case["inputs"], case["output"], mode="certify")


@pytest.mark.parametrize("stale", ["recipe", "path", "hash"])
def test_r2_identity_cannot_be_promoted_to_r3(tmp_path, monkeypatch, stale):
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch)
    performance = case["manifest"]["performance"]
    if stale == "recipe":
        performance["recipe_id"] = "windows-mdb2-s0b-r2"
    elif stale == "path":
        path = case["root"] / (
            "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-performance-inputs-dev9-r2.json"
        )
        _write_json(path, json.loads(Path(performance["policy_ref"]["path"]).read_text(encoding="utf-8")))
        performance["policy_ref"] = {"path": str(path), "sha256": _sha(path)}
    else:
        performance["policy_ref"]["sha256"] = "c0a5da6346da05b7ae88770822b1e0022cac7cb62497dc06b8d2543e9f7357aa"
    _write_json(case["inputs"], case["manifest"])
    with pytest.raises(QualificationError):
        load_performance_request(case["inputs"], case["output"], mode="certify")


@pytest.mark.parametrize("phase", ["development", "production"])
@pytest.mark.parametrize("baseline,candidate,metric", [
    (640, 800, None), (400, 500.001, "page_ratio"), (800, 800.001, "page_p95_ms"),
])
def test_raw_stress_budget_reaches_standalone_and_aggregate_gate(tmp_path, phase, baseline, candidate, metric):
    from scripts.tests.test_windows_performance_evidence import _artifact, _read_json, _receipt_case
    from scripts.tests.test_windows_performance_replay_boundaries import _performance_binding
    from scripts.tests.windows_performance_support import performance_transport_payload, seal_receipt, shift_measurement
    from scripts.validation.windows_host_performance_evidence import validate_performance_result
    from scripts.validation.windows_qualification_evidence import validate_binding

    receipt, request = _receipt_case(tmp_path, mode="certify")
    payload = timed_payload(
        mode="c4", page="home", arm="candidate_saturated", baseline=baseline, candidate=candidate,
        production=phase == "production",
    )
    payload.update(performance_transport_payload(slots=450))
    for name in ("development", "production"):
        path = Path(receipt["measurements"][name]["path"])
        value = payload if name == phase else _read_json(path)
        if name == "production":
            value = shift_measurement(value, 1000 if name == phase else 500)
        receipt["measurements"][name] = _artifact(path, value)
    window_path = Path(receipt["measurement_window"]["path"])
    window = _read_json(window_path)
    window["ended_monotonic"] = 2000
    window["verdict"]["written_monotonic"] = 1990
    receipt["measurement_window"] = _artifact(window_path, window)
    witness_path = Path(receipt["run_directory"]) / "receipt-write-witness.json"
    witness = _read_json(witness_path)
    witness.update(write_started_monotonic=2001, write_completed_monotonic=2002, guard_observed_monotonic=2003)
    _artifact(witness_path, witness)
    # Keep the forged clean summary: only raw replay may decide eligibility.
    seal_receipt(receipt)
    observed = validate_performance_result(receipt, request)
    path = Path(receipt["run_directory"]) / "receipt.json"
    key = "task:10.4"
    binding = _performance_binding(receipt, request, path, key)
    roots = (Path(request["source"]["repository"]), request["_paths"]["owned_root"])
    if metric is None:
        assert observed["acceptance_eligible"] is True
        assert validate_binding(key, binding, request, roots)["acceptance_eligible"] is True
    else:
        assert observed["acceptance_eligible"] is False
        assert len(observed["violations"]) == 1
        assert observed["violations"][0]["metric"] == metric
        assert observed["violations"][0]["phase"] == phase
        with pytest.raises(QualificationError, match="not certification eligible"):
            validate_binding(key, binding, request, roots)
