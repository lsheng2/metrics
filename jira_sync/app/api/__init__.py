from jira_sync.models import JiraSyncCursor


class ApiForJiraSync:
    def get_status(self, scope_id: int) -> JiraSyncCursor:
        return JiraSyncCursor.objects.get(scope_id=scope_id)


jira_sync_api = ApiForJiraSync()
