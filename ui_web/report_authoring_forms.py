import json

from django import forms
from django.utils.translation import gettext_lazy as _

from project_management.app.api import reports as report_api


SCHEMA2_POST_LIMIT = 1_048_576


class ReportAuthoredSaveForm(forms.Form):
    payload_version = forms.ChoiceField(choices=(('2', '2'),), widget=forms.HiddenInput)
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=1, max_value=1_000_000, widget=forms.HiddenInput)
    expected_revision_hash = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput)
    authored_edits = forms.CharField(widget=forms.HiddenInput)
    continuity_changes = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, snapshot=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['continuity_changes'] = forms.CharField(required=False, widget=forms.HiddenInput)
        self.snapshot = snapshot
        self._edits = ()
        self._continuity_changes = ()

    def clean_expected_revision_hash(self):
        value = self.cleaned_data['expected_revision_hash']
        if any(character not in '0123456789abcdef' for character in value):
            raise forms.ValidationError(_('Report request is invalid.'))
        return value

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        self._edits = tuple(self._parse_edits(cleaned['authored_edits']))
        self._continuity_changes = tuple(self._parse_continuity(cleaned.get('continuity_changes') or '[]'))
        return cleaned

    def edits(self):
        return self._edits

    def continuity_changes(self):
        return self._continuity_changes

    def submitted_edits(self):
        return tuple({
            'edit_id': edit.edit_id,
            'kind': edit.kind,
            'target': edit.target,
            'fragment': edit.fragment,
            'expected_original_hash': edit.expected_original_hash,
            'reference_receipts': list(edit.reference_receipts),
            'assist_receipt_id': edit.assist_receipt_id,
        } for edit in self._edits)

    def _parse_edits(self, value):
        payload = self._json(value)
        if not isinstance(payload, list) or len(payload) > 100:
            raise forms.ValidationError(_('Report edit list is not valid.'))
        return tuple(self._edit(item) for item in payload)

    def _parse_continuity(self, value):
        payload = self._json(value)
        if not isinstance(payload, list) or len(payload) > 100:
            raise forms.ValidationError(_('Report request is invalid.'))
        if any(not isinstance(item, dict) for item in payload):
            raise forms.ValidationError(_('Report request is invalid.'))
        return tuple(payload)

    def _json(self, value):
        if len(value.encode('utf-8')) > SCHEMA2_POST_LIMIT:
            raise report_api.ReportError('REPORT_LIMIT')
        try:
            return json.loads(value, object_pairs_hook=reject_duplicate_json_keys)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise forms.ValidationError(_('Report request is invalid.')) from None

    def _edit(self, value):
        if not isinstance(value, dict):
            raise forms.ValidationError(_('Report edit list is not valid.'))
        expected = {
            'edit_id', 'kind', 'target', 'fragment', 'expected_original_hash',
            'reference_receipts', 'assist_receipt_id',
        }
        if set(value) != expected:
            raise forms.ValidationError(_('Report edit list is not valid.'))
        reference_receipts = value['reference_receipts']
        if not isinstance(reference_receipts, list):
            raise forms.ValidationError(_('Report edit list is not valid.'))
        return report_api.AuthoredEditRequest(
            str(value['edit_id']),
            value['kind'],
            value['target'],
            value['fragment'],
            value['expected_original_hash'],
            tuple(reference_receipts),
            value['assist_receipt_id'],
        )


def reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result
