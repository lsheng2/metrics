from copy import deepcopy
import importlib

import pytest

from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_contracts import ReportError
from project_management.tests.report_assist_fixtures import assist_draft


def domain():
    return importlib.import_module('project_management.app.domain.report_assists')


def test_shouldOfferOnlyCurrentNarrativeAndAiOptionalTargets():
    targets = domain().available_targets(assist_draft(daily=True))
    mappings = [item.target for item in targets]
    assert {'scope': 'daily_note', 'note_id': '73000000-0000-4000-8000-000000000001'} in mappings
    assert {'scope': 'daily_note', 'note_id': '73000000-0000-4000-8000-000000000002'} not in mappings
    assert {'scope': 'template_slot', 'slot_id': '74000000-0000-4000-8000-000000000001'} in mappings
    assert {'scope': 'template_slot', 'slot_id': '74000000-0000-4000-8000-000000000002'} not in mappings
    assert not any(item.get('field') in {'status', 'owner_display'} for item in mappings)


def prepared():
    draft = assist_draft()
    selected = next(item for item in domain().available_targets(draft) if item.target == {'scope': 'report'})
    return domain().build_assist_input(draft, (selected.target_id,), 'Summarize the current blockers.'), selected


def output_for(value, selected):
    return {'schema_version': 1, 'targets': [{
        'target_id': selected.target_id, 'status': 'filled', 'fragment': plain_text_fragment('Validation needs follow-up.'),
        'evidence_refs': [value['evidence'][0]['ref_id']], 'reason_code': None,
    }]}


def test_shouldBindInputToDraftSourceTemplateAndCurrentFragment():
    value, selected = prepared()
    assert value['draft']['revision'] == 1
    assert value['draft']['revision_hash'] == 'a' * 64
    assert value['draft']['snapshot_hash'] == 'b' * 64
    assert value['targets'][0]['target'] == {'scope': 'report'}
    assert value['targets'][0]['target_id'] == selected.target_id
    assert value['targets'][0]['fragment_hash'] == selected.fragment_hash
    assert value['instruction'] == 'Summarize the current blockers.'
    assert domain().validate_assist_output(value, output_for(value, selected))['targets'][0]['status'] == 'filled'


@pytest.mark.parametrize('mutation', ('unknown_target', 'invented_evidence', 'reference_metadata', 'unsafe_link', 'quote'))
def test_shouldRejectUntrustedCandidateAuthority(mutation):
    value, selected = prepared()
    candidate = output_for(value, selected)
    target = candidate['targets'][0]
    if mutation == 'unknown_target':
        target['target_id'] = 'd' * 64
    elif mutation == 'invented_evidence':
        target['evidence_refs'] = ['invented']
    elif mutation == 'reference_metadata':
        target['fragment']['blocks'][0]['content'][0]['reference_id'] = 'spoofed'
    elif mutation == 'unsafe_link':
        target['fragment'] = {'schema_version': 2, 'blocks': [{'type': 'paragraph', 'content': [{
            'type': 'link', 'href': 'https://outside.example.test/leak',
            'content': [{'type': 'text', 'text': 'ticket', 'marks': [], 'foreground': None, 'background': None}],
        }]}]}
    else:
        target['fragment'] = plain_text_fragment('Evidence says "This unsupported quotation is fabricated".')
    with pytest.raises(ReportError):
        domain().validate_assist_output(value, candidate)


def test_shouldRequireInsufficientEvidenceToHaveNoFilledFragment():
    value, selected = prepared()
    candidate = output_for(value, selected)
    candidate['targets'][0].update(status='insufficient_evidence', fragment=None,
                                    evidence_refs=[], reason_code='source_missing')
    assert domain().validate_assist_output(value, candidate)['targets'][0]['fragment'] is None
    broken = deepcopy(candidate)
    broken['targets'][0]['fragment'] = plain_text_fragment('Unjustified conclusion.')
    with pytest.raises(ReportError):
        domain().validate_assist_output(value, broken)


def test_shouldRefuseStaleReadOnlyOrOversizedRequests():
    draft = assist_draft()
    selected = domain().available_targets(draft)[0]
    with pytest.raises(ReportError):
        domain().build_assist_input(draft, (selected.target_id,), 'x' * 5000)
    draft.state = 'finalized'
    with pytest.raises(ReportError):
        domain().build_assist_input(draft, (selected.target_id,), 'Summarize.')
