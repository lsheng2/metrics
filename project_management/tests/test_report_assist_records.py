from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from project_management.app.api.ai_profiles import load_task_profile
from project_management.app.api.reports import AuthoringTemplateSelection, ReportDraftService, ReportRenderer
from project_management.app.domain.report_assists import available_targets, build_assist_input
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.task_runs import TaskPrincipal
from project_management.services.report_assist_records import make_intent, read_assist_attempt
from project_management.services.task_contracts import AuthoringTaskContract
from project_management.tests.report_draft_fixtures import DraftArchive, StaticSourceReader, draft_selection


def record(tmp_path):
    archive = DraftArchive(tmp_path)
    drafts = ReportDraftService(archive, StaticSourceReader(rule_hash=archive.stage.definition_hash), ReportRenderer())
    draft = drafts.create_authored(
        archive.actor, archive.project.id, archive.stage.id, command_id=str(uuid4()),
        selection=draft_selection(), template=AuthoringTemplateSelection('builtin', 'daily-standup', '2'),
    )
    target = next(target for target in available_targets(draft) if target.target == {'scope': 'report'})
    value = build_assist_input(draft, (target.target_id,), 'Summarize the next action.')
    contract = AuthoringTaskContract(load_task_profile('metrics.report_authoring'))
    principal = TaskPrincipal(
        subject=archive.actor.subject, runtime_subject=archive.actor.subject,
        display_name='Author', anonymous=False,
    )
    now = datetime.now(UTC)
    intent = make_intent(draft, str(uuid4()), value, contract, principal, now)
    return intent, contract, principal, now


def test_assist_intent_preserves_typed_request_without_backend(tmp_path):
    intent, contract, principal, now = record(tmp_path)
    assert intent['schema_version'] == 2
    assert 'backend' not in intent
    attempt = read_assist_attempt(intent, contract)
    assert attempt.principal == principal
    assert attempt.request.profile_id == 'metrics.report_authoring'
    assert attempt.request.client_run_key == intent['assist_id']
    assert attempt.request.deadline_at == now + timedelta(seconds=180)
    assert read_assist_attempt(deepcopy(intent), contract) == attempt


@pytest.mark.parametrize('mutation', ['old-version', 'backend', 'wrong-principal', 'changed-key', 'changed-input'])
def test_assist_intent_rejects_legacy_and_binding_changes(tmp_path, mutation):
    intent, contract, _, _ = record(tmp_path)
    if mutation == 'old-version':
        intent['schema_version'] = 1
    elif mutation == 'backend':
        intent['backend'] = {'scope_key': 'legacy'}
    elif mutation == 'wrong-principal':
        intent['principal']['subject'] = 'another-owner'
    elif mutation == 'changed-key':
        intent['request']['client_run_key'] = 'another-request'
    else:
        intent['request']['input_json'] = '{}'
    with pytest.raises(ReportError):
        read_assist_attempt(intent, contract)
