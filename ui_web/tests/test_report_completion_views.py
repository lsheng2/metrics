from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.app.domain.contracts import ProjectActor
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario, ProjectApiStub
from project_management.tests.report_completion_fixtures import SyntheticReferenceReader, SyntheticSourceReader, completion_request
from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, draft_command, draft_selection
from project_management.services.report_completion import ReportCompletionService
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.storage.report_reference_admission import CompletionAdmissionStore
from ui_web.tests.project_fixtures import ProjectRouteTestSupport


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestReportCompletionViews(CaptureArchiveScenario, ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.archive = DraftArchive(Path(self.temporary.name) / 'completion-view-archive')
        self.archive.actor = ProjectActor('basic:alice')
        self.archive.repository.owner_subject = self.archive.actor.subject
        self.actor = self.archive.actor
        self.project = self.archive.project
        self.stage = self.archive.stage
        self.source = SyntheticSourceReader(source_commit=self.archive.repository.head(),
                                            rule_hash=self.stage.definition_hash)
        self.service = report_api.ReportDraftService(
            self.archive,
            self.source,
            report_api.ReportRenderer(),
            clock=FixedClock(),
            reference_verifier=ReferenceReceiptVerifier('unit-secret'),
        )
        self.reader = SyntheticReferenceReader()
        self.completion = ReportCompletionService(
            self.service,
            self.source,
            self.reader,
            ReferenceReceiptVerifier('unit-secret'),
            CompletionAdmissionStore(self.archive.config.root),
        )
        self.draft = self.service.create_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(980),
            selection=draft_selection(),
            template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
        )
        self.patch_view()

    def patch_view(self):
        from ui_web.views.report_completion import ReportDraftCompletionView

        completion_original = ReportDraftCompletionView.completion_factory
        project_original = ReportDraftCompletionView.project_api_factory
        ReportDraftCompletionView.completion_factory = staticmethod(lambda: self.completion)
        ReportDraftCompletionView.project_api_factory = staticmethod(
            lambda: ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject)
        )
        self.addCleanup(lambda: setattr(ReportDraftCompletionView, 'completion_factory', completion_original))
        self.addCleanup(lambda: setattr(ReportDraftCompletionView, 'project_api_factory', project_original))

    def url(self):
        return reverse('ui_web:report_draft_completion', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': self.draft.draft_id,
        })

    def payload(self, **changes):
        base = completion_request(self.draft)
        value = {
            'request_id': base.request_id,
            'token': base.token,
            'expected_revision': base.expected_revision,
            'expected_revision_hash': base.expected_revision_hash,
            'snapshot_hash': base.snapshot_hash,
            'region_target': base.region_target,
            'editor_epoch': base.editor_epoch,
            'local_version': base.local_version,
        }
        value.update(changes)
        return value

    def post_json(self, payload):
        return self.client.post(self.url(), json.dumps(payload), content_type='application/json', **self.auth('alice'))

    def test_shouldRejectDuplicateKeysExtraFieldsCoercionAndOversizeBeforeService(self):
        duplicate = self.client.post(
            self.url(),
            b'{"request_id":"aaaaaaaa-aaaa-4aaa-8aaa-000000000001","request_id":"aaaaaaaa-aaaa-4aaa-8aaa-000000000002"}',
            content_type='application/json',
            **self.auth('alice'),
        )
        extra = self.post_json(dict(self.payload(), extra='bad'))
        coerced = self.post_json(dict(self.payload(), expected_revision='1'))
        oversize = self.client.post(self.url(), b'{' + b' ' * 8193 + b'}',
                                    content_type='application/json', **self.auth('alice'))

        self.assertEqual((400, 'COMPLETION_INVALID_REQUEST'), (duplicate.status_code, duplicate.json()['error']['code']))
        self.assertEqual((400, 'COMPLETION_INVALID_REQUEST'), (extra.status_code, extra.json()['error']['code']))
        self.assertEqual((400, 'COMPLETION_INVALID_REQUEST'), (coerced.status_code, coerced.json()['error']['code']))
        self.assertEqual((413, 'COMPLETION_REQUEST_TOO_LARGE'), (oversize.status_code, oversize.json()['error']['code']))
        self.assertEqual([], self.reader.calls)

    def test_shouldMapNotFoundAndRateLimitedStatuses(self):
        not_found = self.client.post(
            reverse('ui_web:report_draft_completion', kwargs={
                'project_id': self.project.id,
                'stage_id': self.stage.id,
                'draft_id': '11111111-1111-4111-8111-111111111111',
            }),
            json.dumps(self.payload()),
            content_type='application/json',
            **self.auth('alice'),
        )

        self.assertEqual(404, not_found.status_code)
