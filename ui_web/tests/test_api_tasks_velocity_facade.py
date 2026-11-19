import unittest
from datetime import datetime

from sd_metrics_lib.utils.time import Duration, TimeUnit, TimePolicy

from tasks.app.domain.model.task import Task, Assignment, TimeTracking, SystemMetadata, TaskSearchCriteria, \
    WorkTimeExtractorType
from ui_web.convertors.velocity_task_detail_convertor import VelocityTaskDetailConvertor
from ui_web.facades.tasks_velocity_facade import TasksVelocityFacade
from ui_web.tests.mocks.mock_task_search_api import MockTaskSearchApi
from ui_web.tests.mocks.mock_velocity_calculation_api import MockVelocityCalculationApi

_START_DATE = datetime(2024, 1, 1)
_END_DATE = datetime(2024, 1, 31)
_IN_PROGRESS_STATUSES = ["In Progress", "Development", "Testing"]
_DEVELOPMENT_STAGE_STATUSES = ["In Progress", "Development"]


def _build_task(task_id, title, story_points, time_by_assignee):
    assignee_durations = {
        name: Duration.of(seconds, TimeUnit.SECOND)
        for name, seconds in time_by_assignee.items()
    }
    total_seconds = sum(time_by_assignee.values())
    time_tracking = TimeTracking(
        total_spent_time=Duration.of(total_seconds, TimeUnit.SECOND),
        spent_time_by_assignee=assignee_durations
    )
    return Task(
        id=task_id,
        title=title,
        system_metadata=SystemMetadata(original_status="Done", project_key="PROJ"),
        assignment=Assignment(),
        time_tracking=time_tracking,
        story_points=story_points
    )


def _create_facade(task_search_api, velocity_calculation_api,
                    member_group_members=None,
                    member_group_custom_filters=None):
    return TasksVelocityFacade(
        task_search_api=task_search_api,
        create_velocity_search_criteria=lambda start, end: TaskSearchCriteria(
            status_filter=["Done", "Closed"],
            resolution_date_range=(start, end)
        ),
        resolve_member_group_members=lambda group_id: member_group_members.get(group_id) if member_group_members else None,
        velocity_task_detail_convertor=VelocityTaskDetailConvertor(
            time_policy=TimePolicy.BUSINESS_HOURS
        ),
        velocity_calculation_api=velocity_calculation_api,
        in_progress_status_codes=_IN_PROGRESS_STATUSES,
        development_stage_status_codes=_DEVELOPMENT_STAGE_STATUSES,
        member_group_custom_filters=member_group_custom_filters
    )


class TestTasksVelocityFacadeTaskRetrieval(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.task_search_api = MockTaskSearchApi()
        self.velocity_calculation_api = MockVelocityCalculationApi()
        self.velocity_calculation_api.mock.calculate_ideal_velocity.return_value = 2.0

    async def test_shouldReturnDeveloperBreakdownWhenTasksHaveTimeTracking(self):
        # Given
        task = _build_task("TASK-1", "Authentication feature", story_points=10.0,
                           time_by_assignee={"alice": 21600, "bob": 14400})
        self.task_search_api.mock.search.return_value = [task]
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        result = await facade.get_tasks(["alice", "bob"], _START_DATE, _END_DATE)

        # Then
        developer_ids = {entry.assignment.assignee.id for entry in result}
        self.assertEqual({"alice", "bob"}, developer_ids)

    async def test_shouldBreakDownEveryLoggedDeveloperWhenNoDevelopersSelected(self):
        # Given
        task = _build_task("TASK-1", "Shared feature", story_points=8.0,
                           time_by_assignee={"alice": 18000, "charlie": 9000})
        self.task_search_api.mock.search.return_value = [task]
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        result = await facade.get_tasks([], _START_DATE, _END_DATE)

        # Then
        developer_ids = {entry.assignment.assignee.id for entry in result}
        self.assertEqual({"alice", "charlie"}, developer_ids)

    def test_shouldResolveAllMemberGroupMembersWhenDeveloperNamesEmpty(self):
        # Given
        facade = _create_facade(
            self.task_search_api, self.velocity_calculation_api,
            member_group_members={"backend-team": ["alice", "bob"]}
        )

        # When
        resolved = facade.resolve_developer_names([], member_group_id="backend-team")

        # Then
        self.assertCountEqual(["alice", "bob"], resolved)

    def test_shouldKeepExplicitDeveloperNamesWhenProvided(self):
        # Given
        facade = _create_facade(
            self.task_search_api, self.velocity_calculation_api,
            member_group_members={"backend-team": ["alice", "bob"]}
        )

        # When
        resolved = facade.resolve_developer_names(["alice"], member_group_id="backend-team")

        # Then
        self.assertEqual(["alice"], resolved)

    async def test_shouldApplyCustomJqlFilterWhenCustomFilterEnabledForMemberGroup(self):
        # Given
        self.task_search_api.mock.search.return_value = []
        facade = _create_facade(
            self.task_search_api, self.velocity_calculation_api,
            member_group_custom_filters={"backend-team": "parent in (PROJ-100, PROJ-200)"}
        )

        # When
        await facade.get_tasks(["alice"], _START_DATE, _END_DATE,
                               member_group_id="backend-team", use_custom_filter=True)

        # Then
        search_criteria = self.task_search_api.mock.search.call_args[0][0]
        self.assertEqual("parent in (PROJ-100, PROJ-200)", search_criteria.raw_jql_filter)

    async def test_shouldUseAssigneeFilterWhenCustomFilterDisabled(self):
        # Given
        self.task_search_api.mock.search.return_value = []
        facade = _create_facade(
            self.task_search_api, self.velocity_calculation_api,
            member_group_members={"backend-team": ["alice", "bob"]},
            member_group_custom_filters={"backend-team": "parent in (PROJ-100)"}
        )

        # When
        await facade.get_tasks(["alice"], _START_DATE, _END_DATE,
                               member_group_id="backend-team", use_custom_filter=False)

        # Then
        search_criteria = self.task_search_api.mock.search.call_args[0][0]
        self.assertEqual(["alice", "bob"], search_criteria.assignee_filter)
        self.assertIsNone(search_criteria.raw_jql_filter)

    async def test_shouldBroadenSearchCriteriaWhenIncludeAllStatusesEnabled(self):
        # Given
        self.task_search_api.mock.search.return_value = []
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        await facade.get_tasks(["alice"], _START_DATE, _END_DATE, include_all_statuses=True)

        # Then
        search_criteria = self.task_search_api.mock.search.call_args[0][0]
        self.assertIsNone(search_criteria.status_filter)
        self.assertIsNone(search_criteria.resolution_date_range)
        self.assertEqual((_START_DATE, _END_DATE), search_criteria.state_change_date_range)

    async def test_shouldBoundWorktimeToSelectedMonthWhenIncludeAllStatusesEnabled(self):
        # Given
        self.task_search_api.mock.search.return_value = []
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        await facade.get_tasks(["alice"], _START_DATE, _END_DATE, include_all_statuses=True)

        # Then
        enrichment = self.task_search_api.mock.search.call_args[0][1]
        self.assertEqual(WorkTimeExtractorType.BOUNDARY_FROM_LAST_MODIFIED, enrichment.worktime_extractor_type)

    async def test_shouldNotBoundWorktimeWhenIncludeAllStatusesDisabled(self):
        # Given
        self.task_search_api.mock.search.return_value = []
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        await facade.get_tasks(["alice"], _START_DATE, _END_DATE)

        # Then
        enrichment = self.task_search_api.mock.search.call_args[0][1]
        self.assertIsNone(enrichment.worktime_extractor_type)


class TestTasksVelocityFacadeTeamTasks(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.task_search_api = MockTaskSearchApi()
        self.velocity_calculation_api = MockVelocityCalculationApi()
        self.velocity_calculation_api.mock.calculate_ideal_velocity.return_value = 2.0

    async def test_shouldExtractDeveloperNamesFromTaskTimeTrackingData(self):
        # Given
        task = _build_task("TASK-1", "Shared feature", story_points=8.0,
                           time_by_assignee={"alice": 18000, "charlie": 9000})
        self.task_search_api.mock.search.return_value = [task]
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        result = await facade.get_team_tasks(_START_DATE, _END_DATE)

        # Then
        developer_ids = {entry.assignment.assignee.id for entry in result}
        self.assertEqual({"alice", "charlie"}, developer_ids)

    async def test_shouldReturnBreakdownForAllDiscoveredDevelopers(self):
        # Given
        task_a = _build_task("TASK-1", "Backend refactoring", story_points=6.0,
                             time_by_assignee={"alice": 14400})
        task_b = _build_task("TASK-2", "API integration", story_points=4.0,
                             time_by_assignee={"bob": 10800})
        self.task_search_api.mock.search.return_value = [task_a, task_b]
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        result = await facade.get_team_tasks(_START_DATE, _END_DATE)

        # Then
        self.assertEqual(2, len(result))

    async def test_shouldApplyCustomFilterToTeamTasksWhenEnabled(self):
        # Given
        self.task_search_api.mock.search.return_value = []
        facade = _create_facade(
            self.task_search_api, self.velocity_calculation_api,
            member_group_custom_filters={"backend-team": "parent in (PROJ-100)"}
        )

        # When
        await facade.get_team_tasks(_START_DATE, _END_DATE,
                                    member_group_id="backend-team", use_custom_filter=True)

        # Then
        search_criteria = self.task_search_api.mock.search.call_args[0][0]
        self.assertEqual("parent in (PROJ-100)", search_criteria.raw_jql_filter)


class TestTasksVelocityFacadeWorklogTransitionStatuses(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.task_search_api = MockTaskSearchApi()
        self.velocity_calculation_api = MockVelocityCalculationApi()
        self.velocity_calculation_api.mock.calculate_ideal_velocity.return_value = 2.0

    async def test_shouldUseDevelopmentStageStatusesForDevVelocityTasks(self):
        # Given
        self.task_search_api.mock.search.return_value = []
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        await facade.get_tasks(["alice"], _START_DATE, _END_DATE)

        # Then
        enrichment = self.task_search_api.mock.search.call_args[0][1]
        self.assertEqual(_DEVELOPMENT_STAGE_STATUSES, enrichment.worklog_transition_statuses)

    async def test_shouldUseInProgressStatusesForTeamVelocityTasks(self):
        # Given
        self.task_search_api.mock.search.return_value = []
        facade = _create_facade(self.task_search_api, self.velocity_calculation_api)

        # When
        await facade.get_team_tasks(_START_DATE, _END_DATE)

        # Then
        enrichment = self.task_search_api.mock.search.call_args[0][1]
        self.assertEqual(_IN_PROGRESS_STATUSES, enrichment.worklog_transition_statuses)


if __name__ == '__main__':
    unittest.main()
