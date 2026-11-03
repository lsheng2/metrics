from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.api.capture_archive import PartCoverage
from project_management.app.domain.summary_input import build_initial_input
from project_management.out.ai_task_contract import AiTaskContract
from project_management.tests.summary_fixtures import SummaryScenario


class TestSummaryAcceptance(SummaryScenario, unittest.TestCase):
    def test_shouldBindCandidateLocallyAndPreserveOriginalResultAndUnknownUsage(self):
        attempt = self.attempt()
        snapshot, result = self.responses(attempt)
        original = deepcopy(result)
        candidate = self.contract.validate_result(attempt, snapshot, result)
        self.assertEqual(attempt.prepared.input_hash, candidate['input_hash'])
        self.assertNotIn('input_hash', json.loads(result['content']))
        self.assertEqual(original, result)
        self.assertEqual({'value': None, 'certainty': 'unknown'}, result['receipt']['inputTokens'])

    def test_shouldRejectWrongSnapshotAuthorityBeforeAcceptingItsResult(self):
        for field, value in [
            ('runStoreId', 'another-store'), ('sourceAppId', 'other-app'), ('scopeKey', 'wrong-scope'),
            ('clientRunKey', 'different-key'), ('grantRevision', 'another-grant'),
            ('limitPolicyRevision', 'another-policy'), ('deadlineAt', '2030-01-01T00:00:00Z'),
            ('acceptedLimits', {'maxInputBytes': 1, 'maxOutputBytes': 1,
                                'maxInputTokens': None, 'maxOutputTokens': None}),
            ('state', 'canceled'), ('unresolvedExposure', True),
        ]:
            attempt = self.attempt()
            snapshot, result = self.responses(attempt)
            snapshot[field] = value
            with self.subTest(field=field), self.assertRaises(AnalysisError):
                self.contract.validate_result(attempt, snapshot, result)

    def test_shouldRejectMismatchedResultMetadataAndContentHashes(self):
        for field, value in [
            ('runId', 'other-run'), ('inputSha256', 'b' * 64), ('effectiveInputSha256', 'c' * 64),
            ('outputSchemaSha256', 'd' * 64), ('sha256', 'e' * 64), ('scopeKey', 'another-scope'),
            ('profile', {'key': 'other-profile', 'revision': 'review-1', 'definitionSha256': 'f' * 64}),
            ('logicalInputHash', {'algorithm': 'another-algorithm', 'digest': 'a' * 64}),
        ]:
            attempt = self.attempt()
            snapshot, result = self.responses(attempt)
            result[field] = value
            with self.subTest(field=field), self.assertRaises(AnalysisError):
                self.contract.validate_result(attempt, snapshot, result)

    def test_shouldRejectInventedEvidenceOwnerQuoteAndFalseConfirmation(self):
        for change in ('reference', 'owner', 'quote', 'confirmed', 'binding', 'target', 'language', 'narrative'):
            attempt = self.attempt()
            output = self.output(attempt.prepared)
            action = output['next_actions'][0]
            if change == 'reference':
                action['evidence'] = ['invented']
            elif change == 'owner':
                action['owner_id'] = 'unknown-person'
            elif change == 'quote':
                action['owner_quote'] = 'Bob confirmed the rerun passed.'
            elif change == 'confirmed':
                action['owner_confirmed'] = True
            elif change == 'binding':
                output['binding']['project_id'] = 'another-project'
            elif change == 'target':
                output['target_capture_id'] = 'another-capture'
            elif change == 'narrative':
                output['what'] = '\u539f\u6587'
            else:
                output['output_language'] = 'zh-CN'
            snapshot, result = self.responses(attempt, output)
            with self.subTest(change=change), self.assertRaises(AnalysisError):
                self.contract.validate_result(attempt, snapshot, result)

    def test_shouldPermitUnknownOwnerWithoutInventingAssignment(self):
        attempt = self.attempt()
        output = self.output(attempt.prepared)
        output['next_actions'][0].update(owner_id=None, owner_basis='unknown', owner_quote=None)
        snapshot, result = self.responses(attempt, output)
        self.assertIsNone(self.contract.validate_result(attempt, snapshot, result)['next_actions'][0]['owner_id'])

    def test_shouldRejectMissingPackInsteadOfLoadingAnotherContract(self):
        with TemporaryDirectory() as root, self.assertRaises(AnalysisError) as caught:
            AiTaskContract.load(Path(root))
        self.assertEqual('ANALYSIS_CONTRACT_INVALID', caught.exception.code)

    def test_shouldValidateAppInputAgainstTheDeliveredStrictProfile(self):
        prepared = self.prepared()
        value = json.loads(prepared.input_content)
        self.contract.validate_input(value)
        value['coverage']['history'] = 'partial'
        with self.assertRaises(AnalysisError):
            self.contract.validate_input(value)

    def test_shouldRejectNonWireDeadlineBeforeSendingEvenWhenThePackOnlyDeclaresString(self):
        request = self.attempt().request
        request['deadlineAt'] = '2030-01-01T00:01:00.123456+00:00'
        with self.assertRaises(AnalysisError):
            self.contract.validate_request(request)
        request['deadlineAt'] = '2030-01-01T00:01:00.123Z'
        self.contract.validate_request(request)

    def test_shouldRequireBlockerAndLimitationReferencesToExistInTheInput(self):
        for field in ('blockers', 'limitations'):
            attempt = self.attempt()
            output = self.output(attempt.prepared)
            output[field] = ['invented-ref']
            snapshot, result = self.responses(attempt, output)
            with self.subTest(field=field), self.assertRaises(AnalysisError):
                self.contract.validate_result(attempt, snapshot, result)
            output[field] = ['comment:202']
            snapshot, result = self.responses(attempt, output)
            self.assertEqual(['comment:202'], self.contract.validate_result(attempt, snapshot, result)[field])

    def test_shouldUseFieldHistoryAsContextButNotAsAnExplicitNextOwnerRequest(self):
        reference, snapshot = self.summary_source()
        quote = 'Bob (qa-b), please rerun validation on build r8.'
        snapshot = replace(
            snapshot, history_by_id={'h1': {'id': 'h1', 'items': [
                {'field': 'description', 'fromString': quote, 'toString': 'Current description.'},
            ]}},
            coverage=replace(snapshot.coverage, history=PartCoverage('complete', 'history-v2', 1, 1, None)),
        )
        prepared = build_initial_input(self.project.id, self.stage, self.source_key(self.intent()), reference,
                                       snapshot, 'project-reporting.summary@review-1')
        attempt = self.attempt(prepared)
        output = self.output(prepared)
        output['evidence'].append('history:h1')
        output['next_actions'][0]['evidence'] = ['history:h1']
        observed, result = self.responses(attempt, output)
        with self.assertRaises(AnalysisError) as caught:
            self.contract.validate_result(attempt, observed, result)
        self.assertEqual('ANALYSIS_OWNER_INVALID', caught.exception.code)
        output['next_actions'][0].update(owner_basis='suggested', owner_quote=None)
        observed, result = self.responses(attempt, output)
        self.assertEqual('suggested', self.contract.validate_result(attempt, observed, result)['next_actions'][0]['owner_basis'])
