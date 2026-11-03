import re

from django import forms
from django.utils.translation import gettext_lazy as _


def clean_project_key(value):
    text = str(value or '')
    if not text or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', text):
        raise forms.ValidationError(_('Use lower-case letters, numbers, underscore or dash.'))
    return text


def clean_display_name(value):
    text = str(value or '').strip()
    if not text or len(text) > 160 or any(ord(char) < 32 for char in text):
        raise forms.ValidationError(_('Enter a name from 1 to 160 characters.'))
    return text


class ProjectCreateForm(forms.Form):
    key = forms.CharField(label=_('Project key'), max_length=64)
    name = forms.CharField(label=_('Project name'), max_length=160)

    def clean_key(self):
        return clean_project_key(self.cleaned_data['key'])

    def clean_name(self):
        return clean_display_name(self.cleaned_data['name'])


class ProjectListQueryForm(forms.Form):
    offset = forms.IntegerField(required=False, min_value=0, max_value=2_147_483_647)

    def clean_offset(self):
        return self.cleaned_data.get('offset') or 0


class StagePreviewForm(forms.Form):
    key = forms.CharField(label=_('Stage key'), max_length=64)
    name = forms.CharField(label=_('Stage name'), max_length=160)
    source = forms.ChoiceField(label=_('Source'))

    def __init__(self, *args, source_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.source_choices = {choice.key: choice for choice in source_choices}
        self.fields['source'].choices = [(choice.key, choice.label) for choice in source_choices]

    def clean_source(self):
        key = self.cleaned_data['source']
        return self.source_choices[key]

    def clean_key(self):
        return clean_project_key(self.cleaned_data['key'])

    def clean_name(self):
        return clean_display_name(self.cleaned_data['name'])


class StageConfirmForm(forms.Form):
    preview_id = forms.CharField(label=_('Preview ID'), max_length=120)

    def clean_preview_id(self):
        value = self.cleaned_data['preview_id']
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,120}', value):
            raise forms.ValidationError(_('Preview is not valid.'))
        return value


class ProjectArchiveForm(forms.Form):
    confirm = forms.BooleanField(label=_('Archive this project'), required=True)
