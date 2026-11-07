from dataclasses import dataclass

from project_management.app.domain.report_observation_history import issue_key


@dataclass(frozen=True, slots=True)
class ReportReadiness:
    tickets: int
    source_complete: int
    source_incomplete: int
    source_unavailable: int
    summaries_available: int
    notes_present: int
    reviewed: int


def report_readiness(source, context):
    complete = incomplete = unavailable = 0
    for row in source.rows:
        if row.source_hash is None or row.pending_reason == 'source_missing':
            unavailable += 1
        elif row.pending_reason == 'source_incomplete':
            incomplete += 1
        else:
            complete += 1
    meetings = [item['meeting']['local_date'] for item in (context or {}).get('meeting_history', ())]
    current = (context or {}).get('meeting')
    current_date = current['local_date'] if current else max(meetings, default=None)
    keys = {(row.identity.provider_id, row.identity.endpoint_id, row.identity.stable_id) for row in source.rows}
    notes = {issue_key(item['issue_ref']) for item in (context or {}).get('notes', ())
             if item['meeting']['local_date'] == current_date}
    reviews = {issue_key(item['issue_ref']) for item in (context or {}).get('meeting_reviews', ())
               if item['meeting']['local_date'] == current_date}
    return ReportReadiness(
        len(source.rows), complete, incomplete, unavailable,
        sum(row.summary_ref is not None and row.pending_reason not in
            {'source_missing', 'source_incomplete', 'summary_pending', 'summary_stale'} for row in source.rows),
        len(notes & keys), len(reviews & keys),
    )


def readiness_text(source, context):
    value = report_readiness(source, context)
    return (
        ('No current tickets. ' if not value.tickets else '')
        + f'Source: {value.source_complete} complete, {value.source_incomplete} incomplete, {value.source_unavailable} unavailable. '
        + f'AI summaries: {value.summaries_available}/{value.tickets} available. '
        + f'Notes: {value.notes_present}/{value.tickets}. Meeting review: {value.reviewed}/{value.tickets}.'
    )
