from dataclasses import dataclass


@dataclass(slots=True)
class DeveloperSeriesData:
    name: str
    palette_slot: int
    shown: bool
