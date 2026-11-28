from copy import deepcopy
from dataclasses import replace
import json
import unittest

from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.api.capture_archive import PartCoverage
from project_management.app.domain.summary_input import build_initial_input
from project_management.tests.summary_fixtures import SummaryScenario


class TestSummaryAcceptance(SummaryScenario, unittest.TestCase):
    def test_output_schema_rejects_prose_in_every_evidence_reference_array(self):
        for field in ('evidence', 'blockers', 'limitations', 'action_evidence'):
            with self.subTest(field=field):
                attempt = self.attempt()
                output = self.output(attempt.prepared)
                target = output['next_actions'][0] if field == 'action_evidence' else output
                target['evidence' if field == 'action_evidence' else field] = ['Follow up [fields]']
                snapshot, result = self.responses(attempt, output)
                with self.assertRaises(AnalysisError):
                    self.contract.validate_result_envelope(attempt.request, snapshot, result)

    def test_well_formed_but_absent_reference_still_fails_business_membership(self):
        attempt = self.attempt()
        output = self.output(attempt.prepared)
        output['limitations'] = ['comment:not-in-the-input']
        snapshot, result = self.responses(attempt, output)
        self.contract.validate_result_envelope(attempt.request, snapshot, result)
        with self.assertRaises(AnalysisError):
            self.contract.validate_result(attempt.prepared, attempt.request, snapshot, result)

    def test_output_schema_preserves_current_and_archived_reference_syntax(self):
        references = [
            'fields', 'comment:201', 'history:301', 'archived:older-capture:fields',
            'archived:older-capture:comment:201', 'archived:older-capture:history:301',
        ]
        for field in ('evidence', 'blockers', 'limitations', 'action_evidence'):
            with self.subTest(field=field):
                attempt = self.attempt()
                output = self.output(attempt.prepared)
                target = output['next_actions'][0] if field == 'action_evidence' else output
                target['evidence' if field == 'action_evidence' else field] = references
                snapshot, result = self.responses(attempt, output)
                self.assertEqual(
                    output, self.contract.validate_result_envelope(attempt.request, snapshot, result),
                )

    def test_shouldBindCandidateLocallyAndPreserveOriginalResultAndUnknownUsage(self):
        attempt = self.attempt()
        snapshot, result = self.responses(attempt)
        original = deepcopy(result)
        candidate = self.contract.validate_result(attempt.prepared, attempt.request, snapshot, result)
        self.assertEqual(attempt.prepared.input_hash, candidate['input_hash'])
        self.assertNotIn('input_hash', json.loads(result.content_json))
        self.assertEqual(original, result)
        self.assertIsNone(result.usage)

    def test_shouldRejectWrongSnapshotAuthorityBeforeAcceptingItsResult(self):
        for field, mutate in [
            ('profile_id', lambda snapshot: replace(snapshot, profile_id='metrics.other')),
            ('profile_version', lambda snapshot: replace(snapshot, profile_version='99')),
            ('source_input_sha256', lambda snapshot: replace(snapshot, source_input_sha256='b' * 64)),
            ('status', lambda snapshot: replace(snapshot, status='canceled')),
            ('dispatch.profile_definition_sha256',
             lambda snapshot: replace(snapshot, dispatch=replace(snapshot.dispatch, profile_definition_sha256='f' * 64))),
            ('result.output_schema_sha256',
             lambda snapshot: replace(snapshot, result=replace(snapshot.result, output_schema_sha256='f' * 64))),
        ]:
            attempt = self.attempt()
            snapshot, result = self.responses(attempt)
            with self.subTest(field=field), self.assertRaises(AnalysisError):
                self.contract.validate_result(attempt.prepared, attempt.request, mutate(snapshot), result)

    def test_shouldRejectMismatchedResultMetadataAndContentHashes(self):
        for field, mutate in [
            ('run_id', lambda result: replace(result, run_id='other-run')),
            ('profile_id', lambda result: replace(result, profile_id='metrics.other')),
            ('profile_version', lambda result: replace(result, profile_version='99')),
            ('source_input_sha256', lambda result: replace(result, source_input_sha256='b' * 64)),
            ('input_sha256', lambda result: replace(result, input_sha256='c' * 64)),
            ('effective_input_sha256', lambda result: replace(result, effective_input_sha256='d' * 64)),
            ('output_schema_sha256', lambda result: replace(result, output_schema_sha256='e' * 64)),
            ('dispatch.profile_definition_sha256',
             lambda result: replace(result, dispatch=replace(result.dispatch, profile_definition_sha256='f' * 64))),
        ]:
            attempt = self.attempt()
            snapshot, result = self.responses(attempt)
            with self.subTest(field=field), self.assertRaises(AnalysisError):
                self.contract.validate_result(attempt.prepared, attempt.request, snapshot, mutate(result))

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
                self.contract.validate_result(attempt.prepared, attempt.request, snapshot, result)

    def test_shouldPermitUnknownOwnerWithoutInventingAssignment(self):
        attempt = self.attempt()
        output = self.output(attempt.prepared)
        output['next_actions'][0].update(owner_id=None, owner_basis='unknown', owner_quote=None)
        snapshot, result = self.responses(attempt, output)
        self.assertIsNone(
            self.contract.validate_result(
                attempt.prepared, attempt.request, snapshot, result,
            )['next_actions'][0]['owner_id']
        )

    def test_shouldValidateAppInputAgainstTheDeliveredStrictProfile(self):
        prepared = self.prepared()
        value = json.loads(prepared.input_content)
        self.contract.validate_input(value)
        value['coverage']['history'] = 'partial'
        with self.assertRaises(AnalysisError):
            self.contract.validate_input(value)

    def test_shouldRequireBlockerAndLimitationReferencesToExistInTheInput(self):
        for field in ('blockers', 'limitations'):
            attempt = self.attempt()
            output = self.output(attempt.prepared)
            output[field] = ['invented-ref']
            snapshot, result = self.responses(attempt, output)
            with self.subTest(field=field), self.assertRaises(AnalysisError):
                self.contract.validate_result(attempt.prepared, attempt.request, snapshot, result)
            output[field] = ['comment:202']
            snapshot, result = self.responses(attempt, output)
            self.assertEqual(
                ['comment:202'],
                self.contract.validate_result(attempt.prepared, attempt.request, snapshot, result)[field],
            )

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
                                       snapshot, self.contract.profile_ref)
        attempt = self.attempt(prepared)
        output = self.output(prepared)
        output['evidence'].append('history:h1')
        output['next_actions'][0]['evidence'] = ['history:h1']
        observed, result = self.responses(attempt, output)
        with self.assertRaises(AnalysisError) as caught:
            self.contract.validate_result(attempt.prepared, attempt.request, observed, result)
        self.assertEqual('ANALYSIS_OWNER_INVALID', caught.exception.code)
        output['next_actions'][0].update(owner_basis='suggested', owner_quote=None)
        observed, result = self.responses(attempt, output)
        self.assertEqual(
            'suggested',
            self.contract.validate_result(
                attempt.prepared, attempt.request, observed, result,
            )['next_actions'][0]['owner_basis'],
        )
