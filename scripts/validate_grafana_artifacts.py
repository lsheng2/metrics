#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse


@dataclass(frozen=True, slots=True)
class ApiSurface:
    required_query_params: frozenset[str]
    optional_query_params: frozenset[str]


@dataclass(frozen=True, slots=True)
class GrafanaAllowlist:
    datasource_uids: frozenset[str]
    api_surfaces: dict[str, ApiSurface]
    sql_views: frozenset[str]
    forbidden_sql_patterns: tuple[re.Pattern[str], ...]
    secret_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    message: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Grafana artifacts against Metrics-owned data surfaces.")
    parser.add_argument("--artifact-root", required=True, help="Directory containing provisioned Grafana JSON artifacts.")
    parser.add_argument("--allowlist", required=True, help="JSON file describing approved Metrics data surfaces.")
    args = parser.parse_args()

    artifact_root = Path(args.artifact_root)
    allowlist = load_allowlist(Path(args.allowlist))
    findings = validate_artifact_root(artifact_root, allowlist)

    for finding in findings:
        print(f"FAIL {finding.path}: {finding.message}")

    if findings:
        raise SystemExit(1)

    print(f"PASS grafana artifacts checked={len(json_artifacts(artifact_root))}")


def load_allowlist(path: Path) -> GrafanaAllowlist:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return GrafanaAllowlist(
        datasource_uids=frozenset(payload.get("datasource_uids", [])),
        api_surfaces=load_api_surfaces(payload.get("api_surfaces", {})),
        sql_views=frozenset(payload.get("sql_views", [])),
        forbidden_sql_patterns=compile_patterns(payload.get("forbidden_sql_patterns", [])),
        secret_patterns=compile_patterns(payload.get("secret_patterns", []), re.IGNORECASE),
    )


def load_api_surfaces(payload: dict[str, Any]) -> dict[str, ApiSurface]:
    return {
        path: ApiSurface(
            required_query_params=frozenset(config.get("required_query_params", [])),
            optional_query_params=frozenset(config.get("optional_query_params", [])),
        )
        for path, config in payload.items()
    }


def compile_patterns(patterns: list[str], flags: int = re.IGNORECASE) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, flags) for pattern in patterns)


def validate_artifact_root(artifact_root: Path, allowlist: GrafanaAllowlist) -> list[Finding]:
    artifacts = json_artifacts(artifact_root)
    if not artifacts:
        return [Finding(artifact_root, "no Grafana JSON artifacts found")]

    findings: list[Finding] = []
    for artifact in artifacts:
        findings.extend(validate_artifact(artifact, allowlist))
    return dedupe_findings(findings)


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[Finding] = set()
    unique_findings: list[Finding] = []
    for finding in findings:
        if finding in seen:
            continue
        seen.add(finding)
        unique_findings.append(finding)
    return unique_findings


def json_artifacts(artifact_root: Path) -> list[Path]:
    if not artifact_root.exists():
        return []
    return sorted(path for path in artifact_root.rglob("*.json") if path.is_file())


def validate_artifact(path: Path, allowlist: GrafanaAllowlist) -> list[Finding]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [Finding(path, f"invalid JSON: {error}")]

    return validate_node(path, "", payload, allowlist, None) + validate_panel_evidence_links(path, payload)


def validate_panel_evidence_links(path: Path, payload: dict[str, Any]) -> list[Finding]:
    panels = payload.get("panels", [])
    if not isinstance(panels, list):
        return []
    findings: list[Finding] = []
    for panel_index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        panel_path = f"panels[{panel_index}]"
        target_fields = evidence_fields_by_target(panel)
        if not target_fields:
            continue
        link_urls = panel_link_urls(panel)
        if not link_urls:
            findings.append(Finding(path, f"{panel_path} declares evidence link fields but has no panel field links"))
            continue
        column_fields = target_column_fields(panel)
        for target_path, fields in target_fields.items():
            missing_columns = fields - column_fields
            if missing_columns:
                findings.append(Finding(path, f"{target_path} evidenceLinkFields missing target columns: {', '.join(sorted(missing_columns))}"))
            for field in sorted(fields):
                field_ref = f"${{__data.fields.{field}}}"
                if not any(field_ref in link_url for link_url in link_urls):
                    findings.append(Finding(path, f"{panel_path} evidence link URL does not reference {field_ref}"))
        findings.extend(validate_evidence_link_param_mapping(path, panel_path, link_urls))
    return findings


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
        if not isinstance(target, dict):
            continue
        columns = target.get("columns", [])
        if not isinstance(columns, list):
            continue
        for column in columns:
            if not isinstance(column, dict):
                continue
            selector = column.get("selector")
            text = column.get("text")
            if isinstance(selector, str):
                fields.add(selector)
            if isinstance(text, str):
                fields.add(text)
    return frozenset(fields)


def validate_evidence_link_param_mapping(path: Path, panel_path: str, link_urls: list[str]) -> list[Finding]:
    required_fragments = {
        "run": "run=${__data.fields.calculation_run_id}",
        "bucket": "bucket=${__data.fields.bucket_id}",
        "series": "series=${__data.fields.series_name}",
    }
    findings: list[Finding] = []
    for param_name, fragment in required_fragments.items():
        if not any(fragment in link_url for link_url in link_urls):
            findings.append(Finding(path, f"{panel_path} evidence link URL must map {param_name} via {fragment}"))
    return findings


def validate_node(
    artifact_path: Path,
    value_path: str,
    value: Any,
    allowlist: GrafanaAllowlist,
    inherited_datasource_uid: str | None,
) -> list[Finding]:
    findings: list[Finding] = []
    datasource_uid = datasource_uid_from(value) if isinstance(value, dict) else None
    effective_datasource_uid = datasource_uid or inherited_datasource_uid

    if datasource_uid and datasource_uid not in allowlist.datasource_uids:
        findings.append(Finding(artifact_path, f"unapproved datasource uid at {value_path or '<root>'}: {datasource_uid}"))

    if isinstance(value, dict):
        findings.extend(validate_query_owner(artifact_path, value_path, value, allowlist, effective_datasource_uid))
        for key, child in value.items():
            child_path = f"{value_path}.{key}" if value_path else str(key)
            findings.extend(validate_node(artifact_path, child_path, child, allowlist, effective_datasource_uid))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{value_path}[{index}]"
            findings.extend(validate_node(artifact_path, child_path, child, allowlist, effective_datasource_uid))
    elif isinstance(value, str):
        findings.extend(validate_string(artifact_path, value_path, value, allowlist))
    return findings


def datasource_uid_from(value: dict[str, Any]) -> str | None:
    datasource = value.get("datasource")
    if isinstance(datasource, str):
        return datasource
    if isinstance(datasource, dict) and isinstance(datasource.get("uid"), str):
        return datasource["uid"]
    datasource_uid = value.get("datasourceUid")
    if isinstance(datasource_uid, str):
        return datasource_uid
    return None


def validate_query_owner(
    artifact_path: Path,
    value_path: str,
    value: dict[str, Any],
    allowlist: GrafanaAllowlist,
    datasource_uid: str | None,
) -> list[Finding]:
    query_values = query_surface_values(value)
    if not query_values:
        return []
    findings: list[Finding] = []
    if datasource_uid is None:
        findings.append(Finding(artifact_path, f"query target at {value_path or '<root>'} has no explicit approved datasource"))
    elif datasource_uid not in allowlist.datasource_uids:
        findings.append(Finding(artifact_path, f"query target at {value_path or '<root>'} uses unapproved datasource uid: {datasource_uid}"))
    for field_name, query_value in query_values:
        child_path = f"{value_path}.{field_name}" if value_path else field_name
        findings.extend(validate_string(artifact_path, child_path, query_value, allowlist))
    return findings


def query_surface_values(value: dict[str, Any]) -> list[tuple[str, str]]:
    fields = []
    for key in ("rawSql", "query", "url", "path"):
        item = value.get(key)
        if isinstance(item, str) and (looks_like_sql(item) or looks_like_metrics_api_path(item)):
            fields.append((key, item))
    return fields


def validate_string(path: Path, value_path: str, value: str, allowlist: GrafanaAllowlist) -> list[Finding]:
    findings: list[Finding] = []
    if looks_like_secret_field(value_path, allowlist) and value:
        findings.append(Finding(path, f"secret-shaped field at {value_path}"))

    if looks_like_sql(value):
        findings.extend(validate_sql(path, value_path, value, allowlist))
    elif looks_like_metrics_api_path(value):
        findings.extend(validate_api_path(path, value_path, value, allowlist))
    return findings


def looks_like_secret_field(value_path: str, allowlist: GrafanaAllowlist) -> bool:
    segments = re.split(r"[.\[\]]+", value_path)
    return any(pattern.fullmatch(segment) for segment in segments if segment for pattern in allowlist.secret_patterns)


def looks_like_sql(value: str) -> bool:
    return bool(re.search(r"\b(select|from|where)\b", value, re.IGNORECASE))


def looks_like_metrics_api_path(value: str) -> bool:
    return urlparse(value).path.startswith("/api/")


def validate_api_path(path: Path, value_path: str, value: str, allowlist: GrafanaAllowlist) -> list[Finding]:
    findings: list[Finding] = []
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        findings.append(Finding(path, f"Metrics API target must be a relative path at {value_path}: {value}"))
    api_surface = allowlist.api_surfaces.get(parsed.path)
    if api_surface is None:
        findings.append(Finding(path, f"unapproved Metrics API path at {value_path}: {value}"))
        return findings
    query_params = {name for name, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    allowed_params = api_surface.required_query_params | api_surface.optional_query_params
    unapproved_params = query_params - allowed_params
    if unapproved_params:
        findings.append(Finding(path, f"unapproved Metrics API query params at {value_path}: {', '.join(sorted(unapproved_params))}"))
    missing_params = api_surface.required_query_params - query_params
    if missing_params:
        findings.append(Finding(path, f"missing required Metrics API query params at {value_path}: {', '.join(sorted(missing_params))}"))
    return findings


def validate_sql(path: Path, value_path: str, sql: str, allowlist: GrafanaAllowlist) -> list[Finding]:
    findings: list[Finding] = []
    if not allowlist.sql_views:
        return [Finding(path, f"SQL datasource disabled for current phase at {value_path}")]
    referenced_tables = set(re.findall(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.IGNORECASE))
    if not referenced_tables:
        findings.append(Finding(path, f"SQL query references no approved Metrics view at {value_path}"))
    unapproved_tables = referenced_tables - allowlist.sql_views
    if unapproved_tables:
        findings.append(Finding(path, f"unapproved SQL table/view at {value_path}: {', '.join(sorted(unapproved_tables))}"))
    for pattern in allowlist.forbidden_sql_patterns:
        if pattern.search(sql):
            findings.append(Finding(path, f"forbidden SQL pattern at {value_path}: {pattern.pattern}"))
    return findings


if __name__ == "__main__":
    main()