from .provider_aggregate_contracts import (
    ProviderChartAggregateQuery,
    ProviderChartAggregateResult,
    ProviderChartEvidenceQuery,
)


class BugTrendProviderChartApiMixin:
    def get_provider_chart_aggregates(self, query: ProviderChartAggregateQuery) -> ProviderChartAggregateResult:
        return self._provider_chart_aggregate_service.get_aggregates(query)

    def build_hsdes_quality_aggregate_artifact(self, query: ProviderChartAggregateQuery, facts: list[dict]) -> ProviderChartAggregateResult:
        return self._provider_chart_aggregate_service.build_hsdes_quality_aggregate_artifact(query, facts)

    def get_provider_profile_readiness(self, provider_id: str, profile_id: str) -> dict:
        return self._provider_profile_readiness_service.get_readiness(provider_id, profile_id)

    def validate_provider_profile_drift(self, provider_id: str, profile_id: str, observed_profile: dict) -> dict:
        return self._provider_profile_readiness_service.validate_drift(provider_id, profile_id, observed_profile)

    def get_provider_capability_manifest(self, provider_id: str, profile_id: str) -> dict:
        return self._provider_profile_readiness_service.get_capability_manifest(provider_id, profile_id)

    def normalize_hsdes_search_page(self, profile_id: str, payload: dict) -> dict:
        return self._hsdes_projection_service.normalize_search_page(profile_id, payload)

    def normalize_hsdes_article_detail(self, profile_id: str, payload: dict) -> dict:
        return self._hsdes_projection_service.normalize_article_detail(profile_id, payload)

    def generate_provider_correlation_candidates(self, source_facts: list[dict], target_facts: list[dict]) -> list[dict]:
        return self._provider_correlation_service.generate_candidates(source_facts, target_facts)

    def review_provider_correlation(self, candidate: dict, state: str, reviewer: str) -> dict:
        return self._provider_correlation_service.review_correlation(candidate, state, reviewer)

    def get_provider_correlation_evidence_view(self, correlations: list[dict]) -> dict:
        return self._provider_correlation_service.evidence_view(correlations)

    def explain_cross_provider_correlation_risk(self, correlations: list[dict]) -> dict:
        return self._provider_correlation_service.explain_risk(correlations)

    def get_provider_chart_evidence(self, query: ProviderChartEvidenceQuery) -> dict:
        return self._provider_chart_evidence_service.get_provider_chart_evidence(query)
