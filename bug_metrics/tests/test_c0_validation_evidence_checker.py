from pathlib import Path

from scripts.check_c0_validation_evidence import validate_evidence_file


def write_evidence(tmp_path, *, v1_status="passed", v2_status="passed", v3_status="passed", v4_status="passed", grafana_state="runtime_render_validated", residual_risk="none", closure_verdict="full_c0_runtime_closure"):
    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "\n".join(
            [
                "| node_id | status | command_or_manual_step | exit_code_or_result | scope_id | begin | end | calculation_run_id | observed_url | evidence_before_after | grafana_runtime_state | residual_risk | closure_verdict |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                f"| C0.V1 | {v1_status} | playwright bug trend click | exit 0 | 131600 | 2026-06-01 | 2026-08-09 | run-1 | http://127.0.0.1:8002/bug-trend/?scope_id=131600&begin=2026-06-01&end=2026-08-09 | 224 to 7 to 224 |  | none |  |",
                f"| C0.V2 | {v2_status} | api runtime probe | exit 0 | 131600 | 2026-06-01 | 2026-08-09 | run-1 |  |  |  | none |  |",
                f"| C0.V3 | {v3_status} | grafana provision smoke | exit 0 | 131600 | 2026-06-01 | 2026-08-09 | run-1 | http://127.0.0.1:3000/d/bug-trend?var-scope_id=131600&var-begin=2026-06-01&var-end=2026-08-09 |  | {grafana_state} | {residual_risk} |  |",
                f"| C0.V4 | {v4_status} | evidence checker | exit 0 |  |  |  |  |  |  | {grafana_state} | {residual_risk} | {closure_verdict} |",
            ]
        ),
        encoding="utf-8",
    )
    return evidence


def test_checkerAcceptsFullRuntimeClosureWhenEveryNodeHasEvidence(tmp_path):
    evidence = write_evidence(tmp_path)

    findings = validate_evidence_file(evidence)

    assert findings == []


def test_checkerRejectsRuntimeUnavailableClaimedAsFullClosure(tmp_path):
    evidence = write_evidence(
        tmp_path,
        v3_status="deferred_with_trigger",
        grafana_state="runtime_not_available",
        residual_risk="validate after Grafana runtime exists",
    )

    findings = validate_evidence_file(evidence)

    assert any("runtime_not_available cannot support full_c0_runtime_closure" in finding.message for finding in findings)


def test_checkerRejectsPendingTemplateEvidence(tmp_path):
    evidence = tmp_path / "evidence.md"
    evidence.write_text(
        "\n".join(
            [
                "| node_id | status | command_or_manual_step | exit_code_or_result | scope_id | begin | end | calculation_run_id | observed_url | evidence_before_after | grafana_runtime_state | residual_risk | closure_verdict |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                "| C0.V1 | pending |  |  |  |  |  |  |  |  |  |  |  |",
                "| C0.V2 | pending |  |  |  |  |  |  |  |  |  |  |  |",
                "| C0.V3 | pending |  |  |  |  |  |  |  |  |  |  |  |",
                "| C0.V4 | pending |  |  |  |  |  |  |  |  |  |  | pending |",
            ]
        ),
        encoding="utf-8",
    )

    findings = validate_evidence_file(evidence)

    assert findings
    assert any("invalid status: pending" in finding.message for finding in findings)


def test_checkerRejectsFailedBrowserEvidenceClaimedAsFullClosure(tmp_path):
    evidence = write_evidence(tmp_path, v1_status="failed")

    findings = validate_evidence_file(evidence)

    assert any("full_c0_runtime_closure requires C0.V1 status=passed" in finding.message for finding in findings)


def test_checkerRejectsBlockedApiEvidenceClaimedAsFullClosure(tmp_path):
    evidence = write_evidence(tmp_path, v2_status="blocked")

    findings = validate_evidence_file(evidence)

    assert any("full_c0_runtime_closure requires C0.V2 status=passed" in finding.message for finding in findings)


def test_checkerRejectsDeferredGrafanaEvidenceClaimedAsFullClosure(tmp_path):
    evidence = write_evidence(tmp_path, v3_status="deferred_with_trigger")

    findings = validate_evidence_file(evidence)

    assert any("full_c0_runtime_closure requires C0.V3 status=passed" in finding.message for finding in findings)


def test_checkerRejectsFailedEvidenceRecordClaimedAsFullClosure(tmp_path):
    evidence = write_evidence(tmp_path, v4_status="failed")

    findings = validate_evidence_file(evidence)

    assert any("full_c0_runtime_closure requires C0.V4 status=passed" in finding.message for finding in findings)


def test_checkerRejectsPartialClosureWhenReferenceUiDidNotPass(tmp_path):
    evidence = write_evidence(
        tmp_path,
        v1_status="failed",
        v3_status="deferred_with_trigger",
        grafana_state="runtime_not_available",
        residual_risk="validate after Grafana runtime exists",
        closure_verdict="partial_c0_static_api_reference_closure",
    )

    findings = validate_evidence_file(evidence)

    assert any("partial_c0_static_api_reference_closure requires C0.V1 status=passed" in finding.message for finding in findings)


def test_checkerAcceptsPartialClosureWhenGrafanaRuntimeIsUnavailable(tmp_path):
    evidence = write_evidence(
        tmp_path,
        v3_status="deferred_with_trigger",
        grafana_state="runtime_not_available",
        residual_risk="validate after Grafana runtime exists",
        closure_verdict="partial_c0_static_api_reference_closure",
    )

    findings = validate_evidence_file(evidence)

    assert findings == []


def test_checkerRejectsReferenceUiUrlWhenQueryDoesNotMatchEvidenceFields(tmp_path):
    evidence = write_evidence(tmp_path)
    text = evidence.read_text(encoding="utf-8").replace("begin=2026-06-01", "begin=2025-04-07", 1)
    evidence.write_text(text, encoding="utf-8")

    findings = validate_evidence_file(evidence)

    assert any("C0.V1 observed_url begin=2025-04-07" in finding.message for finding in findings)


def test_checkerRejectsGrafanaUrlWhenVariableDoesNotMatchEvidenceFields(tmp_path):
    evidence = write_evidence(tmp_path)
    text = evidence.read_text(encoding="utf-8").replace("var-scope_id=131600", "var-scope_id=999")
    evidence.write_text(text, encoding="utf-8")

    findings = validate_evidence_file(evidence)

    assert any("C0.V3 observed_url var-scope_id=999" in finding.message for finding in findings)