from datetime import UTC, datetime
import hashlib
from unittest.mock import patch
from urllib.error import URLError

from django.test import TestCase, override_settings

from bug_metrics.models import AiChartPublication
from bug_metrics.tests.ai_publication_fixtures import chart_request, seed_publication_data


def approved_snapshot(preview, *, call='call-1', approval='approval-1'):
    from bug_metrics.app.api.ai_chart_workflow import canonical_bytes
    from bug_metrics.app.api.ai_publication_contracts import ApprovedChartPublication

    data = canonical_bytes(preview.content)
    return ApprovedChartPublication(
        preview_bytes=data, preview_digest=hashlib.sha256(data).hexdigest(),
        tool_call_id=call, approval_id=approval, run_id='run-1',
        decided_by='synthetic-reviewer', decided_at=datetime(2026, 11, 16, tzinfo=UTC),
    )


@override_settings(
    METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999',
    METRICS_AI_GRAFANA_USERNAME='synthetic-user',
    METRICS_AI_GRAFANA_PASSWORD='synthetic-password',
)
class TestAiChartPublish(TestCase):
    def ready_preview(self):
        from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService

        seed_publication_data()
        return AiChartWorkflowService().preview(chart_request())

    def test_repeated_tool_call_returns_one_record_and_one_external_import(self):
        from bug_metrics.app.api.ai_chart_publication import publish_approved_chart

        preview = self.ready_preview()
        snapshot = approved_snapshot(preview)
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            importer.return_value = {'status': 'success', 'uid': preview.content['target']['uid']}
            first = publish_approved_chart(snapshot)
            repeated = publish_approved_chart(snapshot)
        self.assertEqual(first, repeated)
        self.assertEqual('published', first['status'])
        self.assertEqual('approval-1', first['approval_id'])
        self.assertEqual('call-1', first['tool_call_id'])
        self.assertEqual('synthetic-reviewer', first['actor'])
        self.assertEqual(1, importer.call_count)
        self.assertEqual(preview.content['dashboard'], importer.call_args.args[1])
        self.assertEqual(1, AiChartPublication.objects.count())
        row = AiChartPublication.objects.get()
        self.assertEqual(snapshot.preview_digest, row.preview_digest)
        self.assertEqual(preview.content['publication']['normalized_render_config'], row.normalized_render_config)

    def test_import_failure_is_recorded_without_a_published_url(self):
        from bug_metrics.app.api.ai_chart_publication import publish_approved_chart

        snapshot = approved_snapshot(self.ready_preview())
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            importer.side_effect = URLError('synthetic-password must not escape')
            result = publish_approved_chart(snapshot)
        self.assertEqual('failed', result['status'])
        self.assertEqual('', result['grafana_url'])
        self.assertNotIn('synthetic-password', str(result))
        self.assertEqual(0, AiChartPublication.objects.filter(status='published').count())
        self.assertEqual('grafana_import_failed', AiChartPublication.objects.get().error_code)

    def test_wrong_grafana_acknowledgement_is_not_publication_success(self):
        from bug_metrics.app.api.ai_chart_publication import publish_approved_chart

        snapshot = approved_snapshot(self.ready_preview())
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            importer.return_value = {'status': 'success', 'uid': 'different-target'}
            result = publish_approved_chart(snapshot)
        self.assertEqual('failed', result['status'])
        self.assertEqual('grafana_response_invalid', result['error_code'])

    def test_later_success_supersedes_only_the_previous_success(self):
        from bug_metrics.app.api.ai_chart_publication import publish_approved_chart

        preview = self.ready_preview()
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            importer.return_value = {'status': 'success', 'uid': preview.content['target']['uid']}
            first = publish_approved_chart(approved_snapshot(preview))
            second = publish_approved_chart(approved_snapshot(preview, call='call-2', approval='approval-2'))
        later = AiChartPublication.objects.get(tool_call_id='call-2')
        self.assertEqual(first['publication_id'], str(later.supersedes_id))
        self.assertNotEqual(first['publication_id'], second['publication_id'])

    def test_modified_approved_bytes_do_not_reach_grafana(self):
        from dataclasses import replace
        from bug_metrics.app.api.ai_chart_publication import publish_approved_chart

        snapshot = approved_snapshot(self.ready_preview())
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            with self.assertRaises(ValueError):
                publish_approved_chart(replace(snapshot, preview_bytes=b'{}'))
        importer.assert_not_called()
        self.assertEqual(0, AiChartPublication.objects.count())

    def test_incomplete_publication_metadata_is_rejected_before_import(self):
        from bug_metrics.app.api.ai_chart_publication import publish_approved_chart

        preview = self.ready_preview()
        preview.content['publication'].pop('normalized_render_config')
        snapshot = approved_snapshot(preview)
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            importer.return_value = {'status': 'success', 'uid': preview.content['target']['uid']}
            with self.assertRaises(ValueError):
                publish_approved_chart(snapshot)
        importer.assert_not_called()
        self.assertEqual(0, AiChartPublication.objects.count())
