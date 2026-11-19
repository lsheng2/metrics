from dataclasses import replace
import json
import unittest

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_assists import available_targets, build_assist_input
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.api.ai_profiles import load_task_profile
from project_management.services.task_contracts import AuthoringTaskContract
from project_management.tests.report_assist_fixtures import assist_draft
from project_management.tests.summary_fixtures import SummaryScenario


class TestReportAiTask(SummaryScenario, unittest.TestCase):
    def test_shouldUseDistinctProfileWithTypedRuntimeValidation(self):
        self.contract = AuthoringTaskContract(load_task_profile('metrics.report_authoring'))
        draft = assist_draft()
        target = available_targets(draft)[0]
        value = build_assist_input(draft, (target.target_id,), 'Summarize the next action.')
        data = canonical_bytes(value)
        prepared = replace(self.prepared(), input_content=data.decode(), input_hash=sha256_bytes(data))
        attempt = self.attempt(prepared)
        output = {'schema_version': 1, 'targets': [{
            'target_id': target.target_id, 'status': 'filled',
            'fragment': plain_text_fragment('Follow up the captured action.'),
            'evidence_refs': [value['evidence'][0]['ref_id']], 'reason_code': None,
        }]}
        snapshot, result = self.responses(attempt, output)
        self.contract.validate_request(attempt.request)
        candidate = self.contract.validate_result(attempt.prepared, attempt.request, snapshot, result)

        self.assertEqual('metrics.report_authoring@1', self.contract.profile_ref)
        self.assertEqual(canonical_bytes(output), canonical_bytes(candidate))
        with self.assertRaises(AnalysisError):
            self.contract.validate_result(
                attempt.prepared, attempt.request,
                replace(snapshot, profile_id='metrics.project_summary'),
                result,
            )
        modified = json.loads(result.content_json)
        modified['targets'][0]['target_id'] = 'f' * 64
        payload = canonical_bytes(modified)
        with self.assertRaises(Exception):
            self.contract.validate_result(
                attempt.prepared,
                attempt.request,
                snapshot,
                replace(result, content_json=payload.decode(), output_sha256=sha256_bytes(payload)),
            )
