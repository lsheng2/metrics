from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class VelocityLevelThreshold:
    level_name: str
    threshold: float


@dataclass(slots=True)
class VelocityThresholdsData:
    thresholds: List[VelocityLevelThreshold]
