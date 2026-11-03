from project_management.app.domain.run_contracts import RunError


FINAL_ITEM_STATES = {'accepted', 'no_work'}


def validate_item_progress(current_items, candidate_items):
    current = _by_source(current_items)
    candidate = _by_source(candidate_items)
    for source_hash, old in current.items():
        if source_hash not in candidate:
            raise RunError('RUN_REVISION_CONFLICT')
        new = candidate[source_hash]
        if old.attempt_id is not None and new.attempt_id != old.attempt_id:
            raise RunError('RUN_REVISION_CONFLICT')
        if old.accepted_summary_id is not None and new.accepted_summary_id != old.accepted_summary_id:
            raise RunError('RUN_REVISION_CONFLICT')
        if old.state in FINAL_ITEM_STATES and new.state != old.state:
            raise RunError('RUN_REVISION_CONFLICT')


def _by_source(items):
    result = {}
    for item in items:
        if item.source_key_hash in result:
            raise RunError('RUN_REVISION_CONFLICT')
        result[item.source_key_hash] = item
    return result
