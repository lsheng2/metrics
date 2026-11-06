import json

import pytest

from project_management.app.api.reports import ReportError
from project_management.tests.test_report_preparation_store import fake_store, preparation_intent


IDENTIFIER = '10000000-0000-4000-8000-000000000001'
RECORDS = (
    ('find_intent', f'report-preparations/{IDENTIFIER}/intent.json'),
    ('slot', f'report-preparation-slots/{IDENTIFIER}.json'),
    ('command', f'report-preparation-commands/{IDENTIFIER}.json'),
)


@pytest.mark.parametrize(('method', 'relative'), RECORDS)
@pytest.mark.parametrize('malformed', (None, [], False, 'wrong shape'))
def test_shouldDistinguishMalformedPreparationRecordFromMissingRecord(tmp_path, method, relative, malformed):
    store = fake_store(tmp_path)
    path = store.runtime / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(malformed), encoding='utf-8')

    with pytest.raises(ReportError) as error:
        getattr(store, method)(IDENTIFIER)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


@pytest.mark.parametrize(('method', 'relative'), RECORDS)
def test_shouldReturnNoneOnlyForMissingPreparationRecord(tmp_path, method, relative):
    store = fake_store(tmp_path)

    assert getattr(store, method)(IDENTIFIER) is None


@pytest.mark.parametrize('kind', ('intent', 'slot', 'command'))
@pytest.mark.parametrize('version', (True, 1.0))
def test_shouldRejectNonIntegerControlRecordVersion(tmp_path, kind, version):
    store = fake_store(tmp_path)
    intent = preparation_intent()
    store.reserve(intent['command_id'], intent['request_hash'], intent['slot_id'], intent)
    targets = {
        'intent': ('find_intent', intent['preparation_id'], f"report-preparations/{intent['preparation_id']}/intent.json"),
        'slot': ('slot', intent['slot_id'], f"report-preparation-slots/{intent['slot_id']}.json"),
        'command': ('command', intent['command_id'], f"report-preparation-commands/{intent['command_id']}.json"),
    }
    method, identifier, relative = targets[kind]
    path = store.runtime / relative
    payload = json.loads(path.read_text(encoding='utf-8'))
    payload['schema_version'] = version
    path.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(ReportError) as error:
        getattr(store, method)(identifier)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
