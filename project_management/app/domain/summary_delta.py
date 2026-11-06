from project_management.app.domain.capture_values import canonical_bytes, content_hash, sha256_bytes
from project_management.app.domain.summary_contracts import AnalysisError, PreparedAnalysis
from project_management.app.domain.summary_input import (
    MAX_CHAIN, MAX_EVIDENCE, MAX_INPUT_BYTES, REQUIRED_PARTS, build_initial_input, require_complete_source,
)


def build_analysis_input(project_id, stage, source_key, chain, snapshots, profile_revision, baseline=None):
    if not chain or len(chain) != len(snapshots):
        raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
    if len(chain) > MAX_CHAIN:
        raise AnalysisError('ANALYSIS_CHAIN_LIMIT')
    _validate_chain(stage, source_key, chain, snapshots)
    if baseline is None and len(chain) == 1:
        return build_initial_input(project_id, stage, source_key, chain[0], snapshots[0], profile_revision)
    binding = {
        'project_id': project_id, 'stage_id': stage.id, 'provider': source_key.provider_id,
        'site': stage.descriptor.endpoint, 'stable_id': source_key.stable_id,
        'rule_hash': source_key.rule_hash, 'principal_id': source_key.principal_id,
    }
    start = _baseline_start(baseline, chain, binding, profile_revision)
    segment = tuple(zip(chain[start:], snapshots[start:]))
    for _, source in segment:
        require_complete_source(source)
    count = sum(1 + len(source.comments_by_id) + len(source.history_by_id) for _, source in segment)
    if count > MAX_EVIDENCE:
        raise AnalysisError('ANALYSIS_INPUT_LIMIT')
    target = chain[-1]
    value = {
        'fixture_version': 'review-1', 'profile_revision': profile_revision, 'binding': binding,
        'target_capture_id': target.capture_id,
        'baseline': {
            'summary_id': None if baseline is None else baseline.summary_id,
            'accepted_revision': 0 if baseline is None else baseline.revision,
            'capture_id': None if baseline is None else baseline.target_capture_id,
            'text': None if baseline is None else canonical_bytes(baseline.candidate).decode('utf-8'),
        },
        'required_parts': list(REQUIRED_PARTS),
        'coverage': {part: 'complete' for part in REQUIRED_PARTS},
        'delta': _delta(segment, baseline),
        'evidence': [row for reference, source in segment
                     for row in _evidence(reference, source, target.capture_id)],
    }
    payload = canonical_bytes(value)
    if len(payload) > MAX_INPUT_BYTES:
        raise AnalysisError('ANALYSIS_INPUT_LIMIT')
    return PreparedAnalysis(source_key, target.capture_id, target.source_hash,
                            value['baseline']['accepted_revision'], value['baseline']['summary_id'],
                            payload.decode('utf-8'), sha256_bytes(payload))


def _validate_chain(stage, key, chain, snapshots):
    if (key.rule_hash != stage.definition_hash or key.provider_id != stage.descriptor.provider_id
            or len({row.capture_id for row in chain}) != len(chain)):
        raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
    previous = None
    for sequence, (reference, source) in enumerate(zip(chain, snapshots), 1):
        identity = source.identity
        if (type(reference.sequence) is not int or reference.sequence != sequence
                or reference.previous_capture_id != previous
                or reference.identity != identity
                or (identity.provider_id, identity.endpoint_id, identity.stable_id)
                != (key.provider_id, key.endpoint_id, key.stable_id)):
            raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
        previous = reference.capture_id


def _baseline_start(baseline, chain, binding, profile_revision):
    if baseline is None:
        return 0
    positions = [index for index, row in enumerate(chain) if row.capture_id == baseline.target_capture_id]
    if (len(positions) != 1 or type(baseline.revision) is not int or baseline.revision < 1
            or not baseline.summary_id or baseline.candidate.get('binding') != binding
            or baseline.candidate.get('profile_revision') != profile_revision
            or chain[positions[0]].source_hash != baseline.source_hash):
        raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
    return positions[0]


def _evidence(reference, source, target_id):
    values = [('fields', 'field', 'fields', '/fields', source.facts)]
    for kind, collection, items in (
        ('comment', 'comments', source.comments_by_id), ('history', 'history', source.history_by_id),
    ):
        for source_id, value in sorted(items.items()):
            pointer = source_id.replace('~', '~0').replace('/', '~1')
            values.append((f'{kind}:{source_id}', kind, source_id, f'/{collection}/{pointer}', value))
    for ref_id, kind, source_id, pointer, value in values:
        if reference.capture_id != target_id:
            ref_id = f'archived:{reference.capture_id}:{ref_id}'
        yield {
            'ref_id': ref_id, 'kind': kind, 'source_id': source_id, 'json_pointer': pointer,
            'value': value, 'source_hash': content_hash(value), 'capture_id': reference.capture_id,
        }


def _delta(segment, baseline):
    added, updated, deleted = set(), set(), set()
    if baseline is None:
        added.update(f'comment:{key}' for key in segment[0][1].comments_by_id)
        added.update(f'history:{key}' for key in segment[0][1].history_by_id)
    for (_, previous), (_, current) in zip(segment, segment[1:]):
        if previous.facts != current.facts:
            updated.add('fields')
        for kind, before, after in (
            ('comment', previous.comments_by_id, current.comments_by_id),
            ('history', previous.history_by_id, current.history_by_id),
        ):
            added.update(f'{kind}:{key}' for key in after.keys() - before.keys())
            deleted.update(f'{kind}:{key}' for key in before.keys() - after.keys())
            updated.update(f'{kind}:{key}' for key in before.keys() & after.keys()
                           if before[key] != after[key])
    return {
        'from_capture_id': None if baseline is None else baseline.target_capture_id,
        'to_capture_id': segment[-1][0].capture_id,
        'added_ids': sorted(added), 'updated_ids': sorted(updated), 'deleted_ids': sorted(deleted),
    }
