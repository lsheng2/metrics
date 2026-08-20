from dataclasses import dataclass
from io import StringIO
import csv

from bug_metrics.models import BugTrendAuditEvent


@dataclass(slots=True)
class BugTrendEvidenceExport:
    filename: str
    content_type: str
    content: str
    row_count: int


class BugTrendEvidenceExportService:
    def export_evidence_tickets(self, state, result, actor: str) -> BugTrendEvidenceExport:
        content = self._evidence_csv_content(result)
        BugTrendAuditEvent.objects.create(
            event_type=BugTrendAuditEvent.EVENT_EVIDENCE_EXPORTED,
            actor=actor,
            scope_id=state.scope_id,
            calculation_run_id=state.calculation_run_id,
            chart_id=state.active_chart_id,
            request_summary={
                'begin': state.begin.isoformat(),
                'end': state.end.isoformat(),
                'selected_bucket_id': state.selected_bucket_id,
                'selected_series_name': state.selected_series_name,
                'filters': {
                    'text': state.list_filters.text,
                    'status': state.list_filters.status,
                    'severity': state.list_filters.severity,
                    'owner': state.list_filters.owner,
                    'component': state.list_filters.component,
                },
                'row_count': result.shown_count,
            },
        )
        return BugTrendEvidenceExport(
            filename=f'bug-trend-evidence-scope-{state.scope_id}.csv',
            content_type='text/csv',
            content=content,
            row_count=result.shown_count,
        )

    def _evidence_csv_content(self, result) -> str:
        buffer = StringIO()
        writer = csv.writer(buffer, lineterminator='\n')
        header = ['issue_key', 'summary', 'series_name', 'status', 'severity', 'owner', 'component', 'created_at', 'updated_at'] + result.display_fields
        writer.writerow(header)
        for row in result.rows:
            writer.writerow([
                row.issue_key,
                row.summary,
                row.series_name,
                row.status,
                row.severity,
                row.owner,
                row.component,
                row.created_at,
                row.updated_at,
                *row.extra_field_values,
            ])
        return buffer.getvalue()