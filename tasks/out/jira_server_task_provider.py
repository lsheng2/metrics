from typing import Optional

from sd_metrics_lib.sources.jira.tasks import JiraTaskProvider


class JiraServerTaskProvider(JiraTaskProvider):

    def _fetch_tasks(self, query: str, expand_str: Optional[str]):
        all_tasks = []
        start_at = 0

        while True:
            result = self.jira_client.jql(
                query,
                fields="*all",
                start=start_at,
                limit=self.page_size,
                expand=expand_str
            )
            current_tasks = result.get("issues", [])
            if not current_tasks:
                break

            all_tasks.extend(current_tasks)
            start_at += len(current_tasks)

            total = result.get("total")
            if total is not None and start_at >= total:
                break
            if len(current_tasks) < self.page_size:
                break

        return all_tasks
