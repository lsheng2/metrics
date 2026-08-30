from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from grafana_evidence_contract import validate_panel_evidence_links
from grafana_provider_chart_contract import ChartRecipe, load_provider_chart_recipes, validate_daily_metric_panel, validate_provider_chart_contract


@dataclass(frozen=True, slots=True)
class ApiSurface:
    required_query_params: frozenset[str]
    optional_query_params: frozenset[str]
    approved_contract_versions: frozenset[str]
    approved_render_roots: frozenset[str]
    approved_render_shapes: frozenset[str]


@dataclass(frozen=True, slots=True)
class GrafanaAllowlist:
    datasource_uids: frozenset[str]
    api_surfaces: dict[str, ApiSurface]
    provider_chart_recipes: dict[str, ChartRecipe]
    sql_views: frozenset[str]
    forbidden_sql_patterns: tuple[re.Pattern[str], ...]
    secret_patterns: tuple[re.Pattern[str], ...]
    forbidden_provider_literal_patterns: tuple[re.Pattern[str], ...]
    forbidden_business_calculation_patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    message: str


def load_allowlist(path: Path) -> GrafanaAllowlist:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return GrafanaAllowlist(
        datasource_uids=frozenset(payload.get("datasource_uids", [])),
        api_surfaces=load_api_surfaces(payload.get("api_surfaces", {})),
        provider_chart_recipes=load_provider_chart_recipes(payload.get("provider_chart_recipes", {})),
        sql_views=frozenset(payload.get("sql_views", [])),
        forbidden_sql_patterns=compile_patterns(payload.get("forbidden_sql_patterns", [])),
        secret_patterns=compile_patterns(payload.get("secret_patterns", []), re.IGNORECASE),
        forbidden_provider_literal_patterns=compile_patterns(payload.get("forbidden_provider_literal_patterns", []), re.IGNORECASE),
        forbidden_business_calculation_patterns=compile_patterns(payload.get("forbidden_business_calculation_patterns", []), re.IGNORECASE),
    )


def load_api_surfaces(payload: dict[str, Any]) -> dict[str, ApiSurface]:
    return {
        path: ApiSurface(
            required_query_params=frozenset(config.get("required_query_params", [])),
            optional_query_params=frozenset(config.get("optional_query_params", [])),
            approved_contract_versions=frozenset(config.get("approved_contract_versions", [])),
            approved_render_roots=frozenset(config.get("approved_render_roots", [])),
            approved_render_shapes=frozenset(config.get("approved_render_shapes", [])),
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

    return validate_node(path, "", payload, allowlist, None) + validate_panel_evidence_links(path, payload, Finding) + validate_render_contracts(path, payload, allowlist)


def validate_render_contracts(path: Path, payload: dict[str, Any], allowlist: GrafanaAllowlist) -> list[Finding]:
    panels = payload.get("panels", [])
    if not isinstance(panels, list):
        return []
    findings: list[Finding] = []
    for panel_index, panel in enumerate(panels):
        if not isinstance(panel, dict):
            continue
        findings.extend(validate_daily_metric_panel(path, f"panels[{panel_index}]", panel, Finding))
        for target_index, target in enumerate(panel.get("targets", [])):
            if not isinstance(target, dict):
                continue
            metrics_contract = target.get("metricsContract", {})
            target_path = f"panels[{panel_index}].targets[{target_index}]"
            target_url = target.get("url") or target.get("path") or ""
            surface = api_surface_for_target(target_url, allowlist)
            if surface and (surface.approved_render_roots or surface.approved_render_shapes) and (not isinstance(metrics_contract, dict) or not metrics_contract):
                findings.append(Finding(path, f"{target_path} must declare metricsContract for approved render surface {urlparse(target_url).path}"))
                continue
            if not isinstance(metrics_contract, dict) or not metrics_contract:
                continue
            findings.extend(validate_render_contract_against_allowlist(path, target_path, target_url, metrics_contract, target, allowlist))
            findings.extend(validate_provider_chart_contract(path, target_path, target_url, metrics_contract, allowlist, Finding))
            if metrics_contract.get("shape") == "wide_bucket_series":
                findings.extend(validate_wide_bucket_series_contract(path, target_path, target, metrics_contract))
    return findings


def api_surface_for_target(target_url: str, allowlist: GrafanaAllowlist) -> ApiSurface | None:
    if not target_url:
        return None
    return allowlist.api_surfaces.get(urlparse(target_url).path)


def validate_render_contract_against_allowlist(path: Path, target_path: str, target_url: str, metrics_contract: dict[str, Any], target: dict[str, Any], allowlist: GrafanaAllowlist) -> list[Finding]:
    if not target_url:
        return []
    parsed = urlparse(target_url)
    api_surface = allowlist.api_surfaces.get(parsed.path)
    if api_surface is None:
        return []
    root = str(metrics_contract.get("root", ""))
    shape = str(metrics_contract.get("shape", ""))
    contract_version = str(metrics_contract.get("contractVersion", ""))
    findings = []
    if api_surface.approved_contract_versions and contract_version not in api_surface.approved_contract_versions:
        findings.append(Finding(path, f"{target_path} contractVersion {contract_version!r} is not approved for {parsed.path}; expected one of {sorted(api_surface.approved_contract_versions)}"))
    if api_surface.approved_render_roots and root not in api_surface.approved_render_roots:
        findings.append(Finding(path, f"{target_path} render root {root!r} is not approved for {parsed.path}; expected one of {sorted(api_surface.approved_render_roots)}"))
    if api_surface.approved_render_shapes and shape not in api_surface.approved_render_shapes:
        findings.append(Finding(path, f"{target_path} render shape {shape!r} is not approved for {parsed.path}; expected one of {sorted(api_surface.approved_render_shapes)}"))
    return findings


def validate_wide_bucket_series_contract(path: Path, target_path: str, target: dict[str, Any], metrics_contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if metrics_contract.get("chartId") != chart_id_from_target(target):
        findings.append(Finding(path, f"{target_path} metricsContract chartId must match target chart_id"))
    if metrics_contract.get("root") != "grafana_rows":
        findings.append(Finding(path, f"{target_path} wide_bucket_series root must be grafana_rows"))
    if target.get("root_selector") != "$.grafana_rows":
        findings.append(Finding(path, f"{target_path} wide_bucket_series target must use root_selector $.grafana_rows"))
    if metrics_contract.get("categoryField") != "bucket_label":
        findings.append(Finding(path, f"{target_path} wide_bucket_series categoryField must be bucket_label"))
    column_fields = target_fields(target)
    required_fields = set(metrics_contract.get("requiredFields", []))
    value_fields = set(metrics_contract.get("valueFields", []))
    if not value_fields:
        findings.append(Finding(path, f"{target_path} wide_bucket_series valueFields must not be empty"))
    missing_required = required_fields - column_fields
    missing_values = value_fields - column_fields
    if missing_required:
        findings.append(Finding(path, f"{target_path} wide_bucket_series missing required columns: {', '.join(sorted(missing_required))}"))
    if missing_values:
        findings.append(Finding(path, f"{target_path} wide_bucket_series missing value columns: {', '.join(sorted(missing_values))}"))
    if "label" in column_fields and metrics_contract.get("categoryField") != "label":
        findings.append(Finding(path, f"{target_path} must not use generic label column for render category; use bucket_label"))
    return findings


def chart_id_from_target(target: dict[str, Any]) -> str:
    target_url = target.get("url") or target.get("path") or ""
    params = dict(parse_qsl(urlparse(target_url).query, keep_blank_values=True))
    return params.get("chart_id", "")


def target_fields(target: dict[str, Any]) -> frozenset[str]:
    fields: set[str] = set()
    columns = target.get("columns", [])
    if not isinstance(columns, list):
        return frozenset()
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


def validate_node(artifact_path: Path, value_path: str, value: Any, allowlist: GrafanaAllowlist, inherited_datasource_uid: str | None) -> list[Finding]:
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


def validate_query_owner(artifact_path: Path, value_path: str, value: dict[str, Any], allowlist: GrafanaAllowlist, datasource_uid: str | None) -> list[Finding]:
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
    findings.extend(validate_forbidden_provider_literals(path, value_path, value, allowlist))
    findings.extend(validate_forbidden_business_calculations(path, value_path, value, allowlist))

    if looks_like_sql(value):
        findings.extend(validate_sql(path, value_path, value, allowlist))
    elif looks_like_metrics_api_path(value):
        findings.extend(validate_api_path(path, value_path, value, allowlist))
    return findings


def validate_forbidden_provider_literals(path: Path, value_path: str, value: str, allowlist: GrafanaAllowlist) -> list[Finding]:
    return [
        Finding(path, f"provider-native query or field literal at {value_path}: {pattern.pattern}")
        for pattern in allowlist.forbidden_provider_literal_patterns
        if pattern.search(value)
    ]


def validate_forbidden_business_calculations(path: Path, value_path: str, value: str, allowlist: GrafanaAllowlist) -> list[Finding]:
    return [
        Finding(path, f"Grafana panel-local business calculation at {value_path}: {pattern.pattern}")
        for pattern in allowlist.forbidden_business_calculation_patterns
        if pattern.search(value)
    ]


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
