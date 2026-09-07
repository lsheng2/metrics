import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import DatabaseError

from bug_metrics.provider_profile_security import without_profile_secret_values


def _default_connection_settings(provider_id: str) -> dict[str, str]:
    provider_id = str(provider_id or '').strip().lower()
    if provider_id == 'jira':
        return {
            'base_url': 'settings:METRICS_JIRA_SERVER_URL',
            'auth_mode': 'settings:METRICS_JIRA_AUTH_MODE',
            'credential_ref': 'settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN',
            'credential_storage': 'settings_or_profile',
            'onboarding_status': 'deployment_configured',
        }
    if provider_id == 'hsdes':
        return {
            'base_url': 'settings:METRICS_HSDES_API_BASE_URL',
            'auth_mode': 'settings:METRICS_HSDES_AUTH_MODE',
            'credential_ref': 'settings:METRICS_HSDES_* or Windows Integrated Auth',
            'credential_storage': 'settings_or_profile',
            'onboarding_status': 'configuration_required',
        }
    if provider_id == 'github':
        return {
            'base_url': 'settings:METRICS_GITHUB_BASE_URL',
            'auth_mode': 'token',
            'credential_ref': 'settings:METRICS_GITHUB_TOKEN',
            'credential_storage': 'settings_or_profile',
            'onboarding_status': 'template_only',
        }
    return {
        'base_url': '',
        'auth_mode': '',
        'credential_ref': '',
        'credential_storage': 'settings_or_profile',
        'onboarding_status': 'configuration_required',
    }


@dataclass(frozen=True, slots=True)
class ProjectProviderProfile:
    profile_id: str
    provider_id: str
    display_name: str
    enabled: bool
    connection_settings: dict[str, Any]
    source_population: dict[str, str]
    scope_labels: dict[str, str]
    field_bindings: dict[str, dict[str, Any]]
    value_mappings: dict[str, Any]
    chart_bindings: dict[str, dict[str, Any]]
    mapping_version: int
    mapping_version_hash: str
    sync_policy: dict[str, Any]
    readiness_policy: dict[str, Any]
    lifecycle_state: str = 'enabled'
    source_kind: str = 'bundled'
    provenance: dict[str, Any] = None
    source_version_hash: str = ''

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> 'ProjectProviderProfile':
        source_population = dict(record.get('source_population', {}))
        connection_settings = {
            **_default_connection_settings(record.get('provider_id', '')),
            **dict(record.get('connection_settings', {}) or {}),
        }
        if not source_population.get('source_query_hash'):
            fingerprint = source_population.get('native_query_text') or '|'.join([
                source_population.get('source_query_ref', ''),
                source_population.get('criteria_snapshot', ''),
                source_population.get('exclusion_snapshot', ''),
            ])
            source_population['source_query_hash'] = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest() if fingerprint else ''
        mapping_hash = record.get('mapping_version_hash') or cls._mapping_hash(record, source_population, connection_settings)
        return cls(
            profile_id=record['profile_id'],
            provider_id=record['provider_id'],
            display_name=record.get('display_name', record['profile_id']),
            enabled=bool(record.get('enabled', True)),
            connection_settings=connection_settings,
            source_population=source_population,
            scope_labels=dict(record.get('scope_labels', {})),
            field_bindings=dict(record.get('field_bindings', {})),
            value_mappings=dict(record.get('value_mappings', {})),
            chart_bindings=dict(record.get('chart_bindings', {})),
            mapping_version=int(record.get('mapping_version', 1)),
            mapping_version_hash=mapping_hash,
            sync_policy=dict(record.get('sync_policy', {})),
            readiness_policy=dict(record.get('readiness_policy', {})),
            lifecycle_state=record.get('lifecycle_state', 'enabled' if bool(record.get('enabled', True)) else 'archived'),
            source_kind=record.get('source_kind', 'bundled'),
            provenance=dict(record.get('provenance', {}) or {}),
            source_version_hash=record.get('source_version_hash', source_population.get('source_query_hash', '')),
        )

    @staticmethod
    def _mapping_hash(record: dict[str, Any], source_population: dict[str, str],
                      connection_settings: dict[str, Any]) -> str:
        hash_record = {
            key: value
            for key, value in record.items()
            if key not in {'mapping_version_hash', 'enabled'}
        }
        hash_record['source_population'] = source_population
        hash_record['connection_settings'] = without_profile_secret_values(connection_settings)
        serialized = json.dumps(hash_record, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class ProviderProfileResolution:
    status: str
    profile_id: str
    provider_id: str
    profile: ProjectProviderProfile | None
    blockers: list[dict[str, str]]


@dataclass(frozen=True, slots=True)
class ChartRecipeRequirement:
    chart_id: str
    chart_version: int
    required_canonical_fields: list[str]
    provider_capability: str
    evidence_capability: str


@dataclass(frozen=True, slots=True)
class ChartSupportResolution:
    status: str
    chart_id: str
    chart_version: int
    evidence_capability: str
    required_canonical_fields: list[str]
    missing_canonical_fields: list[str]
    candidate_native_fields: list[str]
    blocker_codes: list[str]
    blockers: list[dict[str, str]]

    def to_binding(self) -> dict[str, Any]:
        return {
            'chart_id': self.chart_id,
            'support_status': self.status,
            'evidence_capability': self.evidence_capability,
            'required_canonical_fields': self.required_canonical_fields,
            'missing_canonical_fields': self.missing_canonical_fields,
            'candidate_native_fields': self.candidate_native_fields,
            'blocker_codes': self.blocker_codes,
            'blockers': self.blockers,
        }


class ProjectProviderProfileRegistry:
    def __init__(self, profiles: list[ProjectProviderProfile]):
        self._profiles = {profile.profile_id: profile for profile in profiles}

    @classmethod
    def load_default(cls) -> 'ProjectProviderProfileRegistry':
        return cls.from_directory(Path(__file__).resolve().parents[2] / 'provider_profile_configs')

    @classmethod
    def from_directory(cls, directory: Path) -> 'ProjectProviderProfileRegistry':
        records = []
        for path in sorted(directory.glob('*.json')):
            with path.open(encoding='utf-8') as profile_file:
                record = json.load(profile_file)
                record.setdefault('source_kind', 'bundled')
                record.setdefault('lifecycle_state', 'enabled' if bool(record.get('enabled', True)) else 'archived')
                records.append(record)
        records.extend(cls._managed_profile_records())
        return cls.from_records(records)

    @classmethod
    def from_records(cls, records: list[dict[str, Any]]) -> 'ProjectProviderProfileRegistry':
        return cls([ProjectProviderProfile.from_record(record) for record in records])

    def get_profile(self, profile_id: str) -> ProjectProviderProfile:
        resolution = self.resolve_profile(profile_id)
        if resolution.profile is None:
            raise KeyError(profile_id)
        return resolution.profile

    def resolve_profile(self, profile_id: str) -> ProviderProfileResolution:
        profile = self._profiles.get(profile_id)
        if profile is None:
            return ProviderProfileResolution(
                status='unsupported',
                profile_id=profile_id,
                provider_id='',
                profile=None,
                blockers=[{
                    'code': 'profile_not_found',
                    'message': f'Provider profile {profile_id} is not configured.',
                }],
            )
        if not profile.enabled:
            return ProviderProfileResolution(
                status='unavailable',
                profile_id=profile.profile_id,
                provider_id=profile.provider_id,
                profile=None,
                blockers=[{
                    'code': 'profile_disabled',
                    'message': f'Provider profile {profile_id} is disabled.',
                }],
            )
        return ProviderProfileResolution(
            status='available',
            profile_id=profile.profile_id,
            provider_id=profile.provider_id,
            profile=profile,
            blockers=[],
        )

    def list_profiles(self, include_disabled: bool = False) -> list[ProjectProviderProfile]:
        profiles = sorted(self._profiles.values(), key=lambda profile: profile.profile_id)
        if include_disabled:
            return profiles
        return [profile for profile in profiles if profile.enabled]

    @staticmethod
    def _managed_profile_records() -> list[dict[str, Any]]:
        try:
            from bug_metrics.models import ProviderProfileConfig
            return [
                {
                    **profile.to_profile_record(),
                    'source_kind': 'managed',
                    'lifecycle_state': profile.lifecycle_state,
                    'provenance': dict(profile.provenance or {}),
                    'source_version_hash': profile.source_version_hash,
                }
                for profile in ProviderProfileConfig.objects.order_by('provider_id', 'profile_id')
            ]
        except Exception as error:
            if error.__class__.__name__ in {'DatabaseOperationForbidden', 'OperationalError', 'ProgrammingError'}:
                return []
            if isinstance(error, DatabaseError):
                return []
            raise

    def resolve_chart_support(self, profile_id: str, recipe: ChartRecipeRequirement,
                              provider_capabilities: dict[str, str]) -> ChartSupportResolution:
        resolution = self.resolve_profile(profile_id)
        if resolution.profile is None:
            return ChartSupportResolution(
                status=resolution.status,
                chart_id=recipe.chart_id,
                chart_version=recipe.chart_version,
                evidence_capability=recipe.evidence_capability,
                required_canonical_fields=list(recipe.required_canonical_fields),
                missing_canonical_fields=[],
                candidate_native_fields=[],
                blocker_codes=[blocker['code'] for blocker in resolution.blockers],
                blockers=resolution.blockers,
            )
        profile = resolution.profile
        binding = profile.chart_bindings.get(recipe.chart_id)
        if binding is None:
            return self._chart_support_result(
                'unsupported',
                recipe,
                [],
                [],
                [{
                    'code': 'chart_not_bound_to_profile',
                    'message': f'Chart {recipe.chart_id} is not bound to provider profile {profile_id}.',
                }],
            )
        binding_status = binding.get('support_status', 'configuration_required')
        if binding_status == 'deferred':
            return self._chart_support_result(
                'deferred',
                recipe,
                [],
                list(binding.get('candidate_native_fields', [])),
                [{
                    'code': code,
                    'message': f'Chart {recipe.chart_id} is deferred for provider profile {profile_id}.',
                } for code in binding.get('blocker_codes', [])],
            )
        capability_status = provider_capabilities.get(recipe.provider_capability, 'unsupported')
        if capability_status not in {'supported', 'seeded_preview'}:
            return self._chart_support_result(
                'configuration_required',
                recipe,
                [],
                list(binding.get('candidate_native_fields', [])),
                [{
                    'code': 'provider_capability_not_ready',
                    'message': f'Provider capability {recipe.provider_capability} is {capability_status}.',
                }],
            )
        missing_fields = sorted(set(recipe.required_canonical_fields) - set(profile.field_bindings))
        if missing_fields:
            return self._chart_support_result(
                'configuration_required',
                recipe,
                missing_fields,
                list(binding.get('candidate_native_fields', [])),
                [{
                    'code': 'missing_canonical_field_bindings',
                    'message': f'Profile {profile_id} is missing canonical field bindings: {", ".join(missing_fields)}.',
                }],
            )
        return self._chart_support_result(
            'supported',
            recipe,
            [],
            list(binding.get('candidate_native_fields', [])),
            [],
        )

    def _chart_support_result(self, status: str, recipe: ChartRecipeRequirement, missing_fields: list[str],
                              candidate_native_fields: list[str], blockers: list[dict[str, str]]) -> ChartSupportResolution:
        return ChartSupportResolution(
            status=status,
            chart_id=recipe.chart_id,
            chart_version=recipe.chart_version,
            evidence_capability=recipe.evidence_capability,
            required_canonical_fields=list(recipe.required_canonical_fields),
            missing_canonical_fields=missing_fields,
            candidate_native_fields=candidate_native_fields,
            blocker_codes=[blocker['code'] for blocker in blockers],
            blockers=blockers,
        )
