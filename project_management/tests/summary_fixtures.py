from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import uuid

from project_management.app.api.capture_archive import MembershipInput, PartCoverage, StoredSnapshotRef
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.summary_contracts import AnalysisAttempt
from project_management.app.domain.task_runs import (
    TaskDispatch, TaskPrincipal, TaskResultSummary, TaskRunResult, TaskRunSnapshot,
)
from project_management.app.domain.summary_input import build_initial_input
from project_management.app.api.ai_profiles import load_task_profile
from project_management.services.task_contracts import SummaryTaskContract
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


PACK_ROOT = Path(__file__).resolve().parents[1] / 'ai_bundle' / 'strict-summary' / 'task-run-contract-0.1.0a2'


class SummaryScenario(CaptureArchiveScenario):
    def setUp(self):
        super().setUp()
        self.contract = SummaryTaskContract(load_task_profile('metrics.project_summary'))

    def summary_source(self):
        original = self.snapshot(('raw-1',))
        snapshot = replace(
            original,
            facts={'summary': 'Intermittent validation failure', 'status': 'Fixed',
                   'assignee': {'key': 'dev-a', 'displayName': 'Alice'},
                   'reporter': {'key': 'qa-b', 'displayName': 'Bob'}},
            comments_by_id={
                '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
                '202': {'id': '202', 'body': 'Logs attached. Failure reproduced on build r7.'},
                '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
            },
            coverage=replace(original.coverage, comments=PartCoverage('complete', 'comments-v1', 3, 3, None),
                             history=PartCoverage('complete', 'history-v1', 0, 0, None)),
        )
        ref = StoredSnapshotRef(snapshot.identity, str(uuid.uuid4()), 1, None, 'a' * 64, 'snapshot.json')
        return ref, snapshot

    def principal(self):
        return TaskPrincipal(
            subject=self.actor.subject, runtime_subject=self.actor.subject,
            display_name=self.actor.subject, anonymous=False,
        )

    def capture_source(self, archive, snapshot=None):
        _, initial = self.summary_source()
        intent = replace(self.intent(), required_parts=('facts', 'comments', 'history'))
        archive.prepare(self.actor, intent)
        page = archive.append_page(self.actor, intent, self.page())
        source = replace(snapshot or initial, raw_page_ids=(page.page_id,))
        archive.append_snapshot(self.actor, intent, source)
        complete = source.consistent and all(
            getattr(source.coverage, part).state == 'complete' for part in intent.required_parts
        )
        archive.finalize(
            self.actor, intent,
            MembershipInput((source.identity,), self.complete_part(), (page.page_id,)),
            complete=complete, failure_code=None if complete else 'SOURCE_INCOMPLETE',
        )
        return self.source_key(intent, source.identity)

    def prepared(self):
        ref, snapshot = self.summary_source()
        return build_initial_input(self.project.id, self.stage, self.source_key(self.intent()), ref,
                                   snapshot, self.contract.profile_ref)

    def attempt(self, prepared=None, principal=None):
        prepared, principal = prepared or self.prepared(), principal or self.principal()
        attempt_id = str(uuid.uuid5(uuid.UUID(self.stage.id), prepared.input_hash))
        request = self.contract.make_request(prepared, attempt_id, datetime.now(UTC) + timedelta(minutes=5))
        return AnalysisAttempt(attempt_id, self.project.id, self.stage.id, prepared.source_key, principal,
                               prepared, request, self.contract.definition_hash, self.contract.output_schema_hash)

    def output(self, prepared):
        value = json.loads(prepared.input_content)
        return {
            'kind': 'summary', 'binding': value['binding'], 'profile_revision': value['profile_revision'],
            'base_summary_id': None, 'target_capture_id': prepared.target_capture_id, 'output_language': 'en',
            'what': 'Intermittent failure during validation.',
            'current_position': 'The item is marked Fixed. A validation rerun on build r8 is requested.',
            'verification': 'The supplied evidence does not confirm that the rerun passed.',
            'next_actions': [{
                'action': 'Rerun validation on build r8.', 'owner_id': 'qa-b', 'owner_basis': 'explicit',
                'owner_quote': 'Bob (qa-b), please rerun validation on build r8.',
                'owner_confirmed': False, 'state': 'open', 'evidence': ['comment:203'],
            }],
            'blockers': [], 'limitations': [], 'evidence': ['fields', 'comment:201', 'comment:202', 'comment:203'],
        }

    def responses(self, attempt, output=None):
        content = canonical_bytes(output or self.output(attempt.prepared)).decode()
        output_hash = hashlib.sha256(content.encode()).hexdigest()
        dispatch = TaskDispatch(
            provider='openai-compatible', model='scripted', runtime_version='0.1.0',
            profile_definition_sha256=attempt.profile_definition_hash, tool_definition_sha256=None,
            dispatched=True, uncertainty='dispatched', usage=None,
        )
        common = dict(
            run_id='run-fixture', profile_id=attempt.request.profile_id,
            profile_version=attempt.request.profile_version, status='succeeded',
            source_input_sha256=attempt.prepared.input_hash,
            input_sha256=attempt.prepared.input_hash, effective_input_sha256=attempt.prepared.input_hash,
            dispatch=dispatch, error_code=None, retry=None,
        )
        result = TaskRunResult(
            **common, output_schema_sha256=attempt.output_schema_hash,
            output_sha256=output_hash, content_json=content, usage=None,
        )
        snapshot = TaskRunSnapshot(
            **common, result=TaskResultSummary(
                output_sha256=output_hash, output_schema_sha256=attempt.output_schema_hash, usage=None,
            ),
        )
        return snapshot, result
