from project_management.app.domain.report_preparation import PreparationResult


def operation_preparation_result(service, actor, project_id, stage_id, intent, disposition, request):
    operation = service.run_service.submit(
        actor,
        project_id,
        stage_id,
        service._daily_run_request(intent),
    )
    review_issues = ()
    if operation.draft_id is not None:
        review_issues = service.draft_service.get(
            actor, project_id, stage_id, operation.draft_id,
        ).preservation_review_issues
    return PreparationResult(
        disposition,
        intent['preparation_id'],
        operation.operation_id,
        intent['draft_id'],
        operation.draft_revision,
        None,
        service._public_selection(intent['effective_selection']),
        () if disposition == 'created' else service._conflicts(service._public_selection(intent['effective_selection']), request),
        operation.state,
        {},
        review_issues,
    )


def draft_preparation_result(service, actor, project_id, stage_id, intent, disposition, draft, request):
    effective = service._public_selection(intent['effective_selection'])
    publication_ref, links = service._links(actor, project_id, stage_id, draft)
    return PreparationResult(
        disposition,
        intent['preparation_id'],
        None,
        draft.draft_id,
        draft.revision,
        publication_ref,
        effective,
        () if disposition == 'created' else service._conflicts(effective, request),
        draft.state,
        links,
        draft.preservation_review_issues,
    )
