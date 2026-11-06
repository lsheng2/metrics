from dataclasses import asdict
from datetime import date

from django.utils.translation import gettext as _

from project_management.app.api.project_runs import get_report_preparation_service
from project_management.app.api.report_factories import build_report_preparation_service
from project_management.app.api import reports as report_api
from project_management.app.api.report_queries import ReportQueryService
from ui_web.report_daily_forms import ReportDailyPreparationForm, ReportDailyPreviewForm, ReportDailyReprepareForm


def report_preparation_runtime(project_api, archive, template_service, draft_service, continuity_service):
    installed = get_report_preparation_service()
    if installed is not None and installed.archive.config.root == archive.config.root:
        run_service = installed.run_service
        ready = installed.runtime_options()['refresh'] and run_service.capture_service is not None
        return installed, ready
    preparation = build_report_preparation_service(
        project_api=project_api,
        archive=archive,
        template_service=template_service,
        continuity_service=continuity_service,
        draft_service=draft_service,
    )
    return preparation, False


class ProjectReportDailyFacadeMixin:
    def preview_daily_query(self, actor, project_id, stage_id, form, *, include_captures=False):
        return ReportQueryService(self.archive, self._service(), self._preparation_service()).daily_preview(
            actor, project_id, stage_id,
            series_id=form.cleaned_data['series_id'], meeting_date=form.meeting_date_value(),
            template_selection=form.template_selection(),
            capture_after=form.cleaned_data.get('capture_after') or None, include_captures=include_captures,
        )

    def daily_context(self, captures, series_page, template_choices, *, data=None, preview=None,
                      prepare_form=None, preview_form=None, result=None, error=None, selection_preview=False):
        series_choices = tuple((item.series_id, item.name) for item in series_page.items)
        capture_choices = tuple((item.capture_id, item.label) for item in captures)
        initial = self._daily_initial(data, series_page)
        if selection_preview and preview is not None:
            initial.update({key: (data or {}).get(key, '') for key in ('series_id', 'meeting_date', 'template_choice', 'capture_after')})
            initial.update(self._preview_expected_initial(preview))
        preview_form = preview_form or ReportDailyPreviewForm(
            data,
            series_choices=series_choices,
            template_choices=template_choices,
            initial=initial,
            auto_id='daily_preview_%s',
        )
        prepare_form = prepare_form or ReportDailyPreparationForm(
            None if selection_preview else data,
            series_choices=series_choices,
            template_choices=template_choices,
            capture_choices=capture_choices,
            runtime_ready=self.preparation_runtime_ready,
            gap_choices=() if preview is None else tuple((item, _('Confirm gap for draft %(draft)s') % {
                'draft': item,
            }) for item in preview.pending_gap_draft_ids),
            initial=initial,
            auto_id='daily_prepare_%s',
        )
        if preview is not None:
            prepare_form.fields['acknowledge_gap_draft_ids'].choices = tuple(
                (item, _('Confirm gap for draft %(draft)s') % {'draft': item})
                for item in preview.pending_gap_draft_ids
            )
        return {
            'daily_preview_form': preview_form,
            'daily_prepare_form': prepare_form,
            'daily_preview': preview,
            'daily_result': self._result_row(result),
            'daily_error': error,
            'daily_runtime_ready': self.preparation_runtime_ready,
            'daily_analysis_ready': self.analysis_ready(),
            'daily_calendar': next((item.calendar for item in series_page.items
                                    if item.series_id == str(prepare_form['series_id'].value())), None),
        }

    def preview_daily(self, actor, project_id, stage_id, form):
        return self._preparation_service().continuity.preview(
            actor,
            project_id,
            stage_id,
            series_id=form.cleaned_data['series_id'],
            meeting_date=form.meeting_date_value(),
            template_selection=form.template_selection(),
        )

    def prepare_daily(self, actor, project_id, stage_id, form):
        expected_policy_hash = form.expected_policy_hash()
        if expected_policy_hash is None:
            raise report_api.ReportError('REPORT_BASELINE_CONFLICT')
        return self._preparation_service().prepare(
            actor,
            project_id,
            stage_id,
            command_id=str(form.cleaned_data['command_id']),
            series_id=form.cleaned_data['series_id'],
            meeting_date=form.meeting_date_value(),
            expected_series_policy_hash=expected_policy_hash,
            expected_baseline_ref=form.expected_baseline_ref(),
            template_selection=form.template_selection(),
            source_mode=form.cleaned_data['source_mode'],
            capture_id=form.capture_id_value(),
            analysis_mode=form.cleaned_data['analysis_mode'],
            acknowledge_gap_draft_ids=form.gap_ids(),
        )

    def reprepare_daily(self, actor, project_id, stage_id, form):
        return self._preparation_service().reprepare(
            actor,
            project_id,
            stage_id,
            command_id=str(form.cleaned_data['command_id']),
            preparation_id=str(form.cleaned_data['preparation_id']),
            expected_operation_revision=form.cleaned_data.get('expected_operation_revision'),
            expected_draft_revision=form.cleaned_data.get('expected_draft_revision'),
            expected_draft_revision_hash=form.cleaned_data.get('expected_draft_revision_hash') or None,
            expected_baseline_ref=form.expected_baseline_ref(),
            template_selection=form.template_selection(),
            source_mode=form.cleaned_data['source_mode'],
            capture_id=form.cleaned_data.get('capture_id') or None,
            analysis_mode=form.cleaned_data['analysis_mode'],
        )

    def daily_reprepare_form(self, template_choices, data=None, details=None):
        initial = {}
        if details is not None:
            result = details.result
            selected = result.effective_selection
            template = selected['template_selection']
            baseline = selected['expected_baseline_ref']
            initial = {
                'preparation_id': result.preparation_id,
                'expected_operation_revision': details.operation_revision,
                'expected_draft_revision': result.draft_revision,
                'expected_draft_revision_hash': details.draft_revision_hash or '',
                'template_choice': f"user|{template['template_id']}|{template['revision']}|{template['revision_hash']}",
                'source_mode': 'saved_capture' if result.draft_id else selected['source_mode'],
                'capture_id': selected['capture_id'] if result.draft_id else '',
                'analysis_mode': 'manual_only',
                'baseline_publication_id': '' if baseline is None else baseline['publication_id'],
                'baseline_manifest_hash': '' if baseline is None else baseline['manifest_hash'],
                'baseline_commit': '' if baseline is None else baseline['commit'],
            }
        return ReportDailyReprepareForm(data, template_choices=template_choices, initial=initial,
                                       auto_id='daily_reprepare_%s')

    def preparation_details(self, actor, project_id, stage_id, preparation_id):
        return self._preparation_service().get(actor, project_id, stage_id, preparation_id)

    def preparation_context(self, actor, project_id, stage_id, preparation_id, template_choices, data=None):
        details = self.preparation_details(actor, project_id, stage_id, preparation_id)
        return self.preparation_controls(details, preparation_id, template_choices, data)

    def can_reprepare(self, details, preparation_id):
        terminal = {'draft', 'draft_ready', 'partial', 'failed', 'canceled'}
        return details.result.state in terminal and details.active_preparation_id == preparation_id

    def preparation_controls(self, details, preparation_id, template_choices, data=None):
        return {
            'preparation_details': details,
            'daily_result': self._result_row(details.result),
            'daily_reprepare_form': self.daily_reprepare_form(template_choices, data, details),
            'daily_can_reprepare': self.can_reprepare(details, preparation_id),
            'daily_runtime_ready': self.preparation_runtime_ready,
            'daily_analysis_ready': self.analysis_ready(),
        }

    def analysis_ready(self):
        return bool(self.preparation_runtime_ready and self.preparation_service.runtime_options()['analysis'])

    def _series_policy(self, actor, project_id, stage_id, series_id):
        for item in self._series_page(actor, project_id, stage_id).items:
            if item.series_id == series_id:
                return item
        raise report_api.ReportError('REPORT_NOT_FOUND')

    def _daily_initial(self, data, series_page):
        if data is not None:
            return {}
        return {
            'series_id': '',
            'meeting_date': date.today().isoformat(),
            'template_choice': '',
            'expected_series_policy_hash': '',
            'baseline_publication_id': '',
            'baseline_manifest_hash': '',
            'baseline_commit': '',
        }

    def _preview_expected_initial(self, preview):
        baseline = preview.baseline_ref
        return {
            'series_id': preview.series_id,
            'expected_series_policy_hash': preview.series_policy_hash,
            'baseline_publication_id': '' if baseline is None else baseline.publication_id,
            'baseline_manifest_hash': '' if baseline is None else baseline.manifest_hash,
            'baseline_commit': '' if baseline is None else baseline.commit,
        }

    def _result_row(self, result):
        if result is None:
            return None
        return {
            'disposition': result.disposition,
            'preparation_id': result.preparation_id,
            'operation_id': result.operation_id,
            'draft_id': result.draft_id,
            'draft_revision': result.draft_revision,
            'state': result.state,
            'effective_selection': dict(result.effective_selection),
            'selection_conflicts': result.selection_conflicts,
            'publication_ref': None if result.publication_ref is None else asdict(result.publication_ref),
            'links': dict(result.links),
            'review_issues': tuple(result.preservation_review_issues),
            'summary': _('Existing preparation') if result.disposition == 'existing' else _('New preparation'),
        }

    def _preparation_service(self):
        if self.preparation_service is None:
            raise report_api.ReportError('REPORT_NOT_FOUND')
        return self.preparation_service
