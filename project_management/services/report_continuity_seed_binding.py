from dataclasses import asdict

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_draft_values import validate_hash_text, validate_uuid_text
from project_management.app.domain.report_continuity import meeting_key, period_identity, period_key


def seed_binding(service, actor, project_id, stage_id, preparation_id, create_command_id,
                 draft_id, series_id, series_policy_hash, expected_baseline_ref, selection,
                 template_use_hash, meeting, period, authority, preservation=None):
    baseline = None if expected_baseline_ref is None else asdict(expected_baseline_ref)
    binding = {
        'preparation_id': validate_uuid_text(preparation_id),
        'create_command_id': validate_uuid_text(create_command_id),
        'draft_id': validate_uuid_text(draft_id),
        'project_id': validate_uuid_text(str(project_id)),
        'stage_id': validate_uuid_text(str(stage_id)),
        'owner_subject': actor.subject,
        'series_id': validate_uuid_text(str(series_id)),
        'series_policy_hash': validate_hash_text(series_policy_hash),
        'effective_selection_hash': service._hash({'selection': selection, 'baseline': baseline}),
        'template_use_hash': validate_hash_text(template_use_hash),
        'expected_baseline_ref': baseline,
        'meeting_key': meeting_key(meeting),
        'period_key': period_key(period),
        'authority': authority,
    }
    if preservation is not None:
        binding['preservation'] = preservation
    return binding


def binding_from_seed(seed):
    keys = {'preparation_id', 'create_command_id', 'draft_id', 'project_id', 'stage_id', 'owner_subject',
            'series_id', 'series_policy_hash', 'effective_selection_hash', 'template_use_hash',
            'expected_baseline_ref', 'meeting_key', 'period_key'}
    if 'authority' in seed:
        keys = keys | {'authority'}
    if seed.get('schema_version') == 3:
        keys = keys | {'preservation'}
    return {**{key: seed[key] for key in keys}, 'authority': seed.get('authority')}


def build_context_seed(service, binding, stage, policy, meeting, pinned, snapshot, context):
    context_hash = sha256_bytes(canonical_bytes(context))
    authority = binding.pop('authority')
    preservation = binding.pop('preservation', None)
    return {
        **binding,
        'schema_version': 3 if preservation is not None else (1 if authority is None else 2),
        'stage_hash': stage.definition_hash,
        'meeting_key': meeting_key(meeting),
        'period_key': period_key(period_identity(meeting)),
        'snapshot_hash': sha256_bytes(canonical_bytes(snapshot)),
        'context': context,
        'context_hash': context_hash,
        'created_at': service._now(),
        'template_request_hash': pinned.request_hash,
        'series_policy_revision': policy.revision,
        **({} if authority is None else {'authority': authority}),
        **({} if preservation is None else {'preservation': preservation}),
    }
