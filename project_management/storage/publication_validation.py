from project_management.app.domain.report_draft_values import bytes_hash
from project_management.app.domain.report_publication_validation import validate_publication_files
from project_management.storage.report_decoding import verified_revision


def verified_packet(repository, publication_id, files, context, actor_subject):
    key = (
        'publication-validation/1', publication_id, context.project_id, context.stage_id,
        context.owner_subject, context.rule_hash, actor_subject,
        tuple(sorted((name, bytes_hash(data)) for name, data in files.items())),
    )
    return repository.validated(
        key, lambda: validate_publication_files(
            publication_id, files, context, actor_subject,
            decode_revision=lambda value: verified_revision(repository, value),
        ),
    )
