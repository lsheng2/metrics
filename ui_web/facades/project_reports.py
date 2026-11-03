from dataclasses import dataclass

from django.utils.translation import gettext as _

from project_management.app.api import ProjectError
from project_management.app.api.capture_archive import ArchiveError
from project_management.app.api.factories import build_capture_archive_service, build_project_api
from project_management.app.api.report_factories import build_report_service
from project_management.app.api import reports as report_api
from ui_web.report_forms import (
    ReportCreateForm,
    ReportFinalizeForm,
    ReportResumeForm,
    ReportRevisionCreateForm,
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


@dataclass(frozen=True, slots=True)
class PublicationChoice:
    publication_id: str
    label: str


def default_report_facade():
    project_api = build_project_api()
    try:
        archive = build_capture_archive_service(project_api=project_api)
        service = build_report_service(project_api=project_api, archive=archive)
        return ProjectReportFacade(project_api, service, archive)
    except ArchiveError as error:
        if error.code == 'ARCHIVE_ROOT_UNCONFIGURED':
            return ProjectReportFacade(project_api, None, None)
        raise
    except Exception as error:
        if getattr(error, 'code', '') == 'ANALYSIS_CONTRACT_INVALID':
            return ProjectReportFacade(project_api, None, None)
        raise


class ProjectReportFacade:
    def __init__(self, project_api, service, archive):
        self.project_api = project_api
        self.service = service
        self.archive = archive

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
        capture_has_more = bool(capture_page and capture_page['next_cursor'])
        form = create_form or self.create_form(captures, publication_choices,
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
        }

    def create_form(self, captures, publications, data=None, require_capture_selection=False):
        initial = {
            'command_id': new_command_id(),
            'template_id': 'daily-standup',
            'template_version': '1',
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
            require_capture_selection=require_capture_selection,
            initial=initial,
        )

    def create_draft(self, actor, project_id, stage_id, form):
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
            'finalize_form': finalize_form,
            'target_choices': target_choices,
            'edit_rows': self._edit_rows(draft, target_choices),
            'new_note_slots': tuple({'edit_id': new_command_id()} for _ in range(3)),
            'new_override_slots': tuple({'edit_id': new_command_id()} for _ in range(2)),
            'finalization_status': finalization_status,
            'resume_form': resume_form,
            'publication_target': publication_target,
        }

    def get_draft(self, actor, project_id, stage_id, draft_id):
        return self._service().get(actor, project_id, stage_id, draft_id)

    def save_form(self, draft, target_choices, data=None):
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

    def save_draft(self, actor, project_id, stage_id, draft_id, form):
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

    def publication_context(self, actor, project_id, stage_id, publication_id):
        detail, stage = self._project_stage(actor, project_id, stage_id)
        publication = self._service().get_publication(actor, project_id, stage_id, publication_id)
        return {
            'detail': detail,
            'stage': stage,
            'publication': publication,
            'revision_form': ReportRevisionCreateForm(initial={
                'command_id': new_command_id(),
                'template_id': 'daily-standup',
                'template_version': '1',
            }),
        }

    def create_revision(self, actor, project_id, stage_id, publication_id, form):
        snapshot, manifest = self._service().publication_revision_selection(actor, project_id, stage_id, publication_id)
        return self._service().create(
            actor,
            project_id,
            stage_id,
            command_id=str(form.cleaned_data['command_id']),
            selection=report_api.ReportSelection(
                capture_id=snapshot.capture_id,
                baseline_publication_id=manifest.baseline_publication_id,
                parent_publication_id=manifest.publication_id,
                purpose='standup',
                timezone=snapshot.timezone,
            ),
            template=form.template(),
        )

    def read_publication_artifact(self, actor, project_id, stage_id, publication_id, format):
        return self._service().read_artifact(actor, project_id, stage_id, publication_id, format)

    def _capture_page(self, actor, project_id, stage_id, capture_after):
        try:
            page = self.archive.list_captures(actor, project_id, stage_id, limit=20, after=capture_after or None)
        except ArchiveError:
            raise report_api.ReportError('REPORT_INVALID') from None
        captures = tuple(
            CaptureChoice(
                item.capture_id,
                _('Capture %(id)s') % {'id': item.capture_id},
                item.complete,
                item.membership_complete,
                item.checkout_state,
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
