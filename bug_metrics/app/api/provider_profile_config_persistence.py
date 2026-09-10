from typing import Any, Dict

from bug_metrics.models import BugTrendAuditEvent, BugTrendScopeProviderBinding, ProviderProfileConfig
from bug_metrics.provider_profile_security import without_profile_secret_values

from .provider_profile_config_payload import PROFILE_JSON_FIELDS, SavedProviderProfileConfig


class ProviderProfilePersistenceMixin:
    def _public_profile_payload(self, profile: SavedProviderProfileConfig) -> Dict[str, Any]:
        payload = {
            field_name: getattr(profile, field_name)
            for field_name in [
                'id',
                'profile_id',
                'provider_id',
                'display_name',
                'lifecycle_state',
                *PROFILE_JSON_FIELDS,
                'mapping_version',
                'mapping_version_hash',
                'source_version_hash',
                'source_kind',
            ]
        }
        payload.pop('id', None)
        return without_profile_secret_values(payload)

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

    def _release_scope_bindings_for_deleted_profile(self, profile: ProviderProfileConfig) -> Dict[str, Any]:
        changed = []
        bindings = BugTrendScopeProviderBinding.objects.select_related('scope').filter(profile_id=profile.profile_id)
        for binding in bindings:
            before = self._binding_snapshot(binding)
            binding.profile_id = ''
            binding.provider_id = profile.provider_id
            binding.status = BugTrendScopeProviderBinding.STATUS_CONFIGURATION_REQUIRED
            binding.provenance = {
                **dict(binding.provenance or {}),
                'source': 'provider_profile_deleted',
                'deleted_profile_id': profile.profile_id,
                'deleted_provider_id': profile.provider_id,
            }
            binding.blockers = [{
                'code': 'provider_profile_deleted',
                'message': f'Provider profile {profile.profile_id} was deleted. Select another provider profile, archive this scope, or delete the archived scope.',
            }]
            binding.save(update_fields=['profile_id', 'provider_id', 'status', 'provenance', 'blockers', 'updated_at'])
            after = self._binding_snapshot(binding)
            changed.append({
                'scope_id': binding.scope_id,
                'scope_name': binding.scope.name,
                'before': before,
                'after': after,
            })
            BugTrendAuditEvent.objects.create(
                event_type=BugTrendAuditEvent.EVENT_SCOPE_BINDING_UPDATED,
                actor='local_operator',
                scope=binding.scope,
                request_summary={
                    'operation': 'provider_profile_deleted_binding_cleanup',
                    'deleted_profile_id': profile.profile_id,
                    'before': before,
                    'after': after,
                },
            )
        return {
            'changed_count': len(changed),
            'changed': changed,
        }

    def _binding_snapshot(self, binding: BugTrendScopeProviderBinding) -> Dict[str, Any]:
        return {
            'status': binding.status,
            'profile_id': binding.profile_id,
            'provider_id': binding.provider_id,
            'provenance': dict(binding.provenance or {}),
            'blockers': list(binding.blockers or []),
        }

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

    def _profile_for_management(self, registry, profile_id: str):
        for profile in registry.list_profiles(include_disabled=True):
            if profile.profile_id == profile_id:
                return profile
        raise KeyError(profile_id)
