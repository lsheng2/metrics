from dataclasses import dataclass

from bug_metrics.app.api import ApiForBugTrend
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.models import BugTrendScopeProviderBinding
from project_management.app.api import ScopeSelection


@dataclass(frozen=True, slots=True)
class ProjectSourceChoice:
    key: str
    label: str
    provider_id: str
    selection: ScopeSelection


class ProjectSourceChoices:
    def __init__(self, scope_api=None, registry_loader=None):
        self.scope_api = scope_api or ApiForBugTrend()
        self.registry_loader = registry_loader or ProjectProviderProfileRegistry.load_default

    def list_choices(self) -> tuple[ProjectSourceChoice, ...]:
        registry = self.registry_loader()
        profiles = {profile.profile_id: profile for profile in registry.list_profiles()}
        return tuple(self._jira_choices(profiles) + self._hsdes_choices(profiles))

    def choice_map(self):
        return {choice.key: choice for choice in self.list_choices()}

    def _jira_choices(self, profiles):
        choices = []
        for scope in self.scope_api.list_enabled_scopes():
            binding = self.scope_api.resolve_scope_provider_binding(scope)
            profile = profiles.get(binding.profile_id)
            if not self._is_explicit_jira_binding(binding, profile):
                continue
            choices.append(ProjectSourceChoice(
                key=f'jira/{profile.profile_id}/{scope.id}',
                label=f'Jira - {scope.name} ({profile.display_name})',
                provider_id='jira',
                selection=ScopeSelection(profile.profile_id, scope.id),
            ))
        return choices

    def _hsdes_choices(self, profiles):
        return [
            ProjectSourceChoice(
                key=f'hsdes/{profile.profile_id}',
                label=f'HSD-ES - {profile.display_name}',
                provider_id='hsdes',
                selection=ScopeSelection(profile.profile_id),
            )
            for profile in profiles.values()
            if profile.provider_id == 'hsdes' and profile.source_population.get('source_query_ref')
        ]

    def _is_explicit_jira_binding(self, binding, profile):
        return (
            profile is not None
            and binding.status == BugTrendScopeProviderBinding.STATUS_EXPLICIT
            and binding.provider_id == 'jira'
            and profile.provider_id == 'jira'
        )
