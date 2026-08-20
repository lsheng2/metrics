from scripts.check_c1_evidence_link_evidence import validate_evidence_file


def write_evidence(tmp_path, *, n1_status='passed', n2_status='passed', n3_status='passed', n4_status='passed', payload_state='payload_captured', reference_count='34', linked_count='34', reference_title='all_open_bugs tickets for 26WW32', linked_title='all_open_bugs tickets for 26WW32', verdict='c_stock_linked_evidence_supported', residual_risk='stock Grafana supports link-out evidence, not same-page evidence list'):
    evidence = tmp_path / 'evidence.md'
    evidence.write_text(
        '\n'.join([
            '| node_id | status | command_or_manual_step | result | observed_grafana_url | payload_state | resolved_link_url | scope_id | begin | end | run | bucket | series | reference_selection_title | linked_selection_title | reference_row_count | linked_row_count | decision_verdict | residual_risk |',
            '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |',
            f'| C1.N1 | {n1_status} | artifact validator link check | exit 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  | none |',
            f'| C1.N2 | {n2_status} | Grafana rendered link inspection | resolved link captured | http://127.0.0.1:3001/d/metrics-bug-trend-c-stock/metrics-bug-trend-c-stock-spike | {payload_state} | http://127.0.0.1:8002/api/bug-trend/evidence/?scope_id=3&begin=2026-06-01&end=2026-08-09&run=run-1&bucket=bucket-1&series=all_open_bugs | 3 | 2026-06-01 | 2026-08-09 | run-1 | bucket-1 | all_open_bugs |  |  |  |  |  | none |',
            f'| C1.N3 | {n3_status} | request resolved link target | row count compared | http://127.0.0.1:3001/d/metrics-bug-trend-c-stock/metrics-bug-trend-c-stock-spike | {payload_state} | http://127.0.0.1:8002/api/bug-trend/evidence/?scope_id=3&begin=2026-06-01&end=2026-08-09&run=run-1&bucket=bucket-1&series=all_open_bugs | 3 | 2026-06-01 | 2026-08-09 | run-1 | bucket-1 | all_open_bugs | {reference_title} | {linked_title} | {reference_count} | {linked_count} |  | none |',
            f'| C1.N4 | {n4_status} | C1 evidence checker | checker passed |  | {payload_state} |  |  |  |  |  |  |  |  |  |  |  | {verdict} | {residual_risk} |',
        ]),
        encoding='utf-8',
    )
    return evidence


def test_checkerAcceptsLinkedEvidenceSupportedWhenRowsMatch(tmp_path):
    evidence = write_evidence(tmp_path)

    findings = validate_evidence_file(evidence)

    assert findings == []


def test_checkerRejectsPendingEvidence(tmp_path):
    evidence = tmp_path / 'evidence.md'
    evidence.write_text(
        '\n'.join([
            '| node_id | status | command_or_manual_step | result | observed_grafana_url | payload_state | resolved_link_url | scope_id | begin | end | run | bucket | series | reference_selection_title | linked_selection_title | reference_row_count | linked_row_count | decision_verdict | residual_risk |',
            '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |',
            '| C1.N1 | pending |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |',
            '| C1.N2 | pending |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |',
            '| C1.N3 | pending |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |',
            '| C1.N4 | pending |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | pending |  |',
        ]),
        encoding='utf-8',
    )

    findings = validate_evidence_file(evidence)

    assert findings
    assert any('invalid status: pending' in finding.message for finding in findings)


def test_checkerRejectsLinkedEvidenceSupportedWhenCountsDiffer(tmp_path):
    evidence = write_evidence(tmp_path, linked_count='33')

    findings = validate_evidence_file(evidence)

    assert any('matching evidence row counts' in finding.message for finding in findings)


def test_checkerRejectsLinkedEvidenceSupportedWithoutResidualRisk(tmp_path):
    evidence = write_evidence(tmp_path, residual_risk='none')

    findings = validate_evidence_file(evidence)

    assert any('link-out vs same-page residual risk' in finding.message for finding in findings)


def test_checkerAcceptsNonEvidenceOnlyWhenPayloadUnavailable(tmp_path):
    evidence = write_evidence(
        tmp_path,
        n2_status='blocked',
        n3_status='skipped_with_reason',
        payload_state='payload_unavailable',
        verdict='c_stock_non_evidence_only',
        residual_risk='stock Grafana did not expose reliable payload',
    )

    findings = validate_evidence_file(evidence)

    assert findings == []
