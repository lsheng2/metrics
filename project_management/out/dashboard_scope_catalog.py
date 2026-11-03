import hashlib
import json

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from bug_metrics.app.api import ApiForBugTrend
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from project_management.app.domain.contracts import ProjectError, ScopeDescriptor, ScopeSelection
from project_management.app.domain.validation import bounded_text, validate_descriptor, validate_selection


class DashboardScopeCatalog:
    def __init__(self, scope_api=None, registry_loader=None):
        self.scope_api = scope_api or ApiForBugTrend()
        self.registry_loader = registry_loader or ProjectProviderProfileRegistry.load_default

    def resolve(self, selection: ScopeSelection) -> ScopeDescriptor:
        validate_selection(selection)
        resolution = self.registry_loader().resolve_profile(selection.profile_id)
        profile = resolution.profile
        if profile is None:
            raise ProjectError('SOURCE_UNAVAILABLE')
        if profile.provider_id == 'jira':
            descriptor = self._jira(selection, profile)
        elif profile.provider_id == 'hsdes':
            descriptor = self._hsdes(selection, profile)
        else:
            raise ProjectError('INVALID_SELECTION')
        validate_descriptor(descriptor, selection)
        return descriptor

    def _jira(self, selection, profile):
        if selection.scope_id is None:
            raise ProjectError('INVALID_SELECTION')
        try:
            scope = self.scope_api.get_scope(selection.scope_id)
        except ObjectDoesNotExist:
            raise ProjectError('SOURCE_UNAVAILABLE') from None
        binding = self.scope_api.resolve_scope_provider_binding(scope)
        if (binding.status != 'explicit' or binding.provider_id != 'jira'
                or binding.profile_id != selection.profile_id):
            raise ProjectError('SOURCE_UNAVAILABLE')
        query = bounded_text(scope.jql, 16384, 'SOURCE_UNAVAILABLE', allow_newlines=True)
        return ScopeDescriptor(
            provider_id='jira', profile_id=profile.profile_id, endpoint=self._endpoint(profile),
            source_ref=f'scope:{scope.id}', query_kind='jql', query=query,
            source_version=hashlib.sha256(query.encode('utf-8')).hexdigest(),
        )

    def _hsdes(self, selection, profile):
        if selection.scope_id is not None:
            raise ProjectError('INVALID_SELECTION')
        source = profile.source_population
        reference = bounded_text(source.get('source_query_ref'), 2048, 'SOURCE_UNAVAILABLE')
        version = bounded_text(source.get('source_query_hash'), 2048, 'SOURCE_UNAVAILABLE')
        fields = {
            key: source.get(key, '')
            for key in ('source_query_ref', 'criteria_snapshot', 'exclusion_snapshot',
                        'tenant_or_site', 'subject_or_issue_type')
        }
        if any(not isinstance(value, str) for value in fields.values()):
            raise ProjectError('SOURCE_UNAVAILABLE')
        query = json.dumps(fields, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        return ScopeDescriptor(
            provider_id='hsdes', profile_id=profile.profile_id, endpoint=self._endpoint(profile),
            source_ref=reference, query_kind='saved_query', query=query, source_version=version,
        )

    def _endpoint(self, profile):
        configured = profile.connection_settings.get('base_url', '')
        allowed = {
            'jira': 'METRICS_JIRA_SERVER_URL',
            'hsdes': 'METRICS_HSDES_API_BASE_URL',
        }
        if configured == f'settings:{allowed[profile.provider_id]}':
            return getattr(settings, allowed[profile.provider_id], '')
        return configured
