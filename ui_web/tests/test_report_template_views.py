import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.models import Project
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_draft_fixtures import FixedClock, StaticSourceReader, draft_command
from project_management.tests.test_report_template_compilation import schema1_document
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.test_report_authoring_views import AuthoringUiArchive, fragment


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestReportTemplateViews(ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.archive = AuthoringUiArchive(Path(self.temporary.name) / 'template-ui-archive')
        self.actor = self.archive.actor
        self.project = self.archive.project
        self.stage = self.archive.stage
        Project.objects.create(
            id=self.project.id,
            owner_subject=self.actor.subject,
            key=self.project.key,
            name=self.project.name,
            archived=False,
        )
        self.template_service = report_api.ReportTemplateService(clock=FixedClock())
        self.draft_service = report_api.ReportDraftService(
            self.archive,
            StaticSourceReader(rule_hash=self.stage.definition_hash),
            report_api.ReportRenderer(),
            clock=FixedClock(),
            template_service=self.template_service,
        )
        self.patch_views()

    def patch_views(self):
        from ui_web.facades.project_reports import ProjectReportFacade
        from ui_web.facades.report_templates import ProjectReportTemplateFacade
        from ui_web.views import project_reports, report_templates

        project_api = ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject)
        report_facade = ProjectReportFacade(project_api, self.draft_service, self.archive, self.template_service)
        template_facade = ProjectReportTemplateFacade(project_api, self.template_service)
        report_classes = (
            project_reports.ProjectStageReportView,
            project_reports.ReportDraftCreateView,
            project_reports.ReportDraftEditView,
            project_reports.ReportDraftSaveView,
            project_reports.ReportDraftFinalizeView,
        )
        template_classes = (
            report_templates.ReportTemplateLibraryView,
            report_templates.ReportTemplateEditorView,
            report_templates.ReportTemplateSaveView,
            report_templates.ReportTemplateArchiveView,
            report_templates.ReportTemplateCopyView,
        )
        self.patch_view_factory(lambda: report_facade, *report_classes)
        self.patch_view_factory(lambda: template_facade, *template_classes)

    def library_url(self):
        return reverse('ui_web:report_templates', kwargs={'project_id': self.project.id})

    def editor_url(self, template_id):
        return reverse('ui_web:report_template_editor', kwargs={
            'project_id': self.project.id,
            'template_id': template_id,
        })

    def save_url(self, template_id):
        return reverse('ui_web:report_template_save', kwargs={
            'project_id': self.project.id,
            'template_id': template_id,
        })

    def stage_url(self):
        return reverse('ui_web:project_stage_reports', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        })

    def create_draft_url(self):
        return reverse('ui_web:report_draft_create', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
        })

    def test_shouldCreateReadyTemplateVisuallyAndUseExactPinnedRevisionForDraft(self):
        created = self.client.post(self.library_url(), {
            'action': 'blank',
            'command_id': draft_command(3000),
            'name': 'Daily visual draft',
        }, **self.auth('alice'))
        template_id = created['Location'].rstrip('/').rsplit('/', 1)[-1]
        saved = self.client.post(self.save_url(template_id), {
            'command_id': draft_command(3001),
            'expected_revision': '1',
            'expected_revision_hash': self.template_service.get(
                self.actor, self.project.id, template_id, revision=1,
            ).revision_hash,
            'name': 'Daily visual ready',
            'document': json.dumps(schema1_document(), ensure_ascii=False),
            'fill_policy': json.dumps({
                'schema_version': 1,
                'instructions': {'40000000-0000-4000-8000-000000000001': 'Use accepted notes.'},
            }),
        }, **self.auth('alice'))
        ready = self.template_service.get(self.actor, self.project.id, template_id, revision=2)
        stage = self.client.get(self.stage_url(), **self.auth('alice')).content.decode('utf-8')
        choice = f'user|{ready.template_id}|2|{ready.revision_hash}'
        draft_response = self.client.post(self.create_draft_url(), {
            'payload_version': '2',
            'command_id': draft_command(3002),
            'capture_id': self.archive.capture_id,
            'template_choice': choice,
            'timezone': 'Asia/Shanghai',
            'purpose': 'standup',
        }, **self.auth('alice'))

        self.assertEqual(302, created.status_code)
        self.assertEqual(302, saved.status_code)
        self.assertIn(choice, stage)
        self.assertEqual(302, draft_response.status_code)
        draft_id = draft_response['Location'].rstrip('/').rsplit('/', 1)[-1]
        draft = self.draft_service.get(self.actor, self.project.id, self.stage.id, draft_id)
        editor = self.client.get(draft_response['Location'], **self.auth('alice')).content.decode('utf-8')
        self.assertEqual(str(ready.template_id), draft.template.template_id)
        self.assertIn('data-template-slot-id="40000000-0000-4000-8000-000000000001"', editor)
        self.assertIn('data-template-data-source="register"', editor)
        self.assertNotIn('<textarea name="authored_edits"', editor)

    def test_shouldKeepPostedTemplateBodyOnConflictAndRejectCsrfWrongOwnerAndDuplicateJson(self):
        ready = self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(3010),
            name='Ready',
            document=schema1_document(),
            fill_policy={'schema_version': 1, 'instructions': {}},
        )
        current = self.template_service.save(
            self.actor,
            self.project.id,
            str(ready.template_id),
            command_id=draft_command(3011),
            expected_revision=1,
            expected_revision_hash=ready.revision_hash,
            name='Ready v2',
            document=schema1_document(),
            fill_policy={'schema_version': 1, 'instructions': {}},
        )
        conflict = self.client.post(self.save_url(ready.template_id), {
            'command_id': draft_command(3012),
            'expected_revision': '1',
            'expected_revision_hash': ready.revision_hash,
            'name': 'Unsaved conflict name',
            'document': json.dumps(schema1_document(), ensure_ascii=False),
            'fill_policy': json.dumps({'schema_version': 1, 'instructions': {}}),
        }, **self.auth('alice'))
        duplicate = self.client.post(self.save_url(ready.template_id), {
            'command_id': draft_command(3013),
            'expected_revision': str(current.revision),
            'expected_revision_hash': current.revision_hash,
            'name': 'Duplicate json',
            'document': '{"schema_version":1,"schema_version":1}',
            'fill_policy': json.dumps({'schema_version': 1, 'instructions': {}}),
        }, **self.auth('alice'))
        csrf = Client(enforce_csrf_checks=True).post(self.save_url(ready.template_id), {
            'command_id': draft_command(3014),
            'expected_revision': str(current.revision),
            'expected_revision_hash': current.revision_hash,
            'name': 'CSRF blocked',
            'document': json.dumps(schema1_document(), ensure_ascii=False),
            'fill_policy': json.dumps({'schema_version': 1, 'instructions': {}}),
        }, **self.auth('alice'))
        wrong_owner = self.client.get(self.library_url(), **self.auth('bob'))

        self.assertEqual(409, conflict.status_code)
        self.assertIn('Unsaved conflict name', conflict.content.decode('utf-8'))
        self.assertIn('&quot;schema_version&quot;: 1', conflict.content.decode('utf-8'))
        self.assertEqual(400, duplicate.status_code)
        self.assertIn('Duplicate json', duplicate.content.decode('utf-8'))
        self.assertIn('{&quot;schema_version&quot;:1,&quot;schema_version&quot;:1}', duplicate.content.decode('utf-8'))
        self.assertEqual(403, csrf.status_code)
        self.assertEqual(404, wrong_owner.status_code)

    def test_shouldRenderPopulatedLibraryCopyAndArchivedEditorAsReadonly(self):
        ready = self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(3030),
            name='Ready template',
            document=schema1_document(),
            fill_policy={'schema_version': 1, 'instructions': {}},
        )
        library = self.client.get(self.library_url(), **self.auth('alice'))
        copy_response = self.client.post(reverse('ui_web:report_template_copy', kwargs={
            'project_id': self.project.id,
            'template_id': ready.template_id,
        }), {
            'command_id': draft_command(3031),
            'revision': str(ready.revision),
            'name': 'Copied template',
        }, **self.auth('alice'))
        self.template_service.archive(
            self.actor,
            self.project.id,
            str(ready.template_id),
            command_id=draft_command(3032),
            expected_revision=ready.revision,
            expected_revision_hash=ready.revision_hash,
        )
        archived = self.client.get(self.editor_url(ready.template_id), **self.auth('alice')).content.decode('utf-8')

        self.assertEqual(200, library.status_code)
        self.assertIn('Ready template', library.content.decode('utf-8'))
        self.assertEqual(302, copy_response.status_code)
        self.assertIn('data-archived="true"', archived)
        self.assertIn('<fieldset disabled aria-disabled="true">', archived)
        self.assertIn('data-template-save-button disabled', archived)

    def test_shouldSaveEmptyRequiredSlotButRejectFinalizeWithoutNewPublicationFiles(self):
        ready = self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(3020),
            name='Ready',
            document=schema1_document(),
            fill_policy={'schema_version': 1, 'instructions': {}},
        )
        draft = self.draft_service.create_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(3021),
            selection=report_api.ReportSelection(capture_id=self.archive.capture_id, timezone='Asia/Shanghai'),
            template=report_api.UserTemplateSelection(str(ready.template_id), ready.revision, ready.revision_hash),
        )
        saved = self.draft_service.save_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            draft.draft_id,
            command_id=draft_command(3022),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                '88000000-0000-4000-8000-000000000001',
                'slot_fill',
                {'scope': 'template_slot', 'slot_id': '40000000-0000-4000-8000-000000000001'},
                fragment(''),
            ),),
        )
        finalize = self.client.post(reverse('ui_web:report_draft_finalize', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft.draft_id,
        }), {
            'command_id': draft_command(3023),
            'expected_revision': str(saved.revision),
            'confirm': 'on',
        }, **self.auth('alice'))

        self.assertEqual(422, finalize.status_code)
        self.assertIn('data-required-slot-error', finalize.content.decode('utf-8'))
        self.assertFalse((self.archive.repository.runtime / 'report-drafts' / draft.draft_id / 'finalization.json').exists())
