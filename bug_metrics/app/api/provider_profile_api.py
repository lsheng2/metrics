from bug_metrics.models import JiraScopeConfig

from .provider_profile_config import SavedProviderProfileConfig
from .scope_provider_binding import ScopeProviderBindingBulkConfirmResult, ScopeProviderBindingResolution


class BugTrendProviderProfileApiMixin:
    def resolve_scope_provider_binding(self, scope: JiraScopeConfig) -> ScopeProviderBindingResolution:
        return self._scope_provider_binding_resolver.resolve(scope)

    def backfill_scope_provider_binding(self, scope: JiraScopeConfig, explicit: bool = False,
                                        actor: str = 'local_operator') -> ScopeProviderBindingResolution:
        return self._scope_provider_binding_resolver.backfill(scope, explicit, actor)

    def list_scope_provider_bindings(self) -> list[tuple[JiraScopeConfig, ScopeProviderBindingResolution]]:
        scopes = JiraScopeConfig.objects.order_by('ip', 'project_label', 'name')
        return [(scope, self._scope_provider_binding_resolver.resolve(scope, enforce_policy=False)) for scope in scopes]

    def confirm_scope_provider_binding(self, scope_id: int, actor: str = 'local_operator') -> ScopeProviderBindingResolution:
        scope = JiraScopeConfig.objects.get(id=scope_id)
        return self.backfill_scope_provider_binding(scope, explicit=True, actor=actor)

    def set_scope_provider_binding(self, scope_id: int, profile_id: str, actor: str = 'local_operator') -> ScopeProviderBindingResolution:
        scope = JiraScopeConfig.objects.get(id=scope_id)
        return self._scope_provider_binding_resolver.set_explicit(scope, profile_id, actor)

    def bulk_confirm_scope_provider_bindings(self, actor: str = 'local_operator') -> ScopeProviderBindingBulkConfirmResult:
        scopes = JiraScopeConfig.objects.order_by('ip', 'project_label', 'name')
        return self._scope_provider_binding_resolver.bulk_confirm_compatibility(scopes, actor)

    def list_scope_provider_profile_choices(self) -> list[dict[str, str]]:
        return self._scope_provider_binding_resolver.list_profile_choices()

    def list_provider_profile_configs(self) -> list[SavedProviderProfileConfig]:
        return self._provider_profile_config_service.list_provider_profile_configs()

    def get_provider_profile_config(self, profile_id: str) -> SavedProviderProfileConfig:
        return self._provider_profile_config_service.get_provider_profile_config(profile_id)

    def new_provider_profile_config(self, provider_id: str = 'jira') -> SavedProviderProfileConfig:
        return self._provider_profile_config_service.new_provider_profile_config(provider_id)

    def save_provider_profile_config(self, config: SavedProviderProfileConfig) -> SavedProviderProfileConfig:
        return self._provider_profile_config_service.save_provider_profile_config(config)

    def test_provider_profile_connection(self, config: SavedProviderProfileConfig) -> dict:
        return self._provider_profile_connection_test_service.test_connection(config).to_dict()

    def duplicate_provider_profile_config(self, profile_id: str) -> SavedProviderProfileConfig:
        return self._provider_profile_config_service.duplicate_provider_profile_config(profile_id)

    def archive_provider_profile_config(self, profile_id: str) -> SavedProviderProfileConfig:
        return self._provider_profile_config_service.archive_provider_profile_config(profile_id)

    def restore_provider_profile_config(self, profile_id: str) -> SavedProviderProfileConfig:
        return self._provider_profile_config_service.restore_provider_profile_config(profile_id)

    def get_provider_profile_delete_impact(self, profile_id: str) -> dict:
        return self._provider_profile_config_service.get_provider_profile_delete_impact(profile_id).to_dict()

    def delete_archived_provider_profile_config(self, profile_id: str, confirmation: str) -> dict:
        return self._provider_profile_config_service.delete_archived_provider_profile_config(profile_id, confirmation).to_dict()

    def export_provider_profile_package(self, profile_id: str) -> dict:
        return self._provider_profile_config_service.export_provider_profile_package(profile_id)

    def import_provider_profile_package(self, package: dict):
        return self._provider_profile_config_service.import_provider_profile_package(package)

    def get_scope_binding_policy(self) -> str:
        return self._scope_provider_binding_resolver.runtime_policy()

    def list_scope_binding_audit_events(self, limit: int = 25) -> list[dict]:
        return self._scope_provider_binding_resolver.list_binding_audit_events(limit)

    def get_scope_provider_binding_health(self) -> dict:
        rows = []
        explicit_only_impacted_rows = []
        counts = {
            'explicit': 0,
            'compatibility': 0,
            'configuration_required': 0,
            'ambiguous': 0,
            'disabled': 0,
        }
        for scope, binding in self.list_scope_provider_bindings():
            counts[binding.status] = counts.get(binding.status, 0) + 1
            row = {
                'scope_id': scope.id,
                'scope_name': scope.name,
                'enabled': scope.enabled,
                'profile_id': binding.profile_id,
                'provider_id': binding.provider_id,
                'status': binding.status,
                'provenance': binding.provenance,
                'provenance_summary': binding.provenance.get('matched_by') or binding.provenance.get('source') or '-',
                'blockers': binding.blockers,
                'explicit_only_blocking': scope.enabled and binding.status != 'explicit',
            }
            rows.append(row)
            if row['explicit_only_blocking']:
                explicit_only_impacted_rows.append(row)
        return {
            'total': len(rows),
            'counts': counts,
            'rows': rows,
            'runtime_policy': self.get_scope_binding_policy(),
            'explicit_only_ready': len(explicit_only_impacted_rows) == 0,
            'explicit_only_blocked_count': len(explicit_only_impacted_rows),
            'explicit_only_impacted_rows': explicit_only_impacted_rows,
        }
