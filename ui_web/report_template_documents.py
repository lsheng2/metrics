from uuid import uuid4


def empty_fragment():
    return {'schema_version': 2, 'blocks': []}


def text_fragment(text):
    if not text:
        return empty_fragment()
    return {
        'schema_version': 2,
        'blocks': [{
            'type': 'paragraph',
            'content': [{
                'type': 'text',
                'text': text,
                'marks': [],
                'foreground': None,
                'background': None,
            }],
        }],
    }


def blank_document():
    return {'schema_version': 1, 'report_kind': 'daily', 'blocks': []}


def starter_document(kind):
    sources = ['key_messages', 'changes', 'register', 'coverage']
    if kind == 'weekly':
        sources.append('weekly_timeline')
    blocks = [
        {
            'kind': 'content',
            'block_id': str(uuid4()),
            'fragment': text_fragment('Report note'),
        },
        {
            'kind': 'slot',
            'block_id': str(uuid4()),
            'slot_id': str(uuid4()),
            'label': 'Manual follow-up',
            'required': True,
            'initial': empty_fragment(),
            'fill_mode': 'manual',
        },
    ]
    blocks.extend(data_block(source) for source in sources)
    return {'schema_version': 1, 'report_kind': kind, 'blocks': blocks}


def continuity_starter_document(kind):
    sources = ['meeting_matrix', 'key_messages', 'changes', 'register', 'coverage']
    if kind == 'weekly':
        sources.append('weekly_timeline')
    return {
        'schema_version': 2,
        'report_kind': kind,
        'blocks': [data_block(source) for source in sources],
    }


def standup_starter_document(kind):
    return {
        'schema_version': 2, 'report_kind': kind, 'presentation_profile': 'standup/1',
        'blocks': [data_block('meeting_matrix')],
    }


def default_fill_policy(document):
    policy = {'schema_version': document['schema_version'], 'instructions': {}}
    if document['schema_version'] == 2:
        policy['daily_note_instructions'] = None
    return policy


def data_block(source):
    if source == 'meeting_matrix':
        options = {
            'row_mode': 'one_ticket',
            'order_mode': 'stable_append',
            'initial_sort': 'key_natural_asc',
            'group_mode': 'none',
            'groups': [],
            'history_mode': 'cumulative',
            'cross_week_carry': 'last_confirmed_and_unresolved',
            'note_prefix': 'workweek_day_source_status',
            'action_labels': {'recorded': 'AR', 'proposed': 'AR?'},
        }
    else:
        options = {'group_by': 'none', 'sort_by': 'key', 'optional_columns': []}
    return {
        'kind': 'data',
        'block_id': str(uuid4()),
        'source': source,
        'options': options,
    }
