#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlparse


NODE_IDS = ("C1.N1", "C1.N2", "C1.N3", "C1.N4")
VALID_STATUSES = {"passed", "failed", "blocked", "skipped_with_reason"}
VALID_PAYLOAD_STATES = {"payload_captured", "payload_unavailable"}
VALID_VERDICTS = {"c_stock_linked_evidence_supported", "c_stock_non_evidence_only", "c_plugin_required"}

BASE_REQUIRED = frozenset({"status", "command_or_manual_step", "result", "residual_risk"})
PAGE_REQUIRED = frozenset({"observed_grafana_url", "scope_id", "begin", "end"})
PAYLOAD_REQUIRED = frozenset({"payload_state", "run", "bucket", "series", "chart_id"})
PARITY_REQUIRED = frozenset({"reference_selection_title", "linked_selection_title", "reference_row_count", "linked_row_count"})

REQUIRED_FIELDS_BY_NODE = {
    "C1.N1": BASE_REQUIRED,
    "C1.N2": BASE_REQUIRED | PAGE_REQUIRED | PAYLOAD_REQUIRED,
    "C1.N3": BASE_REQUIRED | PAGE_REQUIRED | PAYLOAD_REQUIRED | PARITY_REQUIRED,
    "C1.N4": BASE_REQUIRED | frozenset({"payload_state", "decision_verdict"}),
}


@dataclass(frozen=True, slots=True)
class Finding:
    message: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Check C1 evidence-link validation evidence completeness.")
    parser.add_argument("--evidence", required=True, help="Markdown evidence file for C1 evidence-link validation.")
    args = parser.parse_args()

    findings = validate_evidence_file(Path(args.evidence))
    for finding in findings:
        print(f"FAIL {finding.message}")

    if findings:
        raise SystemExit(1)

    print(f"PASS c1 evidence-link validation nodes={len(NODE_IDS)}")


def validate_evidence_file(path: Path) -> list[Finding]:
    if not path.exists():
        return [Finding(f"evidence file not found: {path}")]
    return validate_records(parse_markdown_table(path.read_text(encoding="utf-8")))


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
        findings.extend(validate_resolved_link_query(node_id, record))
    if all(node_id in records_by_node for node_id in NODE_IDS):
        findings.extend(validate_cross_node_consistency(records_by_node))
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
    payload_state = record.get("payload_state", "").strip()
    if payload_state and payload_state not in VALID_PAYLOAD_STATES:
        findings.append(Finding(f"{node_id} invalid payload_state: {payload_state}"))
    verdict = record.get("decision_verdict", "").strip()
    if verdict and verdict not in VALID_VERDICTS:
        findings.append(Finding(f"{node_id} invalid decision_verdict: {verdict}"))
    return findings


def validate_resolved_link_query(node_id: str, record: dict[str, str]) -> list[Finding]:
    if node_id not in {"C1.N2", "C1.N3"} or record.get("payload_state", "").strip() != "payload_captured":
        return []
    resolved_link_url = record.get("resolved_link_url", "").strip()
    if not resolved_link_url:
        return [Finding(f"{node_id} missing required field: resolved_link_url")]
    query = dict(parse_qsl(urlparse(resolved_link_url).query, keep_blank_values=True))
    findings: list[Finding] = []
    for field in ("scope_id", "begin", "end", "run", "bucket", "series", "chart_id"):
        expected = record.get(field, "").strip()
        actual = query.get(field, "").strip()
        if actual != expected:
            findings.append(Finding(f"{node_id} resolved_link_url {field}={actual or '<empty>'} does not match evidence field {expected or '<empty>'}"))
    return findings


def validate_cross_node_consistency(records_by_node: dict[str, dict[str, str]]) -> list[Finding]:
    verdict = records_by_node["C1.N4"].get("decision_verdict", "").strip()
    if verdict == "c_stock_linked_evidence_supported":
        return validate_linked_evidence_supported(records_by_node)
    if verdict == "c_stock_non_evidence_only":
        return validate_non_evidence_only(records_by_node)
    if verdict == "c_plugin_required":
        return validate_plugin_required(records_by_node)
    return []


def validate_linked_evidence_supported(records_by_node: dict[str, dict[str, str]]) -> list[Finding]:
    findings: list[Finding] = []
    for node_id in NODE_IDS:
        findings.extend(require_status(records_by_node, node_id, "passed", "c_stock_linked_evidence_supported"))
    findings.extend(require_payload_state(records_by_node, "payload_captured", "c_stock_linked_evidence_supported"))
    n3 = records_by_node["C1.N3"]
    if n3.get("reference_selection_title") != n3.get("linked_selection_title"):
        findings.append(Finding("c_stock_linked_evidence_supported requires matching evidence selection titles"))
    if n3.get("reference_row_count") != n3.get("linked_row_count"):
        findings.append(Finding("c_stock_linked_evidence_supported requires matching evidence row counts"))
    residual_risk = records_by_node["C1.N4"].get("residual_risk", "").strip().lower()
    if residual_risk in {"", "none"}:
        findings.append(Finding("c_stock_linked_evidence_supported must name link-out vs same-page residual risk"))
    return findings


def validate_non_evidence_only(records_by_node: dict[str, dict[str, str]]) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(require_status(records_by_node, "C1.N1", "passed", "c_stock_non_evidence_only"))
    findings.extend(require_status(records_by_node, "C1.N4", "passed", "c_stock_non_evidence_only"))
    payload_state = records_by_node["C1.N2"].get("payload_state", "").strip()
    n3_status = records_by_node["C1.N3"].get("status", "").strip()
    if payload_state != "payload_unavailable" and n3_status not in {"failed", "skipped_with_reason", "blocked"}:
        findings.append(Finding("c_stock_non_evidence_only requires unavailable payload or non-passing evidence parity"))
    return findings


def validate_plugin_required(records_by_node: dict[str, dict[str, str]]) -> list[Finding]:
    if any(records_by_node[node_id].get("status", "").strip() in {"failed", "blocked"} for node_id in NODE_IDS):
        return []
    return [Finding("c_plugin_required requires at least one failed or blocked C1 node")]


def require_status(records_by_node: dict[str, dict[str, str]], node_id: str, expected: str, verdict: str) -> list[Finding]:
    actual = records_by_node[node_id].get("status", "").strip()
    if actual == expected:
        return []
    return [Finding(f"{verdict} requires {node_id} status={expected}; got {actual or '<empty>'}")]


def require_payload_state(records_by_node: dict[str, dict[str, str]], expected: str, verdict: str) -> list[Finding]:
    findings: list[Finding] = []
    for node_id in ("C1.N2", "C1.N3", "C1.N4"):
        actual = records_by_node[node_id].get("payload_state", "").strip()
        if actual != expected:
            findings.append(Finding(f"{verdict} requires {node_id} payload_state={expected}; got {actual or '<empty>'}"))
    return findings


def meaningful_value(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(normalized) and normalized not in {"pending", "tbd", "n/a"}


if __name__ == "__main__":
    main()
