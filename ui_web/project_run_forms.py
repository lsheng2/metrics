from django import forms

from project_management.app.api.project_runs import RunRequest
from project_management.app.api.reports import TemplateSelection
from ui_web.report_forms import new_command_id


class ProjectRunSubmitForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_stage_hash = forms.CharField(widget=forms.HiddenInput, min_length=64, max_length=64)
    template_id = forms.ChoiceField(choices=(('daily-standup', 'Daily standup'),))
    template_version = forms.ChoiceField(choices=(('1', '1'),), widget=forms.HiddenInput)
    timezone = forms.CharField(max_length=128)

    def request(self):
        return RunRequest(
            str(self.cleaned_data['command_id']),
            self.cleaned_data['expected_stage_hash'],
            TemplateSelection(
                self.cleaned_data['template_id'],
                self.cleaned_data['template_version'],
                {},
            ),
            self.cleaned_data['timezone'],
        )


class ProjectRunRevisionForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=1)


def run_submit_form(stage, data=None):
    return ProjectRunSubmitForm(data, initial={
        'command_id': new_command_id(),
        'expected_stage_hash': stage.definition_hash,
        'template_id': 'daily-standup',
        'template_version': '1',
        'timezone': 'Asia/Shanghai',
    })
