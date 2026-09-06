from dataclasses import dataclass
import hashlib

from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig

from .provider_profile_registry import ProjectProviderProfile, ProjectProviderProfileRegistry


@dataclass(frozen=True, slots=True)
class ScopeProviderBindingResolution:
    scope_id: str
    profile_id: str
    provider_id: str
    status: str
    provenance: dict
    blockers: list[dict[str, str]]

    @property
    def is_resolved(self) -> bool:
        return bool(self.profile_id and self.provider_id and self.status in {
            BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
        })


class ScopeProviderBindingResolver:
    def __init__(self, profile_registry: ProjectProviderProfileRegistry | None = None):
        self._profile_registry = profile_registry or ProjectProviderProfileRegistry.load_default()

    def resolve(self, scope: JiraScopeConfig) -> ScopeProviderBindingResolution:
        explicit_binding = getattr(scope, 'provider_binding', None)
        if explicit_binding:
            return self._resolution_from_binding(explicit_binding)
        compatibility = self._compatibility_resolution(scope)
        if compatibility.status == BugTrendScopeProviderBinding.STATUS_COMPATIBILITY:
            return compatibility
        return compatibility

    def backfill(self, scope: JiraScopeConfig, explicit: bool = False) -> ScopeProviderBindingResolution:
        resolution = self._compatibility_resolution(scope)
        status = BugTrendScopeProviderBinding.STATUS_EXPLICIT if explicit and resolution.is_resolved else resolution.status
        binding, _ = BugTrendScopeProviderBinding.objects.update_or_create(
            scope=scope,
            defaults={
                'profile_id': resolution.profile_id,
                'provider_id': resolution.provider_id,
                'status': status,
                'provenance': {
                    **resolution.provenance,
                    'persisted_by': 'scope_provider_binding_resolver',
                },
                'blockers': resolution.blockers,
            },
        )
        return self._resolution_from_binding(binding)

    def _resolution_from_binding(self, binding: BugTrendScopeProviderBinding) -> ScopeProviderBindingResolution:
        if binding.profile_id and binding.provider_id:
            registry_resolution = self._profile_registry.resolve_profile(binding.profile_id)
            if registry_resolution.profile and registry_resolution.profile.provider_id != binding.provider_id:
                return ScopeProviderBindingResolution(
                    scope_id=str(binding.scope_id),
                    profile_id=binding.profile_id,
                    provider_id=binding.provider_id,
                    status=BugTrendScopeProviderBinding.STATUS_CONFIGURATION_REQUIRED,
                    provenance={**binding.provenance, 'binding_id': binding.id},
                    blockers=[{
                        'code': 'provider_profile_mismatch',
                        'message': f'Binding provider {binding.provider_id} does not match provider profile {binding.profile_id}.',
                    }],
                )
        return ScopeProviderBindingResolution(
            scope_id=str(binding.scope_id),
            profile_id=binding.profile_id,
            provider_id=binding.provider_id,
            status=binding.status,
            provenance={**binding.provenance, 'binding_id': binding.id},
            blockers=list(binding.blockers or []),
        )

    def _compatibility_resolution(self, scope: JiraScopeConfig) -> ScopeProviderBindingResolution:
        matches = [profile for profile in self._profile_registry.list_profiles() if self._scope_matches_profile(scope, profile)]
        if len(matches) == 1:
            profile = matches[0]
            return ScopeProviderBindingResolution(
                scope_id=str(scope.id),
                profile_id=profile.profile_id,
                provider_id=profile.provider_id,
                status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
                provenance={'source': 'compatibility', 'matched_by': 'provider_profile_registry'},
                blockers=[],
            )
        if len(matches) > 1:
            return ScopeProviderBindingResolution(
                scope_id=str(scope.id),
                profile_id='',
                provider_id='',
                status=BugTrendScopeProviderBinding.STATUS_AMBIGUOUS,
                provenance={'source': 'compatibility'},
                blockers=[{
                    'code': 'ambiguous_scope_provider_binding',
                    'message': 'Multiple provider profiles match the selected scope.',
                }],
            )
        fallback_provider_id = self._fallback_provider_id(scope)
        if fallback_provider_id:
            return ScopeProviderBindingResolution(
                scope_id=str(scope.id),
                profile_id=str(scope.name or ''),
                provider_id=fallback_provider_id,
                status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
                provenance={'source': 'compatibility', 'matched_by': f'legacy_{fallback_provider_id}_scope'},
                blockers=[],
            )
        return ScopeProviderBindingResolution(
            scope_id=str(scope.id),
            profile_id='',
            provider_id='',
            status=BugTrendScopeProviderBinding.STATUS_CONFIGURATION_REQUIRED,
            provenance={'source': 'compatibility'},
            blockers=[{
                'code': 'scope_provider_binding_missing',
                'message': 'Scope is not bound to a provider profile.',
            }],
        )

    def _scope_matches_profile(self, scope: JiraScopeConfig, profile: ProjectProviderProfile) -> bool:
        scope_name = str(scope.name or '').strip().lower()
        source_population = profile.source_population
        candidates = [
            profile.profile_id,
            profile.display_name,
            source_population.get('profile_id', ''),
            source_population.get('source_query_name', ''),
        ]
        if scope_name in {str(candidate or '').strip().lower() for candidate in candidates if candidate}:
            return True
        if profile.provider_id == 'jira':
            return self._query_hash(scope.jql) == self._query_hash(source_population.get('native_query_text', ''))
        if profile.provider_id == 'hsdes':
            return self._hsdes_scope_matches_profile(scope, source_population)
        return False

    def _fallback_provider_id(self, scope: JiraScopeConfig) -> str:
        normalized_scope_name = str(scope.name or '').lower()
        if 'hsdes' in normalized_scope_name:
            return 'hsdes'
        if 'jira' in normalized_scope_name or scope.jql:
            return 'jira'
        return ''

    def _query_hash(self, query: str) -> str:
        normalized_query = ' '.join(str(query or '').replace("'", '"').split()).lower()
        return hashlib.sha256(normalized_query.encode('utf-8')).hexdigest() if normalized_query else ''

    def _hsdes_scope_matches_profile(self, scope: JiraScopeConfig, source_population: dict[str, str]) -> bool:
        source_query_ref = str(source_population.get('source_query_ref', '') or '').strip()
        if source_query_ref and source_query_ref in str(scope.jql or ''):
            return True
        profile_ip = str(source_population.get('tenant_or_site', '') or '').split('.')[0].strip().lower()
        scope_ip = str(scope.ip or '').strip().lower()
        return bool(profile_ip and scope_ip and profile_ip == scope_ip and source_population.get('source_query_name'))
