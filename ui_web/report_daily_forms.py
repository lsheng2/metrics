from datetime import date

from django import forms
from django.utils.translation import gettext_lazy as _

from project_management.app.api import reports as report_api
from ui_web.report_forms import hash_text, new_command_id, uuid_text


SOURCE_MODE_CHOICES = (
    ('saved_capture', _('Saved capture')),
    ('refresh', _('Refresh source')),
)
ANALYSIS_MODE_CHOICES = (
    ('manual_only', _('Manual only')),
    ('changed_items', _('Changed items')),
)


class PendingDraftIdsField(forms.MultipleChoiceField):
    def validate(self, value):
        if len(value) > 100 or len(value) != len(set(value)):
            raise forms.ValidationError(_('Report request is invalid.'))
        for item in value:
            uuid_text(item)


class ReportDailyPreviewForm(forms.Form):
    series_id = forms.ChoiceField(label=_('Report series'))
    meeting_date = forms.DateField(label=_('Meeting date'), widget=forms.DateInput(attrs={'type': 'date'}))
    template_choice = forms.ChoiceField(label=_('Matrix template revision'))
    capture_after = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, series_choices=(), template_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['series_id'].choices = (('', _('Select series')), *tuple(series_choices))
        self.fields['template_choice'].choices = (('', _('Select template')), *tuple(template_choices))

    def meeting_date_value(self):
        value = self.cleaned_data['meeting_date']
        if isinstance(value, date):
            return value.isoformat()
        return value

    def template_selection(self):
        return template_selection_from_choice(self.cleaned_data['template_choice'])


class ReportDailyPreparationForm(ReportDailyPreviewForm):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_series_policy_hash = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)
    baseline_publication_id = forms.CharField(required=False, widget=forms.HiddenInput)
    baseline_manifest_hash = forms.CharField(required=False, min_length=64, max_length=64, widget=forms.HiddenInput)
    baseline_commit = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    source_mode = forms.ChoiceField(label=_('Source mode'), choices=SOURCE_MODE_CHOICES)
    capture_id = forms.CharField(label=_('Saved capture'), required=False, max_length=36, widget=forms.Select)
    analysis_mode = forms.ChoiceField(label=_('Analysis mode'), choices=ANALYSIS_MODE_CHOICES)
    acknowledge_gap_draft_ids = PendingDraftIdsField(
        required=False, label=_('Confirm pending-draft gap'), widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, capture_choices=(), gap_choices=(), runtime_ready=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['series_id'] = forms.CharField(max_length=36, widget=forms.HiddenInput)
        self.fields['template_choice'] = forms.CharField(max_length=200, widget=forms.HiddenInput)
        self.runtime_ready = runtime_ready
        self.fields['capture_id'].widget.choices = (('', _('Select saved capture')), *tuple(capture_choices))
        if not self.is_bound:
            self.fields['command_id'].initial = new_command_id()
            self.fields['source_mode'].initial = 'saved_capture'
            self.fields['analysis_mode'].initial = 'manual_only'
        self.fields['acknowledge_gap_draft_ids'].choices = tuple(gap_choices)

    def clean_series_id(self):
        return uuid_text(self.cleaned_data['series_id'])

    def clean_template_choice(self):
        value = self.cleaned_data['template_choice']
        template_selection_from_choice(value)
        return value

    def clean_capture_id(self):
        value = self.cleaned_data.get('capture_id') or ''
        return uuid_text(value) if value else ''

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        baseline_from_fields(cleaned)
        source_mode = cleaned['source_mode']
        analysis_mode = cleaned['analysis_mode']
        capture_id = cleaned.get('capture_id') or None
        if source_mode == 'saved_capture' and (not capture_id or analysis_mode != 'manual_only'):
            raise forms.ValidationError(_('Saved capture preparation is manual only.'))
        if source_mode == 'refresh' and capture_id:
            raise forms.ValidationError(_('Refresh chooses its capture automatically.'))
        return cleaned

    def clean_expected_series_policy_hash(self):
        value = self.cleaned_data.get('expected_series_policy_hash') or ''
        return '' if not value else hash_text(value)

    def clean_baseline_manifest_hash(self):
        value = self.cleaned_data.get('baseline_manifest_hash') or ''
        return '' if not value else hash_text(value)

    def capture_id_value(self):
        return self.cleaned_data.get('capture_id') or None

    def gap_ids(self):
        return tuple(uuid_text(value) for value in self.cleaned_data['acknowledge_gap_draft_ids'])

    def expected_policy_hash(self):
        return self.cleaned_data.get('expected_series_policy_hash') or None

    def expected_baseline_ref(self):
        return baseline_from_fields(self.cleaned_data)


class ReportDailyReprepareForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    preparation_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_operation_revision = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    expected_draft_revision = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    expected_draft_revision_hash = forms.CharField(required=False, min_length=64, max_length=64, widget=forms.HiddenInput)
    baseline_publication_id = forms.CharField(required=False, widget=forms.HiddenInput)
    baseline_manifest_hash = forms.CharField(required=False, min_length=64, max_length=64, widget=forms.HiddenInput)
    baseline_commit = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput)
    template_choice = forms.CharField(label=_('Matrix template revision'), max_length=200, widget=forms.Select)
    source_mode = forms.ChoiceField(label=_('Source mode'), choices=SOURCE_MODE_CHOICES)
    capture_id = forms.CharField(required=False, max_length=36)
    analysis_mode = forms.ChoiceField(label=_('Analysis mode'), choices=ANALYSIS_MODE_CHOICES)
    capture_after = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, template_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template_choice'].widget.choices = tuple(template_choices)
        if not self.is_bound:
            self.fields['command_id'].initial = new_command_id()

    def clean_expected_draft_revision_hash(self):
        value = self.cleaned_data.get('expected_draft_revision_hash')
        return '' if not value else hash_text(value)

    def clean_template_choice(self):
        value = self.cleaned_data['template_choice']
        template_selection_from_choice(value)
        return value

    def clean(self):
        cleaned = super().clean()
        if not self.errors:
            baseline_from_fields(cleaned)
            capture = cleaned.get('capture_id') or ''
            if capture:
                cleaned['capture_id'] = uuid_text(capture)
            if cleaned['source_mode'] == 'saved_capture' and (not capture or cleaned['analysis_mode'] != 'manual_only'):
                raise forms.ValidationError(_('Saved capture preparation is manual only.'))
            if cleaned['source_mode'] == 'refresh' and capture:
                raise forms.ValidationError(_('Refresh chooses its capture automatically.'))
        return cleaned

    def clean_baseline_manifest_hash(self):
        value = self.cleaned_data.get('baseline_manifest_hash') or ''
        return '' if not value else hash_text(value)

    def template_selection(self):
        return template_selection_from_choice(self.cleaned_data['template_choice'])

    def expected_baseline_ref(self):
        return baseline_from_fields(self.cleaned_data)


def baseline_from_fields(value):
    publication_id = value.get('baseline_publication_id') or ''
    manifest_hash = value.get('baseline_manifest_hash') or ''
    commit = value.get('baseline_commit') or ''
    if (publication_id, manifest_hash, commit) == ('', '', ''):
        return None
    if not (publication_id and manifest_hash and commit):
        raise forms.ValidationError(_('Baseline request is invalid.'))
    if len(commit) != 40 or any(character not in '0123456789abcdef' for character in commit):
        raise forms.ValidationError(_('Baseline request is invalid.'))
    return report_api.PublicationRef(uuid_text(publication_id), hash_text(manifest_hash), commit)


def template_selection_from_choice(value):
    parts = value.split('|')
    if len(parts) != 4 or parts[0] != 'user':
        raise forms.ValidationError(_('Template request is invalid.'))
    return report_api.UserTemplateSelection(uuid_text(parts[1]), positive_int(parts[2]), hash_text(parts[3]))


def positive_int(value):
    try:
        parsed = int(value)
    except ValueError:
        raise forms.ValidationError(_('Template request is invalid.')) from None
    if parsed < 1 or parsed > 1_000_000:
        raise forms.ValidationError(_('Template request is invalid.'))
    return parsed
