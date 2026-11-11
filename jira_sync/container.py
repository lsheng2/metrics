from django.conf import settings

from jira_sync.app.api import jira_sync_api
from jira_sync.app.api.scope_metadata import ApiForScopeMetadata, ScopeConfigOptions, TrackerOption
from jira_sync.out.jira_scope_issue_adapter import create_jira_client
from jira_sync.out.jira_scope_metadata_adapter import JiraScopeMetadataAdapter


class OnDemandJiraScopeMetadataProvider:
    """Opens the Jira client on the first metadata request so pages reading local data need no Jira settings."""

    def __init__(self):
        self._adapter = None

    def discover_options(self, query: str, selected_projects: list[str], selected_item_types: list[str]) -> ScopeConfigOptions:
        return self._jira_adapter().discover_options(query, selected_projects, selected_item_types)

    def discover_field_values(self, project_id: str, item_type_ids: list[str], field_id: str) -> list[TrackerOption]:
        return self._jira_adapter().discover_field_values(project_id, item_type_ids, field_id)

    def _jira_adapter(self) -> JiraScopeMetadataAdapter:
        if self._adapter is None:
            self._adapter = JiraScopeMetadataAdapter(create_jira_client(settings))
        return self._adapter


class JiraSyncContainer:
    @property
    def jira_sync_api(self):
        return jira_sync_api

    @property
    def scope_metadata_api(self):
        return ApiForScopeMetadata({'jira': OnDemandJiraScopeMetadataProvider()})


jira_sync_container = JiraSyncContainer()