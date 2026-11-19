from datetime import UTC, datetime

from django.db import IntegrityError, transaction
from django.test import TestCase


def publication_values(tool_call_id, **changes):
    values = {
        'tool_call_id': tool_call_id,
        'approval_id': f'approval-{tool_call_id}',
        'run_id': 'run-1',
        'decided_by': 'synthetic-user',
        'decided_at': datetime(2026, 11, 16, tzinfo=UTC),
        'preview_digest': 'a' * 64,
        'data_fingerprint': 'b' * 64,
        'normalized_render_config': {'dashboard_uid': 'metrics-ai-synthetic', 'sections': []},
        'provider_id': 'jira',
        'profile_id': 'synthetic-jira',
        'chart_id': 'open_bug_trend',
        'chart_version': 1,
        'requested_series': ['new_critical_high'],
        'range_mode': 'ww',
        'range_start': '26WW32',
        'range_end': '26WW35',
        'dashboard_uid': 'metrics-ai-synthetic',
        'title': 'Synthetic dashboard',
        'visualization': 'timeseries',
        'grafana_base_url': 'http://127.0.0.1:39999',
        'grafana_url': 'http://127.0.0.1:39999/d/metrics-ai-synthetic/',
        'correlation_id': 'correlation-1',
        'status': 'published',
    }
    return {**values, **changes}


class TestAiChartPublication(TestCase):
    def test_tool_call_is_unique_and_keeps_approved_provenance(self):
        from bug_metrics.models import AiChartPublication

        row = AiChartPublication.objects.create(**publication_values('call-1'))
        row.refresh_from_db()
        self.assertEqual('approval-call-1', row.approval_id)
        self.assertEqual('synthetic-user', row.decided_by)
        self.assertEqual('b' * 64, row.data_fingerprint)
        self.assertEqual(['new_critical_high'], row.requested_series)
        self.assertEqual('metrics-ai-synthetic', row.normalized_render_config['dashboard_uid'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            AiChartPublication.objects.create(**publication_values('call-1'))
        self.assertEqual(1, AiChartPublication.objects.count())

    def test_published_history_cannot_have_two_successors_for_one_record(self):
        from bug_metrics.models import AiChartPublication

        first = AiChartPublication.objects.create(**publication_values('call-1'))
        second = AiChartPublication.objects.create(**publication_values('call-2', supersedes=first))
        with self.assertRaises(IntegrityError), transaction.atomic():
            AiChartPublication.objects.create(**publication_values('call-3', supersedes=first))
        self.assertEqual(first.id, second.supersedes_id)
        self.assertEqual(2, AiChartPublication.objects.count())

    def test_failure_is_distinct_from_success_and_does_not_replace_history(self):
        from bug_metrics.models import AiChartPublication

        first = AiChartPublication.objects.create(**publication_values('call-1'))
        failed = AiChartPublication.objects.create(**publication_values(
            'call-2', status='failed', error_code='grafana_unreachable', grafana_url='',
        ))
        self.assertIsNone(failed.supersedes_id)
        self.assertEqual('grafana_unreachable', failed.error_code)
        self.assertEqual([first.id], list(AiChartPublication.objects.filter(
            status='published',
        ).values_list('id', flat=True)))
