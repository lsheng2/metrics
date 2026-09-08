from dataclasses import asdict, dataclass, field
import json
from typing import Any, Dict, List

from bug_metrics.models import BugTrendAuditEvent, BugTrendScopeProviderBinding, ProviderProfileConfig
from bug_metrics.provider_profile_security import is_profile_secret_key, without_profile_secret_values
from provider_sync.models import ProviderAggregateArtifact, ProviderFact, ProviderFactSnapshot, ProviderSyncCursor


PROFILE_JSON_FIELDS = (
    'connection_settings',
    'source_population',
    'scope_labels',
    'field_bindings',
    'value_mappings',
    'chart_bindings',
    'sync_policy',
    'readiness_policy',
)


@dataclass(slots=True)
class SavedProviderProfileConfig:
    id: int | None
    profile_id: str
    provider_id: str
    display_name: str
    lifecycle_state: str
    connection_settings: Dict[str, Any] = field(default_factory=dict)
    source_population: Dict[str, Any] = field(default_factory=dict)
    scope_labels: Dict[str, Any] = field(default_factory=dict)
    field_bindings: Dict[str, Any] = field(default_factory=dict)
    value_mappings: Dict[str, Any] = field(default_factory=dict)
    chart_bindings: Dict[str, Any] = field(default_factory=dict)
    sync_policy: Dict[str, Any] = field(default_factory=dict)
    readiness_policy: Dict[str, Any] = field(default_factory=dict)
    mapping_version: int = 1
    mapping_version_hash: str = ''
    source_version_hash: str = ''
    source_kind: str = 'managed'


@dataclass(slots=True)
class ProviderProfileDeleteImpact:
    profile_id: str
    provider_id: str
    lifecycle_state: str
    scope_bindings: int
    fact_snapshots: int
    facts: int
    aggregate_artifacts: int
    sync_cursors: int
    audit_events: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProviderProfileConfigService:
    EXPORT_FORMAT = 'metrics.provider-profile'
    EXPORT_VERSION = 1

    def list_provider_profile_configs(self) -> List[SavedProviderProfileConfig]:
        from .provider_profile_registry import ProjectProviderProfileRegistry
        return [
            self._from_profile(profile)
            for profile in ProjectProviderProfileRegistry.load_default().list_profiles(include_disabled=True)
        ]

    def get_provider_profile_config(self, profile_id: str) -> SavedProviderProfileConfig:
        from .provider_profile_registry import ProjectProviderProfileRegistry
        managed_profile = ProviderProfileConfig.objects.filter(profile_id=profile_id).first()
        if managed_profile:
            return self._to_saved_profile_config(managed_profile)
        profile = self._profile_for_management(ProjectProviderProfileRegistry.load_default(), profile_id)
        return self._from_profile(profile)

    def new_provider_profile_config(self, provider_id: str = 'jira') -> SavedProviderProfileConfig:
        provider_id = provider_id or 'jira'
        return SavedProviderProfileConfig(
            id=None,
            profile_id='',
            provider_id=provider_id,
            display_name='',
            lifecycle_state=ProviderProfileConfig.LIFECYCLE_DRAFT,
            connection_settings=blank_connection_settings_for_provider(provider_id),
            source_population={'provider_id': provider_id, 'ownership_type': self._default_ownership_type(provider_id)},
            scope_labels={},
            field_bindings={},
            value_mappings={},
            chart_bindings={},
            sync_policy={'live_sync': 'configuration_required'},
            readiness_policy={'ready_status': 'configuration_required'},
        )

    def save_provider_profile_config(self, config: SavedProviderProfileConfig) -> SavedProviderProfileConfig:
        errors = self.validate_provider_profile_config(config)
        if errors:
            raise ValueError(errors)
        profile = ProviderProfileConfig.objects.get(id=config.id) if config.id else ProviderProfileConfig()
        before = self._snapshot(profile) if profile.id else {}
        self._merge_existing_credentials(profile, config)
        self._apply_config(profile, config)
        profile.save()
        self._record_profile_audit(
            BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_UPDATED if before else BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_CREATED,
            profile,
            before,
            self._snapshot(profile),
        )
        return self._to_saved_profile_config(profile)

    def duplicate_provider_profile_config(self, profile_id: str) -> SavedProviderProfileConfig:
        source = self.get_provider_profile_config(profile_id)
        duplicate = SavedProviderProfileConfig(
            id=None,
            profile_id=self._duplicate_profile_id(source.profile_id),
            provider_id=source.provider_id,
            display_name=f'{source.display_name} copy',
            lifecycle_state=ProviderProfileConfig.LIFECYCLE_DRAFT,
            connection_settings=dict(source.connection_settings),
            source_population=dict(source.source_population),
            scope_labels=dict(source.scope_labels),
            field_bindings=dict(source.field_bindings),
            value_mappings=dict(source.value_mappings),
            chart_bindings=dict(source.chart_bindings),
            sync_policy=dict(source.sync_policy),
            readiness_policy=dict(source.readiness_policy),
            mapping_version=source.mapping_version,
        )
        saved = self.save_provider_profile_config(duplicate)
        profile = ProviderProfileConfig.objects.get(profile_id=saved.profile_id)
        self._record_profile_audit(
            BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_DUPLICATED,
            profile,
            {'source_profile_id': profile_id},
            self._snapshot(profile),
        )
        return saved

    def archive_provider_profile_config(self, profile_id: str) -> SavedProviderProfileConfig:
        config = self._managed_config_for(profile_id)
        before = self._snapshot(config)
        config.lifecycle_state = ProviderProfileConfig.LIFECYCLE_ARCHIVED
        config.save(update_fields=['lifecycle_state', 'mapping_version_hash', 'source_version_hash', 'updated_at'])
        self._record_profile_audit(BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_ARCHIVED, config, before, self._snapshot(config))
        return self._to_saved_profile_config(config)

    def restore_provider_profile_config(self, profile_id: str) -> SavedProviderProfileConfig:
        config = self._managed_config_for(profile_id)
        before = self._snapshot(config)
        config.lifecycle_state = ProviderProfileConfig.LIFECYCLE_ENABLED
        config.save(update_fields=['lifecycle_state', 'mapping_version_hash', 'source_version_hash', 'updated_at'])
        self._record_profile_audit(BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_RESTORED, config, before, self._snapshot(config))
        return self._to_saved_profile_config(config)

    def get_provider_profile_delete_impact(self, profile_id: str) -> ProviderProfileDeleteImpact:
        profile = self.get_provider_profile_config(profile_id)
        return ProviderProfileDeleteImpact(
            profile_id=profile.profile_id,
            provider_id=profile.provider_id,
            lifecycle_state=profile.lifecycle_state,
            scope_bindings=BugTrendScopeProviderBinding.objects.filter(profile_id=profile.profile_id).count(),
            fact_snapshots=ProviderFactSnapshot.objects.filter(provider_id=profile.provider_id, profile_id=profile.profile_id).count(),
            facts=ProviderFact.objects.filter(provider_id=profile.provider_id, profile_id=profile.profile_id).count(),
            aggregate_artifacts=ProviderAggregateArtifact.objects.filter(provider_id=profile.provider_id, profile_id=profile.profile_id).count(),
            sync_cursors=ProviderSyncCursor.objects.filter(provider_id=profile.provider_id, profile_id=profile.profile_id).count(),
            audit_events=BugTrendAuditEvent.objects.filter(request_summary__profile_id=profile.profile_id).count(),
        )

    def delete_archived_provider_profile_config(self, profile_id: str, confirmation: str) -> ProviderProfileDeleteImpact:
        profile = ProviderProfileConfig.objects.get(profile_id=profile_id)
        expected_confirmation = self.delete_confirmation_token(profile.profile_id)
        if profile.lifecycle_state != ProviderProfileConfig.LIFECYCLE_ARCHIVED:
            raise ValueError({'profile_delete': 'Only archived provider profiles can be deleted.'})
        if confirmation != expected_confirmation:
            raise ValueError({'profile_delete': f'Type {expected_confirmation} to delete this archived provider profile.'})
        impact = self.get_provider_profile_delete_impact(profile.profile_id)
        self._record_profile_audit(
            BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_DELETED,
            profile,
            self._snapshot(profile),
            {'deleted': True, 'impact': impact.to_dict(), 'confirmation': confirmation},
        )
        profile.delete()
        return impact

    def export_provider_profile_package(self, profile_id: str) -> Dict[str, Any]:
        profile = self.get_provider_profile_config(profile_id)
        managed_profile = ProviderProfileConfig.objects.filter(profile_id=profile.profile_id).first()
        if managed_profile:
            self._record_profile_audit(
                BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_EXPORTED,
                managed_profile,
                self._snapshot(managed_profile),
                {'included_runtime_data': False},
            )
        else:
            BugTrendAuditEvent.objects.create(
                event_type=BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_EXPORTED,
                actor='local_operator',
                request_summary={
                    'profile_id': profile.profile_id,
                    'provider_id': profile.provider_id,
                    'before': self._snapshot_from_saved(profile),
                    'after': {'included_runtime_data': False},
                },
            )
        return {
            'format': self.EXPORT_FORMAT,
            'version': self.EXPORT_VERSION,
            'profile': self._public_profile_payload(profile),
            'excludes': [
                'credentials',
                'tokens',
                'provider_facts',
                'fact_snapshots',
                'aggregate_artifacts',
                'sync_cursors',
                'calculation_runs',
                'ai_workspace_artifacts',
                'secrets',
            ],
        }

    def import_provider_profile_package(self, package: Dict[str, Any]) -> SavedProviderProfileConfig:
        if package.get('format') != self.EXPORT_FORMAT or not isinstance(package.get('profile'), dict):
            raise ValueError({'profile_import': 'Provider profile import package is not recognized.'})
        payload = dict(package['profile'])
        payload['id'] = None
        payload['profile_id'] = self._imported_profile_id(str(payload.get('profile_id', '') or 'imported-profile'))
        payload['lifecycle_state'] = ProviderProfileConfig.LIFECYCLE_DRAFT
        saved = self.save_provider_profile_config(provider_profile_config_from_dict(payload))
        profile = ProviderProfileConfig.objects.get(profile_id=saved.profile_id)
        self._record_profile_audit(
            BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_IMPORTED,
            profile,
            {'source_profile_id': package['profile'].get('profile_id', '')},
            self._snapshot(profile),
        )
        return saved

    def validate_provider_profile_config(self, config: SavedProviderProfileConfig) -> Dict[str, str]:
        errors = {}
        if not config.profile_id.strip():
            errors['profile_id'] = 'Profile id is required.'
        if not config.provider_id.strip():
            errors['provider_id'] = 'Provider is required.'
        if not config.display_name.strip():
            errors['display_name'] = 'Display name is required.'
        if config.lifecycle_state not in {
            ProviderProfileConfig.LIFECYCLE_DRAFT,
            ProviderProfileConfig.LIFECYCLE_ENABLED,
            ProviderProfileConfig.LIFECYCLE_ARCHIVED,
        }:
            errors['lifecycle_state'] = 'Lifecycle state must be draft, enabled or archived.'
        for field_name in PROFILE_JSON_FIELDS:
            if not isinstance(getattr(config, field_name), dict):
                errors[field_name] = 'Value must be a JSON object.'
        if config.id is None and ProviderProfileConfig.objects.filter(profile_id=config.profile_id).exists():
            errors['profile_id'] = 'Profile id must be unique.'
        if config.id is not None and ProviderProfileConfig.objects.filter(profile_id=config.profile_id).exclude(id=config.id).exists():
            errors['profile_id'] = 'Profile id must be unique.'
        if config.lifecycle_state == ProviderProfileConfig.LIFECYCLE_ENABLED:
            self._validate_enablement_fields(config, errors)
            self._validate_chart_mapping_requirements(config, errors)
        return errors

    def delete_confirmation_token(self, profile_id: str) -> str:
        return f'DELETE {profile_id}'

    def _public_profile_payload(self, profile: SavedProviderProfileConfig) -> Dict[str, Any]:
        payload = asdict(profile)
        payload.pop('id', None)
        return self._without_secret_values(payload)

    def _without_secret_values(self, value):
        return without_profile_secret_values(value)

    def _secret_key(self, key: str) -> bool:
        return is_profile_secret_key(key)

    def _merge_existing_credentials(self, profile: ProviderProfileConfig, config: SavedProviderProfileConfig) -> None:
        connection_settings = dict(config.connection_settings or {})
        clear_credentials = bool(connection_settings.pop('_clear_credentials', False))
        if clear_credentials:
            connection_settings.pop('credentials', None)
            config.connection_settings = connection_settings
            return
        if profile.id and 'credentials' in connection_settings:
            existing_credentials = dict((profile.connection_settings or {}).get('credentials') or {})
            connection_settings['credentials'] = {
                **existing_credentials,
                **dict(connection_settings.get('credentials') or {}),
            }
            config.connection_settings = connection_settings
            return
        if not profile.id:
            config.connection_settings = connection_settings
            return
        existing_credentials = dict(profile.connection_settings or {}).get('credentials')
        if existing_credentials:
            connection_settings['credentials'] = dict(existing_credentials)
        config.connection_settings = connection_settings

    def _managed_config_for(self, profile_id: str) -> ProviderProfileConfig:
        managed = ProviderProfileConfig.objects.filter(profile_id=profile_id).first()
        if managed:
            return managed
        profile = self.get_provider_profile_config(profile_id)
        managed = ProviderProfileConfig()
        self._apply_config(managed, profile)
        managed.provenance = {'source': 'bundled_profile_override'}
        managed.save()
        return managed

    def _validate_enablement_fields(self, config: SavedProviderProfileConfig, errors: Dict[str, str]) -> None:
        connection_settings = dict(config.connection_settings or {})
        if not connection_settings:
            errors['connection_settings'] = 'Provider connection settings are required before enabling.'
            return
        if not str(connection_settings.get('base_url', '') or '').strip():
            errors['connection_settings'] = 'Base URL is required before enabling.'
        if not str(connection_settings.get('auth_mode', '') or '').strip():
            errors['connection_settings'] = 'Auth mode is required before enabling.'

    def _validate_chart_mapping_requirements(self, config: SavedProviderProfileConfig, errors: Dict[str, str]) -> None:
        missing_by_chart = {}
        for chart_id, chart_binding in config.chart_bindings.items():
            if not isinstance(chart_binding, dict):
                continue
            if chart_binding.get('support_status') not in {'supported', 'supported_from_seed_facts'}:
                continue
            missing = [
                field_name
                for field_name in chart_binding.get('required_canonical_fields', [])
                if not self._has_native_field_binding(config.field_bindings, field_name)
            ]
            if missing:
                missing_by_chart[chart_id] = missing
        if missing_by_chart:
            errors['chart_bindings'] = f'Missing canonical field bindings for enabled charts: {missing_by_chart}.'

    def _has_native_field_binding(self, field_bindings: Dict[str, Any], field_name: str) -> bool:
        binding = field_bindings.get(field_name)
        if not isinstance(binding, dict):
            return False
        return bool(str(binding.get('native_field', '') or '').strip())

    def _apply_config(self, profile: ProviderProfileConfig, config: SavedProviderProfileConfig) -> None:
        profile.profile_id = config.profile_id.strip()
        profile.provider_id = config.provider_id.strip()
        profile.display_name = config.display_name.strip()
        profile.lifecycle_state = config.lifecycle_state
        for field_name in PROFILE_JSON_FIELDS:
            setattr(profile, field_name, dict(getattr(config, field_name) or {}))
        profile.mapping_version = int(config.mapping_version or 1)
        profile.provenance = {
            **dict(getattr(profile, 'provenance', {}) or {}),
            'source': 'provider_setup',
        }

    def _from_profile(self, profile) -> SavedProviderProfileConfig:
        return SavedProviderProfileConfig(
            id=None,
            profile_id=profile.profile_id,
            provider_id=profile.provider_id,
            display_name=profile.display_name,
            lifecycle_state=profile.lifecycle_state,
            connection_settings=dict(profile.connection_settings or {}),
            source_population=dict(profile.source_population or {}),
            scope_labels=dict(profile.scope_labels or {}),
            field_bindings=dict(profile.field_bindings or {}),
            value_mappings=dict(profile.value_mappings or {}),
            chart_bindings=dict(profile.chart_bindings or {}),
            sync_policy=dict(profile.sync_policy or {}),
            readiness_policy=dict(profile.readiness_policy or {}),
            mapping_version=profile.mapping_version,
            mapping_version_hash=profile.mapping_version_hash,
            source_version_hash=profile.source_version_hash,
            source_kind=profile.source_kind,
        )

    def _to_saved_profile_config(self, profile: ProviderProfileConfig) -> SavedProviderProfileConfig:
        return SavedProviderProfileConfig(
            id=profile.id,
            profile_id=profile.profile_id,
            provider_id=profile.provider_id,
            display_name=profile.display_name,
            lifecycle_state=profile.lifecycle_state,
            connection_settings=dict(profile.connection_settings or {}),
            source_population=dict(profile.source_population or {}),
            scope_labels=dict(profile.scope_labels or {}),
            field_bindings=dict(profile.field_bindings or {}),
            value_mappings=dict(profile.value_mappings or {}),
            chart_bindings=dict(profile.chart_bindings or {}),
            sync_policy=dict(profile.sync_policy or {}),
            readiness_policy=dict(profile.readiness_policy or {}),
            mapping_version=profile.mapping_version,
            mapping_version_hash=profile.mapping_version_hash,
            source_version_hash=profile.source_version_hash,
            source_kind='managed',
        )

    def _snapshot(self, profile: ProviderProfileConfig) -> Dict[str, Any]:
        if not profile.id:
            return {}
        return {
            'profile_id': profile.profile_id,
            'provider_id': profile.provider_id,
            'lifecycle_state': profile.lifecycle_state,
            'mapping_version_hash': profile.mapping_version_hash,
            'source_version_hash': profile.source_version_hash,
        }

    def _snapshot_from_saved(self, profile: SavedProviderProfileConfig) -> Dict[str, Any]:
        return {
            'profile_id': profile.profile_id,
            'provider_id': profile.provider_id,
            'lifecycle_state': profile.lifecycle_state,
            'mapping_version_hash': profile.mapping_version_hash,
            'source_version_hash': profile.source_version_hash,
        }

    def _record_profile_audit(self, event_type: str, profile: ProviderProfileConfig, before: Dict[str, Any],
                              after: Dict[str, Any]) -> None:
        BugTrendAuditEvent.objects.create(
            event_type=event_type,
            actor='local_operator',
            request_summary={
                'profile_id': profile.profile_id,
                'provider_id': profile.provider_id,
                'before': before,
                'after': after,
            },
        )

    def _duplicate_profile_id(self, profile_id: str) -> str:
        candidate = f'{profile_id}-copy'
        if not ProviderProfileConfig.objects.filter(profile_id=candidate).exists():
            return candidate
        suffix = 2
        while ProviderProfileConfig.objects.filter(profile_id=f'{candidate}-{suffix}').exists():
            suffix += 1
        return f'{candidate}-{suffix}'

    def _imported_profile_id(self, profile_id: str) -> str:
        candidate = f'{profile_id}-imported'
        if not ProviderProfileConfig.objects.filter(profile_id=candidate).exists():
            return candidate
        suffix = 2
        while ProviderProfileConfig.objects.filter(profile_id=f'{candidate}-{suffix}').exists():
            suffix += 1
        return f'{candidate}-{suffix}'

    def _default_ownership_type(self, provider_id: str) -> str:
        if provider_id == 'hsdes':
            return 'provider_owned_saved_query'
        return 'metrics_managed_native_query'

    def _default_profile_id(self, provider_id: str) -> str:
        provider_id = str(provider_id or '').strip().lower() or 'provider'
        return f'{provider_id}-default'

    def _default_display_name(self, provider_id: str) -> str:
        provider_id = str(provider_id or '').strip().lower()
        labels = {
            'jira': 'Jira Default',
            'hsdes': 'HSD-ES Default',
            'github': 'GitHub Default',
        }
        return labels.get(provider_id, f'{provider_id.upper()} Default' if provider_id else 'Provider Default')

    def _profile_for_management(self, registry, profile_id: str):
        for profile in registry.list_profiles(include_disabled=True):
            if profile.profile_id == profile_id:
                return profile
        raise KeyError(profile_id)


def default_connection_settings_for_provider(provider_id: str) -> Dict[str, Any]:
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


def blank_connection_settings_for_provider(provider_id: str) -> Dict[str, Any]:
    provider_id = str(provider_id or '').strip().lower()
    return {
        'base_url': '',
        'auth_mode': '',
        'credential_ref': '',
        'credential_storage': 'settings_or_profile',
        'onboarding_status': 'template_only' if provider_id == 'github' else 'configuration_required',
    }


def provider_profile_config_from_dict(payload: Dict[str, Any]) -> SavedProviderProfileConfig:
    provider_id = str(payload.get('provider_id', '') or '').strip()
    connection_settings = {
        **default_connection_settings_for_provider(provider_id),
        **_dict_value(payload.get('connection_settings')),
    }
    return SavedProviderProfileConfig(
        id=int(payload['id']) if str(payload.get('id', '') or '').isdecimal() else None,
        profile_id=str(payload.get('profile_id', '') or '').strip(),
        provider_id=provider_id,
        display_name=str(payload.get('display_name', '') or '').strip(),
        lifecycle_state=str(payload.get('lifecycle_state', '') or ProviderProfileConfig.LIFECYCLE_DRAFT).strip(),
        connection_settings=connection_settings,
        source_population=_dict_value(payload.get('source_population')),
        scope_labels=_dict_value(payload.get('scope_labels')),
        field_bindings=_dict_value(payload.get('field_bindings')),
        value_mappings=_dict_value(payload.get('value_mappings')),
        chart_bindings=_dict_value(payload.get('chart_bindings')),
        sync_policy=_dict_value(payload.get('sync_policy')),
        readiness_policy=_dict_value(payload.get('readiness_policy')),
        mapping_version=int(payload.get('mapping_version') or 1),
        mapping_version_hash=str(payload.get('mapping_version_hash', '') or ''),
        source_version_hash=str(payload.get('source_version_hash', '') or ''),
        source_kind=str(payload.get('source_kind', 'managed') or 'managed'),
    )


def provider_profile_config_from_post(post_data) -> SavedProviderProfileConfig:
    payload = {
        'id': post_data.get('id', ''),
        'profile_id': post_data.get('profile_id', ''),
        'provider_id': post_data.get('provider_id', ''),
        'display_name': post_data.get('display_name', ''),
        'lifecycle_state': post_data.get('lifecycle_state', ProviderProfileConfig.LIFECYCLE_DRAFT),
        'mapping_version': post_data.get('mapping_version', '1'),
    }
    for field_name in PROFILE_JSON_FIELDS:
        payload[field_name] = post_data.get(field_name, '{}')
    source_population = _dict_value(payload.get('source_population'))
    if str(payload['provider_id'] or '').strip().lower() == 'hsdes':
        for post_name, source_name in {
            'hsdes_saved_query_id': 'source_query_ref',
            'hsdes_tenant': 'tenant_or_site',
            'hsdes_subject': 'subject_or_issue_type',
        }.items():
            if post_name in post_data:
                source_population[source_name] = str(post_data.get(post_name, '') or '').strip()
        source_population['provider_id'] = 'hsdes'
        if not source_population.get('ownership_type'):
            source_population['ownership_type'] = 'provider_owned_saved_query'
        payload['source_population'] = source_population
    connection_settings = _dict_value(payload.get('connection_settings'))
    connection_settings.pop('onboarding_status', None)
    for post_name, setting_name in {
        'connection_base_url': 'base_url',
        'connection_auth_mode': 'auth_mode',
        'credential_ref': 'credential_ref',
    }.items():
        if post_name in post_data:
            connection_settings[setting_name] = str(post_data.get(post_name, '') or '').strip()
    credentials = dict(connection_settings.get('credentials') or {})
    active_credential_keys = _active_auth_credential_keys(payload['provider_id'], connection_settings.get('auth_mode'))
    if post_data.get('clear_connection_credentials') == 'on':
        credentials = {}
        connection_settings['_clear_credentials'] = True
    else:
        for post_name, credential_name in {
            'connection_username': 'username',
            'connection_email': 'email',
            'connection_api_token': 'api_token',
            'connection_password': 'password',
            'connection_token': 'token',
        }.items():
            raw_value = str(post_data.get(post_name, '') or '').strip()
            if credential_name in {'api_token', 'token'} and _masked_secret_value(raw_value):
                continue
            if post_name in post_data and raw_value and credential_name in active_credential_keys:
                credentials[credential_name] = raw_value
        if credentials:
            connection_settings['credentials'] = credentials
            connection_settings['credential_storage'] = 'profile_local'
    payload['connection_settings'] = connection_settings
    return provider_profile_config_from_dict(payload)


def _dict_value(value) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value in {None, ''}:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


def _masked_secret_value(value: str) -> bool:
    stripped = str(value or '').strip()
    return bool(stripped) and set(stripped) <= {'*'} and len(stripped) >= 6


def _active_auth_credential_keys(provider_id: str, auth_mode: str) -> set[str]:
    provider_id = str(provider_id or '').strip().lower()
    auth_mode = str(auth_mode or '').strip().lower()
    if provider_id == 'jira':
        if not auth_mode:
            return set()
        if auth_mode == 'cloud_basic':
            return {'email', 'api_token'}
        return {'api_token'}
    if provider_id == 'hsdes':
        if auth_mode == 'basic':
            return {'username', 'password'}
        if auth_mode == 'token':
            return {'token'}
        return set()
    if provider_id == 'github':
        return {'token'}
    return {'username', 'email', 'api_token', 'password', 'token'}
