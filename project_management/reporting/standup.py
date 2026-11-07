from html import escape

from project_management.app.domain.report_authoring_fragments import rich_text_fragment_plain_text
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_meeting_matrix import build_meeting_matrix
from project_management.app.domain.report_meeting_snapshot import meeting_skip_text, skipped_dates
from project_management.app.domain.url_validation import require_safe_https_url
from project_management.reporting.fragment_renderers import rich_fragment_to_html
from project_management.reporting.observations import history_entries
from project_management.app.domain.report_readiness import readiness_text


CELL = 'border:1px solid #cbd5e1; padding:8px; vertical-align:top; text-align:left; overflow-wrap:anywhere;'


def compile_standup_report(source, template, edits, context):
    if context is None:
        raise ReportError('REPORT_CONTEXT_REQUIRED')
    document = template['resolved_document']
    name = 'Weekly standup' if document['report_kind'] == 'weekly' else 'Daily standup'
    dates = sorted({item['meeting']['local_date'] for item in context['current_observations']})
    when = context['meeting']['local_date'] if context['meeting'] else ' / '.join(dates)
    title = f'{source.project_name} / {source.stage_name}'
    html = [f'<header><h1 style="font-size:22px;margin:0 0 4px;">{escape(title)}</h1>'
            f'<p style="margin:0 0 12px;">{name} | {escape(when)}</p></header>']
    plain = [title, f'{name} | {when}']
    if context.get('schema_version') == 3:
        cutoff = f'Source cutoff: {source.source_as_of} ({source.timezone})'
        html.append(f'<p>{escape(cutoff)}</p>')
        plain.append(cutoff)
    notice = meeting_skip_text(context)
    if notice:
        html.append(f'<p>{escape(notice)}</p>')
        plain.append(notice)
    slots = {edit.target['slot_id']: edit for edit in edits if edit.kind == 'slot_fill'}
    for block in document['blocks']:
        if block['kind'] == 'data':
            body, text = _table(source, context)
            html.append(body)
            plain.append(text)
        else:
            edit = slots.get(block.get('slot_id'))
            fragment = (block['fragment'] if block['kind'] == 'content'
                        else block['initial'] if edit is None else edit.fragment)
            label = block.get('label', '')
            heading = f'<h2 style="font-size:16px;margin:8px 0;">{escape(label)}</h2>' if label else ''
            html.append(f'<section>{heading}{rich_fragment_to_html(fragment)}</section>')
            plain.append((label + '\n' if label else '') + rich_text_fragment_plain_text(fragment))
    coverage = coverage_text(source, context)
    html.append(f'<p style="font-size:12px;margin:12px 0 0;">{escape(coverage)}</p>')
    plain.append(coverage)
    return ('<main style="max-width:1200px;margin:0 auto;padding:20px;box-sizing:border-box;">'
            + ''.join(html) + '</main>'), '\n\n'.join(plain)


def _table(source, context):
    from project_management.reporting.pinned import _action_label, _action_text, _issue_key, _note_text, _prefix

    projection = build_meeting_matrix(source, context)
    notes = {note['note_id']: note for note in context['notes']}
    actions = {action['action_id']: action for action in context['actions']}
    originals = {(row.identity.provider_id, row.identity.endpoint_id, row.identity.stable_id): row
                 for row in source.rows}
    rows, text_rows = [], []
    for row in projection.rows:
        original = originals.get(_issue_key(row.issue_ref))
        href = None if original is None else original.source_url
        label = escape(row.current_key)
        if href:
            label = f'<a href="{escape(require_safe_https_url(href, allow_query_fragment=False), quote=True)}">{label}</a>'
        label += f'<div style="font-size:12px;font-weight:400;">{escape(row.title or "")}</div>'
        if row.visibility != 'visible':
            label += '<div>Outside current scope</div>'
        current = row.cells[-1] if row.cells else None
        selected_notes = [notes[note_id] for note_id in current.note_ids] if current else []
        selected_actions = [actions[action_id] for action_id in current.action_ids] if current else []
        entries = history_entries(context, row.issue_ref, current.local_date, selected_notes) if current else ()
        body_parts, texts = [], []
        for entry in entries:
            if entry['kind'] == 'note':
                note = entry['note']
                body_parts.append(f'<div style="margin:0 0 8px;"><strong>{escape(_prefix(note))}</strong>'
                                  f'{rich_fragment_to_html(note["body_fragment"])}</div>')
                texts.append(_note_text(note))
            else:
                body_parts.append(f'<p style="margin:0;">{escape(entry["text"])}</p>')
                texts.append(entry['text'])
        body, body_text = ''.join(body_parts), '\n'.join(texts)
        if not body:
            body = '<p style="margin:0;">No note recorded</p>'
            body_text = 'No note recorded'
        action_html = ''.join('<div style="margin:0 0 6px;">'
                              f'<strong>{escape(_action_label(action))}</strong>'
                              f'{rich_fragment_to_html(action["body_fragment"])}</div>' for action in selected_actions)
        persistent = [note for note in context['persistent_notes']
                      if note['target'] == 'issue' and _issue_key(note['issue_ref']) == _issue_key(row.issue_ref)]
        body += ''.join(rich_fragment_to_html(note['fragment']) for note in persistent)
        body_text += ''.join('\n' + rich_text_fragment_plain_text(note['fragment']) for note in persistent)
        rows.append(f'<tr><th style="{CELL}">{label}</th><td style="{CELL}">{body}</td>'
                    f'<td style="{CELL}">{action_html}</td></tr>')
        membership = '\nOutside current scope' if row.visibility != 'visible' else ''
        text_rows.append(f'{row.current_key} {row.title or ""}{membership}\n{body_text}\n'
                         + '\n'.join(_action_text(action) for action in selected_actions))
    persistent = [item for item in context['persistent_notes'] if item['target'] == 'report']
    header = ''.join(rich_fragment_to_html(item['fragment']) for item in persistent)
    header_text = '\n'.join(rich_text_fragment_plain_text(item['fragment']) for item in persistent)
    return (header + '<table style="width:100%;border-collapse:collapse;table-layout:fixed;">'
            '<thead><tr>' + ''.join(f'<th style="{CELL}width:{width}%;">{label}</th>'
                                   for label, width in (('Ticket', 24), ('Updates', 52), ('AR', 24)))
            + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'), (
                header_text + '\n\n'.join(text_rows))


def coverage_text(source, context):
    if context.get('schema_version') == 3:
        value = readiness_text(source, context)
        missing = sorted(day.report_date for day in source.days
                         if day.state != 'published' and day.report_date not in skipped_dates(context))
        if missing:
            value += ' Missing reports: ' + ', '.join(missing) + '.'
        gaps = len(context['acknowledged_gap_draft_ids'])
        if gaps:
            value += f' {gaps} unfinalized draft skipped.' if gaps == 1 else f' {gaps} unfinalized drafts skipped.'
        limitations = source.coverage.get('limitations', ())
        return value + (' ' + '; '.join(map(str, limitations)) if limitations else '')
    coverage = source.coverage
    membership = coverage.get('membership', {})
    complete = coverage.get('complete')
    if complete is None:
        complete = membership == 'complete' or isinstance(membership, dict) and membership.get('state') == 'complete'
        summaries = coverage.get('summaries', {})
        if isinstance(summaries, dict) and summaries.get('state') not in {None, 'complete'}:
            complete = False
    accepted = coverage.get('accepted_count', sum(row.summary_ref is not None for row in source.rows))
    pending = coverage.get('pending_count', len(source.rows) - accepted)
    skipped_meetings = skipped_dates(context)
    missing = sorted(day.report_date for day in source.days
                     if day.state != 'published' and day.report_date not in skipped_meetings)
    skipped = len(context['acknowledged_gap_draft_ids'])
    if missing or skipped:
        complete = False
    text = f'Coverage: {"Complete" if complete else "Partial"}; {len(source.rows)} tickets, {accepted} accepted, {pending} pending.'
    if missing:
        text += ' Missing reports: ' + ', '.join(missing) + '.'
    if skipped:
        text += f' {skipped} unfinalized draft skipped.' if skipped == 1 else f' {skipped} unfinalized drafts skipped.'
    limitations = coverage.get('limitations', ())
    if isinstance(limitations, (tuple, list)) and limitations:
        text += ' ' + '; '.join(str(item) for item in limitations)
    return text
