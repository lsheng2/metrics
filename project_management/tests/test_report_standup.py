from dataclasses import replace
from hashlib import sha256
import json

from bs4 import BeautifulSoup
import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.report_templates import (
    template_snapshot, validate_template_document_snapshot,
)
from project_management.tests.test_report_history_composer_fix2 import context, snapshot
from project_management.tests.test_report_template_compilation import (
    content_block, data_block, fragment, matrix_block, schema1_document, slot_block,
)


TEMPLATE_ID = '99000000-0000-4000-8000-000000000001'
DRAFT_ID = '99000000-0000-4000-8000-000000000002'
POLICY = {'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None}


def standup_document(kind='daily', blocks=None):
    return {'schema_version': 2, 'report_kind': kind, 'presentation_profile': 'standup/1',
            'blocks': [matrix_block()] if blocks is None else blocks}


def pinned(document=None):
    revision = report_api.validate_report_template_revision('Standup', document or standup_document(), POLICY)
    revision = replace(revision, template_id=TEMPLATE_ID, revision=1)
    selection = report_api.UserTemplateSelection(TEMPLATE_ID, 1, revision.revision_hash)
    return template_snapshot(selection, revision)


def authored_context():
    source = snapshot()
    ctx = context(source, '2026-11-02')
    for index, note in enumerate(ctx['notes']):
        body = fragment('Human corrected update.' if index == 0 else '')
        if index == 0:
            body['blocks'][0]['content'][0].update(foreground='#aa0000', background='#fff4cc', marks=['strong'])
        note['body_fragment'] = body
        note['body_hash'] = sha256(canonical_bytes(body)).hexdigest()
    ctx['actions'][0]['tracking_state'] = 'done'
    return source, ctx


def render(source, ctx, template=None):
    return report_api.ReportRenderer().render_pinned(
        source, template or pinned(), authoring_context=ctx,
        draft_id=DRAFT_ID, revision=1, revision_hash='1' * 64, edition_state='final',
    )


def test_shouldRenderOnlyEffectiveNotesProviderStatesAndUnresolvedActions():
    source, ctx = authored_context()
    before = canonical_bytes(ctx)
    output = render(source, ctx)
    soup = BeautifulSoup(output.html_fragment, 'html.parser')
    table = soup.select_one('table')
    assert table is not None
    assert len(table.select('tbody > tr')) == 2
    assert [cell.get_text() for cell in table.select('thead th')] == ['Ticket', 'Updates', 'AR']
    assert output.plain_text.count('Human corrected update.') == 1
    assert 'ww45.1(In Progress):' in output.plain_text
    assert 'ww45.1(Fixed):' in output.plain_text
    assert source.rows[0].what not in output.plain_text
    assert source.rows[1].what not in output.plain_text
    assert 'Evidence refs:' not in output.plain_text
    assert 'Template hash:' not in output.plain_text
    assert '#aa0000' in output.html_fragment and '#fff4cc' in output.html_fragment
    assert soup.find('strong', string='Human corrected update.') is not None
    assert not table.select('tbody > tr')[0].select('td')[-1].get_text(strip=True)
    assert 'AR' in table.select('tbody > tr')[1].select('td')[-1].get_text()
    assert all(link['href'].startswith('https://') for link in table.select('a'))
    assert table.select('a')[0]['href'] == source.rows[0].source_url
    assert table.select('tbody > tr')[1].select_one('a') is None
    assert canonical_bytes(ctx) == before


def test_shouldKeepCompactCoverageAndPendingTicketsWithoutRestoringSourceNarrative():
    source, ctx = authored_context()
    coverage = {**source.coverage, 'complete': False, 'members_count': 2, 'accepted_count': 1,
                'pending_count': 1, 'limitations': ['Some comments are unavailable.']}
    rows = (source.rows[0], replace(source.rows[1], pending_reason='source_incomplete', summary_ref=None))
    output = render(replace(source, coverage=coverage, rows=rows), ctx)
    assert 'Source: 1 complete, 1 incomplete, 0 unavailable' in output.plain_text
    assert 'AI summaries: 1/2 available' in output.plain_text
    assert 'Some comments are unavailable.' in output.plain_text
    assert 'DEMO-101' in output.plain_text and 'DEMO-102' in output.plain_text


def test_shouldKeepMissingMeetingAndAcknowledgedGapVisibleInCompactCoverage():
    source, ctx = authored_context()
    ctx['acknowledged_gap_draft_ids'] = ['99000000-0000-4000-8000-000000000099']
    missing = report_api.ReportDay('2026-11-01', None, 'no_publication', None, {}, (), ())
    output = render(replace(source, coverage={'complete': True}, days=(missing,)), ctx)
    assert 'Missing reports: 2026-11-01' in output.plain_text
    assert '1 unfinalized draft skipped' in output.plain_text
    assert 'Meeting review: 0/2' in output.plain_text


def test_shouldVersionNewProfileAndKeepLegacyPresentationHashAlgorithm():
    old = schema1_document()
    old_hash = sha256(json.dumps(
        {'renderer_version': 'template-document/1', 'document': old},
        sort_keys=True, ensure_ascii=False, separators=(',', ':'),
    ).encode()).hexdigest()
    assert report_api.template_document_presentation_hash(old) == old_hash
    value = pinned()
    assert value['renderer_version'] == 'template-document/2'
    assert validate_template_document_snapshot(value) == value
    value['renderer_version'] = 'template-document/1'
    with pytest.raises(report_api.ReportError):
        validate_template_document_snapshot(value)


@pytest.mark.parametrize('renderer', ['template-document/1', 'template-document/99', 'html-renderer/1', None])
def test_shouldNeverTreatProfiledUserSnapshotAsGenericLegacyRenderer(renderer):
    from project_management.app.domain.report_authoring import validate_template_snapshot
    value = {
        'selection': {'origin': 'user', 'template_id': TEMPLATE_ID, 'revision': 1, 'revision_hash': '1' * 64},
        'resolved_document': standup_document(),
        'fill_policy': POLICY, 'fill_policy_hash': report_api.template_fill_policy_hash(POLICY),
        'presentation_hash': '2' * 64, 'renderer_version': renderer,
    }
    with pytest.raises(report_api.ReportError):
        validate_template_snapshot(value)


@pytest.mark.parametrize('change', [
    {'presentation_profile': None}, {'presentation_profile': 'standup/unknown'},
    {'schema_version': 1}, {'unknown': True},
], ids=['null-profile', 'unknown-profile', 'wrong-schema', 'unknown-field'])
def test_shouldRejectAmbiguousPresentationContracts(change):
    with pytest.raises(report_api.ReportError):
        report_api.validate_report_template_revision('Invalid', {**standup_document(), **change}, POLICY)


def test_shouldRequireOneMatrixWithoutLegacyAuditBlocksForConciseTemplates():
    for kind in ('daily', 'weekly'):
        ready = report_api.validate_report_template_revision('Ready', standup_document(kind), POLICY)
        assert ready.readiness == 'ready'
    for blocks, code in (([], 'TEMPLATE_MISSING_DATA_MEETING_MATRIX'),
                         ([matrix_block(), {**matrix_block(), 'block_id': DRAFT_ID}],
                          'TEMPLATE_DUPLICATE_DATA_MEETING_MATRIX')):
        revision = report_api.validate_report_template_revision('Draft', standup_document(blocks=blocks), POLICY)
        assert revision.readiness == 'draft'
        assert code in revision.validation_codes
    with pytest.raises(report_api.ReportError):
        pinned(standup_document(blocks=[matrix_block(), data_block('register', 3)]))


def test_shouldKeepTemplateContentAndSlotsInTheConciseBody():
    source, ctx = authored_context()
    document = standup_document(blocks=[content_block(1, 'Meeting decisions'), matrix_block(), slot_block(1)])
    output = render(source, ctx, pinned(document))
    assert 'Meeting decisions' in output.plain_text
    assert 'Slot 1' in output.plain_text
