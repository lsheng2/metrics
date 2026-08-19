from jira_sync.app.api import jira_sync_api


class JiraSyncContainer:
    @property
    def jira_sync_api(self):
        return jira_sync_api


jira_sync_container = JiraSyncContainer()