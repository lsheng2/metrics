from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qsl, urlparse


@dataclass(frozen=True, slots=True)
class ChartRecipe:
    version: int
    approved_render_roots: frozenset[str]
    approved_render_shapes: frozenset[str]
    approved_provider_bindings: frozenset[str]
    approved_value_fields: frozenset[str]
    approved_evidence_capabilities: frozenset[str]
    bucket_grains: frozenset[str]


def load_provider_chart_recipes(payload: dict[str, Any]) -> dict[str, ChartRecipe]:
    return {
        chart_id: ChartRecipe(
            version=int(config.get("version", 1)),
            approved_render_roots=frozenset(config.get("approved_render_roots", [])),
            approved_render_shapes=frozenset(config.get("approved_render_shapes", [])),
            approved_provider_bindings=frozenset(config.get("approved_provider_bindings", [])),
            approved_value_fields=frozenset(config.get("approved_value_fields", [])),
            approved_evidence_capabilities=frozenset(config.get("approved_evidence_capabilities", [])),
            bucket_grains=frozenset(config.get("bucket_grains", [])),
        )
        for chart_id, config in payload.items()
    }


def validate_provider_chart_contract(path, target_path, target_url, metrics_contract, allowlist, finding):
    parsed = urlparse(target_url)
    if parsed.path != "/api/provider-charts/data/":
        return []
    query_chart_id = chart_id_from_target({"url": target_url})
    recipe = allowlist.provider_chart_recipes.get(query_chart_id)
    if recipe is None:
        return [finding(path, f"{target_path} chart_id {query_chart_id!r} is not an approved Metrics chart recipe")]

    checks = {"semanticOwner": "metrics", "chartRecipeVersion": recipe.version}
    findings = [
        finding(path, f"{target_path} {field} must be {expected}")
        for field, expected in checks.items()
        if metrics_contract.get(field) != expected
    ]
    if metrics_contract.get("chartRecipeId") != query_chart_id:
        findings.append(finding(path, f"{target_path} chartRecipeId must match target chart_id"))
    if metrics_contract.get("providerBinding") not in recipe.approved_provider_bindings:
        findings.append(finding(path, f"{target_path} providerBinding {metrics_contract.get('providerBinding')!r} is not approved for chart recipe {query_chart_id}"))
    if metrics_contract.get("root") not in recipe.approved_render_roots:
        findings.append(finding(path, f"{target_path} render root {metrics_contract.get('root')!r} is not approved by chart recipe {query_chart_id}"))
    if metrics_contract.get("shape") not in recipe.approved_render_shapes:
        findings.append(finding(path, f"{target_path} render shape {metrics_contract.get('shape')!r} is not approved by chart recipe {query_chart_id}"))
    evidence_capability = metrics_contract.get("evidenceCapability")
    if not evidence_capability:
        findings.append(finding(path, f"{target_path} must declare evidenceCapability"))
    elif recipe.approved_evidence_capabilities and evidence_capability not in recipe.approved_evidence_capabilities:
        findings.append(finding(path, f"{target_path} evidenceCapability {evidence_capability!r} is not approved by chart recipe {query_chart_id}"))

    value_fields = set(metrics_contract.get("valueFields", []))
    extra_value_fields = value_fields - recipe.approved_value_fields
    if extra_value_fields:
        findings.append(finding(path, f"{target_path} uses valueFields outside approved chart recipe {query_chart_id}: {', '.join(sorted(extra_value_fields))}"))
    if query_chart_id.startswith("daily_"):
        findings.extend(validate_daily_metric_contract(path, target_path, metrics_contract, recipe, finding))
    return findings


def validate_daily_metric_contract(path, target_path, metrics_contract, recipe, finding):
    checks = {
        "calculationOwner": "metrics",
        "aggregationOwner": "materialized_aggregate",
    }
    findings = [
        finding(path, f"{target_path} daily metric {field} must be {expected}")
        for field, expected in checks.items()
        if metrics_contract.get(field) != expected
    ]
    if metrics_contract.get("bucketGrain") not in recipe.bucket_grains:
        findings.append(finding(path, f"{target_path} daily metric bucketGrain must be one of {sorted(recipe.bucket_grains)}"))
    return findings


def validate_daily_metric_panel(path, panel_path, panel, finding):
    if not panel_contains_daily_metric(panel):
        return []
    for value in nested_values(panel.get("transformations", [])):
        if isinstance(value, str) and re.search(r"\b(calculateField|reduce|math)\b", value, re.IGNORECASE):
            return [finding(path, f"{panel_path} daily metric panels must not use Grafana calculation transformations")]
    return []


def panel_contains_daily_metric(panel: dict[str, Any]) -> bool:
    targets = panel.get("targets", [])
    if not isinstance(targets, list):
        return False
    for target in targets:
        if isinstance(target, dict) and (
            chart_id_from_target(target).startswith("daily_")
            or str(target.get("metricsContract", {}).get("chartId", "")).startswith("daily_")
        ):
            return True
    return False


def nested_values(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from nested_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_values(child)
    else:
        yield value


def chart_id_from_target(target: dict[str, Any]) -> str:
    target_url = target.get("url") or target.get("path") or ""
    params = dict(parse_qsl(urlparse(target_url).query, keep_blank_values=True))
    return params.get("chart_id", "")
