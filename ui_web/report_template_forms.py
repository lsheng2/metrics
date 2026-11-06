import json
from uuid import UUID

from django import forms
from django.utils.translation import gettext_lazy as _

from project_management.app.api import reports as report_api
from ui_web.report_forms import new_command_id
from ui_web.report_template_documents import blank_document, continuity_starter_document, default_fill_policy, starter_document


MAX_TEMPLATE_POST_BYTES = 262_144


class TemplateLibraryActionForm(forms.Form):
    action = forms.ChoiceField(choices=(
        ('blank', _('Blank template')),
        ('builtin_daily', _('Copy daily starter')),
        ('builtin_weekly', _('Copy weekly starter')),
        ('continuity_daily', _('Copy continuity daily starter')),
        ('continuity_weekly', _('Copy continuity weekly starter')),
    ))
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    name = forms.CharField(label=_('Name'), min_length=1, max_length=160)

    def template_payload(self):
        action = self.cleaned_data['action']
        if action == 'blank':
            document = blank_document()
        elif action == 'builtin_weekly':
            document = starter_document('weekly')
        elif action == 'continuity_daily':
            document = continuity_starter_document('daily')
        elif action == 'continuity_weekly':
            document = continuity_starter_document('weekly')
        else:
            document = starter_document('daily')
        return document, default_fill_policy(document)


class TemplateSaveForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=1, max_value=1_000_000, widget=forms.HiddenInput)
    expected_revision_hash = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)
    name = forms.CharField(label=_('Name'), min_length=1, max_length=160)
    document = forms.CharField(widget=forms.HiddenInput)
    fill_policy = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._document = None
        self._fill_policy = None

    def clean_expected_revision_hash(self):
        return hash_text(self.cleaned_data['expected_revision_hash'])

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        self._document = parse_json(cleaned['document'])
        self._fill_policy = parse_json(cleaned['fill_policy'])
        try:
            report_api.validate_report_template_revision(cleaned['name'], self._document, self._fill_policy)
        except report_api.ReportError as error:
            raise forms.ValidationError(template_error_message(error)) from None
        return cleaned

    def document_value(self):
        return self._document

    def fill_policy_value(self):
        return self._fill_policy


class TemplateArchiveForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=1, max_value=1_000_000, widget=forms.HiddenInput)
    expected_revision_hash = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)
    confirm = forms.BooleanField(label=_('Archive this template'), required=True)

    def clean_expected_revision_hash(self):
        return hash_text(self.cleaned_data['expected_revision_hash'])


class TemplateCopyForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=1, max_value=1_000_000)
    name = forms.CharField(label=_('Name'), min_length=1, max_length=160)


def initial_library_form(action, name):
    return TemplateLibraryActionForm(initial={'action': action, 'name': name, 'command_id': new_command_id()})


def initial_archive_form(revision):
    return TemplateArchiveForm(initial={
        'command_id': new_command_id(),
        'expected_revision': revision.revision,
        'expected_revision_hash': revision.revision_hash,
    })


def initial_save_form(revision):
    return TemplateSaveForm(initial={
        'command_id': new_command_id(),
        'expected_revision': revision.revision,
        'expected_revision_hash': revision.revision_hash,
        'name': revision.name,
        'document': json.dumps(revision.document, ensure_ascii=False, separators=(',', ':')),
        'fill_policy': json.dumps(revision.fill_policy, ensure_ascii=False, separators=(',', ':')),
    })


def initial_copy_form(revision):
    revision_number = getattr(revision, 'revision', getattr(revision, 'current_revision', 1))
    return TemplateCopyForm(initial={
        'command_id': new_command_id(),
        'revision': revision_number,
        'name': revision.name + ' copy',
    })


def parse_json(value):
    if len(value.encode('utf-8')) > MAX_TEMPLATE_POST_BYTES:
        raise report_api.ReportError('REPORT_LIMIT')
    try:
        return json.loads(value, object_pairs_hook=reject_duplicate_json_keys, parse_constant=reject_constant)
    except (TypeError, UnicodeError, ValueError, json.JSONDecodeError):
        raise forms.ValidationError(_('Template payload is invalid.')) from None


def reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError('invalid constant')


def hash_text(value):
    if any(character not in '0123456789abcdef' for character in value):
        raise forms.ValidationError(_('Template request is invalid.'))
    return value


def uuid_text(value):
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise forms.ValidationError(_('Template request is invalid.')) from None
    return str(parsed)


def template_error_message(error):
    return {
        'REPORT_TEMPLATE_UNSUPPORTED': _('Template structure is invalid.'),
        'REPORT_LIMIT': _('Template is over the configured limit.'),
    }.get(error.code, _('Template request is invalid.'))
