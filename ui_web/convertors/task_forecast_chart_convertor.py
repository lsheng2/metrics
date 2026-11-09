from datetime import datetime, timedelta
from typing import List, Optional

from ..data.chart_data import ChartData, ChartDatasetData
from ..data.task_data import TaskData
from ..utils.task_forecast_chart_utils import TaskForecastChartUtils

_CHART_DATE_PADDING = timedelta(days=1)


class TaskForecastChartConvertor:

    def convert_task_data_list_to_chart(self, task_data_list: List[TaskData]) -> Optional[ChartData]:
        if not task_data_list:
            return None

        chart_tasks = self._collect_chart_tasks(task_data_list)

        if not chart_tasks:
            return None

        chart_data_dict = self._prepare_chart_data_from_task_data(chart_tasks)

        datasets = [
            ChartDatasetData(
                label=dataset.get('label', ''),
                data=dataset.get('data', []),
                is_done=dataset.get('done', False)
            )
            for dataset in chart_data_dict.get('datasets', [])
        ]

        if not datasets:
            return None

        return ChartData(
            labels=chart_data_dict.get('labels', []),
            datasets=datasets,
            min_date=chart_data_dict.get('min_date'),
            max_date=chart_data_dict.get('max_date')
        )

    @staticmethod
    def _collect_chart_tasks(task_data_list: List[TaskData]) -> List[TaskData]:
        chart_tasks = []
        for task_data in task_data_list:
            chart_tasks.append(task_data)
            if task_data.child_tasks:
                chart_tasks.extend(task_data.child_tasks)
        return chart_tasks

    def _prepare_chart_data_from_task_data(self, task_data_list: List[TaskData]):
        chart_date_range = self._calculate_chart_date_range_from_task_data(task_data_list)
        chart_datasets = self._build_chart_datasets_from_task_data(task_data_list)

        return {
            'labels': [dataset['label'] for dataset in chart_datasets],
            'datasets': chart_datasets,
            'min_date': chart_date_range['min_date'].isoformat(),
            'max_date': chart_date_range['max_date'].isoformat()
        }

    @staticmethod
    def _calculate_chart_date_range_from_task_data(task_data_list: List[TaskData]):
        task_dates = []
        for task_data in task_data_list:
            if task_data.forecast and task_data.forecast.start_date and task_data.forecast.end_date:
                try:
                    start_date = datetime.fromisoformat(task_data.forecast.start_date.replace('Z', '+00:00'))
                    end_date = datetime.fromisoformat(task_data.forecast.end_date.replace('Z', '+00:00'))
                    task_dates.extend([start_date, end_date])
                except:
                    pass

        if not task_dates:
            current_date = datetime.now().date()
            return {
                'min_date': current_date - timedelta(days=7),
                'max_date': current_date + timedelta(days=7)
            }

        min_task_date = min(task_dates)
        max_task_date = max(task_dates)

        return {
            'min_date': min_task_date - _CHART_DATE_PADDING,
            'max_date': max_task_date + _CHART_DATE_PADDING
        }

    def _build_chart_datasets_from_task_data(self, task_data_list: List[TaskData]):
        dated_tasks = [task_data for task_data in task_data_list if self._task_data_has_forecast_dates(task_data)]
        return [
            self._create_task_data_chart_dataset(
                task_data, task_index, len(dated_tasks), TaskForecastChartUtils.is_task_data_done(task_data)
            )
            for task_index, task_data in enumerate(dated_tasks)
        ]

    @staticmethod
    def _task_data_has_forecast_dates(task_data: TaskData) -> bool:
        return (task_data.forecast and
                task_data.forecast.start_date and
                task_data.forecast.end_date)

    @staticmethod
    def _create_task_data_chart_dataset(task_data: TaskData, task_index: int, total_tasks: int, is_done: bool):
        estimation_days = task_data.forecast.estimation_time_days or 0.0
        task_label = f"{task_data.id}: {task_data.title} ({estimation_days:.1f}d)"
        task_y_position = total_tasks - task_index

        return {
            'label': task_label,
            'data': [
                {
                    'x': task_data.forecast.start_date,
                    'y': task_y_position
                },
                {
                    'x': task_data.forecast.end_date,
                    'y': task_y_position
                }
            ],
            'done': is_done
        }
