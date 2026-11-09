from unittest.mock import Mock, patch

from tasks.app.domain.model.config import WorkflowConfig
from tasks.app.domain.model.task import TaskSearchCriteria, MemberGroup
from ui_web.facades.tasks_facade import TasksFacade
from ui_web.facades.team_velocity_facade import TeamVelocityFacade
from ui_web.convertors.task_convertor import TaskConvertor
from ui_web.convertors.member_convertor import MemberConvertor
from ui_web.convertors.velocity_chart_convertor import VelocityChartConvertor
from ui_web.convertors.velocity_report_convertor import VelocityReportConvertor
from ui_web.utils.federated_data_post_processors import MemberGroupTaskFilter
from ui_web.tests.mocks.mock_task_search_api import MockTaskSearchApi
from ui_web.tests.mocks.mock_forecast_api import MockForecastApi
from ui_web.tests.mocks.mock_velocity_api import MockVelocityApi
from ui_web.tests.mocks.mock_assignee_search_api import MockAssigneeSearchApi


class UIWebFacadeHarness:
    """Mock APIs, convertors and facades shared by ui_web facade integration tests."""

    def setUp(self):
        self.task_search_api = MockTaskSearchApi()
        self.forecast_api = MockForecastApi()
        self.velocity_api = MockVelocityApi()
        self.assignee_search_api = MockAssigneeSearchApi()

        self.available_member_groups = [
            MemberGroup(id="frontend-team", name="Frontend Development Team"),
            MemberGroup(id="backend-team", name="Backend Development Team"),
            MemberGroup(id="devops-team", name="DevOps Team")
        ]

        self.current_tasks_criteria = TaskSearchCriteria(
            status_filter=["In Progress", "Development", "Testing"]
        )

        self.recently_finished_criteria = TaskSearchCriteria(
            status_filter=["Done", "Completed"]
        )

        self.workflow_config = WorkflowConfig(
            in_progress_status_codes=["In Progress", "Development", "Testing"],
            done_status_codes=["Done", "Completed", "Closed"],
            pending_status_codes=["To Do", "Open", "Backlog"],
            stages={
                "development": ["In Progress", "Development"],
                "qa": ["Testing", "Code Review"],
                "done": ["Done", "Completed", "Closed"]
            },
            recently_finished_tasks_days=30
        )

        # Mock member group config for filtering
        member_group_config = Mock()
        member_group_config.members = {
            "alice.johnson": {"member_groups": ["frontend-team"]},
            "bob.smith": {"member_groups": ["backend-team"]},
            "charlie.brown": {"member_groups": ["devops-team"]}
        }
        member_group_config.default_member_group_when_missing = None
        member_group_config.custom_filters = {}

        self.member_group_filter = MemberGroupTaskFilter(member_group_config)

        # Mock time policy for conversion
        with patch('sd_metrics_lib.utils.time.TimePolicy.BUSINESS_HOURS'):
            self.task_convertor = TaskConvertor(Mock())

        self.member_convertor = MemberConvertor()
        self.velocity_chart_convertor = VelocityChartConvertor()
        self.velocity_report_convertor = VelocityReportConvertor(self.assignee_search_api)

        self.tasks_facade = TasksFacade(
            task_search_api=self.task_search_api,
            forecast_api=self.forecast_api,
            task_convertor=self.task_convertor,
            available_member_groups=self.available_member_groups,
            current_tasks_search_criteria=self.current_tasks_criteria,
            recently_finished_tasks_search_criteria=self.recently_finished_criteria,
            workflow_config=self.workflow_config,
            member_group_task_filter=self.member_group_filter,
            member_convertor=self.member_convertor
        )

        self.velocity_facade = TeamVelocityFacade(
            velocity_api=self.velocity_api,
            assignee_search_api=self.assignee_search_api,
            available_member_groups=self.available_member_groups,
            member_convertor=self.member_convertor,
            velocity_chart_convertor=self.velocity_chart_convertor,
            velocity_report_convertor=self.velocity_report_convertor
        )
