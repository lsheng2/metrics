from uuid import UUID, uuid5

from project_management.app.api import reports as report_api
from project_management.models import Project, ProjectStage
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_draft_fixtures import FixedClock, draft_command
from ui_web.facades.project_reports import ProjectReportFacade
from ui_web.facades.report_templates import ProjectReportTemplateFacade
from ui_web.report_template_documents import continuity_starter_document, default_fill_policy
from ui_web.tests.report_authoring_browser_support import ReportAuthoringBrowserTestCase


class ReportHistoryUiBrowserSupport(ReportAuthoringBrowserTestCase):
    def setUp(self):
        super().setUp()
        Project.objects.create(
            id=self.project.id,
            owner_subject=self.actor.subject,
            key=self.project.key,
            name=self.project.name,
            archived=False,
        )
        ProjectStage.objects.create(
            id=self.stage.id,
            project_id=self.project.id,
            key=self.stage.key,
            name=self.stage.name,
            selection_json={'profile_id': 'alpha-jira', 'revision': 1},
            descriptor_json={'provider_id': 'jira'},
            definition_hash=self.stage.definition_hash,
        )
        self.template_service = report_api.ReportTemplateService(clock=FixedClock())
        self.continuity_service = report_api.ReportContinuityService(
            self.archive,
            self.source,
            template_service=self.template_service,
            clock=FixedClock(),
        )
        self.service.template_service = self.template_service
        self._report_facade = None
        self._patch_b2_facades()

    def report_facade(self):
        if self._report_facade is None:
            self._report_facade = ProjectReportFacade(
                ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
                self.service,
                self.archive,
                self.template_service,
                self.continuity_service,
            )
        return self._report_facade

    def template_facade(self):
        return ProjectReportTemplateFacade(
            ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
            self.template_service,
        )

    def _patch_b2_facades(self):
        from ui_web.views import project_reports, report_history, report_templates
        report_classes = (
            project_reports.ProjectStageReportView,
            report_history.ReportSeriesCreateView,
            report_history.ReportSeriesPolicyView,
            report_history.ReportPeriodView,
            report_history.ReportPublicationLinkedRevisionView,
            report_history.ReportWeeklyDraftCreateView,
        )
        template_classes = (
            report_templates.ReportTemplateLibraryView,
            report_templates.ReportTemplateEditorView,
            report_templates.ReportTemplateSaveView,
        )
        self.patch_view_factory(self.report_facade, *report_classes)
        self.patch_view_factory(self.template_facade, *template_classes)

    def finalized_daily_publication(self, *, setup, command_index, save_index, finalize_index, meeting_date,
                                    text, baseline=None):
        draft = self.prepared_continuity_draft(
            setup=setup,
            command_index=command_index,
            meeting_date=meeting_date,
            baseline=baseline,
        )
        note_id = draft.authoring_context['current_observations'][0]['note_id']
        original = next((note for note in draft.authoring_context['notes'] if note['note_id'] == note_id), None)
        saved = self.service.save_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            draft.draft_id,
            command_id=draft_command(save_index),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(report_api.AuthoredEditRequest(
                f'73000000-0000-4000-8000-{save_index:012d}',
                'note',
                {'scope': 'daily_note', 'note_id': note_id},
                {'schema_version': 2, 'blocks': [{
                    'type': 'paragraph',
                    'content': [{
                        'type': 'text',
                        'text': text,
                        'marks': [],
                        'foreground': None,
                        'background': None,
                    }],
                }]},
                None if original is None else original['body_hash'],
            ),),
        )
        return self.service.finalize_and_commit(
            self.actor,
            self.project.id,
            self.stage.id,
            draft.draft_id,
            command_id=draft_command(finalize_index),
            expected_revision=saved.revision,
        )

    def continuity_setup(self, base, document=None):
        document = document or continuity_starter_document('daily')
        template = self.template_service.create(
            self.actor,
            self.project.id,
            command_id=draft_command(base),
            name='Continuity daily',
            document=document,
            fill_policy=default_fill_policy(document),
        )
        template_selection = report_api.UserTemplateSelection(
            str(template.template_id),
            template.revision,
            template.revision_hash,
        )
        series = self.continuity_service.create_series(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(base + 1),
            name='Daily series',
            calendar=report_api.ReportingCalendar('iso8601', 1, 'Asia/Shanghai', 'iso8601', {}),
            template_selection=template_selection,
        )
        return {'template_selection': template_selection, 'series': series}

    def prepared_continuity_draft(self, *, setup=None, command_index=7102, meeting_date='2026-11-02', baseline=None):
        setup = setup or self.continuity_setup(7100)
        template_selection = setup['template_selection']
        series = setup['series']
        command_id = draft_command(command_index)
        preparation_id = f'71000000-0000-4000-8000-{command_index:012d}'
        draft_id = str(uuid5(UUID(self.stage.id), f'draft:{command_id}'))
        selection = report_api.ReportSelection(capture_id=self.archive.capture_id, timezone='Asia/Shanghai')
        template_request_hash = report_api.authored_create_template_use_request_hash(selection, template_selection, preparation_id)
        pinned = self.template_service.use(
            self.actor,
            self.project.id,
            command_id=command_id,
            draft_id=draft_id,
            request_hash=template_request_hash,
            selection=template_selection,
            use_mode='continuity_prepare',
        )
        self.continuity_service.prepare_context(
            self.actor,
            self.project.id,
            self.stage.id,
            preparation_id=preparation_id,
            create_command_id=command_id,
            series_id=series.series_id,
            series_policy_hash=series.revision_hash,
            meeting_date=meeting_date,
            expected_baseline_ref=baseline,
            selection=selection,
            template_use_hash=report_api.pinned_template_use_hash(pinned),
        )
        return self.service.create_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=command_id,
            selection=selection,
            template=template_selection,
            preparation_id=preparation_id,
        )
