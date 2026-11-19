import unittest
from unittest.mock import Mock

from ui_web.facades.tasks_facade import TasksFacade
from ui_web.utils.federated_data_post_processors import MemberGroupTaskFilter
from ui_web.tests.fixtures.ui_web_builders import DomainTaskBuilder
from ui_web.tests.fixtures.ui_web_facade_harness import UIWebFacadeHarness


class TestApiUIWebMemberGroupFilters(UIWebFacadeHarness, unittest.IsolatedAsyncioTestCase):

    async def test_shouldApplyCustomQueryFilterWhenMemberGroupHasCustomFilterConfigured(self):
        # Given - Member group configured with custom JQL/WIQL filter
        member_group_config = Mock()
        member_group_config.members = {}
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {"special-team": "parent in (PROJ-123, PROJ-456)"}

        member_group_filter = MemberGroupTaskFilter(member_group_config)

        tasks_facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=member_group_filter,
            member_convertor=self.member_convertor,
            member_group_custom_filters={"special-team": "parent in (PROJ-123, PROJ-456)"}
        )

        tasks = [DomainTaskBuilder.domain_task_for_ui_conversion().build()]
        self.task_search_api.mock.search.side_effect = [tasks, []]

        # When - Fetch tasks for member group with custom filter
        await tasks_facade.get_tasks("special-team")

        # Then - Search API should be called with raw_jql_filter set
        call_args = self.task_search_api.mock.search.call_args_list[0]
        search_criteria = call_args[0][0]
        self.assertEqual("parent in (PROJ-123, PROJ-456)", search_criteria.raw_jql_filter)

    async def test_shouldSkipAssigneeFilteringWhenMemberGroupUsesCustomFilter(self):
        # Given - Member group with custom filter and tasks from different assignees
        member_group_config = Mock()
        member_group_config.members = {
            "alice.johnson": {"member_groups": ["frontend-team"]},
            "bob.smith": {"member_groups": ["backend-team"]}
        }
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {"special-team": "[System.Parent] IN (174641, 176747)"}

        member_group_filter = MemberGroupTaskFilter(member_group_config)

        tasks_facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=member_group_filter,
            member_convertor=self.member_convertor,
            member_group_custom_filters={"special-team": "[System.Parent] IN (174641, 176747)"}
        )

        mixed_assignee_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion().assigned_to("alice.johnson").build(),
            DomainTaskBuilder.domain_task_for_ui_conversion().assigned_to("bob.smith").build(),
            DomainTaskBuilder.domain_task_for_ui_conversion().assigned_to("charlie.brown").build()
        ]
        self.task_search_api.mock.search.side_effect = [mixed_assignee_tasks, []]

        # When - Fetch tasks for member group with custom filter
        result = await tasks_facade.get_tasks("special-team")

        # Then - All tasks should be returned without assignee filtering
        self.assertEqual(3, len(result))

    async def test_shouldUseAssigneeFilteringWhenMemberGroupHasNoCustomFilter(self):
        # Given - Member group without custom filter
        member_group_config = Mock()
        member_group_config.members = {
            "alice.johnson": {"member_groups": ["frontend-team"]},
            "bob.smith": {"member_groups": ["backend-team"]}
        }
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {}

        member_group_filter = MemberGroupTaskFilter(member_group_config)

        tasks_facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=member_group_filter,
            member_convertor=self.member_convertor,
            member_group_custom_filters={}
        )

        mixed_assignee_tasks = [
            DomainTaskBuilder.domain_task_for_ui_conversion().assigned_to("alice.johnson").build(),
            DomainTaskBuilder.domain_task_for_ui_conversion().assigned_to("bob.smith").build()
        ]
        self.task_search_api.mock.search.side_effect = [mixed_assignee_tasks, []]

        # When - Fetch tasks for frontend team (normal assignee filtering)
        result = await tasks_facade.get_tasks("frontend-team")

        # Then - Only alice's task should be returned (assignee filtering applied)
        self.assertEqual(1, len(result))
        self.assertEqual("alice.johnson", result[0].assignment.assignee.id)


    async def test_shouldRelabelUnassignedTasksUnderFilteredGroupWhenMergeEnabled(self):
        # Given
        member_group_config = Mock()
        member_group_config.members = {"dev1": {"member_groups": ["Headless"]}}
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {"Headless": "parent in (PROJ-100)"}
        member_group_filter = MemberGroupTaskFilter(member_group_config)

        facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=member_group_filter,
            member_convertor=self.member_convertor,
            member_group_custom_filters={"Headless": "parent in (PROJ-100)"},
            merge_unassigned_into_filtered_group=True
        )

        unassigned_task = (DomainTaskBuilder.domain_task_for_ui_conversion()
                           .assigned_to("unknown.dev")
                           .with_member_group("unassigned", "Unassigned")
                           .build())
        self.task_search_api.mock.search.side_effect = [[unassigned_task], []]

        # When
        result = await facade.get_tasks("Headless")

        # Then
        self.assertEqual(1, len(result))
        self.assertEqual("Headless", result[0].assignment.member_group.name)

    async def test_shouldKeepUnassignedSeparateWhenViewingAllGroupsEvenWithMergeEnabled(self):
        # Given
        member_group_config = Mock()
        member_group_config.members = {}
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {"Headless": "parent in (PROJ-100)"}
        member_group_filter = MemberGroupTaskFilter(member_group_config)

        facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=member_group_filter,
            member_convertor=self.member_convertor,
            member_group_custom_filters={"Headless": "parent in (PROJ-100)"},
            merge_unassigned_into_filtered_group=True
        )

        unassigned_task = (DomainTaskBuilder.domain_task_for_ui_conversion()
                           .assigned_to("unknown.dev")
                           .with_member_group("unassigned", "Unassigned")
                           .build())
        self.task_search_api.mock.search.side_effect = [[unassigned_task], []]

        # When
        result = await facade.get_tasks()

        # Then
        self.assertEqual(1, len(result))
        self.assertEqual("Unassigned", result[0].assignment.member_group.name)

    async def test_shouldKeepUnassignedSeparateWhenMergeDisabled(self):
        # Given
        member_group_config = Mock()
        member_group_config.members = {}
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {"Headless": "parent in (PROJ-100)"}
        member_group_filter = MemberGroupTaskFilter(member_group_config)

        facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=member_group_filter,
            member_convertor=self.member_convertor,
            member_group_custom_filters={"Headless": "parent in (PROJ-100)"},
            merge_unassigned_into_filtered_group=False
        )

        unassigned_task = (DomainTaskBuilder.domain_task_for_ui_conversion()
                           .assigned_to("unknown.dev")
                           .with_member_group("unassigned", "Unassigned")
                           .build())
        self.task_search_api.mock.search.side_effect = [[unassigned_task], []]

        # When
        result = await facade.get_tasks("Headless")

        # Then
        self.assertEqual(1, len(result))
        self.assertEqual("Unassigned", result[0].assignment.member_group.name)

    async def test_shouldOnlyRelabelUnassignedTasksNotRegularAssignedTasks(self):
        # Given
        member_group_config = Mock()
        member_group_config.members = {"dev1": {"member_groups": ["Headless"]}}
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {"Headless": "parent in (PROJ-100)"}
        member_group_filter = MemberGroupTaskFilter(member_group_config)

        facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=member_group_filter,
            member_convertor=self.member_convertor,
            member_group_custom_filters={"Headless": "parent in (PROJ-100)"},
            merge_unassigned_into_filtered_group=True
        )

        assigned_task = (DomainTaskBuilder.domain_task_for_ui_conversion()
                         .assigned_to("dev1")
                         .with_member_group("headless", "Headless")
                         .build())
        assigned_task.id = "ASSIGNED-TASK"

        unassigned_task = (DomainTaskBuilder.domain_task_for_ui_conversion()
                           .assigned_to("unknown.dev")
                           .with_member_group("unassigned", "Unassigned")
                           .build())
        unassigned_task.id = "UNASSIGNED-TASK"

        self.task_search_api.mock.search.side_effect = [[assigned_task, unassigned_task], []]

        # When
        result = await facade.get_tasks("Headless")

        # Then
        self.assertEqual(2, len(result))
        assigned_result = next(t for t in result if t.id == "ASSIGNED-TASK")
        relabeled_result = next(t for t in result if t.id == "UNASSIGNED-TASK")

        self.assertEqual("Headless", assigned_result.assignment.member_group.name)
        self.assertEqual("Headless", relabeled_result.assignment.member_group.name)


if __name__ == '__main__':
    unittest.main()
