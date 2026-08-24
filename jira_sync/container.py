from django.conf import settings

from jira_sync.app.api import jira_sync_api
from jira_sync.app.api.scope_metadata import ApiForScopeMetadata
from jira_sync.out.jira_scope_issue_adapter import create_jira_client
from jira_sync.out.jira_scope_metadata_adapter import JiraScopeMetadataAdapter


class JiraSyncContainer:
    @property
    def jira_sync_api(self):
        return jira_sync_api

    @property
    def scope_metadata_api(self):
        return ApiForScopeMetadata({'jira': JiraScopeMetadataAdapter(create_jira_client(settings))})


jira_sync_container = JiraSyncContainer()