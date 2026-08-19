import unittest
from unittest.mock import MagicMock

from tasks.out.jira_server_task_provider import JiraServerTaskProvider


class TestJiraServerTaskProvider(unittest.TestCase):

    def test_shouldFetchServerDataCenterSearchResultsUsingStartAtPagination(self):
        # given
        jira_client = MagicMock()
        jira_client.jql.side_effect = [
            {"issues": [{"key": "STDEL-1"}, {"key": "STDEL-2"}], "total": 3},
            {"issues": [{"key": "STDEL-3"}], "total": 3},
        ]
        provider = JiraServerTaskProvider(
            jira_client,
            "project = STDEL",
            additional_fields=["subtasks"],
            page_size=2,
        )

        # when
        tasks = provider.get_tasks()

        # then
        self.assertEqual(["STDEL-1", "STDEL-2", "STDEL-3"], [task["key"] for task in tasks])
        self.assertEqual(2, jira_client.jql.call_count)
        jira_client.jql.assert_any_call(
            "project = STDEL",
            fields="*all",
            start=0,
            limit=2,
            expand="subtasks",
        )
        jira_client.jql.assert_any_call(
            "project = STDEL",
            fields="*all",
            start=2,
            limit=2,
            expand="subtasks",
        )


if __name__ == "__main__":
    unittest.main()