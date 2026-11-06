from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_draft_values import bytes_hash, validate_hash_text
from project_management.storage.admission import GrowthEstimate, admit
from project_management.storage.paths import read_bytes
from project_management.storage.paths import write_bytes


def intent_with_preparation_binding(intent, binding_bytes, preparation_binding):
    if preparation_binding is None:
        return intent
    return {
        **intent,
        'schema_version': 2,
        'preparation_binding_kind': binding_kind(preparation_binding.get('kind')),
        'preparation_binding_hash': bytes_hash(binding_bytes),
    }


def preparation_binding(root, intent):
    try:
        data = read_bytes(root, 'preparation-binding.json')
    except ArchiveError:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None
    if bytes_hash(data) != intent['preparation_binding_hash']:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    value = decode_json(data)
    if not isinstance(value, dict) or value.get('kind') != intent['preparation_binding_kind']:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def binding_kind(value):
    if value not in {'internal_prepared_context', 'daily_preparation_active_slot'}:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def binding_fields(value):
    return {
        'preparation_binding_kind': binding_kind(value['preparation_binding_kind']),
        'preparation_binding_hash': validate_hash_text(value['preparation_binding_hash']),
    }


def write_create(store, draft_id, command_id, *, request_hash, intent, snapshot_bytes,
                 revision_payload, revision_hash, command_payload, preparation_binding):
    root = store.root(draft_id)
    binding_bytes = None if preparation_binding is None else canonical_bytes(preparation_binding)
    stored_intent = intent_with_preparation_binding(intent, binding_bytes, preparation_binding)
    size = (
        len(snapshot_bytes) + len(canonical_bytes(stored_intent))
        + len(canonical_bytes(revision_payload)) + len(canonical_bytes(command_payload))
        + (0 if binding_bytes is None else len(binding_bytes)) + 4096
    )
    admit(store.archive_root, store.repository.stage_root, root, store.archive_limits, GrowthEstimate(size, 6))
    write_bytes(root, 'snapshot.json', snapshot_bytes, immutable=True, conflict_code='ARCHIVE_CAPTURE_CONFLICT')
    if binding_bytes is not None:
        write_bytes(root, 'preparation-binding.json', binding_bytes, immutable=True,
                    conflict_code='ARCHIVE_CAPTURE_CONFLICT')
    write_bytes(root, 'intent.json', canonical_bytes(stored_intent), immutable=True,
                conflict_code='ARCHIVE_CAPTURE_CONFLICT')
    store.write_revision(draft_id, revision_payload, revision_hash)
    store.write_command(draft_id, command_id, command_payload)
    store.publish_current(draft_id, revision_payload['revision'], revision_hash, expected_revision=None)


class ReportDraftCreateMixin:
    def write_create(self, draft_id: str, command_id: str, *, request_hash: str, intent, snapshot_bytes: bytes,
                     revision_payload, revision_hash: str, command_payload, preparation_binding=None) -> None:
        write_create(
            self, draft_id, command_id, request_hash=request_hash, intent=intent,
            snapshot_bytes=snapshot_bytes, revision_payload=revision_payload,
            revision_hash=revision_hash, command_payload=command_payload,
            preparation_binding=preparation_binding,
        )

    def preparation_binding(self, draft_id: str):
        root = self.root(draft_id)
        intent = self._intent(root, draft_id)
        if intent['schema_version'] == 1:
            return None
        return preparation_binding(root, intent)
