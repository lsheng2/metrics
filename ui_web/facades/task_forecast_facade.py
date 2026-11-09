from datetime import datetime
from typing import Optional, List, Tuple

from django.conf import settings
from sd_metrics_lib.utils.time import TimeUnit

from forecast.app.domain.model.enums import VelocityStrategy, StoryPointsStrategy, SubjectType, TaskScope
from forecast.app.domain.model.forecast import Subject, ForecastGenerationParameters
from ..convertors.task_convertor import TaskConvertor
from ..convertors.task_forecast_chart_convertor import TaskForecastChartConvertor
from ..convertors.task_forecast_convertor import TaskForecastConvertor
from ..data.chart_data import ChartData
from ..data.task_data import TaskData
from ..data.task_forecast_data import TaskForecastRequestData, TaskForecastSummaryData
from ..utils.task_forecast_chart_utils import TaskForecastChartUtils


class TaskForecastFacade:
    def __init__(self, forecast_api, task_forecast_convertor: TaskForecastConvertor,
                 task_convertor: TaskConvertor,
                 task_forecast_chart_convertor: TaskForecastChartConvertor):
        self.forecast_api = forecast_api
        self.task_forecast_convertor = task_forecast_convertor
        self.task_convertor = task_convertor
        self.task_forecast_chart_convertor = task_forecast_chart_convertor

    async def get_task_forecast_hierarchy_data(self, request_data: TaskForecastRequestData) -> List[TaskData]:
        root_task = await self._calculate_task_forecast(request_data)

        if not root_task:
            return []

        task_data = self.task_convertor.convert_task_to_data(root_task)

        if request_data.task_scope == TaskScope.ACTIVE_ONLY:
            self._remove_done_children(task_data)

        return [task_data]

    @staticmethod
    def _remove_done_children(task_data: TaskData) -> None:
        if not task_data.child_tasks:
            return

        active_children = []
        for child in task_data.child_tasks:
            if not TaskForecastChartUtils.is_task_data_done(child):
                TaskForecastFacade._remove_done_children(child)
                active_children.append(child)

        task_data.child_tasks = active_children if active_children else None

    @staticmethod
    def get_forecast_summary_from_data(task_data_list: List[TaskData]) -> Optional[TaskForecastSummaryData]:
        if not task_data_list:
            return None

        total_days = TaskForecastFacade._extract_total_estimation(task_data_list)
        first_task_velocity = TaskForecastFacade._extract_velocity(task_data_list)
        forecasted_start, forecasted_end = TaskForecastFacade._extract_forecast_dates(task_data_list)

        task_forecasts = []
        for task_data in task_data_list:
            task_forecasts.extend(TaskForecastChartUtils.flatten_task_data_hierarchy_for_table(task_data))

        completed_days, remaining_days = TaskForecastFacade._calculate_work_breakdown(task_forecasts)

        return TaskForecastSummaryData(
            total_estimation_days=total_days,
            forecasted_start_date=forecasted_start,
            forecasted_end_date=forecasted_end,
            average_team_velocity=first_task_velocity,
            task_forecasts=task_forecasts,
            completed_estimation_days=completed_days,
            remaining_estimation_days=remaining_days
        )

    def get_forecast_chart_from_data(self, task_data_list: List[TaskData]) -> Optional[ChartData]:
        return self.task_forecast_chart_convertor.convert_task_data_list_to_chart(task_data_list)

    async def _calculate_task_forecast(self, request_data: TaskForecastRequestData):
        subject = Subject(
            type=SubjectType.MEMBER_GROUP,
            id=request_data.member_group or "default"
        )

        forecast_start_date = datetime.now()
        if request_data.start_date:
            try:
                forecast_start_date = datetime.strptime(request_data.start_date, '%Y-%m-%d')
            except ValueError:
                forecast_start_date = datetime.now()

        parameters = ForecastGenerationParameters(
            velocity_strategy=VelocityStrategy.REAL_VELOCITY,
            story_points_strategy=StoryPointsStrategy.CUMULATIVE,
            subject=subject,
            time_unit=TimeUnit[settings.METRICS_DEFAULT_VELOCITY_TIME_UNIT],
            start_date=forecast_start_date,
            task_scope=request_data.task_scope
        )

        tasks = await self.forecast_api.generate_forecasts_for_task_ids([request_data.task_id], parameters)

        if not tasks:
            return None

        return tasks[0]

    @staticmethod
    def _extract_total_estimation(task_data_list: List[TaskData]) -> float:
        total_days = 0.0
        for task_data in task_data_list:
            if task_data.forecast and task_data.forecast.estimation_time_days:
                total_days += task_data.forecast.estimation_time_days
        return total_days

    @staticmethod
    def _extract_velocity(task_data_list: List[TaskData]) -> Optional[float]:
        for task_data in task_data_list:
            if task_data.forecast and task_data.forecast.velocity:
                return task_data.forecast.velocity
        return None

    @staticmethod
    def _extract_forecast_dates(task_data_list: List[TaskData]) -> Tuple[datetime, Optional[datetime]]:
        start_dates = []
        end_dates = []

        for task_data in task_data_list:
            if task_data.forecast and task_data.forecast.start_date:
                try:
                    start_dates.append(datetime.fromisoformat(task_data.forecast.start_date.replace('Z', '+00:00')))
                except:
                    pass
            if task_data.forecast and task_data.forecast.end_date:
                try:
                    end_dates.append(datetime.fromisoformat(task_data.forecast.end_date.replace('Z', '+00:00')))
                except:
                    pass

        forecasted_start = min(start_dates) if start_dates else datetime.now()
        forecasted_end = max(end_dates) if end_dates else None
        return forecasted_start, forecasted_end

    @staticmethod
    def _calculate_work_breakdown(task_forecasts: List) -> Tuple[float, float]:
        completed_days = 0.0
        remaining_days = 0.0
        for item in task_forecasts:
            if item.has_children:
                continue
            if item.is_done:
                completed_days += item.estimation_days
            else:
                remaining_days += item.estimation_days
        return completed_days, remaining_days
