import json

from django.utils.translation import gettext as _

from ui_web.report_template_documents import empty_fragment


DATA_SOURCES = (
    ('meeting_matrix', _('Meeting matrix')),
    ('key_messages', _('Key messages')),
    ('changes', _('Changes')),
    ('register', _('Issue register')),
    ('coverage', _('Coverage')),
    ('weekly_timeline', _('Weekly timeline')),
)
GROUP_CHOICES = (
    ('none', _('No grouping')),
    ('status', _('Status')),
    ('assignee', _('Assignee')),
)


def template_rows(document, fill_policy):
    rows = []
    instructions = fill_policy.get('instructions', {})
    for index, block in enumerate(document.get('blocks', ()), 1):
        row = {
            'index': index,
            'kind': block['kind'],
            'block_id': block['block_id'],
            'fragment_script_id': f'template-fragment-{index}',
            'fragment': empty_fragment(),
            'slot_id': '',
            'label': '',
            'required': False,
            'fill_mode': 'manual',
            'instruction': '',
            'source': 'register',
            'group_by': 'none',
            'optional_columns': (),
        }
        if block['kind'] == 'content':
            row['fragment'] = block['fragment']
        elif block['kind'] == 'slot':
            row.update(
                fragment=block['initial'],
                slot_id=block['slot_id'],
                label=block['label'],
                required=block['required'],
                fill_mode=block['fill_mode'],
                instruction=instructions.get(block['slot_id'], ''),
            )
        else:
            options = block['options']
            row.update(
                source=block['source'],
                group_by=options.get('group_by', 'none'),
                optional_columns=tuple(options.get('optional_columns', ())),
                matrix_group_mode=options.get('group_mode', 'none'),
                matrix_groups=tuple(options.get('groups', ())),
            )
        rows.append(row)
    return tuple(rows)


def editor_payload(revision, *, form=None):
    document = submitted_value(form, 'document_value', revision.document)
    policy = submitted_value(form, 'fill_policy_value', revision.fill_policy)
    name = submitted_name(form, revision.name)
    return {
        'name': name,
        'document': document,
        'fill_policy': policy,
        'document_json': submitted_json(form, 'document', document),
        'fill_policy_json': submitted_json(form, 'fill_policy', policy),
        'rows': template_rows(document, policy),
        'data_sources': DATA_SOURCES,
        'group_choices': GROUP_CHOICES,
    }


def submitted_value(form, method, fallback):
    if form is None:
        return fallback
    value = getattr(form, '_' + method.replace('_value', ''), None)
    return value if value is not None else fallback


def submitted_name(form, fallback):
    if form is None:
        return fallback
    if form.is_bound:
        return str(form.data.get('name', fallback))
    return form.cleaned_data.get('name', fallback) if form.is_valid() else fallback


def submitted_json(form, field, value):
    if form is not None and form.is_bound and field in form.data:
        return str(form.data.get(field, ''))
    return json_text(value)


def template_choice_value(summary):
    return f'user|{summary.template_id}|{summary.current_revision}|{summary.revision_hash}'


def ready_template_choices(page):
    return tuple(
        (template_choice_value(item), _('%(name)s r%(revision)s (%(hash)s)') % {
            'name': item.name,
            'revision': item.current_revision,
            'hash': item.revision_hash[:12],
        })
        for item in page.items
        if item.readiness == 'ready' and not item.archived
    )


def json_text(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
