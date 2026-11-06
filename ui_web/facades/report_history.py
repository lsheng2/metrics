import json

from django.utils.translation import gettext as _

from project_management.app.api import reports as report_api
from project_management.reporting.fragment_renderers import rich_fragment_to_html
from ui_web.report_forms import ReportLinkedRevisionCreateForm, ReportRevisionCreateForm, new_command_id
from ui_web.report_continuity_view_model import pinned_matrix
from ui_web.report_series_forms import ReportSeriesCreateForm, ReportSeriesPolicyForm, ReportWeeklyDraftCreateForm


class ProjectReportHistoryFacadeMixin:
    def series_create_form(self, user_template_choices, data=None):
        return ReportSeriesCreateForm(
            data,
            user_template_choices=user_template_choices,
            initial={
                'command_id': new_command_id(),
                'calendar_choice': 'iso8601',
                'timezone': 'Asia/Shanghai',
            },
        )

    def create_series(self, actor, project_id, stage_id, form):
        return self._continuity_service().create_series(
            actor,
            project_id,
            stage_id,
            command_id=str(form.cleaned_data['command_id']),
            name=form.cleaned_data['series_name'],
            calendar=form.calendar(),
            template_selection=form.template_selection(),
        )

    def series_policy_form(self, revision, template_choices, data=None):
        return ReportSeriesPolicyForm(
            data,
            user_template_choices=template_choices,
            initial={
                'command_id': new_command_id(),
                'series_name': revision.name,
                'calendar_choice': 'iso8601',
                'calendar_id': revision.calendar.calendar_id,
                'calendar_revision': revision.calendar.revision,
                'calendar_week_rule': revision.calendar.week_rule,
                'calendar_date_map': json.dumps(revision.calendar.date_map, ensure_ascii=False, separators=(',', ':')),
                'timezone': revision.calendar.timezone,
                'template_choice': (
                    f'user|{revision.default_template_selection.template_id}|'
                    f'{revision.default_template_selection.revision}|'
                    f'{revision.default_template_selection.revision_hash}'
                ),
                'expected_revision': revision.revision,
                'expected_revision_hash': revision.revision_hash,
            },
        )

    def save_series_policy(self, actor, project_id, stage_id, series_id, form):
        return self._continuity_service().save_series_policy(
            actor,
            project_id,
            stage_id,
            command_id=str(form.cleaned_data['command_id']),
            series_id=series_id,
            expected_revision=form.cleaned_data['expected_revision'],
            expected_revision_hash=form.cleaned_data['expected_revision_hash'],
            name=form.cleaned_data['series_name'],
            calendar=form.calendar(),
            template_selection=form.template_selection(),
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
            'linked_revision_form': ReportLinkedRevisionCreateForm(initial={'command_id': new_command_id()}),
        }

    def period_context(self, actor, project_id, stage_id, period_key, publication_ids):
        detail, stage = self._project_stage(actor, project_id, stage_id)
        publications = tuple(self._service().get_publication(actor, project_id, stage_id, publication_id)
                             for publication_id in publication_ids)
        refs = tuple(report_api.PublicationRef(
            publication.manifest.publication_id,
            publication.manifest_sha256,
            publication.commit_id,
        ) for publication in publications)
        period = self._continuity_service().read_period(
            actor,
            project_id,
            stage_id,
            series_id=publications[0].manifest.series_id,
            period_key=period_key,
            selected_publication_refs=refs,
        )
        period_draft = type('PeriodDraft', (), {
            'snapshot': period.source_snapshot,
            'authoring_context': period.weekly_context,
            'template_snapshot': {'resolved_document': {'blocks': ()}},
        })()
        return {
            'detail': detail,
            'stage': stage,
            'period': period,
            'publications': publications,
            'matrix_view': pinned_matrix(period_draft, {}, read_only=True),
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

    def create_linked_revision(self, actor, project_id, stage_id, publication_id, form):
        publication = self._service().get_publication(actor, project_id, stage_id, publication_id)
        return self._service().create_linked_revision(
            actor,
            project_id,
            stage_id,
            command_id=str(form.cleaned_data['command_id']),
            publication_ref=report_api.PublicationRef(
                publication.manifest.publication_id,
                publication.manifest_sha256,
                publication.commit_id,
            ),
        )

    def read_publication_artifact(self, actor, project_id, stage_id, publication_id, format):
        return self._service().read_artifact(actor, project_id, stage_id, publication_id, format)

    def weekly_create_form(self, series_page, template_choices, publications, data=None):
        publication_choices = tuple(
            (item.manifest.publication_id,
             f"{item.manifest.meeting_key or item.manifest.publication_id} r{item.manifest.draft_revision}")
            for item in publications
            if getattr(item.manifest, 'report_role', None) == 'daily'
        )
        period_choices = tuple(sorted({
            (item.manifest.period_key, item.manifest.period_key)
            for item in publications
            if getattr(item.manifest, 'report_role', None) == 'daily' and item.manifest.period_key
        }))
        return ReportWeeklyDraftCreateForm(
            data,
            template_choices=template_choices,
            publication_choices=publication_choices,
            series_choices=tuple((item.series_id, item.name) for item in series_page.items),
            period_choices=period_choices,
            initial={
                'command_id': new_command_id(),
                'series_id': '',
                'period_key': '',
            },
        )

    def create_weekly_draft(self, actor, project_id, stage_id, form):
        refs = []
        for publication_id in form.cleaned_data['publication_id']:
            publication = self._service().get_publication(actor, project_id, stage_id, publication_id)
            refs.append(report_api.PublicationRef(
                publication.manifest.publication_id,
                publication.manifest_sha256,
                publication.commit_id,
            ))
        return self._service().create_period_view(
            actor,
            project_id,
            stage_id,
            command_id=str(form.cleaned_data['command_id']),
            series_id=form.cleaned_data['series_id'],
            period_key=form.cleaned_data['period_key'],
            selected_publication_refs=tuple(refs),
            template=form.template_selection(),
        )

    def _series_page(self, actor, project_id, stage_id):
        if self.continuity_service is None:
            return report_api.SeriesPage((), None)
        return self.continuity_service.list_series(actor, project_id, stage_id, limit=20, offset=0)

    def _series_row(self, revision, template_choices, form=None, error=None):
        return {
            'item': revision,
            'form': form or self.series_policy_form(revision, template_choices),
            'error': error,
        }
