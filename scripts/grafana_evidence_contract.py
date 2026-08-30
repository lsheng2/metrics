from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlparse


def validate_panel_evidence_links(path, payload: dict[str, Any], finding) -> list:
    panels = payload.get("panels", [])
    if not isinstance(panels, list):
        return []
    findings = []
    for panel_index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        panel_path = f"panels[{panel_index}]"
        findings.extend(validate_evidence_capabilities(path, panel_path, panel, finding))
        target_fields = evidence_fields_by_target(panel)
        if not target_fields:
            continue
        link_urls = panel_link_urls(panel)
        if not link_urls:
            findings.append(finding(path, f"{panel_path} declares evidence link fields but has no panel field links"))
            continue
        column_fields = target_column_fields(panel)
        for target_path, fields in target_fields.items():
            missing_columns = fields - column_fields
            if missing_columns:
                findings.append(finding(path, f"{target_path} evidenceLinkFields missing target columns: {', '.join(sorted(missing_columns))}"))
            for field in sorted(fields):
                field_ref = f"${{__data.fields.{field}}}"
                if not any(field_ref in link_url for link_url in link_urls):
                    findings.append(finding(path, f"{panel_path} evidence link URL does not reference {field_ref}"))
        findings.extend(validate_evidence_link_param_mapping(path, panel_path, link_urls, finding))
    return findings


def validate_evidence_capabilities(path, panel_path: str, panel: dict[str, Any], finding) -> list:
    findings = []
    link_urls = panel_link_urls(panel)
    for target_index, target in enumerate(panel.get("targets", [])):
        if not isinstance(target, dict):
            continue
        metrics_contract = target.get("metricsContract", {})
        if not isinstance(metrics_contract, dict) or not metrics_contract:
            continue
        target_path = f"{panel_path}.targets[{target_index}]"
        evidence_capability = metrics_contract.get("evidenceCapability")
        if evidence_capability not in {"bucket_series", "range_only", "summary_only"}:
            findings.append(finding(path, f"{target_path} must declare evidenceCapability as bucket_series, range_only, or summary_only"))
            continue
        evidence_link_fields = metrics_contract.get("evidenceLinkFields", [])
        if evidence_capability == "bucket_series" and set(evidence_link_fields) != {"calculation_run_id", "bucket_id"}:
            findings.append(finding(path, f"{target_path} bucket_series evidence must declare evidenceLinkFields calculation_run_id and bucket_id"))
        if evidence_capability == "summary_only" and (evidence_link_fields or any(is_ticket_evidence_url(link_url) for link_url in link_urls)):
            findings.append(finding(path, f"{target_path} summary_only evidence must not expose ticket evidence links"))
    return findings


def is_ticket_evidence_url(link_url: str) -> bool:
    return urlparse(link_url).path in {"/api/charts/evidence/", "/api/provider-charts/evidence/"}


def evidence_fields_by_target(panel: dict[str, Any]) -> dict[str, frozenset[str]]:
    fields_by_target: dict[str, frozenset[str]] = {}
    targets = panel.get("targets", [])
    if not isinstance(targets, list):
        return fields_by_target
    for target_index, target in enumerate(targets):
        if not isinstance(target, dict):
            continue
        metrics_contract = target.get("metricsContract", {})
        if not isinstance(metrics_contract, dict):
            continue
        evidence_fields = metrics_contract.get("evidenceLinkFields", [])
        if evidence_fields:
            fields_by_target[f"targets[{target_index}]"] = frozenset(str(field) for field in evidence_fields)
    return fields_by_target


def panel_link_urls(panel: dict[str, Any]) -> list[str]:
    defaults = panel.get("fieldConfig", {}).get("defaults", {})
    links = defaults.get("links", []) if isinstance(defaults, dict) else []
    return [link.get("url", "") for link in links if isinstance(link, dict) and isinstance(link.get("url"), str)]


def target_column_fields(panel: dict[str, Any]) -> frozenset[str]:
    fields: set[str] = set()
    targets = panel.get("targets", [])
    if not isinstance(targets, list):
        return frozenset()
    for target in targets:
        if isinstance(target, dict):
            fields.update(target_fields(target))
    return frozenset(fields)


def target_fields(target: dict[str, Any]) -> frozenset[str]:
    fields: set[str] = set()
    columns = target.get("columns", [])
    if not isinstance(columns, list):
        return frozenset()
    for column in columns:
        if isinstance(column, dict):
            fields.update(str(column[field]) for field in ("selector", "text") if isinstance(column.get(field), str))
    return frozenset(fields)


def validate_evidence_link_param_mapping(path, panel_path: str, link_urls: list[str], finding) -> list:
    required_fragments = {"run": "run=${__data.fields.calculation_run_id}", "bucket": "bucket=${__data.fields.bucket_id}"}
    findings = [
        finding(path, f"{panel_path} evidence link URL must map {param_name} via {fragment}")
        for param_name, fragment in required_fragments.items()
        if not any(fragment in link_url for link_url in link_urls)
    ]
    if not any("series=${__data.fields.series_name}" in link_url or "series=${__field.name}" in link_url for link_url in link_urls):
        findings.append(finding(path, f"{panel_path} evidence link URL must map series via series=${{__data.fields.series_name}} or series=${{__field.name}}"))
    chart_ids = {value for link_url in link_urls for name, value in parse_qsl(urlparse(link_url).query, keep_blank_values=True) if name == "chart_id"}
    if not chart_ids:
        findings.append(finding(path, f"{panel_path} evidence link URL must include chart_id when chart-data target uses Chart Catalog"))
    return findings
