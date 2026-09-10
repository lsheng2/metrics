from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from bug_metrics.models import BugTrendAuditEvent, BugTrendScopeProviderBinding, ProviderProfileConfig
from provider_sync.models import ProviderAggregateArtifact, ProviderFact, ProviderFactSnapshot, ProviderSyncCursor

from .provider_profile_config_payload import (
    PROFILE_JSON_FIELDS,
    SavedProviderProfileConfig,
    blank_connection_settings_for_provider,
    default_connection_settings_for_provider,
    provider_profile_config_from_dict,
    provider_profile_config_from_post,
)
from .provider_profile_config_persistence import ProviderProfilePersistenceMixin


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


class ProviderProfileConfigService(ProviderProfilePersistenceMixin):
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
        binding_cleanup = self._release_scope_bindings_for_deleted_profile(profile)
        self._record_profile_audit(
            BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_DELETED,
            profile,
            self._snapshot(profile),
            {'deleted': True, 'impact': impact.to_dict(), 'confirmation': confirmation, 'binding_cleanup': binding_cleanup},
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
