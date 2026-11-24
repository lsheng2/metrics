from copy import deepcopy
from pathlib import Path

import pytest

from scripts.tests.test_qualify_ai_runtime import _sha, _write_json
from scripts.tests.test_windows_performance_inputs import performance_case
from scripts.tests.windows_performance_support import performance_transport_payload
from scripts.validation.windows_host_transport import validate_transport
from scripts.validation.windows_qualification_inputs import QualificationError


TAIL_POLICY = {
    "method": "nearest_rank",
    "quantile": 0.99,
    "p99_exclusive_ms": 100,
    "max_inclusive_ms": 200,
}


def set_latency(payload, kind, slots, ms):
    for row in payload["saturation"]["probes"]:
        if row["kind"] == kind and row["slot"] in slots:
            row["ms"] = ms
            row["ended"] = row["started"] + ms / 1000
    for slot in slots:
        end = 0
        for row in payload["saturation"]["probes"]:
            if row["slot"] == slot:
                row["started"] = max(row["started"], end)
                row["ended"] = row["started"] + row["ms"] / 1000
                end = row["ended"] + 0.001


def evaluate(payload, **kwargs):
    return validate_transport(payload, spacing_events=50, require_direct_asset=True, **kwargs)


@pytest.mark.parametrize("kind,bucket", [("loop_short", "short"), ("direct_asset", "direct_asset")])
def test_single_200ms_tail_passes_when_99th_rank_is_fast(kind, bucket):
    payload = performance_transport_payload(slots=100)
    set_latency(payload, kind, {99}, 200)
    observed = evaluate(payload)
    assert observed["violations"] == []
    assert observed["latency_tails"][bucket] == {"count": 100, "p99_ms": 20, "max_ms": 200}


@pytest.mark.parametrize("kind,metric", [
    ("loop_short", "short_p99_ms"), ("direct_asset", "direct_asset_p99_ms"),
])
def test_p99_equal_100_fails_without_pooling_the_other_fast_kind(kind, metric):
    payload = performance_transport_payload(slots=100)
    set_latency(payload, kind, {98, 99}, 100)
    with pytest.raises(ValueError):
        evaluate(payload)
    result = evaluate(payload, fail_on_violation=False)
    assert result["violations"] == [{"metric": metric, "value": 100, "limit": 100}]


@pytest.mark.parametrize("kind,metric", [
    ("loop_short", "short_max_ms"), ("direct_asset", "direct_asset_max_ms"),
])
def test_maximum_above_200_fails_even_with_fast_p99(kind, metric):
    payload = performance_transport_payload(slots=100)
    set_latency(payload, kind, {99}, 200.001)
    with pytest.raises(ValueError):
        evaluate(payload)
    result = evaluate(payload, fail_on_violation=False)
    assert result["violations"] == [
        {"metric": metric, "slot": 99, "value": 200.001, "limit": 200},
    ]


def test_small_samples_use_nearest_rank_not_interpolation():
    payload = performance_transport_payload(slots=99)
    set_latency(payload, "direct_asset", {98}, 119)
    with pytest.raises(ValueError):
        evaluate(payload)


@pytest.mark.parametrize("mutation", ["status", "hash", "missing", "retry", "resource_leak", "errors"])
def test_tail_relaxation_never_waives_correctness_or_cleanup(mutation):
    payload = performance_transport_payload(slots=100)
    probes = payload["saturation"]["probes"]
    if mutation == "status":
        probes[0]["status"] = 503
    elif mutation == "hash":
        probes[1]["content_sha256"] = "invalid"
    elif mutation == "missing":
        probes.pop()
    elif mutation == "retry":
        probes[2]["retry_after"] = "3"
    elif mutation == "resource_leak":
        payload["saturation"]["after"]["streamInFlightCount"] = 1
    else:
        payload["saturation"]["errors"].append("probe_failed")
    with pytest.raises(ValueError):
        evaluate(payload, fail_on_violation=False)


def test_active_input_and_resolved_recipe_are_r2(tmp_path, monkeypatch):
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch)
    request = load_performance_request(case["inputs"], case["output"], mode="certify")
    assert request["performance"]["recipe_id"] == "windows-mdb2-s0b-r2"
    assert Path(request["performance"]["policy_ref"]["path"]).name == "windows-performance-inputs-dev9-r2.json"


@pytest.mark.parametrize("changed", [
    {"method": "linear"}, {"quantile": 0.95}, {"p99_exclusive_ms": 101}, {"max_inclusive_ms": 201},
])
def test_canonical_policy_must_match_the_implemented_tail_contract(tmp_path, monkeypatch, changed):
    import json
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch)
    policy_path = Path(case["manifest"]["performance"]["policy_ref"]["path"])
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["full_recipe"]["saturation"]["latency_tail"] = {**TAIL_POLICY, **changed}
    _write_json(policy_path, policy)
    case["manifest"]["performance"]["policy_ref"]["sha256"] = _sha(policy_path)
    _write_json(case["inputs"], case["manifest"])
    with pytest.raises(QualificationError, match="performance policy recipe mismatch"):
        load_performance_request(case["inputs"], case["output"], mode="certify")


@pytest.mark.parametrize("stale", ["recipe", "path", "mixed_field"])
def test_old_recipe_policy_and_mixed_rule_cannot_be_admitted(tmp_path, monkeypatch, stale):
    import json
    from scripts.validation.windows_host_performance_contract import load_performance_request

    case = performance_case(tmp_path, monkeypatch)
    policy_path = Path(case["manifest"]["performance"]["policy_ref"]["path"])
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if stale == "recipe":
        case["manifest"]["performance"]["recipe_id"] = "windows-mdb2-s0b-r1"
    elif stale == "path":
        policy_path = case["root"] / (
            "openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-performance-inputs-dev9.json"
        )
        _write_json(policy_path, policy)
        case["manifest"]["performance"]["policy_ref"] = {"path": str(policy_path), "sha256": _sha(policy_path)}
    else:
        policy["full_recipe"]["saturation"]["latency_tail"] = deepcopy(TAIL_POLICY)
        policy["full_recipe"]["saturation"]["short_ms_exclusive_limit"] = 100
        _write_json(policy_path, policy)
        case["manifest"]["performance"]["policy_ref"]["sha256"] = _sha(policy_path)
    _write_json(case["inputs"], case["manifest"])
    with pytest.raises(QualificationError):
        load_performance_request(case["inputs"], case["output"], mode="certify")


def test_r1_resolved_measurement_cannot_certify_under_r2_request(tmp_path):
    import json
    from scripts.tests.test_windows_performance_evidence import _artifact, _receipt_case
    from scripts.validation.windows_host_performance_evidence import validate_performance_result

    receipt, request = _receipt_case(tmp_path, mode="certify")
    path = Path(receipt["resolved_inputs"]["production"]["path"])
    resolved = json.loads(path.read_text(encoding="utf-8"))
    resolved["recipe_id"] = "windows-mdb2-s0b-r1"
    receipt["resolved_inputs"]["production"] = _artifact(path, resolved)
    with pytest.raises(QualificationError, match="resolved input phase or recipe mismatch"):
        validate_performance_result(receipt, request)
