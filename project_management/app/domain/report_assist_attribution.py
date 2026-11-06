from dataclasses import replace


def apply_assist_attribution(edits, previous_edits, references):
    previous = {edit.edit_id: edit for edit in previous_edits}
    result = []
    for edit in edits:
        reference = references.get(edit.edit_id)
        old = previous.get(edit.edit_id)
        if reference is not None:
            result.append(replace(edit, origin='ai_assisted', source_ai_result_ref=reference))
        elif old is not None and old.target == edit.target and old.kind == edit.kind and old.source_ai_result_ref:
            origin = old.origin if old.fragment == edit.fragment else 'human'
            result.append(replace(edit, origin=origin, source_ai_result_ref=old.source_ai_result_ref))
        else:
            result.append(edit)
    return tuple(result)


def apply_assist_context(context, edits):
    if context is None:
        return None
    notes = list(context['notes'])
    persistent = list(context['persistent_notes'])
    for edit in edits:
        if not edit.source_ai_result_ref:
            continue
        collection = notes if edit.target.get('scope') == 'daily_note' else persistent if edit.target.get('scope') == 'persistent_note' else ()
        for index, note in enumerate(collection):
            if note['note_id'] == edit.target.get('note_id'):
                collection[index] = {**note, 'provenance': {
                    **note['provenance'], 'origin': edit.origin, 'ai_result_ref': edit.source_ai_result_ref,
                }}
    return {**context, 'notes': tuple(notes), 'persistent_notes': tuple(persistent)}
