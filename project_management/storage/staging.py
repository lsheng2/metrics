from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from project_management.app.domain.capture_values import (
    canonical_bytes,
    content_hash,
    decode_json,
    intent_from_mapping,
    raw_page_ref_from_mapping,
    snapshot_from_mapping,
    stored_snapshot_from_mapping,
    work_item_from_mapping,
)
from project_management.app.domain.capture_validation import item_key
from project_management.app.domain.captures import (
    ArchiveError,
    CaptureIntent,
    RawPageRef,
    SnapshotInput,
    StoredSnapshotRef,
)
from project_management.storage.paths import read_bytes, validate_hash, validate_uuid, write_bytes


@dataclass(frozen=True, slots=True)
class PageRecord:
    reference: RawPageRef
    item_key: str | None
    page_key: str


class PendingCaptureStore:
    def __init__(self, runtime_root: Path, capture_id: str):
        self.runtime_root = runtime_root
        self.root = runtime_root / 'pending' / validate_uuid(capture_id)

    def write_intent(self, intent: CaptureIntent, intent_hash: str, limits) -> str:
        payload = {'intent_hash': intent_hash, 'intent': intent, 'prepared_at': datetime.now(UTC).isoformat(),
                   'limits': limits}
        self._write('intent.json', payload, immutable=True)
        return intent_hash

    def read_intent(self) -> tuple[str, CaptureIntent]:
        payload = decode_json(read_bytes(self.root, 'intent.json'))
        intent = intent_from_mapping(payload['intent'])
        if content_hash(intent) != payload['intent_hash']:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return str(payload['intent_hash']), intent

    def write_page_intent(self, page_id: str, payload) -> None:
        self._write(f'pages/{page_id}/intent.json', payload, immutable=True)

    def write_page_receipt(self, page_id: str, reference: RawPageRef, item_key: str | None, page_key: str) -> None:
        self._write(f'pages/{page_id}/receipt.json', {'reference': reference, 'item_key': item_key, 'page_key': page_key}, immutable=True)

    def read_page(self, page_id: str) -> PageRecord:
        validate_hash(page_id)
        payload = decode_json(read_bytes(self.root, f'pages/{page_id}/receipt.json'))
        intent = decode_json(read_bytes(self.root, f'pages/{page_id}/intent.json'))
        reference = raw_page_ref_from_mapping(payload['reference'])
        if (reference.page_id != page_id or reference.sha256 != intent['sha256']
                or reference.size_bytes != intent['size_bytes']
                or payload.get('item_key') != (content_hash(item_key(work_item_from_mapping(intent['item']))) if intent['item'] else None)):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return PageRecord(reference, payload.get('item_key'), str(payload['page_key']))

    def pages(self) -> tuple[RawPageRef, ...]:
        pages_root = self.root / 'pages'
        if not pages_root.exists():
            return ()
        records = []
        for receipt in sorted(pages_root.glob('*/receipt.json')):
            relative = receipt.relative_to(self.root).as_posix()
            records.append(self.read_page(receipt.parent.name).reference)
        return tuple(records)

    def write_snapshot(self, source_hash: str, snapshot: SnapshotInput, reference: StoredSnapshotRef) -> None:
        for old, old_ref in self.snapshots():
            if (old.identity.provider_id, old.identity.endpoint_id, old.identity.stable_id) == (
                    snapshot.identity.provider_id, snapshot.identity.endpoint_id, snapshot.identity.stable_id):
                if canonical_bytes(old) != canonical_bytes(snapshot) or old_ref != reference:
                    raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
                return
        self._write(f'snapshots/{source_hash}.json', {'snapshot': snapshot, 'reference': reference}, immutable=True)

    def snapshots(self) -> tuple[tuple[SnapshotInput, StoredSnapshotRef], ...]:
        snapshots_root = self.root / 'snapshots'
        if not snapshots_root.exists():
            return ()
        records = []
        for path in sorted(snapshots_root.glob('*.json')):
            payload = decode_json(read_bytes(self.root, path.relative_to(self.root).as_posix()))
            records.append((snapshot_from_mapping(payload['snapshot']), stored_snapshot_from_mapping(payload['reference'])))
        return tuple(records)

    def write_receipt(self, payload) -> None:
        self._write('receipt.json', payload)

    def finalize_manifest(self, value):
        path = self.root / 'finalize-manifest.json'
        if path.exists():
            return decode_json(read_bytes(self.root, 'finalize-manifest.json'))
        return decode_json(canonical_bytes(value))

    def freeze_manifest(self, value):
        self._write('finalize-manifest.json', value, immutable=True)

    def prepared_at(self):
        return decode_json(read_bytes(self.root, 'intent.json'))['prepared_at']

    def page_intents(self):
        return tuple(decode_json(read_bytes(self.root, path.relative_to(self.root).as_posix()))
                     for path in sorted((self.root / 'pages').glob('*/intent.json')))

    def recover_pages(self, objects):
        for intent in self.page_intents():
            page_id = validate_hash(intent['page_id'])
            if (self.root / 'pages' / page_id / 'receipt.json').exists():
                objects.read(self.read_page(page_id).reference)
                continue
            reference = RawPageRef(page_id, intent['sha256'], intent['size_bytes'],
                                   intent['content_type'], intent['request_fingerprint'])
            try:
                objects.read(reference)
            except ArchiveError as error:
                if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                    continue
                raise
            self.write_page_receipt(page_id, reference, content_hash(item_key(work_item_from_mapping(intent['item']))) if intent['item'] else None,
                                    intent['page_key'])

    def _write(self, relative: str, payload, *, immutable: bool = False) -> None:
        write_bytes(self.root, relative, canonical_bytes(payload), immutable=immutable)


def active_capture_path(runtime_root: Path) -> str:
    return 'active-capture.json'


def active_payload(intent_hash: str, capture_id: str):
    return {'capture_id': capture_id, 'intent_hash': intent_hash}


def hash_active(intent_hash: str, capture_id: str) -> str:
    return content_hash(active_payload(intent_hash, capture_id))
