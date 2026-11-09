from forecast.app.domain.model.enums import TaskScope

from ..data.task_forecast_data import TaskForecastRequestData


class TaskForecastConvertor:

    @staticmethod
    def extract_request_data_from_request(request) -> TaskForecastRequestData:
        return TaskForecastRequestData(
            task_id=(request.GET.get('task_id') or '').strip() or None,
            start_date=request.GET.get('start_date') or None,
            member_group=request.GET.get('member_group') or None,
            task_scope=TaskForecastConvertor._parse_task_scope(request.GET.get('include_done_tasks'))
        )

    @staticmethod
    def _parse_task_scope(include_done_value: str) -> TaskScope:
        if include_done_value == 'true':
            return TaskScope.ALL
        return TaskScope.ACTIVE_ONLY
