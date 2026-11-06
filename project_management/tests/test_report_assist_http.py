from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from ai_base_application_sdk import TaskRunClient
import httpx
import pytest

from project_management.app.domain.capture_values import canonical_bytes, content_hash, sha256_bytes
from project_management.app.domain.report_assists import available_targets, build_assist_input
from project_management.app.domain.report_authoring import AuthoredEditRequest
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.summary_contracts import AiBackendTarget
from project_management.out.report_ai_task import AuthoringTaskContract, PROFILE_ROOT
from project_management.services.report_assist_receipts import ReportAssistReceiptVerifier
from project_management.services.report_assists import ReportAssistService
from project_management.tests.history_persistence_fixtures import (
    git_head, history_fixture, note_by_id, prepare_daily, publication_file_bytes, ref_for,
)
from project_management.tests.summary_fixtures import PACK_ROOT
from scripts.validation.project_summary_join import wait_connection
from scripts.validation.project_summary_support import (
    child_environment, probe_base_imports, stop_owned_fixture, verify_base_source,
)


def test_shouldSelectOnlyHashMatchedAuthoringProfileForSyntheticBase():
    from scripts.validation.project_summary_base_fixture import load_selected_profile

    manifest = json.loads((PROFILE_ROOT / 'manifest.json').read_bytes())
    assert load_selected_profile(PACK_ROOT)['key'] == 'project-reporting.summary'
    selected = load_selected_profile(PACK_ROOT, PROFILE_ROOT / 'profile.json', manifest['profile_file_sha256'])
    assert selected['key'] == 'project-reporting.authoring'
    with pytest.raises(ValueError):
        load_selected_profile(PACK_ROOT, PROFILE_ROOT / 'profile.json', '0' * 64)


@pytest.mark.django_db(transaction=True)
def test_shouldRetainAuthoringProvenanceThroughRealBaseHttpGitAndNextDay(tmp_path):
    root = Path(__file__).resolve().parents[2]
    selected = root / '.tmp/sdk-020-join-20261105'
    base_python = root.parent / 'Report_creater_agent/.venv/Scripts/python.exe'
    evidence = root / '.tmp/dashboard-assist-20261106' / f'http-{uuid4()}'
    evidence.mkdir(parents=True)
    provenance = verify_base_source(selected, selected / 'base-source')
    probe_base_imports(base_python, selected / 'base-source', tmp_path, evidence)
    fixture = history_fixture(tmp_path)
    day = prepare_daily(fixture, 1, '2026-11-02', None)
    drafts = fixture.draft_service
    args = (fixture.actor, fixture.project.id, fixture.stage.id)
    draft = drafts.create_authored(*args, command_id=day.command_id, selection=day.selection,
                                  template=fixture.template_selection, preparation_id=day.preparation_id)
    target = next(item for item in available_targets(draft) if item.target['scope'] == 'daily_note')
    instruction = 'Summarize the current next action.'
    value = build_assist_input(draft, (target.target_id,), instruction)
    candidate = plain_text_fragment('Review the validation result.')
    scope = f'projects.{fixture.project.id}.stages.{fixture.stage.id}'
    vector = {
        'scope_key': scope, 'input': value, 'input_sha256': content_hash(value),
        'output': {'schema_version': 1, 'targets': [{
            'target_id': target.target_id, 'status': 'filled', 'fragment': candidate,
            'evidence_refs': [f'record:{target.source_key}'], 'reason_code': None,
        }]},
    }
    vector_path = evidence / 'vector.json'
    vector_path.write_bytes(canonical_bytes(vector))
    profile_manifest = json.loads((PROFILE_ROOT / 'manifest.json').read_bytes())
    directory = tmp_path / 'authoring-base'
    environment = tmp_path / 'base-environment'
    environment.mkdir()
    process, connection = None, None
    with (evidence / 'base.log').open('xb') as log:
        try:
            process = subprocess.Popen(
                [str(base_python), '-I', '-B', str(root / 'scripts/validation/project_summary_base_fixture.py'),
                 '--data-dir', str(directory), '--source-root', str(selected / 'base-source'),
                 '--pack-root', str(PACK_ROOT), '--fixture', str(vector_path),
                 '--profile-file', str(PROFILE_ROOT / 'profile.json'),
                 '--profile-sha256', profile_manifest['profile_file_sha256']],
                cwd=tmp_path, env=child_environment(environment), stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            connection = wait_connection(process, directory, scope)
            backend = AiBackendTarget(
                connection['baseUrl'], connection['sourceAppId'], connection['runStoreId'],
                connection['scopeKey'], connection['grantRevision'], connection['limitPolicyRevision'],
            )

            def client(target):
                return TaskRunClient(
                    base_url=target.base_url, source_app_id=target.source_app_id,
                    run_store_id=target.run_store_id, credential_ref=connection['credentialRef'],
                    token=connection['token'], transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False),
                )

            contract = AuthoringTaskContract.load(PACK_ROOT)
            service = ReportAssistService(drafts, contract, backend=backend, client_factory=client)
            drafts.assist_verifier = ReportAssistReceiptVerifier(contract)
            ready = service.submit(*args, draft.draft_id, command_id=str(uuid4()), expected_revision=1,
                                   expected_revision_hash=draft.revision_hash,
                                   target_ids=(target.target_id,), instruction=instruction)
            for _ in range(12):
                if ready.state not in {'observing', 'unknown'}:
                    break
                time.sleep(0.15)
                ready = service.observe(*args, draft.draft_id, ready.assist_id)
            assert ready.state == 'candidate_ready', ready
            output = service.candidate(*args, draft.draft_id, ready.assist_id)
            assert canonical_bytes(candidate) == canonical_bytes(output['targets'][0]['fragment'])
            request = AuthoredEditRequest(str(uuid4()), target.kind, target.target, candidate,
                                         target.expected_original_hash, assist_receipt_id=ready.assist_id)
            saved = drafts.save_authored(
                *args, draft.draft_id, command_id=str(uuid4()), expected_revision=1,
                expected_revision_hash=draft.revision_hash, edits=(request,),
            )
            assert saved.authored_edits[0].origin == 'ai_assisted'
            ai_ref = saved.authored_edits[0].source_ai_result_ref
            note_id = target.target['note_id']
            revised_fragment = plain_text_fragment('Human reviewed the validation result.')
            revised_fragment['blocks'][0]['content'][0]['foreground'] = '#0055aa'
            manual = replace(request, fragment=revised_fragment, assist_receipt_id=None,
                             expected_original_hash=note_by_id(saved.authoring_context, note_id)['body_hash'])
            revised = drafts.save_authored(
                *args, draft.draft_id, command_id=str(uuid4()), expected_revision=2,
                expected_revision_hash=saved.revision_hash, edits=(manual,),
            )
            assert revised.authored_edits[0].origin == 'human'
            assert revised.authored_edits[0].source_ai_result_ref == ai_ref
            publication = drafts.finalize_and_commit(*args, draft.draft_id, command_id=str(uuid4()),
                                                    expected_revision=revised.revision)
            original_files = publication_file_bytes(fixture, publication)
            fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
            next_day = prepare_daily(fixture, 2, '2026-11-03', ref_for(publication))
            inherited = drafts.create_authored(
                *args, command_id=next_day.command_id, selection=next_day.selection,
                template=fixture.template_selection, preparation_id=next_day.preparation_id,
            )
            note = note_by_id(inherited.authoring_context, note_id)
            assert canonical_bytes(note['body_fragment']) == canonical_bytes(revised_fragment)
            assert note['provenance']['ai_result_ref'] == ai_ref
            assert note['provenance']['origin'] == 'human'
            assert publication_file_bytes(fixture, publication) == original_files
            events = [json.loads(line) for line in (directory / 'executor-observations.jsonl').read_text().splitlines()]
            assert len(events) == 1
            assert events[0]['inputSha256'] == vector['input_sha256']
            (evidence / 'result.json').write_bytes(canonical_bytes({
                'status': 'passed', 'sdk_version': '0.2.0a1', 'base_provenance': provenance,
                'profile': 'project-reporting.authoring@1', 'profile_hash': contract.definition_hash,
                'assist_id': ready.assist_id, 'input_hash': vector['input_sha256'], 'base_dispatches': len(events),
                'publication': publication.manifest.publication_id, 'commit': publication.commit_id,
                'inherited_note_hash': note['body_hash'], 'ai_result_ref': ai_ref,
                'publication_files': {name: sha256_bytes(data) for name, data in original_files.items()},
            }))
        finally:
            cleanup = stop_owned_fixture(process, connection, directory)
            (evidence / 'cleanup.json').write_bytes(canonical_bytes(cleanup))
            assert cleanup['normal'], cleanup
