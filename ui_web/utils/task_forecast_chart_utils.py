from datetime import datetime
from typing import List, Optional

from django.conf import settings

from ..data.task_data import TaskData
from ..data.task_forecast_data import TaskForecastBreakdownItem


class TaskForecastChartUtils:

    @staticmethod
    def flatten_task_data_hierarchy_for_table(task_data: TaskData, level: int = 0) -> List[TaskForecastBreakdownItem]:
        tasks = []

        has_children = task_data.child_tasks is not None and len(task_data.child_tasks) > 0

        tasks.append(TaskForecastChartUtils._create_breakdown_item(task_data, level, has_children))

        if task_data.child_tasks:
            for child in task_data.child_tasks:
                tasks.extend(TaskForecastChartUtils.flatten_task_data_hierarchy_for_table(child, level + 1))

        return tasks

    @staticmethod
    def is_task_data_done(task_data: TaskData) -> bool:
        if not task_data.system_metadata or not task_data.system_metadata.original_status:
            return False

        return task_data.system_metadata.original_status in settings.METRICS_DONE_STATUS_CODES

    @staticmethod
    def _create_breakdown_item(task_data: TaskData, level: int,
                                has_children: bool) -> TaskForecastBreakdownItem:
        forecast = task_data.forecast
        estimation_days = 0.0
        if forecast and forecast.estimation_time_days:
            estimation_days = forecast.estimation_time_days

        status = ""
        if task_data.system_metadata and task_data.system_metadata.original_status:
            status = task_data.system_metadata.original_status

        task_url = None
        if task_data.system_metadata:
            task_url = task_data.system_metadata.url

        return TaskForecastBreakdownItem(
            task_id=task_data.id,
            task_title=task_data.title,
            estimation_days=estimation_days,
            level=level,
            has_children=has_children,
            is_done=TaskForecastChartUtils.is_task_data_done(task_data),
            status=status,
            task_url=task_url,
            forecast_start_date=TaskForecastChartUtils._parse_forecast_date(forecast.start_date if forecast else None),
            forecast_end_date=TaskForecastChartUtils._parse_forecast_date(forecast.end_date if forecast else None)
        )

    @staticmethod
    def _parse_forecast_date(value: Optional[str]) -> Optional[datetime]:
        return datetime.fromisoformat(value) if value else None
