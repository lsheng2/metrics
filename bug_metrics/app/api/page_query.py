from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Optional
from uuid import UUID

from django.conf import settings
from django.db.models import Q

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue

from .series import active_bug_trend_series


@dataclass(slots=True)
class BugTrendTicketListFilters:
    text: str = ''
    status: str = ''
    severity: str = ''
    owner: str = ''
    component: str = ''


@dataclass(slots=True)
class BugTrendPageQueryState:
    scope_id: int
    begin: date
    end: date
    calculation_run_id: str = ''
    selected_bucket_id: str = ''
    selected_series_name: str = ''
    list_filters: BugTrendTicketListFilters = field(default_factory=BugTrendTicketListFilters)
    active_chart_id: str = 'default_bug_trend'


@dataclass(slots=True)
class BugTrendEvidenceTicketRow:
    issue_key: str
    source_url: str
    summary: str
    series_name: str
    status: str
    severity: str
    owner: str
    component: str
    created_at: str
    updated_at: str
    extra_fields: Dict[str, str]
    extra_field_values: List[str]


@dataclass(slots=True)
class BugTrendEvidenceTicketResult:
    rows: List[BugTrendEvidenceTicketRow]
    total_count: int
    shown_count: int
    selection_title: str
    display_fields: List[str]


@dataclass(slots=True)
class BugTrendChartListSyncResult:
    is_consistent: bool
    mismatches: List[str]


class BugTrendPageQueryService:
    def __init__(self, get_scope: Callable, format_bucket_label: Callable):
        self._get_scope = get_scope
        self._format_bucket_label = format_bucket_label

    def get_evidence_tickets(self, state: BugTrendPageQueryState) -> BugTrendEvidenceTicketResult:
        scope = self._get_scope(state.scope_id)
        run = self._resolve_run(scope, state)
        if run is None:
            return BugTrendEvidenceTicketResult([], 0, 0, 'Evidence tickets for visible range', list(scope.display_fields))

        chart_memberships = self._chart_memberships(run, state)
        displayed_memberships = self._apply_list_filters(chart_memberships, state.list_filters)
        total_count = self._count_evidence(chart_memberships, state)
        display_fields = list(scope.display_fields)
        rows = self._build_evidence_rows(displayed_memberships, state, display_fields)
        return BugTrendEvidenceTicketResult(rows, total_count, len(rows), self._selection_title(run, state), display_fields)

    def validate_chart_list_sync(self, state: BugTrendPageQueryState) -> BugTrendChartListSyncResult:
        scope = self._get_scope(state.scope_id)
        run = self._resolve_run(scope, state)
        if run is None:
            return BugTrendChartListSyncResult(True, [])

        buckets = list(run.buckets.filter(bucket_start__gte=state.begin, bucket_end__lte=state.end).order_by('bucket_start'))
        memberships = self._chart_memberships(run, state, include_selection=False)
        counts_by_bucket_and_series = {}
        for membership in memberships:
            key = (str(membership.bucket_id), membership.series_name)
            counts_by_bucket_and_series[key] = counts_by_bucket_and_series.get(key, 0) + 1

        mismatches = []
        for bucket in buckets:
            expected_counts = self._expected_counts(scope, bucket)
            for series_name, expected_count in expected_counts.items():
                actual_count = counts_by_bucket_and_series.get((str(bucket.id), series_name), 0)
                if actual_count != expected_count:
                    mismatches.append(f'{self._format_bucket_label(bucket)} {series_name}: expected {expected_count}, found {actual_count}')
        return BugTrendChartListSyncResult(not mismatches, mismatches)

    def _resolve_run(self, scope, state: BugTrendPageQueryState):
        if not state.calculation_run_id:
            return None
        try:
            run_id = UUID(state.calculation_run_id)
        except ValueError:
            return None
        return scope.calculation_runs.filter(
            id=run_id,
            status='completed',
            config_version_hash=scope.config_version_hash,
            source_coverage_start__lte=state.begin,
            source_coverage_end__gte=state.end,
        ).first()

    def _expected_counts(self, scope, bucket) -> Dict[str, int]:
        return {series.series_name: series.count_value(bucket) for series in active_bug_trend_series(scope)}

    def _chart_memberships(self, run, state: BugTrendPageQueryState, include_selection: bool = True):
        memberships = BugTrendBucketIssue.objects.filter(
            calculation_run=run,
            bucket__bucket_start__gte=state.begin,
            bucket__bucket_end__lte=state.end,
        )
        if include_selection and state.selected_bucket_id:
            memberships = memberships.filter(bucket_id=state.selected_bucket_id)
        if include_selection and state.selected_series_name:
            memberships = memberships.filter(series_name=state.selected_series_name)
        return memberships.select_related('bucket').order_by('bucket__bucket_start', 'series_name', 'issue_key')

    def _apply_list_filters(self, memberships, filters: BugTrendTicketListFilters):
        if filters.status:
            memberships = memberships.filter(status=filters.status)
        if filters.severity:
            memberships = memberships.filter(severity_value=filters.severity)
        if filters.owner:
            memberships = memberships.filter(owner_value=filters.owner)
        if filters.component:
            memberships = memberships.filter(component_value=filters.component)
        if filters.text:
            memberships = memberships.filter(Q(summary__icontains=filters.text) | Q(issue_key__icontains=filters.text))
        return memberships

    def _build_evidence_row(self, membership, display_fields: List[str]) -> BugTrendEvidenceTicketRow:
        return BugTrendEvidenceTicketRow(
            issue_key=membership.issue_key,
            source_url=self._source_url(membership.issue_key),
            summary=membership.summary,
            series_name=membership.series_name,
            status=membership.status,
            severity=membership.severity_value,
            owner=membership.owner_value,
            component=membership.component_value,
            created_at=membership.created_at.isoformat() if membership.created_at else '',
            updated_at=membership.updated_at.isoformat() if membership.updated_at else '',
            extra_fields=membership.extra_fields_json,
            extra_field_values=[membership.extra_fields_json.get(field_name, '') for field_name in display_fields],
        )

    def _build_evidence_rows(self, memberships, state: BugTrendPageQueryState, display_fields: List[str]) -> List[BugTrendEvidenceTicketRow]:
        rows = [self._build_evidence_row(membership, display_fields) for membership in memberships]
        if state.selected_bucket_id or state.selected_series_name:
            return rows

        rows_by_issue_key = {}
        series_by_issue_key = {}
        for row in rows:
            rows_by_issue_key.setdefault(row.issue_key, row)
            series_by_issue_key.setdefault(row.issue_key, set()).add(row.series_name)

        distinct_rows = []
        for issue_key in sorted(rows_by_issue_key):
            row = rows_by_issue_key[issue_key]
            row.series_name = ', '.join(sorted(series_by_issue_key[issue_key]))
            distinct_rows.append(row)
        return distinct_rows

    def _count_evidence(self, memberships, state: BugTrendPageQueryState) -> int:
        if state.selected_bucket_id or state.selected_series_name:
            return memberships.count()
        return memberships.values('issue_key').distinct().count()

    def _source_url(self, issue_key: str) -> str:
        jira_server_url = settings.METRICS_JIRA_SERVER_URL
        if not jira_server_url:
            return ''
        return f'{jira_server_url.rstrip("/")}/browse/{issue_key}'

    def _selection_title(self, run, state: BugTrendPageQueryState) -> str:
        if not state.selected_bucket_id:
            return 'Evidence tickets for visible range'

        bucket = run.buckets.filter(id=state.selected_bucket_id).first()
        bucket_label = self._format_bucket_label(bucket) if bucket else 'selected bucket'
        if state.selected_series_name:
            return f'{state.selected_series_name} tickets for {bucket_label}'
        return f'Evidence tickets for {bucket_label}'