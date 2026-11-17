from copy import deepcopy

import pytest

from project_management.app.domain.run_admission_values import admission_hash, validate_stored_request
from project_management.app.domain.run_contracts import RunError
from project_management.tests.project_run_fixtures import ManualRunEnvironment
from project_management.tests.test_project_worker_runtime_port import TypedTaskRunPort, submit_run


def admitted(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive')
    environment.install_summary_service(TypedTaskRunPort(environment))
    operation = submit_run(environment)
    repository = environment.run_service._store(
        environment.actor, environment.project.id, environment.stage.id,
    )
    return environment, operation, repository._required_request(operation.operation_id)


def test_admission_records_the_host_principal_and_exact_profile_without_legacy_backend(tmp_path):
    environment, operation, record = admitted(tmp_path)
    assert record['schema_version'] == 3
    assert 'backend' not in record and 'execution_mode' not in record
    assert not hasattr(operation, 'execution_mode')
    _, _, binding, _, _ = validate_stored_request(record)
    assert binding.principal.subject == environment.actor.subject
    assert binding.profile_id == environment.contract.profile.id
    assert binding.profile_version == environment.contract.profile.version
    assert binding.profile_definition_sha256 == environment.contract.definition_hash
    assert binding.output_schema_sha256 == environment.contract.output_schema_hash
    assert binding.model_identity == {'provider': 'typed-test-port', 'model': 'scripted'}
    assert binding.runtime_version == '0.1.0-test'


@pytest.mark.parametrize('version', [1, 2, True])
def test_old_admission_versions_are_rejected_even_after_rehashing(tmp_path, version):
    _, _, record = admitted(tmp_path)
    record['schema_version'] = version
    record['admission_hash'] = admission_hash(record)
    with pytest.raises(RunError, match='Run storage is invalid'):
        validate_stored_request(record)


def test_admission_principal_cannot_be_replaced_by_another_archive_owner(tmp_path):
    _, _, record = admitted(tmp_path)
    changed = deepcopy(record)
    changed['actor_subject'] = 'another-owner'
    changed['admission_hash'] = admission_hash(changed)
    with pytest.raises(RunError, match='Run storage is invalid'):
        validate_stored_request(changed)


class MissingAdmissionIdentityPort(TypedTaskRunPort):
    def admission_metadata(self):
        raise AttributeError('admission identity unavailable')


def test_missing_admission_identity_cannot_write_request_record(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive')
    environment.install_summary_service(MissingAdmissionIdentityPort(environment))

    with pytest.raises(RunError) as error:
        submit_run(environment)

    operations = (
        tmp_path / 'archive' / 'projects' / environment.project.id / 'stages' / environment.stage.id
        / 'runtime' / 'operations'
    )
    assert error.value.code == 'RUN_UNAVAILABLE'
    assert not tuple(operations.rglob('request.json')) if operations.exists() else True


def test_real_unconfigured_runtime_port_reports_project_unavailable_without_persisting_request(tmp_path):
    from ai_host.task_runs import RuntimeTaskRunPort

    environment = ManualRunEnvironment(tmp_path / 'archive')
    environment.install_summary_service(RuntimeTaskRunPort(object(), admission_metadata=None))

    with pytest.raises(RunError) as error:
        submit_run(environment)

    operations = (
        tmp_path / 'archive' / 'projects' / environment.project.id / 'stages' / environment.stage.id
        / 'runtime' / 'operations'
    )
    assert error.value.code == 'RUN_UNAVAILABLE'
    assert not tuple(operations.rglob('request.json')) if operations.exists() else True


@pytest.mark.parametrize('field,value', [
    ('backend', {'scope_key': 'legacy'}),
    ('execution_mode', 'synthetic'),
])
def test_schema3_admission_rejects_retired_active_wire_fields(tmp_path, field, value):
    _, _, record = admitted(tmp_path)
    record[field] = value
    record['admission_hash'] = admission_hash(record)
    with pytest.raises(RunError, match='Run storage is invalid'):
        validate_stored_request(record)
