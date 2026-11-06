from dataclasses import dataclass
from datetime import UTC, datetime

from django.utils.translation import gettext as _

from project_management.app.api import ProjectError
from project_management.app.api.capture_archive import ArchiveError
from project_management.app.api.factories import build_capture_archive_service, build_project_api
from project_management.app.api.report_factories import (
    build_report_continuity_service,
    build_report_service,
    build_report_template_service,
)
from project_management.app.api import reports as report_api
from ui_web.facades.report_history import ProjectReportHistoryFacadeMixin
from ui_web.facades.report_daily import ProjectReportDailyFacadeMixin, report_preparation_runtime
from ui_web.facades.report_templates import ready_continuity_template_choices, ready_user_template_choices, ready_weekly_template_choices
from ui_web.report_authoring_forms import ReportAuthoredSaveForm
from ui_web.report_authoring_view_model import authored_edit_rows, authored_edits_json, report_body, target_payloads
from ui_web.report_forms import (
    ReportCreateForm,
    ReportFinalizeForm,
    ReportResumeForm,
    ReportSaveForm,
    new_command_id,
    target_choices_for_snapshot,
)


@dataclass(frozen=True, slots=True)
class CaptureChoice:
    capture_id: str
    label: str
    complete: bool
    membership_complete: bool
    checkout_state: str
    source_as_of: str = ''


@dataclass(frozen=True, slots=True)
class PublicationChoice:
    publication_id: str
    label: str


def default_report_facade():
    project_api = build_project_api()
    template_service = build_report_template_service()
    try:
        archive = build_capture_archive_service(project_api=project_api)
        service = build_report_service(project_api=project_api, archive=archive, template_service=template_service)
        continuity = build_report_continuity_service(
            project_api=project_api,
            archive=archive,
            template_service=template_service,
        )
        preparation, runtime_ready = report_preparation_runtime(
            project_api, archive, template_service, service, continuity,
        )
        return ProjectReportFacade(project_api, service, archive, template_service, continuity,
                                   preparation, runtime_ready)
    except ArchiveError as error:
        if error.code == 'ARCHIVE_ROOT_UNCONFIGURED':
            return ProjectReportFacade(project_api, None, None, template_service)
        raise
    except Exception as error:
        if getattr(error, 'code', '') == 'ANALYSIS_CONTRACT_INVALID':
            return ProjectReportFacade(project_api, None, None, template_service)
        raise


class ProjectReportFacade(ProjectReportHistoryFacadeMixin, ProjectReportDailyFacadeMixin):
    def __init__(self, project_api, service, archive, template_service=None, continuity_service=None,
                 preparation_service=None, preparation_runtime_ready=False):
        self.project_api = project_api
        self.service = service
        self.archive = archive
        self.template_service = template_service or build_report_template_service()
        self.continuity_service = continuity_service
        self.preparation_service = preparation_service
        self.preparation_runtime_ready = preparation_runtime_ready

    def stage_context(self, actor, project_id, stage_id, *, create_form=None, capture_after=None,
                      draft_offset=0, publication_offset=0):
        detail, stage = self._project_stage(actor, project_id, stage_id)
        unavailable = self.service is None or self.archive is None
        try:
            archive_stage_status = 'unavailable' if unavailable else self.archive.stage_archive_status(
                actor,
                project_id,
                stage_id,
            )
        except ArchiveError:
            raise report_api.ReportError('REPORT_ARTIFACT_INVALID') from None
        archive_absent = archive_stage_status == 'absent'
        capture_page = None if unavailable or archive_absent else self._capture_page(actor, project_id, stage_id, capture_after)
        captures = () if capture_page is None else capture_page['captures']
        drafts = report_api.ReportDraftPage((), None) if unavailable or archive_absent else self.service.list_drafts(
            actor, project_id, stage_id, limit=20, offset=draft_offset,
        )
        publications = report_api.ReportPublicationPage((), None) if unavailable or archive_absent else self.service.list_publications(
            actor, project_id, stage_id, limit=20, offset=publication_offset,
        )
        publication_choices = self._publication_choices(publications.items)
        user_templates = ready_user_template_choices(self.template_service, actor, project_id)
        continuity_templates = ready_continuity_template_choices(self.template_service, actor, project_id)
        weekly_templates = ready_weekly_template_choices(self.template_service, actor, project_id)
        series = self._series_page(actor, project_id, stage_id)
        capture_has_more = bool(capture_page and capture_page['next_cursor'])
        form = create_form or self.create_form(captures, publication_choices,
                                               user_template_choices=user_templates,
                                               require_capture_selection=capture_has_more)
        if not form.is_bound:
            form.fields['capture_after'].initial = capture_after or ''
        return {
            'detail': detail,
            'stage': stage,
            'captures': captures,
            'drafts': drafts,
            'publications': publications,
            'publication_choices': publication_choices,
            'user_template_choices': user_templates,
            'series_template_choices': continuity_templates,
            'weekly_template_choices': weekly_templates,
            'series_page': series,
            'series_rows': tuple(self._series_row(item, continuity_templates) for item in series.items),
            'series_create_form': self.series_create_form(continuity_templates),
            'weekly_create_form': self.weekly_create_form(series, weekly_templates, publications.items),
            'create_form': form,
            'capture_next_cursor': capture_page['next_cursor'] if capture_page else None,
            'capture_after': capture_after or '',
            'draft_offset': draft_offset,
            'draft_previous_offset': max(draft_offset - 20, 0) if draft_offset else None,
            'publication_offset': publication_offset,
            'publication_previous_offset': max(publication_offset - 20, 0) if publication_offset else None,
            'default_capture_id': captures[-1].capture_id if captures and not capture_has_more else '',
            'report_unavailable': unavailable,
            'archive_stage_status': archive_stage_status,
            'can_create_draft': not unavailable and not archive_absent and bool(captures),
            'source_state': self._source_state(unavailable, archive_absent, captures),
            **self.daily_context(captures, series, continuity_templates),
        }

    def create_form(self, captures, publications, data=None, require_capture_selection=False,
                    user_template_choices=()):
        initial = {
            'command_id': new_command_id(),
            'payload_version': '2',
            'template_id': 'daily-standup',
            'template_version': '2',
            'timezone': 'Asia/Shanghai',
            'purpose': 'standup',
        }
        if captures:
            initial['capture_id'] = captures[-1].capture_id
        initial['capture_after'] = ''
        if require_capture_selection:
            initial['capture_id'] = ''
        return ReportCreateForm(
            data,
            capture_choices=captures,
            publication_choices=publications,
            user_template_choices=user_template_choices,
            require_capture_selection=require_capture_selection,
            initial=initial,
        )

    def create_draft(self, actor, project_id, stage_id, form):
        if form.is_authored():
            return self._service().create_authored(
                actor,
                project_id,
                stage_id,
                command_id=str(form.cleaned_data['command_id']),
                selection=form.selection(),
                template=form.authored_template(),
                preparation_id=None,
            )
        return self._service().create(
            actor,
            project_id,
            stage_id,
            command_id=str(form.cleaned_data['command_id']),
            selection=form.selection(),
            template=form.template(),
        )

    def draft_context(self, actor, project_id, stage_id, draft_id, *, save_form=None, finalize_form=None):
        detail, stage = self._project_stage(actor, project_id, stage_id)
        draft = self.get_draft(actor, project_id, stage_id, draft_id)
        target_choices = target_choices_for_snapshot(draft.snapshot)
        save_form = save_form or self.save_form(draft, target_choices)
        authored_save_form = self.authored_save_form(draft)
        finalize_form = finalize_form or ReportFinalizeForm(initial={
            'command_id': new_command_id(),
            'expected_revision': draft.revision,
        })
        finalization_status = self._service().finalization_status(actor, project_id, stage_id, draft_id)
        publication_target = self._service().publication_target(actor, project_id, stage_id)
        resume_form = None
        if finalization_status and finalization_status.state == 'finalizing':
            resume_form = ReportResumeForm(initial={'command_id': finalization_status.command_id})
        return {
            'detail': detail,
            'stage': stage,
            'draft': draft,
            'save_form': save_form,
            'authored_save_form': authored_save_form,
            'finalize_form': finalize_form,
            'target_choices': target_choices,
            'authored_note_targets': target_payloads(draft.snapshot, target_choices.note_targets,
                                                     target_choices.target_map, include_hash=False),
            'authored_override_targets': target_payloads(draft.snapshot, target_choices.override_targets,
                                                         target_choices.target_map, include_hash=True),
            'edit_rows': self._edit_rows(draft, target_choices),
            'authored_edit_rows': authored_edit_rows(draft, target_choices),
            'report_body': report_body(draft, self._service().renderer),
            'new_note_slots': tuple({'edit_id': new_command_id()} for _ in range(3)),
            'new_override_slots': tuple({'edit_id': new_command_id()} for _ in range(2)),
            'finalization_status': finalization_status,
            'resume_form': resume_form,
            'publication_target': publication_target,
        }

    def get_draft(self, actor, project_id, stage_id, draft_id):
        return self._service().get(actor, project_id, stage_id, draft_id)

    def save_form(self, draft, target_choices, data=None):
        if data is not None and data.get('payload_version') == '2':
            return self.authored_save_form(draft, data)
        initial = {
            'command_id': new_command_id(),
            'expected_revision': draft.revision,
            'template_id': draft.template.template_id,
            'template_version': draft.template.version,
            'note_edit_id': new_command_id(),
            'override_edit_id': new_command_id(),
        }
        self._apply_existing_edit_initial(initial, draft, target_choices)
        return ReportSaveForm(
            data,
            snapshot=draft.snapshot,
            target_choices=target_choices,
            current_edits=draft.edits,
            initial=initial,
        )

    def authored_save_form(self, draft, data=None):
        return ReportAuthoredSaveForm(
            data,
            snapshot=draft.snapshot,
            initial={
                'payload_version': '2',
                'command_id': new_command_id(),
                'expected_revision': draft.revision,
                'expected_revision_hash': draft.revision_hash,
                'authored_edits': authored_edits_json(draft),
                'continuity_changes': '[]',
            },
        )

    def save_draft(self, actor, project_id, stage_id, draft_id, form):
        if isinstance(form, ReportAuthoredSaveForm):
            return self._service().save_authored(
                actor,
                project_id,
                stage_id,
                draft_id,
                command_id=str(form.cleaned_data['command_id']),
                expected_revision=form.cleaned_data['expected_revision'],
                expected_revision_hash=form.cleaned_data['expected_revision_hash'],
                edits=form.edits(),
                continuity_changes=form.continuity_changes(),
            )
        return self._service().save(
            actor,
            project_id,
            stage_id,
            draft_id,
            command_id=str(form.cleaned_data['command_id']),
            expected_revision=form.cleaned_data['expected_revision'],
            edits=form.edits(),
            template=form.template(),
        )

    def render(self, actor, project_id, stage_id, draft_id, revision):
        return self._service().render(actor, project_id, stage_id, draft_id, revision=revision)

    def finalize(self, actor, project_id, stage_id, draft_id, form):
        return self._service().finalize_and_commit(
            actor,
            project_id,
            stage_id,
            draft_id,
            command_id=str(form.cleaned_data['command_id']),
            expected_revision=form.cleaned_data['expected_revision'],
        )

    def resume(self, actor, project_id, stage_id, draft_id, form):
        return self._service().resume_finalization(
            actor,
            project_id,
            stage_id,
            draft_id,
            command_id=str(form.cleaned_data['command_id']),
        )

    def _capture_page(self, actor, project_id, stage_id, capture_after):
        try:
            page = self.archive.list_capture_metadata(actor, project_id, stage_id, limit=20, after=capture_after or None)
        except ArchiveError:
            raise report_api.ReportError('REPORT_INVALID') from None
        captures = tuple(
            CaptureChoice(
                item.receipt.capture_id,
                f"{datetime.fromisoformat(item.source_as_of).astimezone(UTC):%Y-%m-%d %H:%M UTC} / {item.receipt.capture_id[:8]}",
                item.receipt.complete,
                item.receipt.membership_complete,
                item.receipt.checkout_state,
                item.source_as_of,
            )
            for item in page.items
        )
        return {'captures': captures, 'next_cursor': page.next_cursor}

    def _publication_choices(self, publications):
        return tuple(
            PublicationChoice(
                item.manifest.publication_id,
                _('Publication %(id)s') % {'id': item.manifest.publication_id},
            )
            for item in publications
        )

    def _project_stage(self, actor, project_id, stage_id):
        detail = self.project_api.get_project(actor, project_id)
        for stage in detail.stages:
            if stage.id == stage_id:
                return detail, stage
        raise ProjectError('PROJECT_NOT_FOUND')

    def _source_state(self, unavailable, archive_absent, captures):
        if unavailable:
            return {'kind': 'unavailable', 'label': _('Report archive is not configured.')}
        if archive_absent:
            return {'kind': 'absent', 'label': _('Archive has not been initialized for this stage yet.')}
        if not captures:
            return {'kind': 'no_data', 'label': _('No retained source capture is available.')}
        if captures[-1].complete and captures[-1].membership_complete:
            return {'kind': 'current', 'label': _('Current source capture available.')}
        return {'kind': 'partial', 'label': _('Only partial source capture is available.')}

    def _service(self):
        if self.service is None:
            raise report_api.ReportError('REPORT_NOT_FOUND')
        return self.service

    def _continuity_service(self):
        if self.continuity_service is None:
            raise report_api.ReportError('REPORT_NOT_FOUND')
        return self.continuity_service

    def _apply_existing_edit_initial(self, initial, draft, target_choices):
        if len(draft.edits) != 1:
            return
        reverse_targets = {tuple(sorted(value.items())): key for key, value in target_choices.target_map.items()}
        for edit in draft.edits:
            encoded = reverse_targets.get(tuple(sorted(edit.target.items())))
            if encoded is None:
                continue
            if edit.kind == 'note' and not initial.get('note_text'):
                initial.update(note_edit_id=edit.edit_id, note_target=encoded, note_text=edit.text)
            if edit.kind == 'narrative_override' and not initial.get('override_text'):
                initial.update(override_edit_id=edit.edit_id, override_target=encoded, override_text=edit.text)

    def _edit_rows(self, draft, target_choices):
        reverse_targets = {tuple(sorted(value.items())): key for key, value in target_choices.target_map.items()}
        labels = dict(target_choices.note_targets + target_choices.override_targets)
        rows = []
        for edit in draft.edits:
            encoded = reverse_targets.get(tuple(sorted(edit.target.items())))
            if encoded is None:
                continue
            rows.append({
                'edit_id': edit.edit_id,
                'kind': edit.kind,
                'target': encoded,
                'target_label': labels.get(encoded, encoded),
                'text': edit.text,
                'author': edit.author,
                'edited_at': edit.edited_at,
            })
        return tuple(rows)
