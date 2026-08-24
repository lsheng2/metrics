from dataclasses import dataclass, field
import hashlib
import json
from typing import Protocol

from django.conf import settings
from django.core.cache import cache


@dataclass(slots=True)
class TrackerOption:
    id: str
    name: str
    label: str = ''
    source: str = ''


@dataclass(slots=True)
class TrackerFieldOption:
    id: str
    name: str
    label: str = ''
    field_type: str = ''
    source: str = ''


@dataclass(slots=True)
class ScopeConfigOptions:
    projects: list[TrackerOption] = field(default_factory=list)
    item_types: list[TrackerOption] = field(default_factory=list)
    statuses: list[TrackerOption] = field(default_factory=list)
    resolutions: list[TrackerOption] = field(default_factory=list)
    priorities: list[TrackerOption] = field(default_factory=list)
    fields: list[TrackerFieldOption] = field(default_factory=list)
    components: list[TrackerOption] = field(default_factory=list)
    versions: list[TrackerOption] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ScopeMetadataProvider(Protocol):
    def discover_options(self, query: str, selected_projects: list[str], selected_item_types: list[str]) -> ScopeConfigOptions:
        ...

    def discover_field_values(self, project_id: str, item_type_ids: list[str], field_id: str) -> list[TrackerOption]:
        ...


class ApiForScopeMetadata:
    def __init__(self, providers: dict[str, ScopeMetadataProvider], cache_timeout_seconds: int | None = None):
        self._providers = providers
        self._cache_timeout_seconds = cache_timeout_seconds

    def discover_scope_options(
        self,
        provider: str,
        query: str = '',
        selected_projects: list[str] | None = None,
        selected_item_types: list[str] | None = None,
        refresh: bool = False,
    ) -> ScopeConfigOptions:
        selected_projects = selected_projects or []
        selected_item_types = selected_item_types or []
        cache_key = self._scope_options_cache_key(provider, query, selected_projects, selected_item_types)
        if not refresh:
            cached_options = cache.get(cache_key)
            if cached_options is not None:
                return cached_options
        options = self._provider(provider).discover_options(query, selected_projects, selected_item_types)
        cache.set(cache_key, options, self._cache_timeout())
        return options

    def discover_field_values(
        self,
        provider: str,
        project_id: str,
        item_type_ids: list[str] | None,
        field_id: str,
        refresh: bool = False,
    ) -> list[TrackerOption]:
        item_type_ids = item_type_ids or []
        cache_key = self._field_values_cache_key(provider, project_id, item_type_ids, field_id)
        if not refresh:
            cached_options = cache.get(cache_key)
            if cached_options is not None:
                return cached_options
        options = self._provider(provider).discover_field_values(project_id, item_type_ids, field_id)
        cache.set(cache_key, options, self._cache_timeout())
        return options

    def _provider(self, provider: str) -> ScopeMetadataProvider:
        if provider not in self._providers:
            raise ValueError(f'Unsupported scope metadata provider: {provider}')
        return self._providers[provider]

    def _scope_options_cache_key(self, provider: str, query: str, selected_projects: list[str], selected_item_types: list[str]) -> str:
        return self._cache_key('scope_options', {
            'provider': provider,
            'base_url': getattr(settings, 'METRICS_JIRA_SERVER_URL', '') or '',
            'auth_mode': getattr(settings, 'METRICS_JIRA_AUTH_MODE', '') or '',
            'query': query,
            'selected_projects': sorted(selected_projects),
            'selected_item_types': sorted(selected_item_types),
        })

    def _field_values_cache_key(self, provider: str, project_id: str, item_type_ids: list[str], field_id: str) -> str:
        return self._cache_key('field_values', {
            'provider': provider,
            'base_url': getattr(settings, 'METRICS_JIRA_SERVER_URL', '') or '',
            'auth_mode': getattr(settings, 'METRICS_JIRA_AUTH_MODE', '') or '',
            'project_id': project_id,
            'item_type_ids': sorted(item_type_ids),
            'field_id': field_id,
        })

    def _cache_key(self, prefix: str, payload: dict) -> str:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        return f'scope_metadata:{prefix}:{digest}'

    def _cache_timeout(self) -> int:
        if self._cache_timeout_seconds is not None:
            return self._cache_timeout_seconds
        return getattr(settings, 'METRICS_SCOPE_METADATA_CACHE_SECONDS', 300)