from pathlib import Path
from uuid import UUID, uuid5

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError, ArchiveLimits
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_hash_text
from project_management.app.domain.report_preparation_validation import (
    request_payload_from_intent,
    validate_intent_nested_payload,
)
from project_management.app.domain.report_preparation_reprepare_validation import validate_reprepare_intent
from project_management.app.domain.run_values import capture_id as run_capture_id
from project_management.app.domain.run_values import draft_command_id as run_draft_command_id
from project_management.app.domain.run_values import operation_id as run_operation_id
from project_management.storage.admission import GrowthEstimate, admit
from project_management.storage.paths import read_bytes, validate_uuid, write_bytes
from project_management.storage.report_preparation_replacements import (
    has_replacement_descendant,
    slot_allows_replay,
    slot_supersedes_intent,
    verify_replacement_adoption,
)


class ReportPreparationStore:
    def __init__(self, repository, archive_root: Path, archive_limits: ArchiveLimits):
        self.repository = repository
        self.archive_root = archive_root
        self.archive_limits = archive_limits
        self.runtime = repository.runtime

    def reserve(self, command_id, request_hash, slot_id, intent):
        existing = self.existing(command_id, request_hash, slot_id)
        if existing is not None:
            return existing
        intent = self._intent(intent)
        adopted = self._read_intent(intent['preparation_id'])
        if adopted is not None:
            return self._repair_from_intent(command_id, request_hash, slot_id, adopted)
        self.write_intent(intent)
        self.write_slot(slot_id, intent)
        self.write_command(command_id, request_hash, intent['preparation_id'], 'created')
        return intent, 'created'

    def reserve_replacement(self, command_id, request_hash, previous, replacement):
        command_id = validate_uuid(command_id)
        request_hash = validate_hash_text(request_hash)
        previous = self._intent(previous)
        replacement = self._intent(replacement)
        existing_command = self.command(command_id)
        if existing_command is not None:
            if existing_command['request_hash'] != request_hash:
                raise ReportError('REPORT_PREPARATION_COMMAND_CONFLICT')
            intent = self.intent(existing_command['preparation_id'])
            if intent['preparation_id'] != replacement['preparation_id']:
                raise ReportError('REPORT_ARTIFACT_INVALID')
            slot = self.slot(previous['slot_id'])
            self._verify_slot_binding(slot, intent)
            return intent, existing_command['disposition']
        adopted = self._read_intent(replacement['preparation_id'])
        if adopted is not None:
            verify_replacement_adoption(self, command_id, request_hash, previous, adopted, replacement)
            replacement = adopted
        else:
            self.write_intent(replacement)
        slot = self.slot(previous['slot_id'])
        if slot_supersedes_intent(self, slot, previous):
            if slot['preparation_id'] != replacement['preparation_id'] or slot['intent_hash'] != self._hash(replacement):
                raise ReportError('REPORT_REVISION_CONFLICT')
        else:
            self.replace_slot(previous, replacement)
        self.write_command(command_id, request_hash, replacement['preparation_id'], 'created')
        return replacement, 'created'

    def existing(self, command_id, request_hash, slot_id):
        command_id = validate_uuid(command_id)
        request_hash = validate_hash_text(request_hash)
        slot_id = validate_uuid(slot_id)
        existing_command = self.command(command_id)
        if existing_command is not None:
            if existing_command['request_hash'] != request_hash:
                raise ReportError('REPORT_PREPARATION_COMMAND_CONFLICT')
            intent = self.intent(existing_command['preparation_id'])
            if intent['slot_id'] != slot_id:
                raise ReportError('REPORT_ARTIFACT_INVALID')
            self._verify_command_binding(existing_command, intent)
            slot = self.slot(slot_id)
            if slot is None:
                if has_replacement_descendant(self, intent):
                    raise ReportError('REPORT_ARTIFACT_INVALID')
                self.write_slot(slot_id, intent)
            elif not slot_allows_replay(self, slot, intent):
                raise ReportError('REPORT_ARTIFACT_INVALID')
            return intent, existing_command['disposition']
        existing_slot = self.slot(slot_id)
        if existing_slot is not None:
            intent = self.intent(existing_slot['preparation_id'])
            self._verify_slot_binding(existing_slot, intent)
            self.write_command(command_id, request_hash, intent['preparation_id'], 'existing')
            return intent, 'existing'
        return None

    def command(self, command_id):
        command_id = validate_uuid(command_id)
        value = self._read(f'report-preparation-commands/{command_id}.json')
        return None if value is None else self._command(value, command_id)

    def slot(self, slot_id):
        slot_id = validate_uuid(slot_id)
        value = self._read(f'report-preparation-slots/{slot_id}.json')
        return None if value is None else self._slot(value, slot_id)

    def intent(self, preparation_id):
        value = self._read_intent(preparation_id)
        if value is None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return value

    def find_intent(self, preparation_id):
        return self._read_intent(preparation_id)

    def active_intent(self, slot_id):
        slot = self.slot(slot_id)
        if slot is None:
            return None
        intent = self.intent(slot['preparation_id'])
        self._verify_slot_binding(slot, intent)
        return intent

    def write_command(self, command_id, request_hash, preparation_id, disposition):
        payload = {
            'schema_version': 1,
            'command_id': validate_uuid(command_id),
            'request_hash': validate_hash_text(request_hash),
            'preparation_id': validate_uuid(preparation_id),
            'disposition': self._disposition(disposition),
        }
        self._write(f"report-preparation-commands/{payload['command_id']}.json", payload, payload)

    def write_slot(self, slot_id, intent):
        payload = {
            'schema_version': 1,
            'slot_id': validate_uuid(slot_id),
            'slot_key': intent['slot_key'],
            'preparation_id': intent['preparation_id'],
            'intent_hash': self._hash(intent),
        }
        self._write(f"report-preparation-slots/{payload['slot_id']}.json", payload, payload)

    def replace_slot(self, previous, replacement):
        previous = self._intent(previous)
        replacement = self._intent(replacement)
        slot = self.slot(previous['slot_id'])
        self._verify_slot_binding(slot, previous)
        payload = {
            'schema_version': 2,
            'slot_id': previous['slot_id'],
            'slot_key': previous['slot_key'],
            'preparation_id': replacement['preparation_id'],
            'intent_hash': self._hash(replacement),
            'superseded_preparation_id': previous['preparation_id'],
            'superseded_intent_hash': self._hash(previous),
        }
        self._write_mutable(f"report-preparation-slots/{payload['slot_id']}.json", payload)

    def write_intent(self, intent):
        intent = self._intent(intent)
        self._write(f"report-preparations/{intent['preparation_id']}/intent.json", intent, intent)

    def _read_intent(self, preparation_id):
        value = self._read(f'report-preparations/{validate_uuid(preparation_id)}/intent.json')
        return None if value is None else self._intent(value)

    def _read(self, path):
        try:
            value = decode_json(read_bytes(self.runtime, path))
            if not isinstance(value, dict) or type(value.get('schema_version')) is not int:
                raise ReportError('REPORT_ARTIFACT_INVALID')
            return value
        except ArchiveError as error:
            if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                return None
            raise ReportError('REPORT_ARTIFACT_INVALID') from None

    def _write(self, path, payload, admitted):
        data = canonical_bytes(payload)
        root = self.runtime / path.split('/')[0]
        admit(self.archive_root, self.repository.stage_root, root, self.archive_limits, GrowthEstimate(len(data) + 8192, 2))
        try:
            write_bytes(self.runtime, path, data, immutable=True, conflict_code='ARCHIVE_CAPTURE_CONFLICT')
        except ArchiveError as error:
            if error.code != 'ARCHIVE_CAPTURE_CONFLICT' or self._read(path) != admitted:
                raise ReportError('REPORT_ARTIFACT_INVALID') from None

    def _write_mutable(self, path, payload):
        data = canonical_bytes(payload)
        root = self.runtime / path.split('/')[0]
        admit(self.archive_root, self.repository.stage_root, root, self.archive_limits, GrowthEstimate(len(data) + 8192, 2))
        try:
            write_bytes(self.runtime, path, data, immutable=False)
        except ArchiveError:
            raise ReportError('REPORT_ARTIFACT_INVALID') from None

    def _repair_from_intent(self, command_id, request_hash, slot_id, intent):
        if intent['slot_id'] != slot_id:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if intent['command_id'] == command_id and intent['request_hash'] != request_hash:
            raise ReportError('REPORT_PREPARATION_COMMAND_CONFLICT')
        disposition = 'created' if intent['command_id'] == command_id else 'existing'
        self.write_slot(slot_id, intent)
        self.write_command(command_id, request_hash, intent['preparation_id'], disposition)
        return intent, disposition

    def _command(self, value, command_id):
        expected = {'schema_version', 'command_id', 'request_hash', 'preparation_id', 'disposition'}
        if not isinstance(value, dict) or set(value) != expected or value['schema_version'] != 1:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if validate_uuid(value['command_id']) != command_id:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return {
            'schema_version': 1,
            'command_id': command_id,
            'request_hash': validate_hash_text(value['request_hash']),
            'preparation_id': validate_uuid(value['preparation_id']),
            'disposition': self._disposition(value['disposition']),
        }

    def _slot(self, value, slot_id):
        if isinstance(value, dict) and value.get('schema_version') == 2:
            return self._slot_v2(value, slot_id)
        expected = {'schema_version', 'slot_id', 'slot_key', 'preparation_id', 'intent_hash'}
        if not isinstance(value, dict) or set(value) != expected or value['schema_version'] != 1:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if validate_uuid(value['slot_id']) != slot_id:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return {
            'schema_version': 1,
            'slot_id': slot_id,
            'slot_key': value['slot_key'],
            'preparation_id': validate_uuid(value['preparation_id']),
            'intent_hash': validate_hash_text(value['intent_hash']),
        }

    def _slot_v2(self, value, slot_id):
        expected = {
            'schema_version', 'slot_id', 'slot_key', 'preparation_id', 'intent_hash',
            'superseded_preparation_id', 'superseded_intent_hash',
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if validate_uuid(value['slot_id']) != slot_id:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return {
            'schema_version': 2,
            'slot_id': slot_id,
            'slot_key': value['slot_key'],
            'preparation_id': validate_uuid(value['preparation_id']),
            'intent_hash': validate_hash_text(value['intent_hash']),
            'superseded_preparation_id': validate_uuid(value['superseded_preparation_id']),
            'superseded_intent_hash': validate_hash_text(value['superseded_intent_hash']),
        }

    def _intent(self, value):
        if value.get('schema_version') == 3:
            return validate_reprepare_intent(value, self.repository, self._hash)
        if value.get('schema_version') == 2:
            return self._intent_v2(value)
        expected = {
            'schema_version', 'preparation_id', 'slot_id', 'slot_key', 'project_id', 'stage_id',
            'owner_subject', 'command_id', 'request_hash', 'series_id', 'series_policy_hash',
            'meeting_date', 'meeting_key', 'period_key', 'expected_baseline_ref',
            'timezone', 'template_selection', 'source_mode', 'capture_id', 'analysis_mode',
            'acknowledge_gap_draft_ids', 'effective_selection', 'effective_selection_hash',
            'operation_command_id', 'derived_operation_id', 'operation_id',
            'draft_command_id', 'draft_id', 'template_use_command_id', 'created_at',
        }
        if not isinstance(value, dict) or set(value.keys()) != expected or value['schema_version'] != 1:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        for key in (
            'preparation_id', 'slot_id', 'project_id', 'stage_id', 'command_id',
            'series_id', 'operation_command_id', 'derived_operation_id',
            'draft_command_id', 'draft_id', 'template_use_command_id',
        ):
            validate_uuid(value[key])
        validate_hash_text(value['request_hash'])
        validate_hash_text(value['series_policy_hash'])
        validate_hash_text(value['effective_selection_hash'])
        validate_intent_nested_payload(value)
        self._verify_intent_binding(value)
        if value['operation_id'] is not None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if value['source_mode'] != 'saved_capture' or value['analysis_mode'] != 'manual_only':
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return value

    def _intent_v2(self, value):
        expected = {
            'schema_version', 'preparation_id', 'slot_id', 'slot_key', 'project_id', 'stage_id',
            'owner_subject', 'command_id', 'request_hash', 'original_request',
            'preparation_intent_hash', 'run_request_hash', 'series_id', 'series_policy_hash',
            'meeting_date', 'meeting_key', 'period_key', 'expected_baseline_ref',
            'timezone', 'template_selection', 'source_mode', 'capture_id', 'analysis_mode',
            'acknowledge_gap_draft_ids', 'effective_selection', 'effective_selection_hash',
            'operation_command_id', 'derived_operation_id', 'operation_id',
            'draft_command_id', 'draft_id', 'template_use_command_id', 'stage_hash', 'created_at',
        }
        if not isinstance(value, dict) or set(value.keys()) != expected:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        for key in (
            'preparation_id', 'slot_id', 'project_id', 'stage_id', 'command_id',
            'series_id', 'operation_command_id', 'derived_operation_id', 'operation_id',
            'draft_command_id', 'draft_id', 'template_use_command_id', 'capture_id',
        ):
            validate_uuid(value[key])
        for key in (
            'request_hash', 'series_policy_hash', 'effective_selection_hash',
            'preparation_intent_hash', 'run_request_hash', 'stage_hash',
        ):
            validate_hash_text(value[key])
        if value['source_mode'] != 'refresh' or value['analysis_mode'] not in {'manual_only', 'changed_items'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        validate_intent_nested_payload(value)
        self._verify_intent_binding(value)
        if value['preparation_intent_hash'] != self._hash(self._intent_hash_payload(value)):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return value

    def _verify_intent_binding(self, value):
        slot_id = str(uuid5(UUID(value['series_id']), f"daily:{value['meeting_date']}"))
        operation_id = run_operation_id(value['stage_id'], value['operation_command_id'])
        draft_command_id = run_draft_command_id(operation_id)
        draft_id = str(uuid5(UUID(value['stage_id']), f'draft:{draft_command_id}'))
        if (value['slot_id'] != slot_id
                or value['preparation_id'] != str(uuid5(UUID(value['stage_id']), f"preparation:{slot_id}"))
                or value['derived_operation_id'] != operation_id
                or value['draft_command_id'] != draft_command_id
                or value['draft_id'] != draft_id):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if value['schema_version'] == 2:
            effective_capture_id = run_capture_id(operation_id)
            if (value['operation_id'] != operation_id
                    or value['capture_id'] != effective_capture_id
                    or value['effective_selection']['capture_id'] != effective_capture_id
                    or value['original_request']['capture_id'] is not None):
                raise ReportError('REPORT_ARTIFACT_INVALID')
        if value['slot_key'] != {'series_id': value['series_id'], 'local_date': value['meeting_date']}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if value['project_id'] != self.repository.project.id or value['stage_id'] != self.repository.stage.id:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if value['owner_subject'] != self.repository.owner_subject:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if value['request_hash'] != self._hash(request_payload_from_intent(value)):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if value['effective_selection_hash'] != self._hash(value['effective_selection']):
            raise ReportError('REPORT_ARTIFACT_INVALID')

    def _intent_hash_payload(self, value):
        return {key: item for key, item in value.items() if key not in {'preparation_intent_hash', 'run_request_hash'}}

    def _verify_command_binding(self, command, intent):
        if command['preparation_id'] != intent['preparation_id']:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if command['disposition'] == 'created' and command['command_id'] != intent['command_id']:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if command['disposition'] == 'created' and command['request_hash'] != intent['request_hash']:
            raise ReportError('REPORT_ARTIFACT_INVALID')

    def _verify_slot_binding(self, slot, intent):
        if slot is None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if (slot['preparation_id'] != intent['preparation_id']
                or slot['slot_id'] != intent['slot_id']
                or slot['slot_key'] != intent['slot_key']
                or slot['intent_hash'] != self._hash(intent)):
            raise ReportError('REPORT_ARTIFACT_INVALID')

    def _hash(self, value):
        try:
            return sha256_bytes(canonical_bytes(value))
        except ArchiveError:
            raise ReportError('REPORT_ARTIFACT_INVALID') from None

    def _disposition(self, value):
        if value not in {'created', 'existing'}:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return value
