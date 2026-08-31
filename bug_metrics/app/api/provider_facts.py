from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from bug_metrics.models import BugTrendBucket, JiraScopeConfig

from .series import active_bug_trend_series


@dataclass(frozen=True, slots=True)
class CanonicalChartInputFact:
    chart_id: str
    series: str
    value: float
    bucket_grain: str
    bucket_start: date
    bucket_end: date
    bucket_ww: str
    bucket_date: str
    bucket_id: str
    dimensions: dict[str, str]
    source_item_ids: list[str]
    canonical_fields: dict[str, Any]
    project_fields: dict[str, Any]
    provider_fields: dict[str, Any]


class JiraCalculationRunFactAdapter:
    def open_bug_trend_facts(self, scope: JiraScopeConfig, run, begin: date, end: date) -> list[CanonicalChartInputFact]:
        return [
            CanonicalChartInputFact(
                chart_id='open_bug_trend',
                series=series.series_name,
                value=series.count_value(bucket) * series.chart_sign,
                bucket_grain=bucket.granularity,
                bucket_start=bucket.bucket_start,
                bucket_end=bucket.bucket_end,
                bucket_ww=self._ww_label(bucket.bucket_start),
                bucket_date='',
                bucket_id=str(bucket.id),
                dimensions={},
                source_item_ids=[],
                canonical_fields={
                    'submitted_date': bucket.bucket_start.isoformat(),
                    'updated_date': bucket.bucket_end.isoformat(),
                    'implemented_date': bucket.bucket_end.isoformat(),
                    'closed_date': bucket.bucket_end.isoformat(),
                    'status': 'bucketed',
                    'severity': 'bucketed',
                    'exposure': 'bucketed',
                },
                project_fields={
                    'scope_id': str(scope.id),
                    'scope_name': scope.name,
                    'ip': scope.ip,
                    'project_or_product': scope.project_label,
                    'milestone': scope.milestone_field,
                },
                provider_fields={
                    'provider': 'jira',
                    'bucket_id': str(bucket.id),
                },
            )
            for bucket in self._buckets(run, begin, end)
            for series in active_bug_trend_series(scope)
        ]

    def _buckets(self, run, begin: date, end: date):
        return run.buckets.filter(bucket_start__gte=begin, bucket_end__lte=end).order_by('bucket_start')

    def _ww_label(self, bucket_start: date) -> str:
        year, week, _ = bucket_start.isocalendar()
        return f'{str(year)[2:]}WW{week:02d}'


class HsdesCanonicalFactAdapter:
    def open_bug_trend_facts(self, facts: list[dict], begin: date, end: date) -> list[CanonicalChartInputFact]:
        chart_facts = []
        for bucket_start, bucket_end in self._week_ranges(begin, end):
            values = {
                'all_open_bugs': self._open_bug_count(facts, bucket_end),
                'all_open_critical_high': self._open_bug_count(facts, bucket_end, critical_high=True),
                'new_critical_high': self._new_bug_count(facts, bucket_start, bucket_end, critical_high=True),
                'new_medium_low': self._new_bug_count(facts, bucket_start, bucket_end, medium_low=True),
                'fixed_or_closed_bugs': -self._closed_bug_count(facts, bucket_start, bucket_end),
            }
            for series, value in values.items():
                chart_facts.append(CanonicalChartInputFact(
                    chart_id='open_bug_trend',
                    series=series,
                    value=value,
                    bucket_grain='week',
                    bucket_start=bucket_start,
                    bucket_end=bucket_end,
                    bucket_ww=self._ww_label(bucket_start),
                    bucket_date='',
                    bucket_id='',
                    dimensions={},
                    source_item_ids=[],
                    canonical_fields={
                        'submitted_date': bucket_start.isoformat(),
                        'updated_date': bucket_end.isoformat(),
                        'implemented_date': bucket_end.isoformat(),
                        'closed_date': bucket_end.isoformat(),
                        'status': 'bucketed',
                        'severity': 'bucketed',
                        'exposure': 'bucketed',
                    },
                    project_fields={},
                    provider_fields={'provider': 'hsdes'},
                ))
        return chart_facts

    def _week_ranges(self, begin: date, end: date):
        bucket_start = begin
        while bucket_start <= end:
            bucket_end = min(bucket_start + timedelta(days=6), end)
            yield bucket_start, bucket_end
            bucket_start += timedelta(days=7)

    def _ww_label(self, bucket_start: date) -> str:
        year, week, _ = bucket_start.isocalendar()
        return f'{str(year)[2:]}WW{week:02d}'

    def _bug_facts(self, facts):
        return [
            fact for fact in facts
            if fact.get('canonical_fields', {}).get('source_item_type') == 'bug'
        ]

    def _new_bug_count(self, facts, begin: date, end: date, critical_high=False, medium_low=False):
        return len([
            fact for fact in self._bug_facts(facts)
            if self._created_between(fact, begin, end)
            and self._matches_severity(fact, critical_high, medium_low)
        ])

    def _open_bug_count(self, facts, bucket_end: date, critical_high=False):
        return len([
            fact for fact in self._bug_facts(facts)
            if self._is_open_at(fact, bucket_end)
            and self._matches_severity(fact, critical_high, False)
        ])

    def _closed_bug_count(self, facts, begin: date, end: date):
        return len([
            fact for fact in self._bug_facts(facts)
            if self._closed_between(fact, begin, end)
        ])

    def _created_between(self, fact, begin: date, end: date) -> bool:
        created_at = self._date_from_iso(fact.get('canonical_fields', {}).get('created_at', ''))
        return bool(created_at and begin <= created_at <= end)

    def _closed_between(self, fact, begin: date, end: date) -> bool:
        closed_at = self._closed_at(fact)
        return bool(closed_at and begin <= closed_at <= end)

    def _is_open_at(self, fact, bucket_end: date) -> bool:
        created_at = self._date_from_iso(fact.get('canonical_fields', {}).get('created_at', ''))
        closed_at = self._closed_at(fact)
        return bool(created_at and created_at <= bucket_end and (not closed_at or closed_at > bucket_end))

    def _closed_at(self, fact):
        canonical_fields = fact.get('canonical_fields', {})
        return self._date_from_iso(canonical_fields.get('closed_at', '')) or self._date_from_iso(canonical_fields.get('resolved_at', ''))

    def _matches_severity(self, fact, critical_high, medium_low) -> bool:
        if not critical_high and not medium_low:
            return True
        severity = fact.get('canonical_fields', {}).get('severity_or_priority', '').lower()
        is_critical_high = any(token in severity for token in ['critical', 'high', 'p1', 'p2'])
        return is_critical_high if critical_high else not is_critical_high

    def _date_from_iso(self, value):
        if not value:
            return None
        return date.fromisoformat(value[:10])
