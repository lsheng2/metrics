from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry


def resolve_scope_provider_binding(bug_trend_api, scope):
    if hasattr(bug_trend_api, 'resolve_scope_provider_binding'):
        return bug_trend_api.resolve_scope_provider_binding(scope)
    profile_id, provider_id = resolve_scope_profile_binding(scope)
    return LegacyScopeProviderBindingResolution(str(scope.id), profile_id, provider_id)


class LegacyScopeProviderBindingResolution:
    def __init__(self, scope_id, profile_id, provider_id, blockers=None):
        self.scope_id = scope_id
        self.profile_id = profile_id
        self.provider_id = provider_id
        self.status = 'compatibility' if profile_id and provider_id else 'configuration_required'
        self.blockers = blockers if blockers is not None else [{
            'code': 'scope_provider_binding_missing',
            'message': 'Scope is not bound to a provider profile.',
        }]


def resolve_scope_profile_binding(scope) -> tuple[str, str]:
    scope_name = str(scope.name or '').strip()
    if not scope_name:
        return '', ''
    registry = ProjectProviderProfileRegistry.load_default()
    resolution = registry.resolve_profile(scope_name)
    if resolution.profile is not None:
        return resolution.profile.profile_id, resolution.profile.provider_id
    for profile in registry.list_profiles():
        if _scope_matches_profile(scope, profile):
            return profile.profile_id, profile.provider_id
    provider_id = fallback_provider_id_for_profile(scope_name)
    if provider_id:
        return '', provider_id
    if getattr(scope, 'jql', ''):
        return '', 'jira'
    return '', ''


def fallback_provider_id_for_profile(profile_id: str) -> str:
    normalized_profile = profile_id.lower()
    if 'hsdes' in normalized_profile:
        return 'hsdes'
    if 'jira' in normalized_profile:
        return 'jira'
    return ''


def _scope_matches_profile(scope, profile) -> bool:
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
        return _normalized_query(getattr(scope, 'jql', '')) == _normalized_query(source_population.get('native_query_text', ''))
    if profile.provider_id == 'hsdes':
        return _hsdes_scope_matches_profile(scope, source_population)
    return False


def _normalized_query(value: str) -> str:
    return ' '.join(str(value or '').replace("'", '"').split()).lower()


def _hsdes_scope_matches_profile(scope, source_population: dict[str, str]) -> bool:
    source_query_ref = str(source_population.get('source_query_ref', '') or '').strip()
    if source_query_ref and source_query_ref in str(getattr(scope, 'jql', '') or ''):
        return True
    profile_ip = str(source_population.get('tenant_or_site', '') or '').split('.')[0].strip().lower()
    scope_ip = str(getattr(scope, 'ip', '') or '').strip().lower()
    return bool(profile_ip and scope_ip and profile_ip == scope_ip and source_population.get('source_query_name'))
