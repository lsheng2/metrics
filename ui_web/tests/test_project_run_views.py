from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib
import uuid

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from project_management.app.api import ProjectActor
from project_management.app.api.capture_archive import ArchiveStorageConfig
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.services.capture_archive import CaptureArchiveService
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.project_run_fixtures import ManualRunEnvironment
from project_management.tests.report_draft_fixtures import draft_command, draft_note
from project_management.tests.report_render_fixtures import daily_template
from ui_web.tests.project_fixtures import ProjectRouteTestSupport


class UnusedReportService:
    def list_drafts(self, *args, **kwargs):
        raise AssertionError('Absent stage archive must not list drafts.')

    def list_publications(self, *args, **kwargs):
        raise AssertionError('Absent stage archive must not list publications.')


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestProjectRunViews(ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'archive-root'

    def route_modules(self):
        return (
            importlib.import_module('ui_web.views.project_reports'),
            importlib.import_module('ui_web.views.project_run_views'),
            importlib.import_module('ui_web.facades.project_runs'),
            importlib.import_module('ui_web.facades.project_reports'),
        )

    def patch_facades(self, report_facade, run_facade):
        project_reports, project_run_views, _, _ = self.route_modules()
        report_classes = [project_reports.ProjectStageReportView]
        run_classes = [
            project_run_views.ProjectRunSubmitView,
            project_run_views.ProjectRunStatusView,
            project_run_views.ProjectRunCancelView,
            project_run_views.ProjectRunResumeView,
        ]
        report_originals = [view.facade_factory for view in report_classes]
        run_originals = [view.facade_factory for view in run_classes]
        for view in report_classes:
            view.facade_factory = staticmethod(lambda: report_facade)
        for view in run_classes:
            view.facade_factory = staticmethod(lambda: run_facade)
        self.addCleanup(lambda: [setattr(view, 'facade_factory', original)
                                 for view, original in zip(report_classes, report_originals)])
        self.addCleanup(lambda: [setattr(view, 'facade_factory', original)
                                 for view, original in zip(run_classes, run_originals)])

    def report_url(self, project_id, stage_id):
        return reverse('ui_web:project_stage_reports', kwargs={'project_id': project_id, 'stage_id': stage_id})

    def run_create_url(self, project_id, stage_id):
        return reverse('ui_web:project_run_submit', kwargs={'project_id': project_id, 'stage_id': stage_id})

    def run_status_url(self, project_id, stage_id, operation_id):
        return reverse('ui_web:project_run_status', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'operation_id': operation_id,
        })

    def run_cancel_url(self, project_id, stage_id, operation_id):
        return reverse('ui_web:project_run_cancel', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'operation_id': operation_id,
        })

    def run_resume_url(self, project_id, stage_id, operation_id):
        return reverse('ui_web:project_run_resume', kwargs={
            'project_id': project_id,
            'stage_id': stage_id,
            'operation_id': operation_id,
        })

    def run_payload(self, environment, command_id):
        return {
            'command_id': command_id,
            'expected_stage_hash': environment.stage.definition_hash,
            'template_id': 'daily-standup',
            'template_version': '1',
            'timezone': 'Asia/Shanghai',
        }

    def browser_environment(self, *, notifier):
        environment = ManualRunEnvironment(self.root, notifier=notifier)
        environment.actor = ProjectActor('basic:alice')
        environment.project_api.owner_subject = environment.actor.subject
        environment.archive.project_api.owner_subject = environment.actor.subject
        return environment

    def run_facade(self, environment, *, runtime_ready=True):
        _, _, project_runs, _ = self.route_modules()
        return project_runs.ProjectRunFacade(
            ProjectApiStub(environment.project, environment.stage, owner_subject='basic:alice'),
            environment.run_service,
            runtime_ready=runtime_ready,
        )

    def report_facade(self, environment):
        _, _, _, project_reports = self.route_modules()
        return project_reports.ProjectReportFacade(
            ProjectApiStub(environment.project, environment.stage, owner_subject='basic:alice'),
            environment.draft_service,
            environment.archive,
        )

    def test_shouldExposeRunOnAbsentStageArchiveWithoutCreatingFiles(self):
        environment = self.browser_environment(notifier=None)
        self.root.mkdir(parents=True, exist_ok=True)
        project_api = ProjectApiStub(environment.project, environment.stage, owner_subject='basic:alice')
        archive = CaptureArchiveService(
            project_api,
            LocalArchiveRepositoryFactory(),
            ArchiveStorageConfig(self.root, 'Archive Test', 'archive@example.test', environment.archive.config.limits),
        )
        _, _, project_runs, project_reports = self.route_modules()
        report_facade = project_reports.ProjectReportFacade(project_api, UnusedReportService(), archive)
        run_facade = project_runs.ProjectRunFacade(project_api, environment.run_service, runtime_ready=True)
        self.patch_facades(report_facade, run_facade)

        response = self.client.get(self.report_url(environment.project.id, environment.stage.id), **self.auth('alice'))

        stage_root = self.root / 'projects' / environment.project.id / 'stages' / environment.stage.id
        content = response.content.decode('utf-8')
        self.assertEqual(200, response.status_code)
        self.assertIn('Run stage report', content)
        self.assertIn('Archive has not been initialized for this stage yet.', content)
        self.assertIn(self.run_create_url(environment.project.id, environment.stage.id), content)
        self.assertFalse(stage_root.exists())

    def test_shouldRefusePresentCorruptArchiveWithoutCreatingRuntimeFiles(self):
        environment = self.browser_environment(notifier=None)
        self.root.mkdir(parents=True, exist_ok=True)
        stage_root = self.root / 'projects' / environment.project.id / 'stages' / environment.stage.id
        stage_root.mkdir(parents=True)
        project_api = ProjectApiStub(environment.project, environment.stage, owner_subject='basic:alice')
        archive = CaptureArchiveService(
            project_api,
            LocalArchiveRepositoryFactory(),
            ArchiveStorageConfig(self.root, 'Archive Test', 'archive@example.test', environment.archive.config.limits),
        )
        _, _, project_runs, project_reports = self.route_modules()
        report_facade = project_reports.ProjectReportFacade(project_api, UnusedReportService(), archive)
        run_facade = project_runs.ProjectRunFacade(project_api, environment.run_service, runtime_ready=True)
        self.patch_facades(report_facade, run_facade)
        before = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob('*'))

        response = self.client.get(self.report_url(environment.project.id, environment.stage.id), **self.auth('alice'))

        after = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob('*'))
        content = response.content.decode('utf-8')
        self.assertEqual(400, response.status_code)
        self.assertEqual(before, after)
        self.assertNotIn('Run stage report', content)

    def test_shouldCreateReplayRefreshCancelAndResumeRunWithAuthCsrfAndStrictForms(self):
        environment = self.browser_environment(notifier=lambda *args: None)
        self.patch_facades(self.report_facade(environment), self.run_facade(environment))
        command_id = str(uuid.uuid4())
        payload = self.run_payload(environment, command_id)
        csrf_client = Client(enforce_csrf_checks=True)

        missing_csrf = csrf_client.post(
            self.run_create_url(environment.project.id, environment.stage.id),
            payload,
            **self.auth('alice'),
        )
        created = self.client.post(
            self.run_create_url(environment.project.id, environment.stage.id),
            payload,
            **self.auth('alice'),
        )
        replay = self.client.post(
            self.run_create_url(environment.project.id, environment.stage.id),
            payload,
            **self.auth('alice'),
        )
        operation_id = created['Location'].rstrip('/').rsplit('/', 1)[-1]
        status = self.client.get(created['Location'], **self.auth('alice'))
        htmx_status = self.client.get(created['Location'], **{
            **self.auth('alice'),
            'HTTP_HX_REQUEST': 'true',
        })
        forged = self.client.post(
            self.run_create_url(environment.project.id, environment.stage.id),
            {**payload, 'backend': 'https://attacker.invalid'},
            **self.auth('alice'),
        )
        foreign_cancel = self.client.post(
            self.run_cancel_url(environment.project.id, environment.stage.id, operation_id),
            {'expected_revision': '1'},
            **self.auth('bob'),
        )
        canceled = self.client.post(
            self.run_cancel_url(environment.project.id, environment.stage.id, operation_id),
            {'expected_revision': '1'},
            **self.auth('alice'),
        )

        resumed_operation = environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )
        store = environment.archive.project_operation_repository(
            environment.actor, environment.project.id, environment.stage.id, write=True,
        )
        interrupted = store.transition(
            replace(resumed_operation, state='interrupted', revision=2),
            expected_revision=1,
        )
        resumed = self.client.post(
            self.run_resume_url(environment.project.id, environment.stage.id, interrupted.operation_id),
            {'expected_revision': '2'},
            **self.auth('alice'),
        )

        self.assertEqual(403, missing_csrf.status_code)
        self.assertEqual(302, created.status_code)
        self.assertEqual(created['Location'], replay['Location'])
        self.assertEqual(200, status.status_code)
        self.assertIn(operation_id, status.content.decode('utf-8'))
        htmx_content = htmx_status.content.decode('utf-8')
        self.assertEqual(200, htmx_status.status_code)
        self.assertIn('id="project-run-status-fragment"', htmx_content)
        self.assertNotIn('<!doctype html>', htmx_content.lower())
        self.assertNotIn('<html', htmx_content.lower())
        self.assertEqual(400, forged.status_code)
        self.assertEqual(404, foreign_cancel.status_code)
        self.assertEqual(302, canceled.status_code)
        self.assertEqual(302, resumed.status_code)
        self.assertEqual(0, environment.provider.open_count)
        self.assertEqual([], environment.http.requests)

    def test_shouldStatusLinkOriginalProducedRevisionSeparatelyFromLatestEditor(self):
        environment = self.browser_environment(notifier=lambda *args: None)
        self.patch_facades(self.report_facade(environment), self.run_facade(environment))
        operation = environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )
        completed = environment.worker.execute(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
        )
        saved = environment.draft_service.save(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            completed.draft_id,
            command_id=draft_command(810),
            expected_revision=1,
            edits=(draft_note(811),),
            template=daily_template(),
        )
        response = self.client.get(
            self.run_status_url(environment.project.id, environment.stage.id, completed.operation_id),
            **self.auth('alice'),
        )

        content = response.content.decode('utf-8')
        exact_render = reverse('ui_web:report_draft_render', kwargs={
            'project_id': environment.project.id,
            'stage_id': environment.stage.id,
            'draft_id': completed.draft_id,
        }) + '?revision=1'
        latest_edit = reverse('ui_web:report_draft_edit', kwargs={
            'project_id': environment.project.id,
            'stage_id': environment.stage.id,
            'draft_id': completed.draft_id,
        })
        self.assertEqual(200, response.status_code)
        self.assertIn(exact_render, content)
        self.assertIn(latest_edit, content)
        self.assertIn('Produced draft revision 1', content)
        self.assertIn('Open latest draft', content)

    def test_shouldPollQueuedRunIntoTerminalFragmentWithItemsLinksAndControls(self):
        environment = self.browser_environment(notifier=lambda *args: None)
        self.patch_facades(self.report_facade(environment), self.run_facade(environment))
        operation = environment.run_service.submit(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            environment.request(str(uuid.uuid4())),
        )
        status_url = self.run_status_url(environment.project.id, environment.stage.id, operation.operation_id)

        queued_page = self.client.get(status_url, **self.auth('alice'))
        queued = self.client.get(status_url, **{**self.auth('alice'), 'HTTP_HX_REQUEST': 'true'})
        completed = environment.worker.execute(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
        )
        terminal = self.client.get(status_url, **{**self.auth('alice'), 'HTTP_HX_REQUEST': 'true'})

        exact_render = reverse('ui_web:report_draft_render', kwargs={
            'project_id': environment.project.id,
            'stage_id': environment.stage.id,
            'draft_id': completed.draft_id,
        }) + '?revision=1'
        latest_edit = reverse('ui_web:report_draft_edit', kwargs={
            'project_id': environment.project.id,
            'stage_id': environment.stage.id,
            'draft_id': completed.draft_id,
        })
        queued_page_content = queued_page.content.decode('utf-8')
        queued_shell = queued_page_content.split('id="project-run-status-fragment"', 1)[0]
        queued_content = queued.content.decode('utf-8')
        terminal_content = terminal.content.decode('utf-8')

        self.assertEqual(200, queued_page.status_code)
        self.assertNotIn('queued', queued_shell)
        self.assertEqual(200, queued.status_code)
        self.assertEqual('private, no-store', queued['Cache-Control'])
        self.assertIn('id="project-run-status-fragment"', queued_content)
        self.assertIn('queued', queued_content)
        self.assertIn(self.run_cancel_url(environment.project.id, environment.stage.id, operation.operation_id),
                      queued_content)
        self.assertIn('project_run_status.js', queued_page_content)
        self.assertIn(f'data-run-status-url="{status_url}"', queued_content)
        self.assertIn(f'data-operation-id="{operation.operation_id}"', queued_content)
        self.assertNotIn('hx-get=', queued_content)
        self.assertNotIn('<!doctype html>', queued_content.lower())
        self.assertNotIn('<html', queued_content.lower())

        self.assertEqual(200, terminal.status_code)
        self.assertEqual('private, no-store', terminal['Cache-Control'])
        self.assertIn('id="project-run-status-fragment"', terminal_content)
        self.assertIn('draft_ready', terminal_content)
        self.assertNotIn('queued', terminal_content)
        self.assertIn('accepted', terminal_content)
        self.assertIn(exact_render, terminal_content)
        self.assertIn(latest_edit, terminal_content)
        self.assertIn('Produced draft revision 1', terminal_content)
        self.assertIn('Open latest draft', terminal_content)
        self.assertNotIn(self.run_cancel_url(environment.project.id, environment.stage.id, operation.operation_id),
                         terminal_content)
        self.assertNotIn('data-run-status-url=', terminal_content)
        self.assertNotIn('<!doctype html>', terminal_content.lower())
        self.assertNotIn('<html', terminal_content.lower())
