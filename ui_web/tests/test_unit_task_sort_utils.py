import unittest

from sd_metrics_lib.utils.enums import HealthStatus

from ui_web.tests.fixtures.ui_web_builders import TaskDataBuilder, sorting_config
from ui_web.utils.task_sort_utils import TaskSortUtils


class TestTaskSortUtilsHealthStatusPrioritization(unittest.TestCase):

    def test_shouldShowCriticalTasksFirstWhenSprintReviewNeedsAttention(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_red_health_forecast()
                .assigned_to("alice")
                .build(),
            TaskDataBuilder.capacity_planning_epic()
                .with_yellow_health_forecast()
                .assigned_to("alice")
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(HealthStatus.RED, result[0].forecast.health_status)
        self.assertEqual(HealthStatus.YELLOW, result[1].forecast.health_status)
        self.assertEqual(HealthStatus.GREEN, result[2].forecast.health_status)

    def test_shouldDisplayHealthyTasksBeforeUnestimatedTasksWhenPlanningSprintBacklog(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .assigned_to("alice")
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(HealthStatus.GREEN, result[0].forecast.health_status)
        self.assertIsNone(result[1].forecast)

    def test_shouldPrioritizeOverrunTasksInDailyStandupWhenTeamNeedsToReactQuickly(self):
        green_task = (TaskDataBuilder.sprint_dashboard_task()
                     .with_green_health_forecast()
                     .assigned_to("alice")
                     .build())
        yellow_task = (TaskDataBuilder.team_velocity_task()
                      .with_yellow_health_forecast()
                      .assigned_to("alice")
                      .build())
        red_task = (TaskDataBuilder.capacity_planning_epic()
                   .with_red_health_forecast()
                   .assigned_to("alice")
                   .build())

        tasks = [green_task, yellow_task, red_task]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(HealthStatus.RED, result[0].forecast.health_status)
        self.assertEqual(HealthStatus.YELLOW, result[1].forecast.health_status)
        self.assertEqual(HealthStatus.GREEN, result[2].forecast.health_status)


class TestTaskSortUtilsTeamMemberGrouping(unittest.TestCase):

    def test_shouldGroupTasksByDeveloperWhenTeamLeadReviewsWorkDistribution(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("charlie")
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .build(),
            TaskDataBuilder.capacity_planning_epic()
                .with_green_health_forecast()
                .assigned_to("bob")
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config('assignee'))

        self.assertEqual("alice (Developer)", result[0].assignment.assignee.display_name)
        self.assertEqual("bob (Developer)", result[1].assignment.assignee.display_name)
        self.assertEqual("charlie (Developer)", result[2].assignment.assignee.display_name)

    def test_shouldShowUnassignedTasksFirstWhenScrumMasterAllocatesWorkInSprintPlanning(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("bob")
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .with_no_assignee()
                .build(),
            TaskDataBuilder.capacity_planning_epic()
                .with_green_health_forecast()
                .assigned_to("alice")
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config('assignee'))

        self.assertIsNone(result[0].assignment.assignee)
        self.assertEqual("alice (Developer)", result[1].assignment.assignee.display_name)
        self.assertEqual("bob (Developer)", result[2].assignment.assignee.display_name)

    def test_shouldSortDeveloperNamesAlphabeticallyWhenProductManagerReviewsTeamProgress(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("ZEBRA")
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertIn("ZEBRA", result[0].assignment.assignee.display_name)
        self.assertIn("alice", result[1].assignment.assignee.display_name)


class TestTaskSortUtilsTimeInvestmentTracking(unittest.TestCase):

    def test_shouldHighlightHighInvestmentTasksWhenManagerEvaluatesResourceAllocation(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(5.0)
                .build(),
            TaskDataBuilder.capacity_planning_epic()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(3.0)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(5.0, result[0].time_tracking.total_spent_time_days)
        self.assertEqual(3.0, result[1].time_tracking.total_spent_time_days)
        self.assertEqual(1.0, result[2].time_tracking.total_spent_time_days)

    def test_shouldShowTrackedTasksBeforeUntrackedWhenAnalyzingTeamEffortInRetrospective(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(2.0)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(2.0, result[0].time_tracking.total_spent_time_days)
        self.assertIsNone(result[1].time_tracking.total_spent_time_days)

    def test_shouldIncludeRecentlyStartedTasksWhenDailyStandupShowsActiveWork(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(0.0)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(1.0, result[0].time_tracking.total_spent_time_days)
        self.assertEqual(0.0, result[1].time_tracking.total_spent_time_days)


class TestTaskSortUtilsBusinessPriorityOrdering(unittest.TestCase):

    def test_shouldEscalateHighPriorityTasksWhenStakeholderDeadlineApproaches(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(3)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(1)
                .build(),
            TaskDataBuilder.capacity_planning_epic()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(2)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config('priority'))

        self.assertEqual(1, result[0].priority)
        self.assertEqual(2, result[1].priority)
        self.assertEqual(3, result[2].priority)

    def test_shouldDeprioritizeUnprioritizedTasksWhenBacklogRefinementIdentifiesGaps(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(2)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config('priority'))

        self.assertEqual(2, result[0].priority)
        self.assertIsNone(result[1].priority)

    def test_shouldHandleVaryingPriorityScalesWhenMultipleProjectsUseJiraAndAzure(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(100)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(1)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config('priority'))

        self.assertEqual(1, result[0].priority)
        self.assertEqual(100, result[1].priority)


class TestTaskSortUtilsStoryPointEstimation(unittest.TestCase):

    def test_shouldEscalateLargerEstimatesWhenPlanningCapacityBySize(self):
        # given
        small = TaskDataBuilder.sprint_dashboard_task().with_story_points(2.0).build()
        large = TaskDataBuilder.team_velocity_task().with_story_points(8.0).build()

        # when
        result = TaskSortUtils.sort_tasks([small, large], sorting_config('story_points'))

        # then
        self.assertEqual(2.0, result[0].story_points)
        self.assertEqual(8.0, result[1].story_points)

    def test_shouldDeprioritizeUnestimatedTasksWhenSortingByStoryPoints(self):
        # given
        estimated = TaskDataBuilder.sprint_dashboard_task().with_story_points(5.0).build()
        unestimated = TaskDataBuilder.team_velocity_task().build()

        # when
        result = TaskSortUtils.sort_tasks([unestimated, estimated], sorting_config('story_points'))

        # then
        self.assertEqual(5.0, result[0].story_points)
        self.assertIsNone(result[1].story_points)


class TestTaskSortUtilsMultiFactorDecisionMaking(unittest.TestCase):

    def test_shouldEscalateCriticalTasksOverTeamPreferencesWhenSprintGoalAtRisk(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_red_health_forecast()
                .assigned_to("zebra")
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(HealthStatus.RED, result[0].forecast.health_status)
        self.assertEqual(HealthStatus.GREEN, result[1].forecast.health_status)

    def test_shouldFocusOnBlockedTasksOverTimeInvestmentWhenDailyStandupIdentifiesImpediments(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(10.0)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_red_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(HealthStatus.RED, result[0].forecast.health_status)
        self.assertEqual(1.0, result[0].time_tracking.total_spent_time_days)

    def test_shouldPrioritizeOverrunTasksOverBusinessPriorityWhenTeamNeedsToRecoverFromDelay(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_priority(1)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_red_health_forecast()
                .assigned_to("alice")
                .with_priority(3)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(HealthStatus.RED, result[0].forecast.health_status)
        self.assertEqual(3, result[0].priority)

    def test_shouldOrganizeByDeveloperOverTimeInvestmentWhenTeamLeadReviewsIndividualContributions(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("bob")
                .with_time_spent_days(10.0)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config('assignee,-spent_time'))

        self.assertEqual("alice (Developer)", result[0].assignment.assignee.display_name)
        self.assertEqual(1.0, result[0].time_tracking.total_spent_time_days)

    def test_shouldGroupByDeveloperOverPriorityWhenManagerAssessesTeamWorkload(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("bob")
                .with_priority(1)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_priority(3)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config('assignee,priority'))

        self.assertEqual("alice (Developer)", result[0].assignment.assignee.display_name)
        self.assertEqual(3, result[0].priority)

    def test_shouldShowHighInvestmentBeforeLowPriorityWhenRetrospectiveAnalyzesEfficiency(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(1)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(5.0)
                .with_priority(3)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(5.0, result[0].time_tracking.total_spent_time_days)
        self.assertEqual(3, result[0].priority)

    def test_shouldApplyAllFactorsWhenProductOwnerPrioritizesSprintBacklog(self):
        tasks = [
            TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("charlie")
                .with_time_spent_days(2.0)
                .with_priority(2)
                .build(),
            TaskDataBuilder.team_velocity_task()
                .with_red_health_forecast()
                .assigned_to("bob")
                .with_time_spent_days(1.0)
                .with_priority(3)
                .build(),
            TaskDataBuilder.capacity_planning_epic()
                .with_red_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(5.0)
                .with_priority(1)
                .build(),
            TaskDataBuilder.retrospective_analysis_task()
                .with_yellow_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(3.0)
                .with_priority(1)
                .build(),
            TaskDataBuilder.health_monitoring_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(1)
                .build()
        ]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config('priority,assignee,-health,-spent_time'))

        self.assertEqual("PROJ-001", result[0].id)
        self.assertEqual("PROJ-789", result[1].id)
        self.assertEqual("PROJ-321", result[2].id)
        self.assertEqual("PROJ-123", result[3].id)
        self.assertEqual("PROJ-456", result[4].id)

    def test_shouldMaintainConsistentOrderingWhenAllBusinessCriteriaIdentical(self):
        task1 = (TaskDataBuilder.sprint_dashboard_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(1)
                .build())
        task2 = (TaskDataBuilder.team_velocity_task()
                .with_green_health_forecast()
                .assigned_to("alice")
                .with_time_spent_days(1.0)
                .with_priority(1)
                .build())

        tasks = [task1, task2]

        result = TaskSortUtils.sort_tasks(tasks, sorting_config())

        self.assertEqual(2, len(result))
        self.assertIn(task1.id, [result[0].id, result[1].id])
        self.assertIn(task2.id, [result[0].id, result[1].id])
