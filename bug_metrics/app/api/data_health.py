from dataclasses import dataclass
from typing import List

from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig


@dataclass(slots=True)
class BugTrendCalculationHealth:
    scope_id: int
    scope_name: str
    status: str
    freshness_status: str
    calculation_run_id: str
    run_config_version_hash: str
    current_config_version_hash: str
    source_coverage_start: str
    source_coverage_end: str
    completed_at: str


class BugTrendCalculationHealthService:
    def list_calculation_health(self) -> List[BugTrendCalculationHealth]:
        return [self._calculation_health_for_scope(scope) for scope in JiraScopeConfig.objects.filter(enabled=True).order_by('name')]

    def _calculation_health_for_scope(self, scope: JiraScopeConfig) -> BugTrendCalculationHealth:
        run = scope.calculation_runs.order_by('-started_at').first()
        if run is None:
            return BugTrendCalculationHealth(scope.id, scope.name, 'no_run', 'missing', '', '', scope.config_version_hash, '', '', '')
        freshness_status = 'fresh' if run.status == BugTrendCalculationRun.STATUS_COMPLETED and run.config_version_hash == scope.config_version_hash else 'stale_config'
        if run.status != BugTrendCalculationRun.STATUS_COMPLETED:
            freshness_status = run.status
        return BugTrendCalculationHealth(
            scope_id=scope.id,
            scope_name=scope.name,
            status=run.status,
            freshness_status=freshness_status,
            calculation_run_id=str(run.id),
            run_config_version_hash=run.config_version_hash,
            current_config_version_hash=scope.config_version_hash,
            source_coverage_start=run.source_coverage_start.isoformat(),
            source_coverage_end=run.source_coverage_end.isoformat(),
            completed_at=run.completed_at.isoformat() if run.completed_at else '',
        )