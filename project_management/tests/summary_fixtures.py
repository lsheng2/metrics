from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import uuid

from project_management.app.api.capture_archive import PartCoverage, StoredSnapshotRef
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.summary_contracts import AiBackendTarget, AnalysisAttempt
from project_management.app.domain.summary_input import build_initial_input
from project_management.out.ai_task_contract import AiTaskContract
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


PACK_ROOT = Path(__file__).resolve().parents[1] / 'ai_bundle' / 'strict-summary' / 'task-run-contract-0.1.0a2'


class SummaryScenario(CaptureArchiveScenario):
    def setUp(self):
        super().setUp()
        self.contract = AiTaskContract.load(PACK_ROOT)

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

    def backend(self):
        return AiBackendTarget('http://127.0.0.1:18888', 'metrics-dashboard', 'store-fixture',
                               f'projects.{self.project.id}.stages.{self.stage.id}',
                               'dashboard-join-1', 'base-b-cancel-synthetic-1')

    def prepared(self):
        ref, snapshot = self.summary_source()
        return build_initial_input(self.project.id, self.stage, self.source_key(self.intent()), ref,
                                   snapshot, 'project-reporting.summary@review-1')

    def attempt(self, prepared=None, backend=None):
        prepared, backend = prepared or self.prepared(), backend or self.backend()
        attempt_id = str(uuid.uuid5(uuid.UUID(self.stage.id), prepared.input_hash))
        request = {
            'clientRunKey': attempt_id, 'scopeKey': backend.scope_key, 'profile': self.contract.profile_ref,
            'input': {'mediaType': 'application/json', 'content': prepared.input_content,
                      'sha256': prepared.input_hash},
            'logicalInputHash': {'algorithm': 'dashboard-json-review-1', 'digest': prepared.input_hash},
            'deadlineAt': (datetime.now(UTC) + timedelta(minutes=5)).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'limits': {'maxInputBytes': len(prepared.input_content.encode()), 'maxOutputBytes': 65536,
                       'maxInputTokens': None, 'maxOutputTokens': None},
            'minimumResultRetentionSeconds': 60,
        }
        return AnalysisAttempt(attempt_id, self.project.id, self.stage.id, prepared.source_key, backend,
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
        receipt = {
            'revision': 1, 'executionMode': 'synthetic', 'backendId': 'fixture', 'modelName': None,
            'qualificationRef': None, 'inputTokens': {'value': None, 'certainty': 'unknown'},
            'outputTokens': {'value': None, 'certainty': 'unknown'},
            'providerRequests': {'value': 0, 'certainty': 'known'},
            'cost': {'amountDecimal': None, 'currency': None, 'certainty': 'unknown'},
        }
        common = {
            'contractVersion': 'task-run/1', 'runStoreId': attempt.backend.run_store_id, 'runId': 'run-fixture',
            'scopeKey': attempt.request['scopeKey'],
            'profile': dict(attempt.request['profile'], definitionSha256=attempt.profile_definition_hash),
            'inputSha256': attempt.prepared.input_hash, 'logicalInputHash': attempt.request['logicalInputHash'],
            'effectiveInputSha256': hashlib.sha256(b'synthetic compiled fixture').hexdigest(), 'receipt': receipt,
        }
        result = dict(common, outputSchemaSha256=attempt.output_schema_hash, content=content,
                      mediaType='application/json', sha256=output_hash)
        snapshot = dict(
            common, sourceAppId=attempt.backend.source_app_id, clientRunKey=attempt.attempt_id,
            state='succeeded', lifecycleVersion=2, acceptedAt='2026-11-02T00:00:00.000Z',
            updatedAt='2026-11-02T00:00:30.000Z', terminalAt='2026-11-02T00:00:30.000Z',
            deadlineAt=attempt.request['deadlineAt'], grantRevision=attempt.backend.grant_revision,
            limitPolicyRevision=attempt.backend.limit_policy_revision, acceptedLimits=attempt.request['limits'],
            resultRetentionSeconds=3600, observationRetentionSeconds=7200,
            observationExpiresAt='2026-11-02T02:00:30.000Z', unresolvedExposure=False,
            dispatch={'attemptCount': 1, 'knowledge': 'response_received', 'remoteStop': 'not_requested'},
            result={'availability': 'available', 'sha256': output_hash, 'mediaType': 'application/json',
                    'expiresAt': '2026-11-02T01:00:30.000Z'}, error=None,
        )
        return snapshot, result
