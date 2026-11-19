from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class VelocitySummaryData:
    period_count: int
    average_velocity: float
    latest_period: str
    latest_velocity: float
    latest_change: Optional[float]
    total_story_points: float
    best_period: str
    best_velocity: float
