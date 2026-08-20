#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


NODE_IDS = ("C0.V1", "C0.V2", "C0.V3", "C0.V4")
VALID_STATUSES = {"passed", "failed", "blocked", "deferred_with_trigger"}
VALID_GRAFANA_STATES = {"runtime_render_validated", "runtime_not_available"}
VALID_CLOSURE_VERDICTS = {"full_c0_runtime_closure", "partial_c0_static_api_reference_closure", "failed"}

BASE_REQUIRED_FIELDS = frozenset({"status", "command_or_manual_step", "exit_code_or_result", "residual_risk"})
CONTEXT_REQUIRED_FIELDS = frozenset({"scope_id", "begin", "end", "calculation_run_id"})

REQUIRED_FIELDS_BY_NODE = {
    "C0.V1": BASE_REQUIRED_FIELDS | CONTEXT_REQUIRED_FIELDS | frozenset({"observed_url", "evidence_before_after"}),
    "C0.V2": BASE_REQUIRED_FIELDS | CONTEXT_REQUIRED_FIELDS,
    "C0.V3": BASE_REQUIRED_FIELDS | CONTEXT_REQUIRED_FIELDS | frozenset({"observed_url", "grafana_runtime_state"}),
    "C0.V4": BASE_REQUIRED_FIELDS | frozenset({"grafana_runtime_state", "closure_verdict"}),
}


@dataclass(frozen=True, slots=True)
class Finding:
    message: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Check C0 validation closure evidence completeness.")
    parser.add_argument("--evidence", required=True, help="Markdown evidence file for C0 validation closure.")
    args = parser.parse_args()

    findings = validate_evidence_file(Path(args.evidence))
    for finding in findings:
        print(f"FAIL {finding.message}")

    if findings:
        raise SystemExit(1)

    print(f"PASS c0 validation evidence nodes={len(NODE_IDS)}")


def validate_evidence_file(path: Path) -> list[Finding]:
    if not path.exists():
        return [Finding(f"evidence file not found: {path}")]
    records = parse_markdown_table(path.read_text(encoding="utf-8"))
    findings = validate_records(records)
    return findings


def parse_markdown_table(text: str) -> list[dict[str, str]]:
    headers: list[str] | None = None
    records: list[dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if "node_id" in cells:
            headers = cells
            continue
        if headers is None or is_separator_row(cells):
            continue
        if len(cells) != len(headers):
            continue
        record = dict(zip(headers, cells))
        if record.get("node_id") in NODE_IDS:
            records.append(record)
    return records


def is_separator_row(cells: list[str]) -> bool:
    return all(cell and set(cell) <= {"-", ":"} for cell in cells)


def validate_records(records: list[dict[str, str]]) -> list[Finding]:
    records_by_node = {record["node_id"]: record for record in records}
    findings: list[Finding] = []
    for node_id in NODE_IDS:
        record = records_by_node.get(node_id)
        if record is None:
            findings.append(Finding(f"missing evidence row for {node_id}"))
            continue
        findings.extend(validate_required_fields(node_id, record))
        findings.extend(validate_field_values(node_id, record))
    if all(node_id in records_by_node for node_id in ("C0.V3", "C0.V4")):
        findings.extend(validate_closure_consistency(records_by_node["C0.V3"], records_by_node["C0.V4"]))
    if all(node_id in records_by_node for node_id in NODE_IDS):
        findings.extend(validate_closure_verdict_consistency(records_by_node))
    return findings


def validate_required_fields(node_id: str, record: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for field in sorted(REQUIRED_FIELDS_BY_NODE[node_id]):
        if not meaningful_value(record.get(field, "")):
            findings.append(Finding(f"{node_id} missing required field: {field}"))
    return findings


def validate_field_values(node_id: str, record: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    status = record.get("status", "").strip()
    if status and status not in VALID_STATUSES:
        findings.append(Finding(f"{node_id} invalid status: {status}"))
    grafana_state = record.get("grafana_runtime_state", "").strip()
    if grafana_state and grafana_state not in VALID_GRAFANA_STATES:
        findings.append(Finding(f"{node_id} invalid grafana_runtime_state: {grafana_state}"))
    closure_verdict = record.get("closure_verdict", "").strip()
    if closure_verdict and closure_verdict not in VALID_CLOSURE_VERDICTS:
        findings.append(Finding(f"{node_id} invalid closure_verdict: {closure_verdict}"))
    return findings


def validate_closure_consistency(grafana_record: dict[str, str], closure_record: dict[str, str]) -> list[Finding]:
    grafana_state = grafana_record.get("grafana_runtime_state", "").strip()
    closure_state = closure_record.get("grafana_runtime_state", "").strip()
    closure_verdict = closure_record.get("closure_verdict", "").strip()
    findings: list[Finding] = []
    if grafana_state and closure_state and grafana_state != closure_state:
        findings.append(Finding("C0.V4 grafana_runtime_state must match C0.V3"))
    if grafana_state == "runtime_not_available" and closure_verdict == "full_c0_runtime_closure":
        findings.append(Finding("runtime_not_available cannot support full_c0_runtime_closure"))
    if grafana_state == "runtime_render_validated" and closure_verdict == "partial_c0_static_api_reference_closure":
        findings.append(Finding("runtime_render_validated should not be recorded as partial static closure"))
    return findings


def validate_closure_verdict_consistency(records_by_node: dict[str, dict[str, str]]) -> list[Finding]:
    closure_verdict = records_by_node["C0.V4"].get("closure_verdict", "").strip()
    if closure_verdict == "full_c0_runtime_closure":
        return validate_full_runtime_closure(records_by_node)
    if closure_verdict == "partial_c0_static_api_reference_closure":
        return validate_partial_static_closure(records_by_node)
    if closure_verdict == "failed":
        return validate_failed_closure(records_by_node)
    return []


def validate_full_runtime_closure(records_by_node: dict[str, dict[str, str]]) -> list[Finding]:
    findings: list[Finding] = []
    for node_id in NODE_IDS:
        findings.extend(require_status(records_by_node, node_id, "passed", "full_c0_runtime_closure"))
    findings.extend(require_grafana_state(records_by_node, "runtime_render_validated", "full_c0_runtime_closure"))
    return findings


def validate_partial_static_closure(records_by_node: dict[str, dict[str, str]]) -> list[Finding]:
    findings: list[Finding] = []
    for node_id in ("C0.V1", "C0.V2", "C0.V4"):
        findings.extend(require_status(records_by_node, node_id, "passed", "partial_c0_static_api_reference_closure"))
    findings.extend(require_status(records_by_node, "C0.V3", "deferred_with_trigger", "partial_c0_static_api_reference_closure"))
    findings.extend(require_grafana_state(records_by_node, "runtime_not_available", "partial_c0_static_api_reference_closure"))
    findings.extend(require_non_empty_residual_risk(records_by_node, "C0.V3", "partial_c0_static_api_reference_closure"))
    findings.extend(require_non_empty_residual_risk(records_by_node, "C0.V4", "partial_c0_static_api_reference_closure"))
    return findings


def validate_failed_closure(records_by_node: dict[str, dict[str, str]]) -> list[Finding]:
    if any(records_by_node[node_id].get("status", "").strip() in {"failed", "blocked", "deferred_with_trigger"} for node_id in NODE_IDS):
        return []
    return [Finding("failed closure_verdict requires at least one failed, blocked, or deferred C0.V status")]


def require_status(records_by_node: dict[str, dict[str, str]], node_id: str, expected_status: str, verdict: str) -> list[Finding]:
    actual_status = records_by_node[node_id].get("status", "").strip()
    if actual_status == expected_status:
        return []
    return [Finding(f"{verdict} requires {node_id} status={expected_status}; got {actual_status or '<empty>'}")]


def require_grafana_state(records_by_node: dict[str, dict[str, str]], expected_state: str, verdict: str) -> list[Finding]:
    actual_state = records_by_node["C0.V3"].get("grafana_runtime_state", "").strip()
    if actual_state == expected_state:
        return []
    return [Finding(f"{verdict} requires C0.V3 grafana_runtime_state={expected_state}; got {actual_state or '<empty>'}")]


def require_non_empty_residual_risk(records_by_node: dict[str, dict[str, str]], node_id: str, verdict: str) -> list[Finding]:
    residual_risk = records_by_node[node_id].get("residual_risk", "").strip().lower()
    if residual_risk and residual_risk != "none":
        return []
    return [Finding(f"{verdict} requires {node_id} residual_risk to name the deferred trigger")]


def meaningful_value(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(normalized) and normalized not in {"pending", "tbd", "n/a"}


if __name__ == "__main__":
    main()