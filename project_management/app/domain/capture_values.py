from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from .capture_validation import validate_snapshot, validate_intent

from .captures import (
    ArchiveError,
    ArchiveLimits,
    CaptureCoverage,
    CaptureIntent,
    CaptureManifest,
    CaptureSourceIdentity,
    MembershipInput,
    PartCoverage,
    RawPageRef,
    SnapshotInput,
    StoredSnapshotRef,
    WorkItemIdentity,
)


def json_value(value):
    if value is None or type(value) in (str, bool, int, float):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, datetime):
        return utc_datetime(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def canonical_bytes(value) -> bytes:
    try:
        return json.dumps(
            json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False,
        ).encode('utf-8')
    except (TypeError, ValueError, RecursionError):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None


def content_hash(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def decode_json(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
            result[key] = value
        return result

    def constant(_):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')

    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (ArchiveError, UnicodeError, ValueError, RecursionError):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None


def decode_snapshot(payload: bytes) -> SnapshotInput:
    return snapshot_from_mapping(_mapping(decode_json(payload)))


def utc_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value.astimezone(UTC)


def limits_hash(limits: ArchiveLimits) -> str:
    return content_hash(limits)


def manifest_from_bytes(data: bytes) -> CaptureManifest:
    return manifest_from_mapping(_mapping(decode_json(data)))


def manifest_from_mapping(value: Mapping) -> CaptureManifest:
    return CaptureManifest(
        schema_version=_literal(value.get('schema_version'), 1),
        intent=intent_from_mapping(_mapping(value.get('intent'))),
        membership=membership_from_mapping(_mapping(value.get('membership'))),
        snapshots=tuple(stored_snapshot_from_mapping(_mapping(item)) for item in _list(value.get('snapshots'))),
        pages=tuple(raw_page_ref_from_mapping(_mapping(item)) for item in _list(value.get('pages'))),
        complete=_bool(value.get('complete')),
        failure_code=_optional_str(value.get('failure_code')),
        prepared_at=_str(value.get('prepared_at')),
        finalized_at=_str(value.get('finalized_at')),
    )


def intent_from_mapping(value: Mapping) -> CaptureIntent:
    intent = CaptureIntent(
        project_id=_str(value.get('project_id')),
        stage_id=_str(value.get('stage_id')),
        capture_id=_str(value.get('capture_id')),
        request_id=_str(value.get('request_id')),
        source=source_from_mapping(_mapping(value.get('source'))),
        original_input_hash=_str(value.get('original_input_hash')),
        required_parts=tuple(_str(item) for item in _list(value.get('required_parts'))),
        deadline_at=_datetime(value.get('deadline_at')),
    )
    validate_intent(intent)
    return intent


def source_from_mapping(value: Mapping) -> CaptureSourceIdentity:
    return CaptureSourceIdentity(
        provider_id=_str(value.get('provider_id')),
        endpoint_id=_str(value.get('endpoint_id')),
        endpoint_url=_str(value.get('endpoint_url')),
        principal_id=_str(value.get('principal_id')),
        credential_revision=_str(value.get('credential_revision')),
        rule_hash=_str(value.get('rule_hash')),
    )


def work_item_from_mapping(value: Mapping) -> WorkItemIdentity:
    return WorkItemIdentity(
        provider_id=_str(value.get('provider_id')),
        endpoint_id=_str(value.get('endpoint_id')),
        stable_id=_str(value.get('stable_id')),
        display_key=_str(value.get('display_key')),
    )


def part_from_mapping(value: Mapping) -> PartCoverage:
    return PartCoverage(
        state=_str(value.get('state')),
        source_version=_optional_str(value.get('source_version')),
        observed_count=_optional_int(value.get('observed_count')),
        total_count=_optional_int(value.get('total_count')),
        reason_code=_optional_str(value.get('reason_code')),
    )


def coverage_from_mapping(value: Mapping) -> CaptureCoverage:
    return CaptureCoverage(
        facts=part_from_mapping(_mapping(value.get('facts'))),
        comments=part_from_mapping(_mapping(value.get('comments'))),
        history=part_from_mapping(_mapping(value.get('history'))),
        attachments=part_from_mapping(_mapping(value.get('attachments'))),
        dependencies=part_from_mapping(_mapping(value.get('dependencies'))),
    )


def raw_page_ref_from_mapping(value: Mapping) -> RawPageRef:
    return RawPageRef(
        page_id=_str(value.get('page_id')),
        sha256=_str(value.get('sha256')),
        size_bytes=_int(value.get('size_bytes')),
        content_type=_str(value.get('content_type')),
        request_fingerprint=_str(value.get('request_fingerprint')),
    )


def snapshot_from_mapping(value: Mapping) -> SnapshotInput:
    snapshot = SnapshotInput(
        identity=work_item_from_mapping(_mapping(value.get('identity'))),
        facts=_mapping(value.get('facts')),
        comments_by_id=_mapping(value.get('comments_by_id')),
        history_by_id=_mapping(value.get('history_by_id')),
        attachments_by_id=_mapping(value.get('attachments_by_id')),
        dependencies_by_id=_mapping(value.get('dependencies_by_id')),
        coverage=coverage_from_mapping(_mapping(value.get('coverage'))),
        raw_page_ids=tuple(_str(item) for item in _list(value.get('raw_page_ids'))),
        consistent=_bool(value.get('consistent')),
    )
    validate_snapshot(snapshot)
    return snapshot


def stored_snapshot_from_mapping(value: Mapping) -> StoredSnapshotRef:
    return StoredSnapshotRef(
        identity=work_item_from_mapping(_mapping(value.get('identity'))),
        capture_id=_str(value.get('capture_id')),
        sequence=_int(value.get('sequence')),
        previous_capture_id=_optional_str(value.get('previous_capture_id')),
        source_hash=_str(value.get('source_hash')),
        git_path=_str(value.get('git_path')),
    )


def membership_from_mapping(value: Mapping) -> MembershipInput:
    return MembershipInput(
        items=tuple(work_item_from_mapping(_mapping(item)) for item in _list(value.get('items'))),
        coverage=part_from_mapping(_mapping(value.get('coverage'))),
        raw_page_ids=tuple(_str(item) for item in _list(value.get('raw_page_ids'))),
    )


def _datetime(value) -> datetime:
    text = _str(value)
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None
    return utc_datetime(parsed)


def _mapping(value) -> Mapping:
    if not isinstance(value, Mapping):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def _list(value) -> list:
    if not isinstance(value, list):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def _str(value) -> str:
    if type(value) is not str:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def _optional_str(value) -> str | None:
    if value is None:
        return None
    return _str(value)


def _int(value) -> int:
    if type(value) is not int or value < 0:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def _optional_int(value) -> int | None:
    if value is None:
        return None
    return _int(value)


def _bool(value) -> bool:
    if type(value) is not bool:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def _literal(value, expected):
    if type(value) is not type(expected) or value != expected:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return expected
