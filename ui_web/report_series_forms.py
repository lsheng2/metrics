import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.utils.translation import gettext_lazy as _

from project_management.app.api import reports as report_api
from ui_web.report_forms import hash_text, uuid_text


class ReportSeriesCreateForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    series_name = forms.CharField(label=_('Name'), min_length=1, max_length=160)
    calendar_choice = forms.ChoiceField(label=_('Calendar'), choices=(('iso8601', _('ISO 8601 week')),))
    timezone = forms.CharField(label=_('Timezone'), max_length=64)
    template_choice = forms.ChoiceField(label=_('Matrix template'))
    calendar_id = forms.CharField(required=False, widget=forms.HiddenInput)
    calendar_revision = forms.IntegerField(required=False, min_value=1, max_value=1_000_000, widget=forms.HiddenInput)
    calendar_week_rule = forms.CharField(required=False, widget=forms.HiddenInput)
    calendar_date_map = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, user_template_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template_choice'].choices = tuple(user_template_choices)

    def clean_timezone(self):
        value = self.cleaned_data['timezone']
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise forms.ValidationError(_('Timezone is not available.')) from None
        return value

    def clean_template_choice(self):
        value = self.cleaned_data['template_choice']
        parts = value.split('|')
        if len(parts) != 4 or parts[0] != 'user':
            raise forms.ValidationError(_('Template request is invalid.'))
        self._template_selection = report_api.UserTemplateSelection(
            uuid_text(parts[1]),
            self._positive_int(parts[2]),
            hash_text(parts[3]),
        )
        return value

    def calendar(self):
        if self.cleaned_data.get('calendar_id'):
            return report_api.ReportingCalendar(
                self.cleaned_data['calendar_id'],
                self.cleaned_data['calendar_revision'],
                self.cleaned_data['timezone'],
                self.cleaned_data['calendar_week_rule'],
                json.loads(self.cleaned_data.get('calendar_date_map') or '{}'),
            )
        if self.cleaned_data['calendar_choice'] != 'iso8601':
            raise forms.ValidationError(_('Calendar is not available.'))
        return report_api.ReportingCalendar('iso8601', 1, self.cleaned_data['timezone'], 'iso8601', {})

    def template_selection(self):
        return self._template_selection

    def _positive_int(self, value):
        try:
            parsed = int(value)
        except ValueError:
            raise forms.ValidationError(_('Template request is invalid.')) from None
        if parsed < 1 or parsed > 1_000_000:
            raise forms.ValidationError(_('Template request is invalid.'))
        return parsed


class ReportSeriesPolicyForm(ReportSeriesCreateForm):
    expected_revision = forms.IntegerField(min_value=1, max_value=1_000_000, widget=forms.HiddenInput)
    expected_revision_hash = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)

    def clean_expected_revision_hash(self):
        return hash_text(self.cleaned_data['expected_revision_hash'])


class ReportWeeklyDraftCreateForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    series_id = forms.ChoiceField(label=_('Report series'))
    period_key = forms.ChoiceField(label=_('Period'))
    template_choice = forms.ChoiceField(label=_('Weekly matrix template'))
    publication_id = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, template_choices=(), publication_choices=(), series_choices=(),
                 period_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['series_id'].choices = (('', _('Select series')), *tuple(series_choices))
        self.fields['period_key'].choices = (('', _('Select period')), *tuple(period_choices))
        self.fields['template_choice'].choices = tuple(template_choices)
        self.fields['publication_id'].choices = tuple(publication_choices)

    def clean_template_choice(self):
        value = self.cleaned_data['template_choice']
        parts = value.split('|')
        if len(parts) != 4 or parts[0] != 'user':
            raise forms.ValidationError(_('Template request is invalid.'))
        self._template_selection = report_api.UserTemplateSelection(
            uuid_text(parts[1]),
            self._positive_int(parts[2]),
            hash_text(parts[3]),
        )
        return value

    def template_selection(self):
        return self._template_selection

    def _positive_int(self, value):
        try:
            parsed = int(value)
        except ValueError:
            raise forms.ValidationError(_('Template request is invalid.')) from None
        if parsed < 1 or parsed > 1_000_000:
            raise forms.ValidationError(_('Template request is invalid.'))
        return parsed
