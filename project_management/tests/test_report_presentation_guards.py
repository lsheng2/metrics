from hashlib import sha256

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.tests.report_draft_fixtures import DraftArchive, draft_command, draft_root, draft_selection
from project_management.tests.test_report_template_rendering import (
    build_service, ready_template, register_project, slot_fill,
)


@pytest.mark.django_db(transaction=True)
def test_shouldRejectUnknownPinnedRendererAtAllDraftConsumersWithoutPublication(tmp_path):
    environment = DraftArchive(tmp_path / 'archive')
    register_project(environment)
    template = ready_template(environment.actor, environment.project.id, command=draft_command(13001))
    service = build_service(environment)
    args = environment.actor, environment.project.id, environment.stage.id
    draft = service.create_authored(
        *args, command_id=draft_command(13002), selection=draft_selection(),
        template=report_api.UserTemplateSelection(str(template.template_id), template.revision, template.revision_hash),
    )
    saved = service.save_authored(
        *args, draft.draft_id, command_id=draft_command(13003), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash, edits=(slot_fill('Ready', edit=13003),),
    )
    root = draft_root(environment, draft.draft_id)
    path = root / 'revisions/00000002.json'
    payload = decode_json(path.read_bytes())
    payload['template_snapshot']['renderer_version'] = 'template-document/99'
    payload['template_definition']['renderer_version'] = 'template-document/99'
    data = canonical_bytes(payload)
    digest = sha256(data).hexdigest()
    path.write_bytes(data)
    (root / 'current.json').write_bytes(canonical_bytes({
        'schema_version': 1, 'revision': 2, 'revision_hash': digest,
    }))
    head = environment.repository.head()
    consumers = (
        lambda: service.get(*args, draft.draft_id),
        lambda: service.render(*args, draft.draft_id, revision=2),
        lambda: service.save_authored(*args, draft.draft_id, command_id=draft_command(13004),
                                      expected_revision=2, expected_revision_hash=digest, edits=()),
        lambda: service.finalize_and_commit(*args, draft.draft_id,
                                            command_id=draft_command(13005), expected_revision=2),
    )
    for consume in consumers:
        with pytest.raises(report_api.ReportError) as error:
            consume()
        assert error.value.code in {'REPORT_ARTIFACT_INVALID', 'REPORT_DOCUMENT_UNSUPPORTED'}
    assert environment.repository.head() == head
    assert not (root / 'finalization.json').exists()
