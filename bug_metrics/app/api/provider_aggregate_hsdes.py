import hashlib
from datetime import timedelta

from .provider_aggregate_common import provider_query_range_mode


class HsdesAggregateRowsMixin:
    def _build_hsdes_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        if query.chart_id == 'component_bug':
            return self._hsdes_component_bug_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        if query.chart_id == 'rolling_valid_bug':
            return self._hsdes_rolling_valid_bug_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        if query.chart_id == 'open_bug_trend':
            return self._hsdes_open_bug_trend_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        if query.chart_id == 'total_bug_trend':
            return self._hsdes_total_bug_trend_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        if query.chart_id == 'open_bug_aging':
            return self._hsdes_open_bug_aging_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)
        return self._hsdes_daily_new_standard_bug_rows(query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id)

    def _hsdes_component_bug_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        component_issue_ids = {}
        for fact in self._hsdes_bug_facts(facts):
            canonical_fields = fact.get('canonical_fields', {})
            created_at = self._date_from_iso(canonical_fields.get('created_at', ''))
            if created_at and not begin <= created_at <= end:
                continue
            component = canonical_fields.get('component_or_area') or 'Unassigned'
            component_issue_ids.setdefault(component, set()).add(fact.get('source_item_id', ''))
        return [
            self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'component_bug_count', 'range', begin, end, query.begin_ww, '', {'component': component}, 'component_bug_count', len(issue_ids))
            for component, issue_ids in sorted(component_issue_ids.items())
        ]

    def _hsdes_rolling_valid_bug_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        rows = []
        previous_counts = []
        for bucket_start, bucket_end in self._week_ranges(begin, end):
            valid_count = self._hsdes_new_bug_count(facts, bucket_start, bucket_end)
            previous_counts.append(valid_count)
            rolling_window = previous_counts[max(0, len(previous_counts) - 4):]
            rows.append(self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'rolling_valid_bug_count', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'rolling_valid_bug_count', sum(rolling_window) / len(rolling_window), self._hsdes_bucket_id(query, 'rolling_valid_bug_count', bucket_start)))
        return rows

    def _hsdes_open_bug_trend_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        return [
            self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, fact.series, fact.bucket_grain, fact.bucket_start, fact.bucket_end, fact.bucket_ww, fact.bucket_date, fact.dimensions, fact.series, fact.value, self._hsdes_bucket_id(query, fact.series, fact.bucket_start))
            for fact in self._hsdes_fact_adapter.open_bug_trend_facts(facts, begin, end)
        ]

    def _hsdes_total_bug_trend_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        rows = []
        for bucket_start, bucket_end in self._week_ranges(begin, end):
            rows.extend([
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'total_new_bugs', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'total_new_bugs', self._hsdes_new_bug_count(facts, bucket_start, bucket_end), self._hsdes_bucket_id(query, 'total_new_bugs', bucket_start)),
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'total_open_bugs', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'total_open_bugs', self._hsdes_open_bug_count(facts, bucket_end), self._hsdes_bucket_id(query, 'total_open_bugs', bucket_start)),
                self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'total_fixed_or_closed_bugs', 'week', bucket_start, bucket_end, self._ww_label(bucket_start), '', {}, 'total_fixed_or_closed_bugs', self._hsdes_closed_bug_count(facts, bucket_start, bucket_end), self._hsdes_bucket_id(query, 'total_fixed_or_closed_bugs', bucket_start)),
            ])
        return rows

    def _hsdes_open_bug_aging_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        aging_counts = {'aging_0_7_days': 0, 'aging_8_14_days': 0, 'aging_15_30_days': 0, 'aging_31_plus_days': 0}
        for fact in self._hsdes_bug_facts(facts):
            canonical_fields = fact.get('canonical_fields', {})
            created_at = self._date_from_iso(canonical_fields.get('created_at', ''))
            if not created_at or not self._hsdes_is_open_at(fact, end):
                continue
            age_days = (end - created_at).days
            if age_days <= 7:
                aging_counts['aging_0_7_days'] += 1
            elif age_days <= 14:
                aging_counts['aging_8_14_days'] += 1
            elif age_days <= 30:
                aging_counts['aging_15_30_days'] += 1
            else:
                aging_counts['aging_31_plus_days'] += 1
        return [
            self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, metric_id, 'range', begin, end, query.begin_ww, '', {}, metric_id, value)
            for metric_id, value in aging_counts.items()
        ]

    def _hsdes_daily_new_standard_bug_rows(self, query, facts, begin, end, source_population, fact_snapshot_id, calculation_run_id):
        rows = []
        cursor = begin
        while cursor <= end:
            rows.append(self._hsdes_row(query, source_population, fact_snapshot_id, calculation_run_id, 'daily_new_standard_bug_count', 'day', cursor, cursor, self._ww_label(cursor), cursor.isoformat(), {}, 'new_standard_bugs', self._hsdes_new_bug_count(facts, cursor, cursor), self._hsdes_bucket_id(query, 'new_standard_bugs', cursor)))
            cursor += timedelta(days=1)
        return rows

    def _week_ranges(self, begin, end):
        bucket_start = begin
        while bucket_start <= end:
            bucket_end = min(bucket_start + timedelta(days=6), end)
            yield bucket_start, bucket_end
            bucket_start += timedelta(days=7)

    def _hsdes_bug_facts(self, facts):
        return [fact for fact in facts if fact.get('canonical_fields', {}).get('source_item_type') == 'bug']

    def _hsdes_new_bug_count(self, facts, begin, end, critical_high=False, medium_low=False):
        return len([
            fact for fact in self._hsdes_bug_facts(facts)
            if self._hsdes_created_between(fact, begin, end)
            and self._hsdes_matches_severity(fact, critical_high, medium_low)
        ])

    def _hsdes_open_bug_count(self, facts, bucket_end, critical_high=False):
        return len([
            fact for fact in self._hsdes_bug_facts(facts)
            if self._hsdes_is_open_at(fact, bucket_end)
            and self._hsdes_matches_severity(fact, critical_high, False)
        ])

    def _hsdes_closed_bug_count(self, facts, begin, end):
        return len([fact for fact in self._hsdes_bug_facts(facts) if self._hsdes_closed_between(fact, begin, end)])

    def _hsdes_created_between(self, fact, begin, end):
        created_at = self._date_from_iso(fact.get('canonical_fields', {}).get('created_at', ''))
        return bool(created_at and begin <= created_at <= end)

    def _hsdes_closed_between(self, fact, begin, end):
        closed_at = self._hsdes_closed_at(fact)
        return bool(closed_at and begin <= closed_at <= end)

    def _hsdes_is_open_at(self, fact, bucket_end):
        created_at = self._date_from_iso(fact.get('canonical_fields', {}).get('created_at', ''))
        closed_at = self._hsdes_closed_at(fact)
        return bool(created_at and created_at <= bucket_end and (not closed_at or closed_at > bucket_end))

    def _hsdes_closed_at(self, fact):
        canonical_fields = fact.get('canonical_fields', {})
        return self._date_from_iso(canonical_fields.get('closed_at', '')) or self._date_from_iso(canonical_fields.get('resolved_at', ''))

    def _hsdes_matches_severity(self, fact, critical_high, medium_low):
        if not critical_high and not medium_low:
            return True
        severity = fact.get('canonical_fields', {}).get('severity_or_priority', '').lower()
        is_critical_high = any(token in severity for token in ['critical', 'high', 'p1', 'p2'])
        return is_critical_high if critical_high else not is_critical_high

    def _hsdes_bucket_id(self, query, metric_id, bucket_start):
        return f'{query.profile_id}:{query.chart_id}:{metric_id}:{bucket_start.isoformat()}'

    def _range_identity(self, query, begin, end):
        if provider_query_range_mode(query) == 'date':
            return f'{begin.isoformat()}-{end.isoformat()}'
        return f'{query.begin_ww}-{query.end_ww}'

    def _hsdes_fact_snapshot_id(self, query, facts):
        payload = '|'.join(sorted(f'{fact.get("source_item_id", "")}:{fact.get("source_item_revision", "")}' for fact in facts))
        digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]
        return f'hsdes-profile-{query.profile_id}-{digest}'
