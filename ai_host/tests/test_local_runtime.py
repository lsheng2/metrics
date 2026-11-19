from datetime import UTC, datetime, timedelta
import threading

import pytest
from django.test import override_settings

from project_management.app.api import ProjectActor
from project_management.app.api.ai_profiles import load_task_profile
from project_management.app.api.task_runtime import open_local_task_run_port
from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.task_runs import TaskRunError, TaskRunRequest


@pytest.mark.django_db(transaction=True)
def test_registered_local_port_uses_installed_runtime_and_releases_owned_thread_and_state(tmp_path):
    profile = load_task_profile('metrics.project_summary')
    request = TaskRunRequest(
        profile_id=profile.id, profile_version=profile.version,
        profile_definition_sha256=profile.definition_sha256,
        output_schema_sha256=profile.output_schema_sha256,
        input_json='{}', input_sha256=content_hash({}), client_run_key='absent-local-request',
        deadline_at=datetime.now(UTC) + timedelta(seconds=60),
        limits=profile.limits, minimum_result_retention_seconds=60,
    )
    baseline = {thread.ident for thread in threading.enumerate()}
    with override_settings(
        METRICS_STATE_DIR=str(tmp_path), METRICS_AI_MODEL_BASE_URL='',
        METRICS_AI_MODEL_NAME='', METRICS_AI_MODEL_API_KEY='', METRICS_BASIC_AUTH_USERS=None,
    ):
        with open_local_task_run_port() as local:
            principal = local.principal_resolver(ProjectActor('local_operator'))
            assert local.task_runs.lookup(principal, request) is None
        with pytest.raises(TaskRunError) as stopped:
            local.task_runs.lookup(principal, request)
        assert stopped.value.runtime_code == 'runtime_not_running'
        # A second context using the same state proves that the first released its lock.
        with open_local_task_run_port() as reopened:
            assert reopened.task_runs.lookup(principal, request) is None
    assert not [thread.name for thread in threading.enumerate() if thread.ident not in baseline]
