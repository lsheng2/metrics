import unittest

from ui_web.tests.fixtures.ui_web_builders import TaskDataBuilder, sorting_config
from ui_web.utils.task_sort_utils import TaskSortUtils


class TestTaskSortUtilsDataQualityHandling(unittest.TestCase):

    def test_shouldHandleEmptySprintBacklogWhenNoTasksAssigned(self):
        tasks = []

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(0, len(result))

    def test_shouldProcessSingleTaskWhenOnlyOneStoryInSprint(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(1, len(result))
        self.assertEqual("PROJ-123", result[0].id)

    def test_shouldHandleIncompleteTaskDataWhenJiraFieldsMissing(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .build(),
            TaskDataBuilder.team_velocity_task()
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(2, len(result))

    def test_shouldScaleToLargeBacklogsWhenEnterpriseTeamManagesManyTasks(self):
        tasks = []
        for i in range(100):
            task = (TaskDataBuilder.sprint_dashboard_task()
                   .with_green_health_forecast()
                   .assigned_to(f"developer_{i % 10}")
                   .with_time_spent_days(float(i % 5))
                   .with_priority(i % 4 + 1)
                   .build())
            tasks.append(task)

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(100, len(result))

    def test_shouldPreserveOriginalDataWhenSortingForDashboardDisplay(self):
        original_task1 = (TaskDataBuilder.sprint_dashboard_task()
                         .with_green_health_forecast()
                         .assigned_to("charlie")
                         .build())
        original_task2 = (TaskDataBuilder.team_velocity_task()
                         .with_green_health_forecast()
                         .assigned_to("alice")
                         .build())
        tasks = [original_task1, original_task2]
        original_first_id = tasks[0].id

        TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(original_first_id, tasks[0].id)


class TestTaskSortUtilsCustomFieldPrioritization(unittest.TestCase):

    def test_shouldOrderByNumericPriorityFirstWhenPrioritiesDifferRegardlessOfLevel(self):
        # given
        higher_priority_low_level = (TaskDataBuilder.sprint_dashboard_task()
                                     .with_priority(1)
                                     .with_custom_sort_field("Custom.PriorityLevel", "3 - Low")
                                     .build())
        lower_priority_high_level = (TaskDataBuilder.team_velocity_task()
                                     .with_priority(2)
                                     .with_custom_sort_field("Custom.PriorityLevel", "1 - High")
                                     .build())
        tasks = [lower_priority_high_level, higher_priority_low_level]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("priority,Custom.PriorityLevel"))

        # then
        self.assertEqual("PROJ-123", result[0].id)

    def test_shouldBreakTiesByPriorityLevelWhenNumericPrioritiesMatch(self):
        # given
        medium_level = (TaskDataBuilder.sprint_dashboard_task()
                        .with_priority(2)
                        .with_custom_sort_field("Custom.PriorityLevel", "2 - Medium")
                        .build())
        high_level = (TaskDataBuilder.team_velocity_task()
                      .with_priority(2)
                      .with_custom_sort_field("Custom.PriorityLevel", "1 - High")
                      .build())
        tasks = [medium_level, high_level]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("priority,Custom.PriorityLevel"))

        # then
        self.assertEqual("PROJ-456", result[0].id)

    def test_shouldRankPriorityLevelNumericallyNotLexicallyWhenLeadingNumbersDiffInLength(self):
        # given
        tenth_level = (TaskDataBuilder.sprint_dashboard_task()
                       .with_priority(2)
                       .with_custom_sort_field("Custom.PriorityLevel", "10 - Backlog")
                       .build())
        second_level = (TaskDataBuilder.team_velocity_task()
                        .with_priority(2)
                        .with_custom_sort_field("Custom.PriorityLevel", "2 - Medium")
                        .build())
        tasks = [tenth_level, second_level]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("priority,Custom.PriorityLevel"))

        # then
        self.assertEqual("PROJ-456", result[0].id)

    def test_shouldPlaceTasksMissingPriorityLevelLastWhenSortingByLevel(self):
        # given
        with_level = (TaskDataBuilder.sprint_dashboard_task()
                      .with_priority(2)
                      .with_custom_sort_field("Custom.PriorityLevel", "1 - High")
                      .build())
        without_level = (TaskDataBuilder.team_velocity_task()
                         .with_priority(2)
                         .build())
        tasks = [without_level, with_level]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("priority,Custom.PriorityLevel"))

        # then
        self.assertEqual("PROJ-456", result[1].id)

    def test_shouldFallBackToAlphabeticalWhenCustomFieldHasNoNumericPrefix(self):
        # given
        high = (TaskDataBuilder.sprint_dashboard_task()
                .with_custom_sort_field("Custom.Severity", "High")
                .build())
        low = (TaskDataBuilder.team_velocity_task()
               .with_custom_sort_field("Custom.Severity", "Low")
               .build())
        medium = (TaskDataBuilder.capacity_planning_epic()
                  .with_custom_sort_field("Custom.Severity", "Medium")
                  .build())
        tasks = [medium, low, high]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("Custom.Severity"))

        # then
        self.assertEqual(["PROJ-123", "PROJ-456", "PROJ-001"], [task.id for task in result])


class TestTaskSortUtilsNaturalOrdering(unittest.TestCase):

    def test_shouldOrderMultiDigitLevelsNumericallyWhenBacklogHasMoreThanNinePriorities(self):
        # given
        eleven = TaskDataBuilder.sprint_dashboard_task().with_custom_sort_field("Custom.Rank", "11 - name").build()
        two = TaskDataBuilder.team_velocity_task().with_custom_sort_field("Custom.Rank", "2 - name").build()
        thirty_four = TaskDataBuilder.capacity_planning_epic().with_custom_sort_field("Custom.Rank", "34 - name").build()
        one = TaskDataBuilder.retrospective_analysis_task().with_custom_sort_field("Custom.Rank", "1 - name").build()
        tasks = [thirty_four, eleven, two, one]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("Custom.Rank"))

        # then
        self.assertEqual(["PROJ-789", "PROJ-456", "PROJ-123", "PROJ-001"], [task.id for task in result])

    def test_shouldOrderMultiSegmentReleasesByVersionWhenPlanningDeploymentSequence(self):
        # given
        patch = TaskDataBuilder.sprint_dashboard_task().with_custom_sort_field("Custom.Release", "2026.022.01").build()
        later = TaskDataBuilder.team_velocity_task().with_custom_sort_field("Custom.Release", "2026.023").build()
        base = TaskDataBuilder.capacity_planning_epic().with_custom_sort_field("Custom.Release", "2026.022").build()
        earlier = TaskDataBuilder.retrospective_analysis_task().with_custom_sort_field("Custom.Release", "2026.021").build()
        tasks = [later, patch, base, earlier]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("Custom.Release"))

        # then
        self.assertEqual(["PROJ-789", "PROJ-001", "PROJ-123", "PROJ-456"], [task.id for task in result])

    def test_shouldOrderReleasesByNumericSegmentWhenPaddingIsInconsistent(self):
        # given
        tenth = TaskDataBuilder.sprint_dashboard_task().with_custom_sort_field("Custom.Release", "2026.10").build()
        second = TaskDataBuilder.team_velocity_task().with_custom_sort_field("Custom.Release", "2026.2").build()
        tasks = [tenth, second]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("Custom.Release"))

        # then
        self.assertEqual(["PROJ-456", "PROJ-123"], [task.id for task in result])

    def test_shouldReverseCustomFieldOrderWhenSortingDescending(self):
        # given
        high = TaskDataBuilder.sprint_dashboard_task().with_custom_sort_field("Custom.PriorityLevel", "1 - High").build()
        low = TaskDataBuilder.team_velocity_task().with_custom_sort_field("Custom.PriorityLevel", "3 - Low").build()
        medium = TaskDataBuilder.capacity_planning_epic().with_custom_sort_field("Custom.PriorityLevel", "2 - Medium").build()
        tasks = [medium, high, low]

        # when
        result = TaskSortUtils.sort_tasks(tasks, sorting_config("-Custom.PriorityLevel"))

        # then
        self.assertEqual(["PROJ-456", "PROJ-001", "PROJ-123"], [task.id for task in result])
