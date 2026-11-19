"""Publication must coexist with the runtime's independent audit writer."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from django.db import connection, connections, transaction
from django.test import override_settings
import pytest

from ai_host.models import RuntimeAuditEvent
from bug_metrics.app.api.ai_chart_publication import publish_approved_chart
from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService
from bug_metrics.models import AiChartPublication
from bug_metrics.tests.ai_publication_fixtures import chart_request, seed_publication_data
from bug_metrics.tests.test_ai_chart_publish import approved_snapshot


@pytest.mark.django_db(transaction=True)
@override_settings(
    METRICS_AI_GRAFANA_BASE_URL="http://127.0.0.1:39999",
    METRICS_AI_GRAFANA_USERNAME="synthetic-user",
    METRICS_AI_GRAFANA_PASSWORD="synthetic-password",
)
def test_publication_survives_audit_write_between_latest_read_and_publication_insert():
    assert connection.vendor == "sqlite"
    database_name = str(connection.settings_dict["NAME"])
    assert database_name != ":memory:" and "mode=memory" not in database_name
    seed_publication_data()
    preview = AiChartWorkflowService().preview(chart_request())
    approved = approved_snapshot(preview)
    latest_read, audit_inserted, release_audit = Event(), Event(), Event()
    manager = AiChartPublication.objects
    original_filter = manager.filter
    original_save = AiChartPublication.save

    def observed_filter(*args, **kwargs):
        queryset = original_filter(*args, **kwargs)
        if kwargs.get("superseded_by__isnull") is True:
            original_first = queryset.first
            def first():
                result = original_first()
                latest_read.set()
                assert audit_inserted.wait(5), "Audit insert did not reach its transaction"
                return result
            queryset.first = first
        return queryset

    def observed_save(instance, *args, **kwargs):
        release_audit.set()
        return original_save(instance, *args, **kwargs)

    def audit_writer():
        try:
            assert latest_read.wait(5), "Publication did not read the latest row"
            with transaction.atomic():
                RuntimeAuditEvent.objects.create(
                    event_id=str(uuid4()), category="tool_result", occurred_at=datetime.now(timezone.utc),
                    sequence=1, runtime_id="synthetic-contention", payload={},
                )
                audit_inserted.set()
                assert release_audit.wait(5), "Publication did not attempt its insert"
        finally:
            connections.close_all()

    with patch(
        "bug_metrics.app.api.ai_chart_publication.import_grafana_dashboard_payload",
        return_value={"status": "success", "uid": preview.content["target"]["uid"]},
    ) as importer, patch.object(manager, "filter", observed_filter), \
            patch.object(AiChartPublication, "save", observed_save), ThreadPoolExecutor(max_workers=1) as executor:
        audit = executor.submit(audit_writer)
        try:
            result = publish_approved_chart(approved)
        finally:
            release_audit.set()
            audit.result(timeout=10)
        assert result["status"] == "published"
        assert importer.call_count == 1
    assert AiChartPublication.objects.count() == 1
    assert RuntimeAuditEvent.objects.filter(runtime_id="synthetic-contention").count() == 1
