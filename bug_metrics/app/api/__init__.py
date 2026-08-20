from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from django.utils import timezone

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig
from jira_history.container import jira_history_container

from .page_query import (
    BugTrendChartListSyncResult,
    BugTrendEvidenceTicketResult,
    BugTrendPageQueryService,
    BugTrendPageQueryState,
    BugTrendTicketListFilters,
)
from .scope_audit import ScopeAudit, ScopeAuditService
from .series import active_bug_trend_series


@dataclass(slots=True)
class BugTrendDataset:
    series_name: str
    chart_type: str
    values: List[int]
    color: str


@dataclass(slots=True)
class BugTrendRunMetadata:
    calculation_run_id: str
    run_config_version_hash: str
    current_config_version_hash: str
    freshness_status: str
    source_coverage_start: str
    source_coverage_end: str
    completed_at: str


@dataclass(slots=True)
class BugTrendChart:
    scope_id: int
    calculation_run_id: Optional[str]
    labels: List[str]
    bucket_ids: List[str]
    datasets: List[BugTrendDataset]
    unavailable_reason: str = ''
    run_metadata: Optional[BugTrendRunMetadata] = None
    current_evidence_available: bool = False


class ApiForBugTrend:
    def __init__(self):
        self._page_query_service = BugTrendPageQueryService(
            self.get_scope,
            self._format_bucket_label,
        )
        self._scope_audit_service = ScopeAuditService()

    def list_enabled_scopes(self) -> List[JiraScopeConfig]:
        return list(JiraScopeConfig.objects.filter(enabled=True).order_by('ip', 'project_label', 'name'))

    def get_scope(self, scope_id: int) -> JiraScopeConfig:
        return JiraScopeConfig.objects.get(id=scope_id, enabled=True)

    def get_chart(self, scope_id: int, begin: date, end: date) -> BugTrendChart:
        scope = self.get_scope(scope_id)
        run = self._latest_authoritative_run(scope, begin, end)
        if run is None:
            stale_run = self._latest_stale_run(scope, begin, end)
            if stale_run:
                return BugTrendChart(
                    scope.id,
                    str(stale_run.id),
                    [],
                    [],
                    [],
                    'Calculation run does not match the current scope configuration. Recalculate this scope to refresh the Bug Trend chart.',
                    self._run_metadata(scope, stale_run, 'stale_config'),
                    current_evidence_available=False,
                )
            return BugTrendChart(scope.id, None, [], [], [], 'No completed calculation covers the selected range for the current scope configuration.', current_evidence_available=False)

        return self._chart_from_run(scope, run, begin, end)

    def get_chart_for_run(self, calculation_run_id: str, begin: date | None = None, end: date | None = None) -> BugTrendChart:
        run = BugTrendCalculationRun.objects.select_related('scope').get(
            id=calculation_run_id,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
        )
        scope = self.get_scope(run.scope_id)
        chart_begin = begin or run.source_coverage_start
        chart_end = end or run.source_coverage_end
        if run.config_version_hash != scope.config_version_hash:
            return BugTrendChart(scope.id, str(run.id), [], [], [], 'Calculation run does not match the current scope configuration.', self._run_metadata(scope, run, 'stale_config'), current_evidence_available=False)
        return self._chart_from_run(scope, run, chart_begin, chart_end)

    def _chart_from_run(self, scope: JiraScopeConfig, run: BugTrendCalculationRun, begin: date, end: date) -> BugTrendChart:
        if run.source_coverage_start > begin or run.source_coverage_end < end:
            return BugTrendChart(scope.id, str(run.id), [], [], [], 'Calculation run does not cover the selected range.', current_evidence_available=False)

        buckets = list(run.buckets.filter(bucket_start__gte=begin, bucket_end__lte=end).order_by('bucket_start'))
        return BugTrendChart(
            scope_id=scope.id,
            calculation_run_id=str(run.id),
            labels=[self._format_bucket_label(bucket) for bucket in buckets],
            bucket_ids=[str(bucket.id) for bucket in buckets],
            datasets=self._build_datasets(scope, buckets),
            run_metadata=self._run_metadata(scope, run, 'fresh'),
            current_evidence_available=True,
        )

    def get_evidence_tickets(self, state: BugTrendPageQueryState) -> BugTrendEvidenceTicketResult:
        return self._page_query_service.get_evidence_tickets(state)

    def validate_chart_list_sync(self, state: BugTrendPageQueryState) -> BugTrendChartListSyncResult:
        return self._page_query_service.validate_chart_list_sync(state)

    def get_scope_audit(self, scope_id: int) -> ScopeAudit:
        scope = self.get_scope(scope_id)
        facts = jira_history_container.jira_history_api.get_scope_audit_facts(scope)
        return self._scope_audit_service.build_scope_audit(scope, facts)

    def recalculate_scope(self, scope_id: int, coverage_start: date, coverage_end: date) -> BugTrendCalculationRun:
        scope = self.get_scope(scope_id)
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            config_version_hash=scope.config_version_hash,
            source_coverage_start=coverage_start,
            source_coverage_end=coverage_end,
            bucket_granularity=scope.bucket_granularity,
        )
        buckets = self._build_bucket_ranges(scope, coverage_start, coverage_end)
        history_api = jira_history_container.jira_history_api
        issues = history_api.list_issues(scope)
        transitions = history_api.list_status_resolution_transitions(scope)
        transitions_by_issue = self._group_transitions_by_issue(transitions)

        for bucket_start, bucket_end in buckets:
            bucket = self._create_bucket(scope, run, bucket_start, bucket_end, issues, transitions_by_issue)
            self._create_memberships(scope, run, bucket, issues, transitions_by_issue)

        run.status = BugTrendCalculationRun.STATUS_COMPLETED
        run.completed_at = timezone.now()
        run.save(update_fields=['status', 'completed_at'])
        return run

    def _latest_authoritative_run(self, scope: JiraScopeConfig, begin: date, end: date) -> Optional[BugTrendCalculationRun]:
        return BugTrendCalculationRun.objects.filter(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            config_version_hash=scope.config_version_hash,
            source_coverage_start__lte=begin,
            source_coverage_end__gte=end,
        ).order_by('-completed_at').first()

    def _latest_stale_run(self, scope: JiraScopeConfig, begin: date, end: date) -> Optional[BugTrendCalculationRun]:
        return BugTrendCalculationRun.objects.filter(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            source_coverage_start__lte=begin,
            source_coverage_end__gte=end,
        ).exclude(config_version_hash=scope.config_version_hash).order_by('-completed_at').first()

    def _run_metadata(self, scope: JiraScopeConfig, run: BugTrendCalculationRun, freshness_status: str) -> BugTrendRunMetadata:
        return BugTrendRunMetadata(
            calculation_run_id=str(run.id),
            run_config_version_hash=run.config_version_hash,
            current_config_version_hash=scope.config_version_hash,
            freshness_status=freshness_status,
            source_coverage_start=run.source_coverage_start.isoformat(),
            source_coverage_end=run.source_coverage_end.isoformat(),
            completed_at=run.completed_at.isoformat() if run.completed_at else '',
        )

    def _build_bucket_ranges(self, scope: JiraScopeConfig, coverage_start: date, coverage_end: date):
        ranges = []
        cursor = coverage_start
        while cursor <= coverage_end:
            if scope.bucket_granularity == JiraScopeConfig.GRANULARITY_WEEKLY:
                bucket_end = min(cursor + timedelta(days=6), coverage_end)
            else:
                bucket_end = cursor
            ranges.append((cursor, bucket_end))
            cursor = bucket_end + timedelta(days=1)
        return ranges

    def _create_bucket(self, scope, run, bucket_start, bucket_end, issues, transitions_by_issue):
        new_critical_high_keys = self._new_issue_keys(scope, issues, bucket_start, bucket_end, critical=True)
        new_medium_low_keys = self._new_issue_keys(scope, issues, bucket_start, bucket_end, critical=False)
        fixed_or_closed_keys = self._fixed_or_closed_issue_keys(scope, issues, transitions_by_issue, bucket_start, bucket_end)
        open_keys = self._open_issue_keys_at_bucket_end(scope, issues, transitions_by_issue, bucket_end)
        open_critical_high_keys = {issue.issue_key for issue in issues if issue.issue_key in open_keys and self._is_critical_high(scope, issue)}
        return BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=bucket_start,
            bucket_end=bucket_end,
            granularity=scope.bucket_granularity,
            new_critical_high_count=len(new_critical_high_keys),
            new_medium_low_count=len(new_medium_low_keys),
            fixed_or_closed_count=len(fixed_or_closed_keys),
            open_count=len(open_keys),
            open_critical_high_count=len(open_critical_high_keys),
        )

    def _create_memberships(self, scope, run, bucket, issues, transitions_by_issue):
        memberships_by_series = {
            'new_critical_high': self._new_issue_keys(scope, issues, bucket.bucket_start, bucket.bucket_end, critical=True),
            'new_medium_low': self._new_issue_keys(scope, issues, bucket.bucket_start, bucket.bucket_end, critical=False),
            'fixed_or_closed_bugs': self._fixed_or_closed_issue_keys(scope, issues, transitions_by_issue, bucket.bucket_start, bucket.bucket_end),
            'all_open_bugs': self._open_issue_keys_at_bucket_end(scope, issues, transitions_by_issue, bucket.bucket_end),
        }
        memberships_by_series['all_open_critical_high'] = {
            issue.issue_key for issue in issues
            if issue.issue_key in memberships_by_series['all_open_bugs'] and self._is_critical_high(scope, issue)
        }
        issue_by_key = {issue.issue_key: issue for issue in issues}
        for series in active_bug_trend_series(scope):
            issue_keys = memberships_by_series[series.series_name]
            for issue_key in sorted(issue_keys):
                issue = issue_by_key[issue_key]
                BugTrendBucketIssue.objects.create(
                    scope=scope,
                    bucket=bucket,
                    calculation_run=run,
                    series_name=series.series_name,
                    issue_key=issue_key,
                    summary=issue.summary,
                    status=issue.status,
                    severity_value=issue.severity_value,
                    owner_value=issue.owner_value,
                    component_value=issue.component_value,
                    created_at=issue.created_at,
                    updated_at=issue.updated_at,
                    extra_fields_json={field_name: self._display_field_value(issue.raw_fields_json.get(field_name)) for field_name in scope.display_fields},
                )

    def _new_issue_keys(self, scope, issues, bucket_start, bucket_end, critical: bool):
        return {
            issue.issue_key for issue in issues
            if self._is_bug(scope, issue)
            and issue.created_at
            and bucket_start <= self._local_date(scope, issue.created_at) <= bucket_end
            and self._matches_new_severity(scope, issue, critical)
        }

    def _fixed_or_closed_issue_keys(self, scope, issues, transitions_by_issue, bucket_start, bucket_end):
        terminal_values = set(scope.fixed_status_values + scope.closed_status_values + scope.fixed_resolution_values + scope.closed_resolution_values)
        issue_by_key = {issue.issue_key: issue for issue in issues}
        return {
            issue_key for issue_key, transitions in transitions_by_issue.items()
            if issue_key in issue_by_key
            and self._is_bug(scope, issue_by_key[issue_key])
            and any(bucket_start <= self._local_date(scope, transition.transitioned_at) <= bucket_end and transition.to_value in terminal_values for transition in transitions)
        }

    def _open_issue_keys_at_bucket_end(self, scope, issues, transitions_by_issue, bucket_end):
        end_datetime = datetime.combine(bucket_end, time.max, tzinfo=self._scope_timezone(scope))
        terminal_status_values = set(scope.fixed_status_values + scope.closed_status_values + scope.terminal_excluded_status_values)
        terminal_resolution_values = set(scope.fixed_resolution_values + scope.closed_resolution_values)
        open_keys = set()
        for issue in issues:
            if not self._is_bug(scope, issue) or not issue.created_at or self._local_datetime(scope, issue.created_at) > end_datetime:
                continue
            latest_status = self._latest_status_at(issue, transitions_by_issue.get(issue.issue_key, []), end_datetime)
            latest_resolution = self._latest_resolution_at(issue, transitions_by_issue.get(issue.issue_key, []), end_datetime)
            if self._is_open_status(scope, latest_status) and latest_status not in terminal_status_values and latest_resolution not in terminal_resolution_values:
                open_keys.add(issue.issue_key)
        return open_keys

    def _is_open_status(self, scope, status):
        return not scope.open_status_values or status in scope.open_status_values

    def _latest_status_at(self, issue, transitions, end_datetime):
        status_transitions = sorted(
            [transition for transition in transitions if transition.field == 'status'],
            key=lambda item: item.transitioned_at,
        )
        latest_status = issue.status
        for transition in status_transitions:
            transitioned_at = self._local_datetime(issue.scope, transition.transitioned_at)
            if transitioned_at <= end_datetime:
                latest_status = transition.to_value
            else:
                return transition.from_value or latest_status
        return latest_status

    def _latest_resolution_at(self, issue, transitions, end_datetime):
        resolution_transitions = sorted(
            [transition for transition in transitions if transition.field == 'resolution'],
            key=lambda item: item.transitioned_at,
        )
        latest_resolution = issue.resolution_value if issue.resolved_at and self._local_datetime(issue.scope, issue.resolved_at) <= end_datetime else ''
        for transition in resolution_transitions:
            transitioned_at = self._local_datetime(issue.scope, transition.transitioned_at)
            if transitioned_at <= end_datetime:
                latest_resolution = transition.to_value
            else:
                return transition.from_value or latest_resolution
        return latest_resolution

    def _is_bug(self, scope, issue):
        return not scope.bug_type_values or issue.issue_type in scope.bug_type_values

    def _is_critical_high(self, scope, issue):
        return bool(scope.critical_high_values and issue.severity_value in scope.critical_high_values)

    def _matches_new_severity(self, scope, issue, critical: bool):
        if critical:
            return self._is_critical_high(scope, issue)
        if scope.medium_low_values:
            return issue.severity_value in scope.medium_low_values
        return not self._is_critical_high(scope, issue)

    def _local_date(self, scope, value):
        return self._local_datetime(scope, value).date()

    def _local_datetime(self, scope, value):
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone=timezone.utc)
        return value.astimezone(self._scope_timezone(scope))

    def _scope_timezone(self, scope):
        return ZoneInfo(scope.timezone or 'UTC')

    def _group_transitions_by_issue(self, transitions):
        grouped = {}
        for transition in transitions:
            grouped.setdefault(transition.issue_key, []).append(transition)
        return grouped

    def _build_datasets(self, scope: JiraScopeConfig, buckets: List[BugTrendBucket]) -> List[BugTrendDataset]:
        return [
            BugTrendDataset(series.series_name, series.chart_type, series.chart_values(buckets), series.color)
            for series in active_bug_trend_series(scope)
        ]

    def _format_bucket_label(self, bucket: BugTrendBucket) -> str:
        if bucket.granularity == JiraScopeConfig.GRANULARITY_WEEKLY:
            year, week, _ = bucket.bucket_start.isocalendar()
            return f'{str(year)[2:]}WW{week:02d}'
        return bucket.bucket_start.isoformat()

    def _display_field_value(self, raw_value):
        if raw_value is None:
            return ''
        if isinstance(raw_value, list):
            return ', '.join(self._display_field_value(item) for item in raw_value if item is not None)
        if isinstance(raw_value, dict):
            return raw_value.get('name') or raw_value.get('displayName') or raw_value.get('value') or raw_value.get('key') or ''
        return str(raw_value)


bug_trend_api = ApiForBugTrend()
