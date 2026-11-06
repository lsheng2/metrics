from copy import deepcopy
from types import SimpleNamespace

import pytest

from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import canonical_hash
from project_management.services.report_historical_references import HistoricalReferenceResolver


UUIDS = {
    'reference': '11111111-1111-4111-8111-111111111111',
    'parent_draft': '22222222-2222-4222-8222-222222222222',
    'publication': '33333333-3333-4333-8333-333333333333',
}


class SourceAccessForbidden:
    def __init__(self):
        self.accesses = 0

    def _report_repository(self, *args, **kwargs):
        self.accesses += 1
        raise AssertionError('historical source storage was accessed before validation completed')


def resolver_with_forbidden_source():
    archive = SourceAccessForbidden()
    service = SimpleNamespace(archive=archive)
    resolver = HistoricalReferenceResolver(
        service,
        SimpleNamespace(subject='owner@example.test'),
        '44444444-4444-4444-8444-444444444444',
        '55555555-5555-4555-8555-555555555555',
    )
    return resolver, archive


def valid_record(kind):
    legacy = {
        'reference_id': UUIDS['reference'],
        'option_id': 'id',
        'issued_fragment_hash': 'a' * 64,
        'content_basis': 'human_composed',
        'observation': {
            'identity': {
                'provider_id': 'jira',
                'endpoint_id': 'alpha',
                'stable_id': '10001',
                'display_key': 'ALPHA-1',
            },
            'requested_key': 'ALPHA-1',
            'current_key': 'ALPHA-1',
            'canonical_url': 'https://tracker.example.test/browse/ALPHA-1',
            'title': 'Provider title',
            'assignee': {'id': 'dev-a', 'display_name': 'Alice'},
            'assignee_state': 'assigned',
            'observed_at': '2026-11-03T01:00:00+00:00',
            'source_updated_at': '2026-11-02T23:59:00+00:00',
            'lookup_kind': 'live',
            'scope_snapshot_hash': 'b' * 64,
        },
    }
    association = {
        'schema_version': 1,
        'kind': kind,
        'target_hash': 'c' * 64,
        'reference_id': legacy['reference_id'],
        'record_hash': canonical_hash(legacy),
    }
    if kind == 'parent_draft_revision':
        association = association | {
            'parent_draft_id': UUIDS['parent_draft'],
            'parent_draft_revision': 1,
            'parent_draft_revision_hash': 'd' * 64,
        }
    elif kind == 'source_publication':
        association = association | {
            'publication_id': UUIDS['publication'],
            'manifest_hash': 'e' * 64,
            'commit': 'f' * 40,
        }
    return legacy | {'schema_version': 2, 'historical_association': association}


def malformed_record(kind, change):
    record = deepcopy(valid_record(kind))
    changed = change(record)
    return record if changed is None else changed


def without_record_field(field):
    def remove(record):
        del record[field]
    return remove


def without_association_field(field):
    def remove(record):
        del record['historical_association'][field]
    return remove


def set_record_field(field, value):
    return lambda record: record.__setitem__(field, value)


def set_association_field(field, value):
    return lambda record: record['historical_association'].__setitem__(field, value)


RECORD_FIELDS = (
    'schema_version',
    'reference_id',
    'option_id',
    'issued_fragment_hash',
    'content_basis',
    'observation',
    'historical_association',
)

ASSOCIATION_FIELDS_BY_KIND = {
    'parent_draft_revision': (
        'schema_version',
        'kind',
        'target_hash',
        'reference_id',
        'record_hash',
        'parent_draft_id',
        'parent_draft_revision',
        'parent_draft_revision_hash',
    ),
    'source_publication': (
        'schema_version',
        'kind',
        'target_hash',
        'reference_id',
        'record_hash',
        'publication_id',
        'manifest_hash',
        'commit',
    ),
}

MALFORMED_SHAPES = (
    ('record_extra_key', lambda record: record.__setitem__('extra', True)),
    ('association_extra_key', set_association_field('extra', True)),
    ('record_bool_schema_version', set_record_field('schema_version', True)),
    ('association_bool_schema_version', set_association_field('schema_version', True)),
    ('association_null_target_hash', set_association_field('target_hash', None)),
    ('association_list_value', set_record_field('historical_association', [])),
    ('record_list_value', lambda record: []),
    ('unknown_kind', set_association_field('kind', 'unknown')),
    ('list_kind', set_association_field('kind', [])),
    ('object_kind', set_association_field('kind', {})),
    ('list_option_id', set_record_field('option_id', [])),
    ('object_option_id', set_record_field('option_id', {})),
    ('wrong_target_hash', set_association_field('target_hash', 'A' * 64)),
    ('wrong_record_hash', set_association_field('record_hash', '0' * 63)),
)

KIND_SPECIFIC_MALFORMED_SHAPES = {
    'parent_draft_revision': (
        ('parent_revision_bool', set_association_field('parent_draft_revision', True)),
        ('parent_revision_null', set_association_field('parent_draft_revision', None)),
        ('parent_draft_id_list', set_association_field('parent_draft_id', [])),
        ('parent_revision_hash_wrong', set_association_field('parent_draft_revision_hash', 'D' * 64)),
    ),
    'source_publication': (
        ('publication_id_list', set_association_field('publication_id', [])),
        ('manifest_hash_wrong', set_association_field('manifest_hash', 'E' * 64)),
        ('commit_uppercase', set_association_field('commit', 'F' * 40)),
        ('commit_null', set_association_field('commit', None)),
    ),
}


def invalid_cases():
    for kind in ('parent_draft_revision', 'source_publication'):
        for field in RECORD_FIELDS:
            yield pytest.param(kind, without_record_field(field), id=f'{kind}-record-missing-{field}')
        for field in ASSOCIATION_FIELDS_BY_KIND[kind]:
            yield pytest.param(kind, without_association_field(field), id=f'{kind}-association-missing-{field}')
        for name, change in MALFORMED_SHAPES:
            yield pytest.param(kind, change, id=f'{kind}-{name}')
        for name, change in KIND_SPECIFIC_MALFORMED_SHAPES[kind]:
            yield pytest.param(kind, change, id=f'{kind}-{name}')


@pytest.mark.parametrize(('kind', 'change'), tuple(invalid_cases()))
def test_shouldRejectMalformedHistoricalAssociationBeforeAnySourceAccess(kind, change):
    resolver, archive = resolver_with_forbidden_source()
    record = malformed_record(kind, change)

    with pytest.raises(ReportError) as error:
        resolver(record)

    assert error.value.code == 'REFERENCE_INVALID'
    assert archive.accesses == 0


@pytest.mark.parametrize('kind', ('parent_draft_revision', 'source_publication'))
def test_shouldKeepWellFormedHistoricalAssociationOnSourceResolutionPath(kind):
    resolver, archive = resolver_with_forbidden_source()

    with pytest.raises(AssertionError, match='historical source storage was accessed'):
        resolver(valid_record(kind))

    assert archive.accesses == 1
