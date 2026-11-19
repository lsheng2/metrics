import json
import unittest
from unittest.mock import patch

from ui_web.convertors.task_forecast_chart_convertor import TaskForecastChartConvertor
from ui_web.data.task_data import AssignmentData, ForecastData, SystemMetadataData, TaskData, TimeTrackingData
from ui_web.utils.chart_json_utils import ChartJsonUtils


class TestTaskForecastChartConvertor(unittest.TestCase):

    @patch("ui_web.utils.task_forecast_chart_utils.settings")
    def test_shouldDrawOnlyDatedTasksWithDayEstimatesAndDoneFlags(self, mock_settings):
        # Given
        mock_settings.METRICS_DONE_STATUS_CODES = ["Done"]
        undated_child = _build_task("CHILD-1", "Undated child", "To Do", 1.0)
        done_child = _build_task("CHILD-2", "Done child", "Done", 2.0, "2026-11-10T00:00:00", "2026-11-12T00:00:00")
        root = _build_task("ROOT-1", "Root", "In Progress", 20.5, "2026-11-09T00:00:00", "2026-11-22T00:00:00",
                           children=[undated_child, done_child])

        # When
        chart = TaskForecastChartConvertor().convert_task_data_list_to_chart([root])
        payload = json.loads(ChartJsonUtils.convert_chart_data_to_timeline_chartjs_json(chart))

        # Then
        self.assertEqual(["ROOT-1: Root (20.5d)", "CHILD-2: Done child (2.0d)"], payload["labels"])
        self.assertEqual([2, 1], [dataset["data"][0]["y"] for dataset in payload["datasets"]])
        self.assertEqual([False, True], [dataset["done"] for dataset in payload["datasets"]])

    def test_shouldReturnNoChartWhenNoTaskHasForecastDates(self):
        # Given
        root = _build_task("ROOT-1", "Root", "In Progress", 3.0)

        # When
        chart = TaskForecastChartConvertor().convert_task_data_list_to_chart([root])

        # Then
        self.assertIsNone(chart)


def _build_task(task_id, title, status, estimation_days, start_date=None, end_date=None, children=None):
    return TaskData(
        id=task_id,
        title=title,
        assignment=AssignmentData(),
        time_tracking=TimeTrackingData(),
        system_metadata=SystemMetadataData(original_status=status),
        child_tasks=children,
        child_tasks_count=len(children) if children else 0,
        forecast=ForecastData(estimation_time_days=estimation_days, start_date=start_date, end_date=end_date),
    )
