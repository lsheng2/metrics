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
