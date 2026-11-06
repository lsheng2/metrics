import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.tests.history_persistence_fixtures import history_fixture, prepare_daily


@pytest.mark.django_db(transaction=True)
def test_should_reject_seed_when_path_preparation_id_differs_from_embedded_binding(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    seed_path = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime' / 'report-preparations' / day1.preparation_id / 'context.json'
    seed = decode_json(seed_path.read_bytes())
    seed['preparation_id'] = '71000000-0000-4000-8000-000000009999'
    seed_path.write_bytes(canonical_bytes(seed))

    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.create_authored(
            fixture.actor, fixture.project.id, fixture.stage.id,
            command_id=day1.command_id, selection=day1.selection,
            template=fixture.template_selection, preparation_id=day1.preparation_id,
        )

    assert error.value.code in {'REPORT_REVISION_CONFLICT', 'REPORT_ARTIFACT_INVALID'}
