from django import forms
from django.utils.translation import gettext_lazy as _

from ui_web.report_forms import hash_text, uuid_text


class MeetingQueryForm(forms.Form):
    series_id = forms.ChoiceField(label=_('Report series'))
    from_date = forms.DateField(label=_('From date'), widget=forms.DateInput(attrs={'type': 'date', 'class': 'input'}))
    through_date = forms.DateField(label=_('Through date'), widget=forms.DateInput(attrs={'type': 'date', 'class': 'input'}))

    def __init__(self, *args, series_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['series_id'].choices = (('', _('Select series')), *tuple(series_choices))

    def interval(self):
        return {
            'series_id': str(self.cleaned_data['series_id']),
            'from_date': self.cleaned_data['from_date'].isoformat(),
            'through_date': self.cleaned_data['through_date'].isoformat(),
        }


class MeetingChangeForm(MeetingQueryForm):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    expected_revision_hash = forms.CharField(validators=[hash_text], widget=forms.HiddenInput)
    expected_series_policy_hash = forms.CharField(validators=[hash_text], widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=(('skip', _('Skip meetings')), ('restore', _('Restore meetings'))))
    reason = forms.CharField(label=_('Reason'), required=False, max_length=240,
                             widget=forms.TextInput(attrs={'class': 'input'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['series_id'] = forms.CharField(validators=[uuid_text], widget=forms.HiddenInput)
