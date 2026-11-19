from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from unittest.mock import patch

from django.db import OperationalError, connections
from django.test import TransactionTestCase, override_settings

from bug_metrics.app.api.ai_chart_publication import list_chart_publications, publish_approved_chart
from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService
from bug_metrics.models import AiChartPublication
from bug_metrics.tests.ai_publication_fixtures import chart_request, seed_publication_data
from bug_metrics.tests.test_ai_chart_publish import approved_snapshot


@override_settings(
    METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999',
    METRICS_AI_GRAFANA_USERNAME='synthetic-user',
    METRICS_AI_GRAFANA_PASSWORD='synthetic-password',
)
class TestPublicationRecovery(TransactionTestCase):
    def preview(self):
        seed_publication_data()
        return AiChartWorkflowService().preview(chart_request())

    def test_lost_database_write_retries_the_same_approved_target_and_bytes(self):
        preview = self.preview()
        snapshot = approved_snapshot(preview)
        imported = []

        def external_import(base, dashboard, username, password):
            imported.append((base, dashboard))
            return {'status': 'success', 'uid': dashboard['uid']}

        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload', external_import):
            with patch.object(AiChartPublication, 'save', side_effect=OperationalError('synthetic write failure')):
                with self.assertRaises(OperationalError):
                    publish_approved_chart(snapshot)
            self.assertEqual(0, AiChartPublication.objects.count())
            result = publish_approved_chart(snapshot)
            repeated = publish_approved_chart(snapshot)
        self.assertEqual(result, repeated)
        self.assertEqual('published', result['status'])
        self.assertEqual(2, len(imported))
        self.assertEqual(imported[0], imported[1])
        self.assertEqual(1, AiChartPublication.objects.count())

    def test_duplicate_key_with_different_authority_cannot_return_another_approval_result(self):
        preview = self.preview()
        snapshot = approved_snapshot(preview)
        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload') as importer:
            importer.return_value = {'status': 'success', 'uid': preview.content['target']['uid']}
            publish_approved_chart(snapshot)
            for changes in ({'approval_id': 'another'}, {'run_id': 'another'}, {'decided_by': 'another'}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    publish_approved_chart(replace(snapshot, **changes))
        self.assertEqual(1, importer.call_count)
        self.assertEqual(1, AiChartPublication.objects.count())

    def test_concurrent_same_target_publications_form_one_ordered_supersession_chain(self):
        preview = self.preview()
        first_entered, release_first, second_started = Event(), Event(), Event()
        imports = []

        def external_import(base, dashboard, username, password):
            imports.append(dashboard['uid'])
            if len(imports) == 1:
                first_entered.set()
                if not release_first.wait(5):
                    raise AssertionError('Second publication did not reach the service.')
            return {'status': 'success', 'uid': dashboard['uid']}

        def publish(snapshot, started=None):
            try:
                if started:
                    started.set()
                return publish_approved_chart(snapshot)
            finally:
                connections.close_all()

        with patch('bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload', external_import):
            with ThreadPoolExecutor(max_workers=2) as workers:
                first = workers.submit(publish, approved_snapshot(preview))
                self.assertTrue(first_entered.wait(5))
                second = workers.submit(
                    publish, approved_snapshot(preview, call='call-2', approval='approval-2'), second_started,
                )
                try:
                    self.assertTrue(second_started.wait(5))
                    self.assertEqual(1, len(imports))
                finally:
                    release_first.set()
                first_result, second_result = first.result(5), second.result(5)
        self.assertEqual('published', first_result['status'])
        self.assertEqual('published', second_result['status'])
        history = list_chart_publications()['items']
        self.assertEqual(2, len(history))
        self.assertEqual([True, False], [row['latest'] for row in history])
        self.assertEqual(first_result['publication_id'], history[0]['supersedes'])
