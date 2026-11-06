from html import escape

from django.template import Context

from project_management.app.domain.report_authoring import validate_authored_edits
from project_management.app.domain.report_authoring_fragments import rich_text_fragment_plain_text
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.app.domain.report_continuity_edits import validate_continuity_authored_edits
from project_management.app.domain.report_meeting_matrix import build_meeting_matrix
from project_management.app.domain.report_presentation import TemplateDefinition
from project_management.app.domain.report_templates import validate_template_document_snapshot
from project_management.reporting.fragment_renderers import rich_fragment_to_html
from project_management.reporting.text import build_plain_text
from project_management.reporting.timeline import build_timeline
from project_management.reporting.view_model import build_report_model


def compile_pinned_report(engine, source_snapshot, template_snapshot, edits, *, authoring_context=None, draft_id, revision,
                          revision_hash, edition_state):
    snapshot = validate_template_document_snapshot(template_snapshot)
    _require_ready_data(snapshot['resolved_document'])
    context, validated_edits = _validated_edits(source_snapshot, snapshot, edits, authoring_context)
    if snapshot['resolved_document'].get('presentation_profile') == 'standup/1':
        from project_management.reporting.standup import compile_standup_report
        return compile_standup_report(source_snapshot, snapshot, validated_edits, context)
    data_edits = tuple(edit for edit in validated_edits if edit.kind != 'slot_fill' and context is None)
    slots = {edit.target['slot_id']: edit for edit in validated_edits if edit.kind == 'slot_fill'}
    model = _model(source_snapshot, snapshot, data_edits, draft_id, revision, revision_hash, edition_state)
    html_parts = [_header(model, snapshot)]
    text_parts = [_plain_header(model)]
    for block in snapshot['resolved_document']['blocks']:
        if block['kind'] == 'content':
            html_parts.append(_content_html(block['fragment']))
            text_parts.append(rich_text_fragment_plain_text(block['fragment']))
        elif block['kind'] == 'slot':
            html, text = _slot(block, slots.get(block['slot_id']))
            html_parts.append(html)
            text_parts.append(text)
        else:
            if block['source'] == 'meeting_matrix':
                html, text = _meeting_matrix(source_snapshot, context)
            else:
                html, text = _data(engine, source_snapshot, snapshot, data_edits, block, draft_id,
                                   revision, revision_hash, edition_state)
            html_parts.append(html)
            text_parts.append(text)
    return '<main style="width:100%; box-sizing:border-box; padding:24px;">' + ''.join(html_parts) + '</main>', '\n\n'.join(
        part for part in text_parts if part
    )


def missing_required_slots(source_snapshot, template_snapshot, edits):
    snapshot = validate_template_document_snapshot(template_snapshot)
    slot_edits = tuple(edit for edit in tuple(edits or ()) if edit.kind == 'slot_fill')
    validated_edits = validate_authored_edits(source_snapshot, slot_edits, snapshot)
    slots = {edit.target['slot_id']: edit for edit in validated_edits if edit.kind == 'slot_fill'}
    missing = []
    for block in snapshot['resolved_document']['blocks']:
        if block['kind'] == 'slot' and block['required']:
            edit = slots.get(block['slot_id'])
            if edit is None or rich_text_fragment_plain_text(edit.fragment).strip() == '':
                missing.append(block['slot_id'])
    return tuple(missing)


def compile_pinned_data_block(engine, source_snapshot, template_snapshot, edits, block, *, draft_id, revision,
                              revision_hash, edition_state):
    snapshot = validate_template_document_snapshot(template_snapshot)
    _require_ready_data(snapshot['resolved_document'])
    if block not in snapshot['resolved_document']['blocks'] or block['kind'] != 'data':
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    validated_edits = validate_authored_edits(source_snapshot, edits, snapshot)
    data_edits = tuple(edit for edit in validated_edits if edit.kind != 'slot_fill')
    return _data(engine, source_snapshot, snapshot, data_edits, block, draft_id, revision, revision_hash, edition_state)


def _validated_edits(source_snapshot, snapshot, edits, authoring_context):
    if authoring_context is None:
        return None, validate_authored_edits(source_snapshot, edits, snapshot)
    context = validate_daily_authoring_context(authoring_context)
    edits = tuple(edits or ())
    slots = tuple(edit for edit in edits if edit.kind == 'slot_fill')
    daily = tuple(edit for edit in edits if edit.kind != 'slot_fill')
    return context, validate_continuity_authored_edits(context, daily) + validate_authored_edits(source_snapshot, slots, snapshot)


def _model(source_snapshot, snapshot, edits, draft_id, revision, revision_hash, edition_state, source='register',
           options=None):
    options = options or {'group_by': 'none', 'sort_by': 'key', 'optional_columns': ()}
    definition = TemplateDefinition(
        snapshot['selection']['template_id'],
        str(snapshot['selection']['revision']),
        {
            'section_order': () if source == 'weekly_timeline' else (source,),
            'optional_columns': tuple(options.get('optional_columns', ())),
            'group_by': options.get('group_by', 'none'),
            'sort_by': options.get('sort_by', 'key'),
        },
        snapshot['presentation_hash'],
        snapshot['renderer_version'],
    )
    model = build_report_model(
        source_snapshot,
        definition,
        edits,
        draft_id=draft_id,
        revision=revision,
        revision_hash=revision_hash,
        edition_state=edition_state,
    )
    model['title'] = 'Weekly timeline' if snapshot['resolved_document']['report_kind'] == 'weekly' else 'Daily standup report'
    if source == 'weekly_timeline':
        model['timeline'] = build_timeline(source_snapshot, _current_rows(model))
    return model


def _current_rows(model):
    return [row for group in model['groups'] for row in group['rows']]


def _header(model, snapshot):
    meta = model['metadata']
    return (
        '<header style="border-bottom:2px solid #0f766e; padding-bottom:12px; margin-bottom:18px;">'
        f'<h1 style="margin:0 0 8px 0; color:#0f766e; font-size:24px;">{escape(model["title"])}</h1>'
        '<table style="width:100%; border-collapse:collapse; table-layout:fixed;"><tbody>'
        f'<tr><th style="text-align:left; border:1px solid #cbd5e1; padding:6px;">Project / stage</th><td style="border:1px solid #cbd5e1; padding:6px;">{escape(meta["project_name"])} / {escape(meta["stage_name"])}</td></tr>'
        f'<tr><th style="text-align:left; border:1px solid #cbd5e1; padding:6px;">Source cutoff / timezone</th><td style="border:1px solid #cbd5e1; padding:6px;">{escape(meta["source_as_of"])} / {escape(meta["timezone"])}</td></tr>'
        f'<tr><th style="text-align:left; border:1px solid #cbd5e1; padding:6px;">Pinned template</th><td style="border:1px solid #cbd5e1; padding:6px;">{escape(snapshot["selection"]["template_id"])} r{snapshot["selection"]["revision"]}; template {escape(snapshot["presentation_hash"])}</td></tr>'
        f'<tr><th style="text-align:left; border:1px solid #cbd5e1; padding:6px;">Provenance</th><td style="border:1px solid #cbd5e1; padding:6px;">draft {escape(meta["draft_id"])} revision {meta["revision"]}; renderer {escape(meta["renderer_version"])}</td></tr>'
        '</tbody></table></header>'
    )


def _plain_header(model):
    meta = model['metadata']
    return '\n'.join((
        model['title'],
        f"Project: {meta['project_name']} / {meta['stage_name']}",
        f"Source cutoff: {meta['source_as_of']} {meta['timezone']}",
        f"Draft: {meta['draft_id']} revision {meta['revision']}",
        f"Template hash: {meta['template_hash']}",
        f"Renderer version: {meta['renderer_version']}",
    ))


def _content_html(fragment):
    return f'<section style="margin:0 0 18px 0;">{rich_fragment_to_html(fragment)}</section>'


def _slot(block, edit):
    fragment = block['initial'] if edit is None else edit.fragment
    provenance = '' if edit is None else f'<p style="margin:4px 0 0 0;"><strong>{escape(edit.author)}</strong> {escape(edit.edited_at)}</p>'
    html = (
        '<section style="margin:0 0 18px 0;">'
        f'<h2 style="margin:0 0 8px 0; color:#0f766e; font-size:18px;">{escape(block["label"])}</h2>'
        f'{rich_fragment_to_html(fragment)}{provenance}</section>'
    )
    text = block['label'] + '\n' + rich_text_fragment_plain_text(fragment)
    if edit is not None:
        text += f"\nEdited by {edit.author} at {edit.edited_at}"
    return html, text


def _data(engine, source_snapshot, snapshot, edits, block, draft_id, revision, revision_hash, edition_state):
    if block['source'] == 'meeting_matrix':
        raise ReportError('REPORT_CONTEXT_REQUIRED')
    model = _model(source_snapshot, snapshot, edits, draft_id, revision, revision_hash, edition_state,
                   block['source'], block['options'])
    html = engine.from_string('{% include "body_authored.html" %}').render(
        Context(model, autoescape=True, use_l10n=False, use_tz=False)
    ).strip()
    text = build_plain_text(model).split('\n\n', 1)
    return html, text[1] if len(text) == 2 else text[0]


def _meeting_matrix(source_snapshot, context):
    if context is None:
        raise ReportError('REPORT_CONTEXT_REQUIRED')
    projection = build_meeting_matrix(source_snapshot, context)
    notes_by_id = {note['note_id']: note for note in context['notes']}
    actions_by_id = {action['action_id']: action for action in context['actions']}
    persistent_by_issue = {}
    report_persistent = []
    for note in context['persistent_notes']:
        if note['target'] == 'report':
            report_persistent.append(note)
        if note['target'] == 'issue':
            persistent_by_issue.setdefault(_issue_key(note['issue_ref']), []).append(note)
    header = ''.join(f'<th style="border:1px solid #cbd5e1; padding:6px;">{escape(column.label)}</th>' for column in projection.columns)
    rows = []
    text_rows = []
    for row in projection.rows:
        cells = ''.join(_cell_html(cell, notes_by_id, actions_by_id) for cell in row.cells)
        label = row.current_key
        row_persistent = tuple(persistent_by_issue.get(_issue_key(row.issue_ref), ()))
        rows.append(
            '<tr>'
            f'<th style="border:1px solid #cbd5e1; padding:6px; text-align:left;">{escape(label)}<br><span style="font-weight:400;">{escape(row.title or "")}</span>{_persistent_notes_html(row_persistent)}</th>'
            f'{cells}'
            '</tr>'
        )
        row_text = label + _persistent_notes_text(row_persistent)
        text_rows.append(row_text + '\n' + '\n'.join(_cell_text(cell, notes_by_id, actions_by_id) for cell in row.cells))
    html = (
        '<section style="margin:0 0 18px 0;">'
        '<h2 style="margin:0 0 8px 0; color:#0f766e; font-size:18px;">Meeting matrix</h2>'
        + _report_persistent_html(tuple(report_persistent))
        + '<table style="width:100%; border-collapse:collapse; table-layout:fixed;"><thead><tr><th style="border:1px solid #cbd5e1; padding:6px;">Ticket</th>'
        + header
        + '</tr></thead><tbody>'
        + ''.join(rows)
        + '</tbody></table></section>'
    )
    report_text = _report_persistent_text(tuple(report_persistent))
    return html, 'Meeting matrix\n' + report_text + '\n\n'.join(text_rows)


def _cell_html(cell, notes_by_id, actions_by_id):
    notes = ''.join(_note_html(notes_by_id[note_id]) for note_id in cell.note_ids)
    actions = ''.join(_action_html(actions_by_id[action_id]) for action_id in cell.action_ids)
    status = _status_html(cell.state)
    body = status + notes + actions
    if not body:
        body = f'<p style="margin:0; color:#64748b;">{escape(_empty_label(cell.state))}</p>'
    return f'<td style="border:1px solid #cbd5e1; padding:6px; vertical-align:top;">{body}</td>'


def _cell_text(cell, notes_by_id, actions_by_id):
    parts = [_empty_label(cell.state)] if cell.state in {'missing', 'not_captured', 'unavailable'} else []
    parts.extend(_note_text(notes_by_id[note_id]) for note_id in cell.note_ids)
    parts.extend(_action_text(actions_by_id[action_id]) for action_id in cell.action_ids)
    return '\n'.join(parts) if parts else _empty_label(cell.state)


def _note_html(note):
    return (
        '<div style="margin:0 0 8px 0;">'
        f'<strong>{escape(_prefix(note))}</strong> '
        f'{rich_fragment_to_html(note["body_fragment"])}'
        '</div>'
    )


def _note_text(note):
    return _prefix(note) + ' ' + rich_text_fragment_plain_text(note['body_fragment'])


def _action_html(action):
    return f'<p style="margin:4px 0 0 0;"><strong>{escape(_action_label(action))}</strong> {rich_fragment_to_html(action["body_fragment"])}</p>'


def _action_text(action):
    return _action_label(action) + ' ' + rich_text_fragment_plain_text(action['body_fragment'])


def _action_label(action):
    label = 'AR' if action['basis'] == 'recorded' else 'AR?'
    owner = action['owner_ref']
    if owner is None:
        return label
    display = owner.get('display_name') or owner.get('owner_id')
    return label if not display else f'{label} @{display}'


def _status_html(state):
    if state not in {'missing', 'not_captured', 'unavailable'}:
        return ''
    return f'<p style="margin:0 0 8px 0; color:#64748b;">{escape(_empty_label(state))}</p>'


def _report_persistent_html(notes):
    if not notes:
        return ''
    return (
        '<div style="margin:0 0 8px 0;">'
        '<strong>Persistent notes</strong>'
        + ''.join(_persistent_note_html(note) for note in notes)
        + '</div>'
    )


def _report_persistent_text(notes):
    if not notes:
        return ''
    return 'Persistent notes\n' + '\n'.join(_persistent_note_text(note) for note in notes) + '\n\n'


def _persistent_notes_html(notes):
    if not notes:
        return ''
    return (
        '<div style="margin:6px 0 0 0; font-weight:400;">'
        '<strong>Persistent</strong>'
        + ''.join(_persistent_note_html(note) for note in notes)
        + '</div>'
    )


def _persistent_notes_text(notes):
    if not notes:
        return ''
    return '\nPersistent\n' + '\n'.join(_persistent_note_text(note) for note in notes)


def _persistent_note_html(note):
    return f'<div style="margin:4px 0 0 0;">{rich_fragment_to_html(note["fragment"])}</div>'


def _persistent_note_text(note):
    return rich_text_fragment_plain_text(note['fragment'])


def _empty_label(state):
    if state == 'missing':
        return 'Missing report'
    if state == 'not_captured':
        return 'Not captured'
    if state == 'unavailable':
        return 'Unavailable'
    return 'No note recorded'


def _prefix(note):
    meeting = note['meeting']
    status = note['source_status']['value']
    suffix = '' if status is None else f'({status})'
    return f"ww{meeting['workweek']}.{meeting['weekday']}{suffix}:"


def _issue_key(issue_ref):
    return (issue_ref['provider_id'], issue_ref['endpoint_fingerprint'], issue_ref['stable_id'])


def _require_ready_data(document):
    sources = [block['source'] for block in document['blocks'] if block['kind'] == 'data']
    concise = document.get('presentation_profile') == 'standup/1'
    required = [] if concise else ['key_messages', 'changes', 'register', 'coverage']
    if document['report_kind'] == 'weekly' and not concise:
        required.append('weekly_timeline')
    if document['schema_version'] == 2:
        required.append('meeting_matrix')
    if any(sources.count(source) != 1 for source in required):
        raise ReportError('REPORT_ARTIFACT_INVALID')
