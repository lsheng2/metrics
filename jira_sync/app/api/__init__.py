from dataclasses import dataclass
from typing import List

from jira_sync.models import JiraSyncCursor


@dataclass(slots=True)
class JiraSyncHealth:
    scope_id: int
    scope_name: str
    status: str
    last_successful_sync_at: str
    last_jira_updated_cutoff: str
    earliest_reliable_bucket_start: str
    latest_reliable_bucket_end: str
    changelog_coverage_status: str
    materialized_config_version_hash: str
    current_config_version_hash: str
    last_error: str


class ApiForJiraSync:
    def get_status(self, scope_id: int) -> JiraSyncCursor:
        return JiraSyncCursor.objects.get(scope_id=scope_id)

    def list_sync_health(self) -> List[JiraSyncHealth]:
        return [self._to_health(cursor) for cursor in JiraSyncCursor.objects.select_related('scope').order_by('scope__name')]

    def _to_health(self, cursor: JiraSyncCursor) -> JiraSyncHealth:
        return JiraSyncHealth(
            scope_id=cursor.scope_id,
            scope_name=cursor.scope.name,
            status=cursor.status,
            last_successful_sync_at=cursor.last_successful_sync_at.isoformat() if cursor.last_successful_sync_at else '',
            last_jira_updated_cutoff=cursor.last_jira_updated_cutoff.isoformat() if cursor.last_jira_updated_cutoff else '',
            earliest_reliable_bucket_start=cursor.earliest_reliable_bucket_start.isoformat() if cursor.earliest_reliable_bucket_start else '',
            latest_reliable_bucket_end=cursor.latest_reliable_bucket_end.isoformat() if cursor.latest_reliable_bucket_end else '',
            changelog_coverage_status=cursor.changelog_coverage_status,
            materialized_config_version_hash=cursor.materialized_config_version_hash,
            current_config_version_hash=cursor.scope.config_version_hash,
            last_error=cursor.last_error,
        )


jira_sync_api = ApiForJiraSync()
