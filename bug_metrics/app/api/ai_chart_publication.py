import hashlib
import json
import threading

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef

from bug_metrics.models import AiChartPublication
from .ai_dashboard_grafana_publish import import_grafana_dashboard_payload
from .ai_publication_contracts import ApprovedChartPublication, normalized_grafana_base_url


_PUBLICATION_LOCK = threading.Lock()


def publish_approved_chart(approval):
    if not isinstance(approval, ApprovedChartPublication):
        raise ValueError('Runtime-authorized publication is required.')
    if hashlib.sha256(approval.preview_bytes).hexdigest() != approval.preview_digest:
        raise ValueError('Approved preview digest does not match.')
    row, dashboard = _record_for_approved_content(approval)
    base_url = row.grafana_base_url
    # One App/process owns publication. Serialize import and history so a later
    # acknowledgement cannot be recorded ahead of an earlier same-target import.
    with _PUBLICATION_LOCK:
        existing = AiChartPublication.objects.filter(tool_call_id=approval.tool_call_id).first()
        if existing is not None:
            if (existing.preview_digest != approval.preview_digest
                    or existing.approval_id != approval.approval_id
                    or existing.run_id != approval.run_id
                    or existing.decided_by != approval.decided_by):
                raise ValueError('Publication identity conflict.')
            return publication_result(existing)
        status, error_code, grafana_url = 'failed', '', ''
        try:
            imported = import_grafana_dashboard_payload(
                base_url, dashboard,
                str(settings.METRICS_AI_GRAFANA_USERNAME),
                str(settings.METRICS_AI_GRAFANA_PASSWORD),
            )
        except Exception:
            error_code = 'grafana_import_failed'
        else:
            if (isinstance(imported, dict) and imported.get('status') == 'success'
                    and imported.get('uid') == row.dashboard_uid):
                status = 'published'
                grafana_url = f'{base_url}/d/{row.dashboard_uid}'
            else:
                error_code = 'grafana_response_invalid'
        with transaction.atomic():
            previous = None
            if status == 'published':
                previous = AiChartPublication.objects.filter(
                    dashboard_uid=row.dashboard_uid, grafana_base_url=base_url,
                    status='published', superseded_by__isnull=True,
                ).first()
            row.status = status
            row.error_code = error_code
            row.grafana_url = grafana_url
            row.supersedes = previous
            row.save(force_insert=True)
        return publication_result(row)


def _record_for_approved_content(approval):
    try:
        content = json.loads(approval.preview_bytes)
        dashboard, target, metadata = content['dashboard'], content['target'], content['publication']
        base_url = normalized_grafana_base_url(target['grafana_base_url'])
        if base_url is None or target['uid'] != dashboard['uid']:
            raise ValueError()
        row = AiChartPublication(
            tool_call_id=approval.tool_call_id, approval_id=approval.approval_id,
            run_id=approval.run_id, decided_by=approval.decided_by,
            decided_at=approval.decided_at, preview_digest=approval.preview_digest,
            data_fingerprint=metadata['data_fingerprint'],
            normalized_render_config=metadata['normalized_render_config'],
            provider_id=metadata['provider_id'], profile_id=metadata['profile_id'],
            chart_id=metadata['chart_id'], chart_version=metadata['chart_version'],
            requested_series=metadata['requested_series'], range_mode=metadata['range_mode'],
            range_start=metadata['range_start'], range_end=metadata['range_end'],
            dashboard_uid=target['uid'], title=dashboard['title'],
            visualization=metadata['visualization'], grafana_base_url=base_url,
            grafana_url='', correlation_id=approval.run_id, status='failed', error_code='',
        )
        row.full_clean(validate_unique=False, validate_constraints=False)
    except (KeyError, TypeError, ValueError, ValidationError):
        raise ValueError('Approved publication metadata is invalid.') from None
    return row, dashboard


def publication_result(row):
    return {
        'publication_id': str(row.id),
        'status': row.status,
        'error_code': row.error_code,
        'validation_status': 'draft_validated',
        'approval_id': row.approval_id,
        'tool_call_id': row.tool_call_id,
        'run_id': row.run_id,
        'actor': row.decided_by,
        'decided_at': row.decided_at.isoformat(),
        'preview_digest': row.preview_digest,
        'data_fingerprint': row.data_fingerprint,
        'normalized_render_config': row.normalized_render_config,
        'provider_id': row.provider_id,
        'profile_id': row.profile_id,
        'chart_id': row.chart_id,
        'chart_version': row.chart_version,
        'requested_series': row.requested_series,
        'range_mode': row.range_mode,
        'range_start': row.range_start,
        'range_end': row.range_end,
        'visualization': row.visualization,
        'dashboard_uid': row.dashboard_uid,
        'title': row.title,
        'grafana_url': row.grafana_url,
        'correlation_id': row.correlation_id,
        'created_at': row.created_at.isoformat(),
    }


def list_chart_publications(limit=25):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('History limit must be between 1 and 100.')
    successors = AiChartPublication.objects.filter(supersedes_id=OuterRef('pk'), status='published')
    rows = AiChartPublication.objects.annotate(has_successor=Exists(successors))[:limit]
    return {
        'contract_version': '0.3',
        'items': [
            {
                **publication_result(row),
                'latest': row.status == 'published' and not row.has_successor,
                'supersedes': str(row.supersedes_id) if row.supersedes_id else None,
            }
            for row in rows
        ],
    }
