from project_management.app.domain.capture_values import canonical_bytes, content_hash, sha256_bytes
from project_management.app.domain.summary_contracts import AnalysisError, PreparedAnalysis


REQUIRED_PARTS = ('facts', 'comments', 'history')
MAX_INPUT_BYTES = 65536
MAX_EVIDENCE = 64
MAX_CHAIN = 100


def build_initial_input(project_id, stage, source_key, reference, snapshot, profile_revision):
    if reference.sequence != 1 or reference.previous_capture_id is not None:
        raise AnalysisError('ANALYSIS_DELTA_REQUIRED')
    require_complete_source(snapshot)
    if (source_key.rule_hash != stage.definition_hash
            or (source_key.provider_id, source_key.endpoint_id, source_key.stable_id)
            != (snapshot.identity.provider_id, snapshot.identity.endpoint_id, snapshot.identity.stable_id)
            or snapshot.identity != reference.identity):
        raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
    if 1 + len(snapshot.comments_by_id) + len(snapshot.history_by_id) > MAX_EVIDENCE:
        raise AnalysisError('ANALYSIS_INPUT_LIMIT')
    evidence = [_evidence('fields', 'field', 'fields', '/fields', snapshot.facts, reference.capture_id)]
    for kind, collection, values in (
        ('comment', 'comments', snapshot.comments_by_id), ('history', 'history', snapshot.history_by_id),
    ):
        for source_id, value in sorted(values.items()):
            escaped = source_id.replace('~', '~0').replace('/', '~1')
            evidence.append(_evidence(f'{kind}:{source_id}', kind, source_id, f'/{collection}/{escaped}',
                                      value, reference.capture_id))
    value = {
        'fixture_version': 'review-1',
        'profile_revision': profile_revision,
        'binding': {'project_id': project_id, 'stage_id': stage.id, 'provider': source_key.provider_id,
                    'site': stage.descriptor.endpoint, 'stable_id': source_key.stable_id,
                    'rule_hash': source_key.rule_hash, 'principal_id': source_key.principal_id},
        'target_capture_id': reference.capture_id,
        'baseline': {'summary_id': None, 'accepted_revision': 0, 'capture_id': None, 'text': None},
        'required_parts': list(REQUIRED_PARTS),
        'coverage': {part: 'complete' for part in REQUIRED_PARTS},
        'delta': {'from_capture_id': None, 'to_capture_id': reference.capture_id,
                  'added_ids': sorted(snapshot.comments_by_id), 'updated_ids': [], 'deleted_ids': []},
        'evidence': evidence,
    }
    payload = canonical_bytes(value)
    if len(payload) > MAX_INPUT_BYTES:
        raise AnalysisError('ANALYSIS_INPUT_LIMIT')
    return PreparedAnalysis(source_key, reference.capture_id, reference.source_hash, 0, None,
                            payload.decode('utf-8'), sha256_bytes(payload))


def require_complete_source(snapshot):
    if (not snapshot.consistent
            or any(getattr(snapshot.coverage, part).state != 'complete' for part in REQUIRED_PARTS)):
        raise AnalysisError('ANALYSIS_SOURCE_INCOMPLETE')
    if snapshot.attachments_by_id or snapshot.dependencies_by_id:
        raise AnalysisError('ANALYSIS_PART_UNSUPPORTED')
    for name in ('attachments', 'dependencies'):
        part = getattr(snapshot.coverage, name)
        if (part.state not in {'not_requested', 'complete'}
                or part.observed_count not in (None, 0) or part.total_count not in (None, 0)
                or (part.state == 'complete' and (part.observed_count != 0 or part.total_count != 0))):
            raise AnalysisError('ANALYSIS_PART_UNSUPPORTED')


def complete_source(snapshot):
    try:
        require_complete_source(snapshot)
    except AnalysisError:
        return False
    return True


def _evidence(ref_id, kind, source_id, pointer, value, capture_id):
    return {'ref_id': ref_id, 'kind': kind, 'source_id': source_id, 'json_pointer': pointer,
            'value': value, 'source_hash': content_hash(value), 'capture_id': capture_id}


def unchanged_since(capture_id, source_hash, chain):
    positions = [index for index, row in enumerate(chain) if row.capture_id == capture_id]
    if len(positions) != 1 or not chain or len(chain) > MAX_CHAIN:
        return False
    window = chain[positions[0]:]
    if len({row.capture_id for row in window}) != len(window):
        return False
    if any(current.sequence != previous.sequence + 1 or current.previous_capture_id != previous.capture_id
           for previous, current in zip(window, window[1:])):
        return False
    return all(row.source_hash == source_hash for row in window)
