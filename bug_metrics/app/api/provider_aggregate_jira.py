from datetime import timedelta

from django.db.models import QuerySet

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue

from .provider_aggregate_contracts import FIRST_JIRA_PROFILE_ID


class JiraAggregateRowsMixin:
    def _build_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        if query.chart_id == 'component_bug':
            return self._component_bug_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        if query.chart_id == 'rolling_valid_bug':
            return self._rolling_valid_bug_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        if query.chart_id == 'open_bug_trend':
            return self._open_bug_trend_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        if query.chart_id == 'total_bug_trend':
            return self._total_bug_trend_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        if query.chart_id == 'open_bug_aging':
            return self._open_bug_aging_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)
        return self._daily_new_standard_bug_rows(query, scope, run, begin, end, fact_snapshot_id, source_population)

    def _component_bug_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        component_issue_keys = {}
        for membership in self._bucket_memberships(run, begin, end):
            component = membership.component_value or 'Unassigned'
            component_issue_keys.setdefault(component, set()).add(membership.issue_key)
        return [
            self._row(query, scope, run, fact_snapshot_id, source_population, 'component_bug_count', 'range', begin, end, query.begin_ww, '', {'component': component}, 'component_bug_count', len(issue_keys))
            for component, issue_keys in sorted(component_issue_keys.items())
        ]

    def _rolling_valid_bug_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        rows = []
        buckets = list(self._buckets(run, begin, end))
        valid_counts = [bucket.new_critical_high_count + bucket.new_medium_low_count for bucket in buckets]
        for index, bucket in enumerate(buckets):
            window = valid_counts[max(0, index - 3):index + 1]
            rows.append(self._row(query, scope, run, fact_snapshot_id, source_population, 'rolling_valid_bug_count', bucket.granularity, bucket.bucket_start, bucket.bucket_end, self._ww_label(bucket.bucket_start), '', {}, 'rolling_valid_bug_count', sum(window) / len(window), str(bucket.id)))
        return rows

    def _open_bug_trend_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        return [
            self._row(query, scope, run, fact_snapshot_id, source_population, fact.series, fact.bucket_grain, fact.bucket_start, fact.bucket_end, fact.bucket_ww, fact.bucket_date, fact.dimensions, fact.series, fact.value, fact.bucket_id)
            for fact in self._jira_fact_adapter.open_bug_trend_facts(scope, run, begin, end)
        ]

    def _total_bug_trend_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        rows = []
        metric_fields = [
            ('total_new_bugs', lambda bucket: bucket.new_critical_high_count + bucket.new_medium_low_count),
            ('total_open_bugs', lambda bucket: bucket.open_count),
            ('total_fixed_or_closed_bugs', lambda bucket: bucket.fixed_or_closed_count),
        ]
        for bucket in self._buckets(run, begin, end):
            for metric_id, value_for_bucket in metric_fields:
                rows.append(self._row(query, scope, run, fact_snapshot_id, source_population, metric_id, bucket.granularity, bucket.bucket_start, bucket.bucket_end, self._ww_label(bucket.bucket_start), '', {}, metric_id, value_for_bucket(bucket), str(bucket.id)))
        return rows

    def _open_bug_aging_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        buckets = list(self._buckets(run, begin, end))
        if not buckets:
            return []
        bucket = buckets[-1]
        aging_counts = {'aging_0_7_days': 0, 'aging_8_14_days': 0, 'aging_15_30_days': 0, 'aging_31_plus_days': 0}
        for membership in BugTrendBucketIssue.objects.filter(bucket=bucket, series_name='all_open_bugs'):
            if not membership.created_at:
                continue
            age_days = (bucket.bucket_end - membership.created_at.date()).days
            if age_days <= 7:
                aging_counts['aging_0_7_days'] += 1
            elif age_days <= 14:
                aging_counts['aging_8_14_days'] += 1
            elif age_days <= 30:
                aging_counts['aging_15_30_days'] += 1
            else:
                aging_counts['aging_31_plus_days'] += 1
        return [
            self._row(query, scope, run, fact_snapshot_id, source_population, metric_id, 'range', begin, end, query.begin_ww, '', {}, metric_id, value)
            for metric_id, value in aging_counts.items()
        ]

    def _daily_new_standard_bug_rows(self, query, scope, run, begin, end, fact_snapshot_id, source_population):
        rows = []
        issues = list(JiraIssue.objects.filter(scope=scope, is_in_current_scope=True))
        cursor = begin
        while cursor <= end:
            value = len([
                issue for issue in issues
                if self._is_bug(scope, issue) and issue.created_at and issue.created_at.date() == cursor
            ])
            rows.append(self._row(query, scope, run, fact_snapshot_id, source_population, 'daily_new_standard_bug_count', 'day', cursor, cursor, self._ww_label(cursor), cursor.isoformat(), {}, 'new_standard_bugs', value))
            cursor += timedelta(days=1)
        return rows

    def _jira_scope_for_profile(self, profile_id):
        query = JiraScopeConfig.objects.filter(enabled=True)
        scope = query.filter(name=profile_id).first()
        if scope:
            return scope
        if profile_id == FIRST_JIRA_PROFILE_ID:
            return query.filter(jql='project = "131600" AND component = "team_int_qemu"').first()
        return query.filter(name__iexact=profile_id).first()

    def jira_scope_for_profile(self, profile_id):
        return self._jira_scope_for_profile(profile_id)

    def _latest_authoritative_run(self, scope, begin, end):
        return BugTrendCalculationRun.objects.filter(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            config_version_hash=scope.config_version_hash,
            source_coverage_start__lte=begin,
            source_coverage_end__gte=end,
        ).order_by('-completed_at').first()

    def _latest_stale_run(self, scope, begin, end):
        return BugTrendCalculationRun.objects.filter(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            source_coverage_start__lte=begin,
            source_coverage_end__gte=end,
        ).exclude(config_version_hash=scope.config_version_hash).order_by('-completed_at').first()

    def _buckets(self, run, begin, end) -> QuerySet[BugTrendBucket]:
        return run.buckets.filter(bucket_start__gte=begin, bucket_end__lte=end).order_by('bucket_start')

    def _bucket_memberships(self, run, begin, end):
        return BugTrendBucketIssue.objects.filter(
            calculation_run=run,
            bucket__bucket_start__gte=begin,
            bucket__bucket_end__lte=end,
        )

    def _is_bug(self, scope, issue):
        return not scope.bug_type_values or issue.issue_type in scope.bug_type_values

    def _run_metadata(self, scope, run, freshness_status):
        return {
            'calculation_run_id': str(run.id),
            'run_config_version_hash': run.config_version_hash,
            'current_config_version_hash': scope.config_version_hash,
            'freshness_status': freshness_status,
            'source_coverage_start': run.source_coverage_start.isoformat(),
            'source_coverage_end': run.source_coverage_end.isoformat(),
            'completed_at': run.completed_at.isoformat() if run.completed_at else '',
        }

    def _ww_label(self, bucket_start):
        year, week, _ = bucket_start.isocalendar()
        return f'{str(year)[2:]}WW{week:02d}'
