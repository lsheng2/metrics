from project_management.app.domain.report_contracts import ReportError
from project_management.storage.report_preparations import ReportPreparationStore


def verify_active_preparation_binding(service, repository, draft, draft_store):
    context = draft.authoring_context
    if context is None or context.get('report_role') != 'daily' or draft.selection.parent_publication_id is not None:
        return
    binding = draft_store.preparation_binding(draft.draft_id)
    if binding is None or binding['kind'] == 'internal_prepared_context':
        return
    store = ReportPreparationStore(repository, service.archive.config.root, service.archive.config.limits)
    intent = store.intent(binding['preparation_id'])
    slot = store.slot(intent['slot_id'])
    if (binding['preparation_intent_hash'] != store._hash(intent)
            or slot is None
            or slot['preparation_id'] != intent['preparation_id']
            or slot['intent_hash'] != store._hash(intent)):
        raise ReportError('REPORT_REVISION_CONFLICT')
