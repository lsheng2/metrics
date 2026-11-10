import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import Client, TestCase, override_settings
from django.test.html import parse_html
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.app.api.capture_archive import CapturePage, CaptureReceipt
from project_management.app.domain.contracts import ProjectActor
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario, ProjectApiStub
from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, StaticSourceReader, draft_command
from project_management.tests.report_render_fixtures import source_key_hash
from ui_web.tests.project_fixtures import ProjectRouteTestSupport


class AuthoringUiArchive(DraftArchive):
    def __init__(self, root: Path):
        super().__init__(root)
        self.actor = ProjectActor('basic:alice')
        self.repository.owner_subject = self.actor.subject
        self.capture_id = '99999999-9999-4999-8999-999999999999'

    def list_captures(self, actor, project_id, stage_id, *, limit=100, after=None):
        self._stage_for_read(actor, project_id, stage_id)
        return CapturePage((
            CaptureReceipt(
                self.capture_id,
                self.repository.head(),
                '1' * 64,
                None,
                True,
                True,
                None,
                (),
                'current',
            ),
        ), None)


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestReportAuthoringViews(CaptureArchiveScenario, ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.archive = AuthoringUiArchive(Path(self.temporary.name) / 'authoring-archive')
        self.actor = self.archive.actor
        self.project = self.archive.project
        self.stage = self.archive.stage
        self.source = StaticSourceReader(rule_hash=self.stage.definition_hash)
        self.service = report_api.ReportDraftService(
            self.archive,
            self.source,
            report_api.ReportRenderer(),
            clock=FixedClock(),
        )
        self.facade = None
        self.with_report_facade()

    def report_facade(self):
        from ui_web.facades.project_reports import ProjectReportFacade

        if self.facade is None:
            self.facade = ProjectReportFacade(ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
                                              self.service, self.archive)
        return self.facade

    def with_report_facade(self):
        from ui_web.views import project_reports

        classes = (
            project_reports.ProjectStageReportView,
            project_reports.ReportDraftCreateView,
            project_reports.ReportDraftEditView,
            project_reports.ReportDraftSaveView,
            project_reports.ReportDraftRenderView,
            project_reports.ReportDraftDownloadView,
            project_reports.ReportDraftClipboardView,
            project_reports.ReportDraftFinalizeView,
            project_reports.ReportDraftResumeView,
            project_reports.ReportPublicationView,
            project_reports.ReportPublicationRevisionView,
            project_reports.ReportPublicationDownloadView,
        )
        self.patch_view_factory(self.report_facade, *classes)

    def create_url(self):
        return reverse('ui_web:report_draft_create', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        })

    def editor_url(self, draft_id):
        return reverse('ui_web:report_draft_edit', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        })

    def save_url(self, draft_id):
        return reverse('ui_web:report_draft_save', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        })

    def render_url(self, draft_id, revision):
        return reverse('ui_web:report_draft_render', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        }) + f'?revision={revision}'

    def create_authored_draft(self, command=600):
        response = self.client.post(self.create_url(), {
            'payload_version': '2',
            'command_id': draft_command(command),
            'capture_id': self.archive.capture_id,
            'template_id': 'daily-standup',
            'template_version': '2',
            'timezone': 'Asia/Shanghai',
            'purpose': 'standup',
        }, **self.auth('alice'))
        draft_id = response['Location'].rstrip('/').rsplit('/', 1)[-1] if response.status_code == 302 else ''
        return draft_id, response

    def authored_post(self, draft, edits, *, command=610, expected_revision=None, expected_hash=None):
        return {
            'payload_version': '2',
            'command_id': draft_command(command),
            'expected_revision': str(expected_revision or draft.revision),
            'expected_revision_hash': expected_hash or draft.revision_hash,
            'authored_edits': json.dumps(edits, ensure_ascii=False),
            'continuity_changes': '[]',
        }

    def test_shouldCreateBrowserDraftWithAuthoredSchema2AndRenderWysiwygRegions(self):
        draft_id, created = self.create_authored_draft()
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        editor = self.client.get(self.editor_url(draft_id), **self.auth('alice'))
        content = editor.content.decode('utf-8')

        self.assertEqual(302, created.status_code)
        self.assertEqual('report-authoring/2', draft.authoring_schema)
        self.assertEqual('2', draft.template.version)
        self.assertEqual(200, editor.status_code)
        self.assertIn('data-report-wysiwyg-region', content)
        self.assertIn('name="expected_revision_hash"', content)
        self.assertIn('name="authored_edits"', content)
        textareas = [node for node in html_elements(parse_html(content)) if node.name == 'textarea']
        self.assertTrue(all('data-report-assist-instruction' in dict(node.attributes) for node in textareas))
        self.assertIn('Saved report preview', content)

    def test_shouldSaveRichAuthoredPayloadWithHashCasAndRenderPersistedPaint(self):
        draft_id, _ = self.create_authored_draft(601)
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        row = draft.snapshot.rows[0]
        target_hash = source_key_hash(row.source_key)
        edits = (
            authored_edit('10000000-0000-4000-8000-000000000101', 'note', {'scope': 'report'},
                          fragment('会议 note with paint', foreground='#0055aa', background='#fff4cc')),
            authored_edit(
                '20000000-0000-4000-8000-000000000101',
                'narrative_override',
                {'scope': 'issue', 'source_key_hash': target_hash, 'field': 'what'},
                fragment('Edited rich override', marks=('strong',)),
                expected_original_hash=report_api.text_hash(row.what),
            ),
        )

        saved_response = self.client.post(
            self.save_url(draft_id),
            self.authored_post(draft, edits),
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            **self.auth('alice'),
        )
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        render = self.client.get(self.render_url(draft_id, saved.revision), **self.auth('alice'))

        self.assertEqual(200, saved_response.status_code)
        self.assertEqual('saved', saved_response.json()['state'])
        self.assertEqual(2, saved.revision)
        self.assertEqual(2, len(saved.authored_edits))
        self.assertEqual('#0055aa', saved.authored_edits[0].fragment['blocks'][0]['content'][0]['foreground'])
        self.assertIn(b'color:#0055aa', render.content)
        self.assertIn('Edited rich override', saved.edits[1].text)

    def test_authored_save_does_not_preload_draft_before_locked_service(self):
        from unittest.mock import patch

        draft_id, _ = self.create_authored_draft(18300)
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        with patch.object(self.report_facade(), 'get_draft', side_effect=AssertionError('Duplicate form read')):
            response = self.client.post(
                self.save_url(draft_id), self.authored_post(draft, (), command=18301),
                HTTP_ACCEPT='application/json', **self.auth('alice'),
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()['revision'])
        self.assertEqual(2, self.service.get(self.actor, self.project.id, self.stage.id, draft_id).revision)

    def test_shouldRejectStaleMalformedOversizedAndForgedSchema2PayloadsWithoutDroppingPostedText(self):
        draft_id, _ = self.create_authored_draft(602)
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        valid = (authored_edit('10000000-0000-4000-8000-000000000201', 'note', {'scope': 'report'},
                               fragment('fresh note')),)
        saved = self.service.save_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            draft_id,
            command_id=draft_command(603),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=tuple(report_api.AuthoredEditRequest(**item) for item in valid),
            continuity_changes=(),
        )
        stale_edits = (authored_edit('10000000-0000-4000-8000-000000000202', 'note', {'scope': 'report'},
                                     fragment('stale unsaved text')),)

        stale = self.client.post(
            self.save_url(draft_id),
            self.authored_post(draft, stale_edits, command=604),
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            **self.auth('alice'),
        )
        malformed = self.client.post(
            self.save_url(draft_id),
            dict(self.authored_post(saved, valid, command=605),
                 authored_edits='[{"edit_id":"10000000-0000-4000-8000-000000000203","edit_id":"10000000-0000-4000-8000-000000000204"}]'),
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            **self.auth('alice'),
        )
        forged_target = (authored_edit('10000000-0000-4000-8000-000000000205', 'note',
                                       {'scope': 'issue', 'source_key_hash': '0' * 64},
                                       fragment('forged source target')),)
        forged = self.client.post(
            self.save_url(draft_id),
            self.authored_post(saved, forged_target, command=606),
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            **self.auth('alice'),
        )
        oversized = self.client.post(
            self.save_url(draft_id),
            dict(self.authored_post(saved, valid, command=607), authored_edits='[' + (' ' * 1_050_000) + ']'),
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            **self.auth('alice'),
        )

        self.assertEqual(409, stale.status_code)
        self.assertEqual('stale unsaved text', stale.json()['submitted_edits'][0]['fragment']['blocks'][0]['content'][0]['text'])
        self.assertEqual(400, malformed.status_code)
        self.assertEqual(400, forged.status_code)
        self.assertEqual(413, oversized.status_code)

    def test_shouldProtectAuthoredWritesWithCsrfAndKeepChineseLabels(self):
        csrf_client = Client(enforce_csrf_checks=True)
        create = csrf_client.post(self.create_url(), {
            'payload_version': '2',
            'command_id': draft_command(608),
            'capture_id': self.archive.capture_id,
            'template_id': 'daily-standup',
            'template_version': '2',
            'timezone': 'Asia/Shanghai',
            'purpose': 'standup',
        }, **self.auth('alice'))
        draft_id, _ = self.create_authored_draft(609)
        self.client.cookies['django_language'] = 'zh-hans'
        editor = self.client.get(self.editor_url(draft_id), **self.auth('alice'))
        content = editor.content.decode('utf-8')

        self.assertEqual(403, create.status_code)
        self.assertEqual(200, editor.status_code)
        self.assertIn('草稿报告', content)
        self.assertIn('源状态', content)
        self.assertIn('发布目标', content)

    def test_shouldSafelyBootstrapFragmentContainingScriptEndText(self):
        draft_id, _ = self.create_authored_draft(620)
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        hostile = '</script><script>window.__editorCanary=1</script>'
        saved = self.service.save_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            draft_id,
            command_id=draft_command(621),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                '10000000-0000-4000-8000-000000000621',
                'note',
                {'scope': 'report'},
                fragment(hostile),
            ),),
            continuity_changes=(),
        )

        editor = self.client.get(self.editor_url(draft_id), **self.auth('alice'))
        content = editor.content.decode('utf-8')

        self.assertEqual(200, editor.status_code)
        self.assertEqual(2, saved.revision)
        self.assertNotIn('</script><script>window.__editorCanary=1</script>', content)
        self.assertIn('\\u003C/script\\u003E\\u003Cscript\\u003Ewindow.__editorCanary=1\\u003C/script\\u003E', content)

    def test_shouldKeepExistingActionNarrativeOverrideWhenSavingUnrelatedReportNote(self):
        draft_id, _ = self.create_authored_draft(630)
        draft = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        row = draft.snapshot.rows[0]
        source_hash = source_key_hash(row.source_key)
        action_target = {
            'scope': 'action',
            'source_key_hash': source_hash,
            'summary_id': row.summary_ref.summary_id,
            'action_index': 0,
            'field': 'action',
        }
        action_override = report_api.AuthoredEditRequest(
            '20000000-0000-4000-8000-000000000630',
            'narrative_override',
            action_target,
            fragment('Keep this action override'),
            expected_original_hash=report_api.text_hash(row.next_actions[0]['action']),
        )
        prepared = self.service.save_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            draft_id,
            command_id=draft_command(631),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(action_override,),
            continuity_changes=(),
        )
        editor = self.client.get(self.editor_url(draft_id), **self.auth('alice'))
        self.assertIn('&quot;field&quot;:&quot;action&quot;', editor.content.decode('utf-8'))
        payload = json.loads(editor.context['authored_save_form']['authored_edits'].value())
        payload.append(authored_edit(
            '10000000-0000-4000-8000-000000000630',
            'note',
            {'scope': 'report'},
            fragment('new report note'),
        ))

        saved_response = self.client.post(self.save_url(draft_id), {
            'payload_version': '2',
            'command_id': draft_command(632),
            'expected_revision': str(prepared.revision),
            'expected_revision_hash': prepared.revision_hash,
            'authored_edits': json.dumps(payload),
            'continuity_changes': '[]',
        }, HTTP_ACCEPT='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest', **self.auth('alice'))
        saved = self.service.get(self.actor, self.project.id, self.stage.id, draft_id)
        by_id = {edit.edit_id: edit for edit in saved.authored_edits}

        self.assertEqual(200, saved_response.status_code)
        self.assertIn('20000000-0000-4000-8000-000000000630', by_id)
        self.assertIn('10000000-0000-4000-8000-000000000630', by_id)
        self.assertEqual('Keep this action override', saved.edits[0].text)


def authored_edit(edit_id, kind, target, rich_fragment, expected_original_hash=None):
    return {
        'edit_id': edit_id,
        'kind': kind,
        'target': target,
        'fragment': rich_fragment,
        'expected_original_hash': expected_original_hash,
        'reference_receipts': [],
        'assist_receipt_id': None,
    }


def fragment(text, *, marks=(), foreground=None, background=None):
    if text == '':
        return {'schema_version': 2, 'blocks': []}
    return {
        'schema_version': 2,
        'blocks': [{
            'type': 'paragraph',
            'content': [{
                'type': 'text',
                'text': text,
                'marks': list(marks),
                'foreground': foreground,
                'background': background,
            }],
        }],
    }


def html_elements(node):
    yield node
    for child in node.children:
        if not isinstance(child, str):
            yield from html_elements(child)
