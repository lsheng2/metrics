from atlassian import Jira


class JiraScopeIssueAdapter:
    def __init__(self, jira_client, page_size: int = 100):
        self._jira_client = jira_client
        self._page_size = page_size

    def fetch_issues(self, jql: str, field_names: list[str]) -> list[dict]:
        issues = []
        start_at = 0
        fields = sorted(set(field_names)) or '*all'
        while True:
            result = self._jira_client.jql(
                jql,
                fields=fields,
                start=start_at,
                limit=self._page_size,
                expand='changelog',
            )
            page_issues = result.get('issues', [])
            if not page_issues:
                break
            for issue in page_issues:
                self._require_complete_changelog(issue)
            issues.extend(page_issues)
            start_at += len(page_issues)
            total = result.get('total')
            if total is not None and start_at >= total:
                break
            if len(page_issues) < self._page_size:
                break
        return issues

    def _require_complete_changelog(self, issue: dict):
        changelog = issue.get('changelog')
        if not changelog:
            raise ValueError(f"Issue {issue.get('key', '<unknown>')} is missing expanded changelog")
        total = changelog.get('total')
        histories = changelog.get('histories', [])
        if total is not None and len(histories) < total:
            raise ValueError(f"Issue {issue.get('key', '<unknown>')} has partial expanded changelog")


def create_jira_client(settings):
    if settings.METRICS_JIRA_AUTH_MODE == 'server_pat':
        return Jira(
            url=settings.METRICS_JIRA_SERVER_URL,
            token=settings.METRICS_JIRA_API_TOKEN,
            verify_ssl=settings.METRICS_JIRA_CA_BUNDLE or settings.METRICS_JIRA_VERIFY_SSL,
        )
    return Jira(
        url=settings.METRICS_JIRA_SERVER_URL,
        username=settings.METRICS_JIRA_EMAIL,
        password=settings.METRICS_JIRA_API_TOKEN,
        verify_ssl=settings.METRICS_JIRA_CA_BUNDLE or settings.METRICS_JIRA_VERIFY_SSL,
        cloud=True,
    )
