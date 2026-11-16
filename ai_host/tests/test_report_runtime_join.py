from dataclasses import replace
import threading
import time
from uuid import uuid4

import pytest

from ai_base_runtime import start_blocking
from ai_base_runtime.spi import HostConfig, LifecycleLimits
from ai_base_runtime.testkit import InMemoryHost, scripted_model_endpoint

from ai_host.package import METRICS_APP
from ai_host.settings import RUNTIME_START_SECONDS, build_runtime_settings
from ai_host.task_runs import RuntimeTaskRunPort
from ai_host.tests.test_summary_runtime_join import completion
from project_management.app.api.ai_profiles import load_task_profile
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.report_assists import available_targets, build_assist_input
from project_management.app.domain.report_authoring import AuthoredEditRequest
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.task_runs import TaskPrincipal, TaskRunError
from project_management.services.report_assist_receipts import ReportAssistReceiptVerifier
from project_management.services.report_assists import ReportAssistService
from project_management.services.task_contracts import AuthoringTaskContract
from project_management.storage.report_assists import ReportAssistStore
from project_management.tests.history_persistence_fixtures import (
    git_head, history_fixture, note_by_id, prepare_daily, publication_file_bytes, ref_for,
)


@pytest.mark.django_db(transaction=True)
def test_installed_runtime_recovers_authoring_and_preserves_native_archive_provenance(tmp_path, monkeypatch):
    fixture = history_fixture(tmp_path, actor_subject='basic:alice')
    args = (fixture.actor, fixture.project.id, fixture.stage.id)
    day = prepare_daily(fixture, 1, '2026-11-02', None)
    drafts = fixture.draft_service
    draft = drafts.create_authored(
        *args, command_id=day.command_id, selection=day.selection,
        template=fixture.template_selection, preparation_id=day.preparation_id,
    )
    target = next(item for item in available_targets(draft) if item.target['scope'] == 'daily_note')
    instruction = 'Summarize the current next action.'
    value = build_assist_input(draft, (target.target_id,), instruction)
    fragment = plain_text_fragment('Review the validation result.')
    evidence_ref = next(item['ref_id'] for item in value['evidence']
                        if item['source_key'] == target.source_key)
    output = {'schema_version': 1, 'targets': [{
        'target_id': target.target_id, 'status': 'filled', 'fragment': fragment,
        'evidence_refs': [evidence_ref], 'reason_code': None,
    }]}
    principal = TaskPrincipal(
        subject=fixture.actor.subject, runtime_subject='alice', display_name='Alice', anonymous=False,
    )
    contract = AuthoringTaskContract(load_task_profile('metrics.report_authoring'))
    drafts.assist_verifier = ReportAssistReceiptVerifier(contract)
    state = tmp_path / 'runtime'
    state.mkdir()
    threads = {thread.ident for thread in threading.enumerate()}
    with scripted_model_endpoint([completion(output)]) as endpoint:
        host = InMemoryHost(HostConfig(
            state_dir=state, allowed_hosts=('127.0.0.1',),
            lifecycle=LifecycleLimits(stop_timeout_seconds=1.0), model=endpoint.model,
        ))
        context = start_blocking(
            build_runtime_settings(), host, (METRICS_APP,), start_timeout=RUNTIME_START_SECONDS,
        )
        with context as handle:
            port = RuntimeTaskRunPort(handle.blocking.task_runs)
            actual_start = port.start
            admitted = []

            def lose_admitted_reply(owner, request):
                snapshot = actual_start(owner, request)
                admitted.append((request, snapshot.run_id))
                raise TaskRunError('RUN_UNAVAILABLE', runtime_code='runtime_call_timeout', retry='observe')

            monkeypatch.setattr(port, 'start', lose_admitted_reply)
            service = ReportAssistService(
                drafts, contract, task_run_port=port, principal_resolver=lambda actor: principal,
            )
            first = service.submit(
                *args, draft.draft_id, command_id=str(uuid4()), expected_revision=draft.revision,
                expected_revision_hash=draft.revision_hash, target_ids=(target.target_id,), instruction=instruction,
            )
            with fixture.archive._report_repository(*args, write=False) as repository:
                observations = ReportAssistStore(repository).observations(first.assist_id)
            diagnosis = [{key: item.get(key) for key in ('operation', 'state', 'code', 'retry', 'error_code')}
                         for item in observations]
            assert first.state == 'unknown', diagnosis
            original = service._read_intent(*args, draft.draft_id, first.assist_id)['request']
            restored = ReportAssistService(
                drafts, contract, task_run_port=port, principal_resolver=lambda actor: principal,
            )
            deadline = time.monotonic() + 60
            ready = restored.observe(*args, draft.draft_id, first.assist_id)
            while ready.state in {'unknown', 'observing'}:
                assert time.monotonic() < deadline, ready
                assert ready.error_code != 'REPORT_AI_LIMIT', ready
                time.sleep(0.05)
                ready = restored.observe(*args, draft.draft_id, first.assist_id)
            assert ready.state == 'candidate_ready', ready
            assert len(admitted) == 1
            assert restored._read_intent(*args, draft.draft_id, first.assist_id)['request'] == original
            candidate = restored.candidate(*args, draft.draft_id, first.assist_id)
            assert canonical_bytes(candidate) == canonical_bytes(output)
            request = AuthoredEditRequest(
                str(uuid4()), target.kind, target.target, fragment,
                target.expected_original_hash, assist_receipt_id=first.assist_id,
            )
            saved = drafts.save_authored(
                *args, draft.draft_id, command_id=str(uuid4()), expected_revision=draft.revision,
                expected_revision_hash=draft.revision_hash, edits=(request,),
            )
            reference = saved.authored_edits[0].source_ai_result_ref
            assert reference['schema_version'] == 2
            assert reference['run_id'] == admitted[0][1]
            assert 'run_store_id' not in reference
            note_id = target.target['note_id']
            revised_fragment = plain_text_fragment('Human reviewed the validation result.')
            revised_fragment['blocks'][0]['content'][0]['foreground'] = '#0055aa'
            manual = replace(
                request, fragment=revised_fragment, assist_receipt_id=None,
                expected_original_hash=note_by_id(saved.authoring_context, note_id)['body_hash'],
            )
            revised = drafts.save_authored(
                *args, draft.draft_id, command_id=str(uuid4()), expected_revision=saved.revision,
                expected_revision_hash=saved.revision_hash, edits=(manual,),
            )
            assert revised.authored_edits[0].origin == 'human'
            assert revised.authored_edits[0].source_ai_result_ref == reference
            publication = drafts.finalize_and_commit(
                *args, draft.draft_id, command_id=str(uuid4()), expected_revision=revised.revision,
            )
            original_files = publication_file_bytes(fixture, publication)
            fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
            next_day = prepare_daily(fixture, 2, '2026-11-03', ref_for(publication))
            inherited = drafts.create_authored(
                *args, command_id=next_day.command_id, selection=next_day.selection,
                template=fixture.template_selection, preparation_id=next_day.preparation_id,
            )
            note = note_by_id(inherited.authoring_context, note_id)
            assert canonical_bytes(note['body_fragment']) == canonical_bytes(revised_fragment)
            assert note['provenance']['ai_result_ref'] == reference
            assert note['provenance']['origin'] == 'human'
            assert publication_file_bytes(fixture, publication) == original_files
            assert len(endpoint.requests) == 1
        assert handle.stop_result.completed
        assert handle.stop_result.persistent_state_flushed
        assert handle.stop_result.unclosed_resources == ()
    assert not [thread.name for thread in threading.enumerate() if thread.ident not in threads]
