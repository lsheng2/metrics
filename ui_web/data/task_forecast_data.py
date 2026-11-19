from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

from forecast.app.domain.model.enums import TaskScope


@dataclass(slots=True)
class TaskForecastBreakdownItem:
    task_id: str
    task_title: str
    estimation_days: float
    level: int
    has_children: bool
    is_done: bool = False
    status: str = ""
    task_url: Optional[str] = None
    forecast_start_date: Optional[datetime] = None
    forecast_end_date: Optional[datetime] = None


@dataclass(slots=True)
class TaskForecastSummaryData:
    total_estimation_days: float
    forecasted_start_date: datetime
    forecasted_end_date: datetime
    average_team_velocity: Optional[float]
    task_forecasts: List[TaskForecastBreakdownItem]
    completed_estimation_days: float = 0.0
    remaining_estimation_days: float = 0.0

    @property
    def completed_share(self) -> float:
        scheduled_days = self.completed_estimation_days + self.remaining_estimation_days
        return self.completed_estimation_days / scheduled_days if scheduled_days else 0.0

    @property
    def has_nested_tasks(self) -> bool:
        return any(item.level > 1 for item in self.task_forecasts)


@dataclass(slots=True)
class TaskForecastRequestData:
    task_id: Optional[str] = None
    start_date: Optional[str] = None
    member_group: Optional[str] = None
    task_scope: TaskScope = TaskScope.ACTIVE_ONLY
