from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry


def resolve_scope_profile_binding(scope) -> tuple[str, str]:
    scope_name = str(scope.name or '').strip()
    if not scope_name:
        return '', ''
    registry = ProjectProviderProfileRegistry.load_default()
    resolution = registry.resolve_profile(scope_name)
    if resolution.profile is not None:
        return resolution.profile.profile_id, resolution.profile.provider_id
    provider_id = fallback_provider_id_for_profile(scope_name)
    if provider_id:
        return scope_name, provider_id
    return '', ''


def fallback_provider_id_for_profile(profile_id: str) -> str:
    normalized_profile = profile_id.lower()
    if 'hsdes' in normalized_profile:
        return 'hsdes'
    if 'jira' in normalized_profile:
        return 'jira'
    return ''
