from jira_history.app.api import jira_history_api


class JiraHistoryContainer:
    @property
    def jira_history_api(self):
        return jira_history_api


jira_history_container = JiraHistoryContainer()
