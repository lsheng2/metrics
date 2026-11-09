import unittest
from datetime import datetime
from unittest.mock import patch

from ui_web.data.task_data import TaskData, AssignmentData, TimeTrackingData, SystemMetadataData, ForecastData
from ui_web.utils.task_forecast_chart_utils import TaskForecastChartUtils


class TestTaskForecastChartUtilsIsDone(unittest.TestCase):

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldReturnTrueWhenTaskStatusIsInDoneStatusCodes(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = ["Done", "Closed", "Resolved"]
        task = _build_task("TASK-1", "Completed feature", original_status="Done")

        # When
        result = TaskForecastChartUtils.is_task_data_done(task)

        # Then
        self.assertTrue(result)

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldReturnFalseWhenTaskStatusIsNotInDoneStatusCodes(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = ["Done", "Closed", "Resolved"]
        task = _build_task("TASK-2", "Active feature", original_status="In Progress")

        # When
        result = TaskForecastChartUtils.is_task_data_done(task)

        # Then
        self.assertFalse(result)

    def test_shouldReturnFalseWhenSystemMetadataIsNone(self):
        # Given
        task = _build_task("TASK-3", "Task without metadata", system_metadata=None)

        # When
        result = TaskForecastChartUtils.is_task_data_done(task)

        # Then
        self.assertFalse(result)

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldReturnFalseWhenOriginalStatusIsEmpty(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = ["Done", "Closed", "Resolved"]
        task = _build_task("TASK-4", "Task with empty status", original_status="")

        # When
        result = TaskForecastChartUtils.is_task_data_done(task)

        # Then
        self.assertFalse(result)


class TestTaskForecastChartUtilsFlattenHierarchy(unittest.TestCase):

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldIncludeBothDoneAndActiveChildrenWithCorrectFlags(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = ["Done", "Closed"]
        done_child = _build_task("CHILD-1", "Completed subtask", original_status="Done",
                                 estimation_days=2.0)
        active_child = _build_task("CHILD-2", "Active subtask", original_status="In Progress",
                                   estimation_days=3.0)
        parent = _build_task("PARENT-1", "Parent epic", original_status="In Progress",
                             estimation_days=5.0, children=[done_child, active_child])

        # When
        result = TaskForecastChartUtils.flatten_task_data_hierarchy_for_table(parent)

        # Then
        self.assertEqual(3, len(result))
        self.assertEqual("PARENT-1", result[0].task_id)
        self.assertFalse(result[0].is_done)
        self.assertEqual("CHILD-1", result[1].task_id)
        self.assertTrue(result[1].is_done)
        self.assertEqual("CHILD-2", result[2].task_id)
        self.assertFalse(result[2].is_done)

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldSetCorrectNestingLevelsForDeepHierarchy(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = ["Done"]
        grandchild = _build_task("GRAND-1", "Grandchild task", original_status="To Do")
        child = _build_task("CHILD-1", "Child task", original_status="To Do",
                            children=[grandchild])
        parent = _build_task("PARENT-1", "Parent task", original_status="To Do",
                             children=[child])

        # When
        result = TaskForecastChartUtils.flatten_task_data_hierarchy_for_table(parent)

        # Then
        self.assertEqual(0, result[0].level)
        self.assertEqual(1, result[1].level)
        self.assertEqual(2, result[2].level)

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldMarkParentAsHavingChildrenWhenChildrenExist(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = []
        child = _build_task("CHILD-1", "Child task", original_status="To Do")
        parent = _build_task("PARENT-1", "Parent task", original_status="To Do",
                             children=[child])

        # When
        result = TaskForecastChartUtils.flatten_task_data_hierarchy_for_table(parent)

        # Then
        self.assertTrue(result[0].has_children)
        self.assertFalse(result[1].has_children)

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldExtractEstimationDaysAndStatusIntoBreakdownItem(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = []
        task = _build_task("TASK-1", "Feature task", original_status="In Progress",
                           estimation_days=7.5, url="https://jira.example.com/TASK-1")

        # When
        result = TaskForecastChartUtils.flatten_task_data_hierarchy_for_table(task)

        # Then
        self.assertEqual(7.5, result[0].estimation_days)
        self.assertEqual("In Progress", result[0].status)
        self.assertEqual("https://jira.example.com/TASK-1", result[0].task_url)

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldUseZeroEstimationWhenForecastIsMissing(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = []
        task = _build_task("TASK-1", "Task without forecast", original_status="To Do")

        # When
        result = TaskForecastChartUtils.flatten_task_data_hierarchy_for_table(task)

        # Then
        self.assertEqual(0.0, result[0].estimation_days)
        self.assertIsNone(result[0].forecast_end_date)

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldCarryForecastWindowIntoBreakdownItem(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = []
        task = _build_task("TASK-1", "Scheduled task", original_status="To Do", estimation_days=2.0,
                           start_date="2026-11-09T09:30:00", end_date="2026-11-11T09:30:00")

        # When
        result = TaskForecastChartUtils.flatten_task_data_hierarchy_for_table(task)

        # Then
        self.assertEqual(datetime(2026, 11, 9, 9, 30), result[0].forecast_start_date)
        self.assertEqual(datetime(2026, 11, 11, 9, 30), result[0].forecast_end_date)


def _build_task(task_id, title, original_status="To Do", estimation_days=None,
                url=None, children=None, system_metadata=None, start_date=None, end_date=None):
    if system_metadata is None and original_status is not None:
        system_metadata = SystemMetadataData(original_status=original_status, url=url)

    forecast = None
    if estimation_days is not None:
        forecast = ForecastData(estimation_time_days=estimation_days, start_date=start_date, end_date=end_date)

    return TaskData(
        id=task_id,
        title=title,
        assignment=AssignmentData(),
        time_tracking=TimeTrackingData(),
        system_metadata=system_metadata,
        child_tasks=children if children else None,
        child_tasks_count=len(children) if children else 0,
        forecast=forecast
    )
