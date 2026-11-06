import pytest

from project_management.app.api import reports as report_api


def fragment(text='template text'):
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


def data_block(source, block_id):
    return {
        'kind': 'data',
        'block_id': f'10000000-0000-4000-8000-{block_id:012d}',
        'source': source,
        'options': {'group_by': 'none', 'sort_by': 'key', 'optional_columns': []},
    }


def content_block(index, text='literal {{ not_code }}'):
    return {'kind': 'content', 'block_id': f'20000000-0000-4000-8000-{index:012d}', 'fragment': fragment(text)}


def slot_block(index, *, fill_mode='manual', required=True):
    return {
        'kind': 'slot',
        'block_id': f'30000000-0000-4000-8000-{index:012d}',
        'slot_id': f'40000000-0000-4000-8000-{index:012d}',
        'label': f'Slot {index}',
        'required': required,
        'initial': fragment(''),
        'fill_mode': fill_mode,
    }


def schema1_document(*, report_kind='daily', include_data=True, extra_blocks=()):
    blocks = [content_block(1), slot_block(1, fill_mode='ai_optional')]
    if include_data:
        blocks.extend(data_block(source, index) for index, source in enumerate(
            ('key_messages', 'changes', 'register', 'coverage'), 1
        ))
        if report_kind == 'weekly':
            blocks.append(data_block('weekly_timeline', 5))
    blocks.extend(extra_blocks)
    return {'schema_version': 1, 'report_kind': report_kind, 'blocks': blocks}


def matrix_block():
    return {
        'kind': 'data',
        'block_id': '50000000-0000-4000-8000-000000000001',
        'source': 'meeting_matrix',
        'options': {
            'row_mode': 'one_ticket',
            'order_mode': 'stable_append',
            'initial_sort': 'key_natural_asc',
            'group_mode': 'manual',
            'groups': [{
                'group_id': '60000000-0000-4000-8000-000000000001',
                'label': 'Unclassified',
                'rank': 0,
            }],
            'history_mode': 'cumulative',
            'cross_week_carry': 'last_confirmed_and_unresolved',
            'note_prefix': 'workweek_day_source_status',
            'action_labels': {'recorded': 'AR', 'proposed': 'AR?'},
        },
    }


def test_should_validate_schema1_ready_and_policy_hashes_without_evaluating_literals():
    document = schema1_document()
    policy = {'schema_version': 1, 'instructions': {'40000000-0000-4000-8000-000000000001': 'Use the source notes.'}}

    revision = report_api.validate_report_template_revision('Daily', document, policy)

    assert revision.readiness == 'ready'
    assert revision.validation_codes == ()
    assert revision.document['blocks'][0]['fragment']['blocks'][0]['content'][0]['text'] == 'literal {{ not_code }}'
    assert revision.presentation_hash == report_api.template_document_presentation_hash(revision.document)
    assert revision.fill_policy_hash == report_api.template_fill_policy_hash(revision.fill_policy)


def test_should_save_incomplete_structure_as_draft_with_mandatory_codes():
    revision = report_api.validate_report_template_revision('Draft', schema1_document(include_data=False), {'schema_version': 1, 'instructions': {}})

    assert revision.readiness == 'draft'
    assert 'TEMPLATE_MISSING_DATA_KEY_MESSAGES' in revision.validation_codes
    assert 'TEMPLATE_MISSING_DATA_COVERAGE' in revision.validation_codes


def test_should_require_matrix_for_schema2_readiness_but_keep_valid_matrix_structural_ready():
    missing = dict(schema1_document())
    missing['schema_version'] = 2
    ready = dict(missing)
    ready['blocks'] = [*ready['blocks'], matrix_block()]

    missing_revision = report_api.validate_report_template_revision('Matrix missing', missing, {'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None})
    ready_revision = report_api.validate_report_template_revision('Matrix ready', ready, {'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None})

    assert missing_revision.readiness == 'draft'
    assert 'TEMPLATE_MISSING_DATA_MEETING_MATRIX' in missing_revision.validation_codes
    assert ready_revision.readiness == 'ready'
    assert ready_revision.document['schema_version'] == 2


@pytest.mark.parametrize('bad_document', [
    {'schema_version': 1, 'report_kind': 'daily', 'blocks': [], 'unknown': True},
    {'schema_version': 1, 'report_kind': 'daily', 'blocks': [content_block(1) | {'expression': 'x'}]},
    {'schema_version': 1, 'report_kind': 'daily', 'blocks': [data_block('unknown_source', 1)]},
    {'schema_version': 1, 'report_kind': 'daily', 'blocks': [content_block(1, text=object())]},
])
def test_should_reject_unknown_fields_sources_and_non_json_template_values(bad_document):
    with pytest.raises(report_api.ReportError) as error:
        report_api.validate_report_template_revision('Bad', bad_document, {'schema_version': 1, 'instructions': {}})

    assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'


def test_should_reject_fill_policy_for_manual_or_unknown_slots_and_instruction_limits():
    document = schema1_document(extra_blocks=(slot_block(2, fill_mode='manual'),))

    for policy in (
        {'schema_version': 1, 'instructions': {'40000000-0000-4000-8000-000000000002': 'manual'}},
        {'schema_version': 1, 'instructions': {'40000000-0000-4000-8000-999999999999': 'missing'}},
        {'schema_version': 1, 'instructions': {'40000000-0000-4000-8000-000000000001': 'x' * 4097}},
    ):
        with pytest.raises(report_api.ReportError) as error:
            report_api.validate_report_template_revision('Policy', document, policy)
        assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'
