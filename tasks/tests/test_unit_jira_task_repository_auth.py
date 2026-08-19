import asyncio
import unittest
from unittest.mock import patch

from tasks.app.domain.model.config import (
    AzureConfig,
    EstimationConfig,
    JiraConfig,
    MemberGroupConfig,
    ProjectConfig,
    SortingConfig,
    TaskFilterConfig,
    TasksConfig,
    WorkflowConfig,
)
from tasks.out.jira_task_repository import JiraTaskRepository


def _build_tasks_config(jira_config: JiraConfig) -> TasksConfig:
    return TasksConfig(
        jira=jira_config,
        azure=AzureConfig(azure_organization_url=None, azure_pat=None),
        project=ProjectConfig(project_keys=["STDEL"], task_tracker="jira"),
        workflow=WorkflowConfig(
            stages={"Development": ["In Progress"]},
            in_progress_status_codes=["In Progress"],
            pending_status_codes=["Blocked"],
            done_status_codes=["Done"],
            recently_finished_tasks_days=14,
        ),
        task_filter=TaskFilterConfig(global_task_types_filter=None, global_team_filter=None),
        member_group=MemberGroupConfig(members={}, default_member_group_when_missing=None),
        estimation=EstimationConfig(
            working_days_per_month=22,
            default_story_points_value_when_missing=3.0,
            ideal_hours_per_day=4.0,
            story_points_to_ideal_hours_convertion_ratio=1.0,
            default_seniority_level_when_missing="middle",
            default_health_status_when_missing="GREEN",
        ),
        sorting=SortingConfig(stage_sort_overrides={}, default_sort_criteria="-health"),
    )


class TestJiraTaskRepositoryAuth(unittest.TestCase):

    @patch("tasks.out.jira_task_repository.Jira")
    def test_shouldUseServerDataCenterPersonalAccessTokenWhenConfigured(self, jira_client):
        # given
        config = _build_tasks_config(JiraConfig(
            jira_server_url="https://jira.devtools.intel.com",
            jira_email=None,
            jira_api_token="pat",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
        ))

        # when
        JiraTaskRepository(config)

        # then
        jira_client.assert_called_once_with(url="https://jira.devtools.intel.com", token="pat", verify_ssl=True)

    @patch("tasks.out.jira_task_repository.Jira")
    def test_shouldKeepCloudBasicAuthenticationWhenServerPatIsNotConfigured(self, jira_client):
        # given
        config = _build_tasks_config(JiraConfig(
            jira_server_url="https://example.atlassian.net",
            jira_email="pm@example.com",
            jira_api_token="api-token",
            story_point_custom_field_id="customfield_10016",
        ))

        # when
        JiraTaskRepository(config)

        # then
        jira_client.assert_called_once_with(
            url="https://example.atlassian.net",
            username="pm@example.com",
            password="api-token",
            verify_ssl=True,
            cloud=True,
        )

    @patch("tasks.out.jira_task_repository.JiraServerTaskProvider")
    @patch("tasks.out.jira_task_repository.CachingTaskProvider")
    @patch("tasks.out.jira_task_repository.Jira")
    def test_shouldUseServerDataCenterTaskProviderWhenServerPatIsConfigured(self, jira_client,
                                                                            caching_provider,
                                                                            server_provider):
        # given
        config = _build_tasks_config(JiraConfig(
            jira_server_url="https://jira.devtools.intel.com",
            jira_email=None,
            jira_api_token="pat",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
        ))
        caching_provider.return_value.get_tasks.return_value = []
        repository = JiraTaskRepository(config)

        # when
        result = asyncio.run(repository._fetch_jira_tasks("key in (STDEL-8942)", include_time_tracking=False))

        # then
        self.assertEqual([], result)
        server_provider.assert_called_once()
        caching_provider.assert_called_once_with(server_provider.return_value, None)


if __name__ == "__main__":
    unittest.main()