from dataclasses import dataclass
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.utils.translation import gettext_lazy as _

from project_management.app.api import reports as report_api


TEMPLATE_CHOICES = (
    ('daily-standup', _('Daily standup')),
    ('weekly-timeline', _('Weekly timeline')),
)
TEMPLATE_VERSIONS = (('1', '1'), ('2', '2'))
PURPOSE_CHOICES = (
    ('standup', _('Standup')),
    ('historical_export', _('Historical export')),
)

@dataclass(frozen=True, slots=True)
class ReportTargetChoices:
    note_targets: tuple[tuple[str, str], ...]
    override_targets: tuple[tuple[str, str], ...]
    target_map: dict[str, dict]


def new_command_id():
    return str(uuid4())


def hash_text(value):
    if any(character not in '0123456789abcdef' for character in value):
        raise forms.ValidationError(_('Template request is invalid.'))
    return value


def uuid_text(value):
    field = forms.UUIDField()
    try:
        return str(field.clean(value))
    except forms.ValidationError:
        raise forms.ValidationError(_('Template request is invalid.')) from None


class ReportCreateForm(forms.Form):
    payload_version = forms.ChoiceField(required=False, choices=(('2', '2'),), widget=forms.HiddenInput)
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    capture_after = forms.CharField(required=False, max_length=1368, widget=forms.HiddenInput)
    capture_id = forms.ChoiceField(label=_('Source capture'))
    template_choice = forms.ChoiceField(label=_('Template'), required=False)
    template_origin = forms.ChoiceField(required=False, choices=(('builtin', 'builtin'), ('user', 'user')))
    template_id = forms.ChoiceField(label=_('Template'), choices=TEMPLATE_CHOICES, required=False)
    template_version = forms.ChoiceField(required=False, widget=forms.HiddenInput, choices=TEMPLATE_VERSIONS)
    template_revision = forms.IntegerField(required=False, min_value=1, max_value=1_000_000)
    template_revision_hash = forms.CharField(required=False, min_length=64, max_length=64)
    timezone = forms.CharField(label=_('Timezone'), max_length=64)
    baseline_publication_id = forms.ChoiceField(label=_('Baseline publication'), required=False)
    parent_publication_id = forms.ChoiceField(label=_('Parent publication'), required=False)
    purpose = forms.ChoiceField(label=_('Purpose'), choices=PURPOSE_CHOICES)

    def __init__(self, *args, capture_choices=(), publication_choices=(), require_capture_selection=False,
                 user_template_choices=(), **kwargs):
        super().__init__(*args, **kwargs)
        capture_values = tuple((item.capture_id, item.label) for item in capture_choices)
        if require_capture_selection:
            capture_values = (('', _('Select capture')), *capture_values)
        publication_values = (('', _('No baseline')), *((item.publication_id, item.label) for item in publication_choices))
        parent_values = (('', _('No parent publication')), *((item.publication_id, item.label) for item in publication_choices))
        builtin_choices = tuple((f'builtin|{value}|2|', label) for value, label in TEMPLATE_CHOICES)
        self.fields['capture_id'].choices = capture_values
        self.fields['template_choice'].choices = (*builtin_choices, *tuple(user_template_choices))
        self.fields['template_id'].choices = (*TEMPLATE_CHOICES, *((choice[0].split('|')[1], choice[1]) for choice in user_template_choices))
        self.fields['baseline_publication_id'].choices = publication_values
        self.fields['parent_publication_id'].choices = parent_values

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        self._apply_template_choice(cleaned)
        if not cleaned.get('template_origin'):
            cleaned['template_origin'] = 'builtin'
        if cleaned['template_origin'] == 'user':
            if not cleaned.get('template_id') or not cleaned.get('template_revision') or not cleaned.get('template_revision_hash'):
                raise forms.ValidationError(_('Template request is invalid.'))
            cleaned['template_id'] = uuid_text(cleaned['template_id'])
            cleaned['template_revision_hash'] = hash_text(cleaned['template_revision_hash'])
        elif not cleaned.get('template_id') or not cleaned.get('template_version'):
            raise forms.ValidationError(_('Template request is invalid.'))
        return cleaned

    def clean_timezone(self):
        value = self.cleaned_data['timezone']
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise forms.ValidationError(_('Timezone is not available.')) from None
        return value

    def selection(self):
        return report_api.ReportSelection(
            capture_id=self.cleaned_data['capture_id'],
            baseline_publication_id=self.cleaned_data.get('baseline_publication_id') or None,
            parent_publication_id=self.cleaned_data.get('parent_publication_id') or None,
            purpose=self.cleaned_data['purpose'],
            timezone=self.cleaned_data['timezone'],
        )

    def template(self):
        return report_api.TemplateSelection(
            self.cleaned_data['template_id'],
            self.cleaned_data['template_version'],
            {},
        )

    def authored_template(self):
        if self.cleaned_data.get('template_origin') == 'user':
            return report_api.UserTemplateSelection(
                self.cleaned_data['template_id'],
                self.cleaned_data['template_revision'],
                self.cleaned_data['template_revision_hash'],
            )
        return report_api.AuthoringTemplateSelection(
            'builtin',
            self.cleaned_data['template_id'],
            self.cleaned_data['template_version'],
            {},
        )

    def is_authored(self):
        return self.cleaned_data.get('payload_version') == '2'

    def _apply_template_choice(self, cleaned):
        choice = cleaned.get('template_choice')
        if not choice:
            return
        parts = choice.split('|')
        if len(parts) != 4 or parts[0] not in {'builtin', 'user'}:
            raise forms.ValidationError(_('Template request is invalid.'))
        cleaned['template_origin'] = parts[0]
        cleaned['template_id'] = parts[1]
        if parts[0] == 'builtin':
            cleaned['template_version'] = parts[2]
            return
        try:
            cleaned['template_revision'] = int(parts[2])
        except ValueError:
            raise forms.ValidationError(_('Template request is invalid.')) from None
        cleaned['template_revision_hash'] = parts[3]


class ReportSaveForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=1, max_value=1_000_000, widget=forms.HiddenInput)
    template_id = forms.ChoiceField(label=_('Template'), choices=TEMPLATE_CHOICES)
    template_version = forms.ChoiceField(widget=forms.HiddenInput, choices=TEMPLATE_VERSIONS)
    note_edit_id = forms.UUIDField(required=False, widget=forms.HiddenInput)
    note_target = forms.ChoiceField(label=_('Note target'), required=False)
    note_text = forms.CharField(label=_('Meeting note'), required=False, max_length=16_384,
                                widget=forms.Textarea(attrs={'rows': 4}))
    override_edit_id = forms.UUIDField(required=False, widget=forms.HiddenInput)
    override_target = forms.ChoiceField(label=_('Narrative field'), required=False)
    override_text = forms.CharField(label=_('Narrative override'), required=False, max_length=16_384,
                                    widget=forms.Textarea(attrs={'rows': 4}))
    edit_id = forms.CharField(required=False)
    edit_kind = forms.CharField(required=False)
    edit_target = forms.CharField(required=False)
    edit_text = forms.CharField(required=False, max_length=16_384)
    edit_operation = forms.CharField(required=False)

    def __init__(self, *args, snapshot, target_choices: ReportTargetChoices, current_edits=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshot = snapshot
        self.target_choices = target_choices
        self.current_edits = tuple(current_edits)
        self._edit_rows = ()
        self.fields['note_target'].choices = (('', _('Select target')), *target_choices.note_targets)
        self.fields['override_target'].choices = (('', _('Select field')), *target_choices.override_targets)

    def clean(self):
        cleaned = super().clean()
        self._validate_edit_group(cleaned, 'note')
        self._validate_edit_group(cleaned, 'override')
        self._edit_rows = tuple(self._clean_edit_rows())
        return cleaned

    def edits(self):
        result = list(self.current_edits)
        positions = {edit.edit_id: index for index, edit in enumerate(result)}
        for row in self._edit_rows:
            existing = positions.get(row['edit_id'])
            if row['operation'] == 'remove':
                if existing is not None:
                    result.pop(existing)
                    positions = {edit.edit_id: index for index, edit in enumerate(result)}
                continue
            edit = self._edit_from_row(row)
            if existing is None:
                positions[edit.edit_id] = len(result)
                result.append(edit)
            else:
                result[existing] = edit
        if self.cleaned_data.get('note_text'):
            result = self._upsert_legacy(result, str(self.cleaned_data['note_edit_id']), 'note',
                                         self.cleaned_data['note_target'], self.cleaned_data['note_text'])
        if self.cleaned_data.get('override_text'):
            result = self._upsert_legacy(result, str(self.cleaned_data['override_edit_id']), 'narrative_override',
                                         self.cleaned_data['override_target'], self.cleaned_data['override_text'])
        return tuple(result)

    def template(self):
        return report_api.TemplateSelection(
            self.cleaned_data['template_id'],
            self.cleaned_data['template_version'],
            {},
        )

    def _validate_edit_group(self, cleaned, prefix):
        text = cleaned.get(f'{prefix}_text')
        edit_id = cleaned.get(f'{prefix}_edit_id')
        target = cleaned.get(f'{prefix}_target')
        if bool(text) != bool(edit_id and target):
            raise forms.ValidationError(_('Choose a target and enter text before saving.'))

    def _clean_edit_rows(self):
        if not hasattr(self.data, 'getlist'):
            return ()
        keys = ('edit_id', 'edit_kind', 'edit_target', 'edit_text', 'edit_operation')
        values = {key: self.data.getlist(key) for key in keys}
        lengths = {len(item) for item in values.values()}
        if lengths == {0}:
            return ()
        if len(lengths) != 1 or next(iter(lengths)) > 64:
            raise forms.ValidationError(_('Report edit list is not valid.'))
        seen_ids = set()
        rows = []
        current_ids = {edit.edit_id for edit in self.current_edits}
        for index in range(next(iter(lengths))):
            row = {key: values[key][index] for key in keys}
            if row['edit_operation'] == 'add' and not row['edit_text'] and not row['edit_target']:
                continue
            row['edit_id'] = self._valid_uuid(row['edit_id'])
            if row['edit_id'] in seen_ids:
                raise forms.ValidationError(_('Report edit list is not valid.'))
            seen_ids.add(row['edit_id'])
            if row['edit_kind'] not in {'note', 'narrative_override'}:
                raise forms.ValidationError(_('Report edit list is not valid.'))
            if row['edit_target'] not in self.target_choices.target_map:
                raise forms.ValidationError(_('Report edit list is not valid.'))
            if row['edit_operation'] not in {'add', 'keep', 'remove'}:
                raise forms.ValidationError(_('Report edit list is not valid.'))
            if row['edit_operation'] == 'add' and row['edit_id'] in current_ids:
                raise forms.ValidationError(_('Report edit list is not valid.'))
            if row['edit_operation'] in {'keep', 'remove'} and row['edit_id'] not in current_ids:
                raise forms.ValidationError(_('Report edit list is not valid.'))
            if row['edit_operation'] != 'remove' and not row['edit_text']:
                raise forms.ValidationError(_('Report edit list is not valid.'))
            rows.append({
                'edit_id': row['edit_id'],
                'kind': row['edit_kind'],
                'target_key': row['edit_target'],
                'text': row['edit_text'],
                'operation': row['edit_operation'],
            })
        return rows

    def _edit_from_row(self, row):
        target = self.target_choices.target_map[row['target_key']]
        original = report_api.original_target_text(self.snapshot, target)
        return report_api.ReportEdit(
            row['edit_id'],
            row['kind'],
            target,
            row['text'],
            None if row['kind'] == 'note' else report_api.text_hash(original or ''),
        )

    def _upsert_legacy(self, edits, edit_id, kind, target_key, text):
        target = self.target_choices.target_map[target_key]
        original = report_api.original_target_text(self.snapshot, target)
        edit = report_api.ReportEdit(
            edit_id,
            kind,
            target,
            text,
            None if kind == 'note' else report_api.text_hash(original or ''),
        )
        for index, current in enumerate(edits):
            if current.edit_id == edit.edit_id:
                edits[index] = edit
                return edits
        return [*edits, edit]

    def _valid_uuid(self, value):
        field = forms.UUIDField()
        try:
            return str(field.clean(value))
        except forms.ValidationError:
            raise forms.ValidationError(_('Report edit list is not valid.')) from None


class ReportFinalizeForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(min_value=1, max_value=1_000_000, widget=forms.HiddenInput)
    confirm = forms.BooleanField(label=_('Finalize this exact saved revision'), required=True)


class ReportResumeForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)


class ReportRevisionCreateForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)
    template_id = forms.ChoiceField(label=_('Template'), choices=TEMPLATE_CHOICES)
    template_version = forms.ChoiceField(widget=forms.HiddenInput, choices=TEMPLATE_VERSIONS)

    def template(self):
        return report_api.TemplateSelection(
            self.cleaned_data['template_id'],
            self.cleaned_data['template_version'],
            {},
        )


class ReportLinkedRevisionCreateForm(forms.Form):
    command_id = forms.UUIDField(widget=forms.HiddenInput)


class ReportRenderQueryForm(forms.Form):
    revision = forms.IntegerField(min_value=1, max_value=1_000_000)


class ReportDownloadQueryForm(forms.Form):
    format = forms.ChoiceField(choices=(('html', 'html'), ('plain_text', 'plain_text')))


class ReportStageQueryForm(forms.Form):
    capture_after = forms.CharField(required=False, max_length=1368)
    draft_offset = forms.IntegerField(required=False, min_value=0, max_value=1000)
    publication_offset = forms.IntegerField(required=False, min_value=0, max_value=1000)

    def clean_draft_offset(self):
        return self.cleaned_data.get('draft_offset') or 0

    def clean_publication_offset(self):
        return self.cleaned_data.get('publication_offset') or 0


def target_choices_for_snapshot(snapshot) -> ReportTargetChoices:
    note_targets = [('report', _('Whole report'))]
    override_targets = []
    target_map = {'report': {'scope': 'report'}}
    for message in snapshot.key_messages:
        value = f'message:{message.message_id}:text'
        target_map[value] = {'scope': 'message', 'message_id': message.message_id, 'field': 'text'}
        override_targets.append((value, _('Key message: %(message)s') % {'message': message.message_id}))
    for row in snapshot.rows:
        key_hash = report_api.source_key_hash(row.source_key)
        issue_label = row.identity.display_key
        note_value = f'issue:{key_hash}'
        target_map[note_value] = {'scope': 'issue', 'source_key_hash': key_hash}
        note_targets.append((note_value, _('Issue %(key)s') % {'key': issue_label}))
        for field in ('what', 'current_position', 'verification'):
            value = f'issue:{key_hash}:{field}'
            target_map[value] = {'scope': 'issue', 'source_key_hash': key_hash, 'field': field}
            override_targets.append((value, _('%(key)s %(field)s') % {'key': issue_label, 'field': field}))
        if row.summary_ref is None:
            continue
        for index, action in enumerate(row.next_actions):
            action_label = action.get('action') or _('Action %(number)s') % {'number': index + 1}
            note_value = f'action:{key_hash}:{row.summary_ref.summary_id}:{index}'
            target_map[note_value] = {
                'scope': 'action',
                'source_key_hash': key_hash,
                'summary_id': row.summary_ref.summary_id,
                'action_index': index,
            }
            note_targets.append((note_value, _('%(key)s action: %(action)s') % {'key': issue_label, 'action': action_label}))
            for field in ('action', 'owner_display'):
                value = f'action:{key_hash}:{row.summary_ref.summary_id}:{index}:{field}'
                target_map[value] = dict(target_map[note_value], field=field)
                override_targets.append((value, _('%(key)s action %(field)s') % {'key': issue_label, 'field': field}))
    return ReportTargetChoices(tuple(note_targets), tuple(override_targets), target_map)
