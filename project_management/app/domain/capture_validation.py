from dataclasses import fields
import re
from typing import Mapping

from .captures import ArchiveError, ArchiveLimits, CaptureIntent, CaptureSourceIdentity, RawPageInput


PARTS = {'facts', 'comments', 'history', 'attachments', 'dependencies'}
STATES = {'complete', 'partial', 'unsupported', 'access_lost', 'not_requested'}


def text(value, limit=2048):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value


def validate_limits(limits):
    if not isinstance(limits, ArchiveLimits):
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')
    if any(type(getattr(limits, field.name)) is not int or getattr(limits, field.name) <= 0 for field in fields(limits)):
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')


def validate_intent(intent):
    if not isinstance(intent, CaptureIntent) or not isinstance(intent.source, CaptureSourceIdentity):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    for name in ('project_id', 'stage_id', 'capture_id', 'request_id'):
        text(getattr(intent, name), 36)
    for field in fields(CaptureSourceIdentity):
        text(getattr(intent.source, field.name))
    if (not isinstance(intent.original_input_hash, str)
            or not re.fullmatch('[0-9a-f]{64}', intent.original_input_hash)
            or not re.fullmatch('[0-9a-f]{64}', intent.source.rule_hash)
            or not isinstance(intent.required_parts, tuple)
            or not intent.required_parts
            or any(not isinstance(part, str) or part not in PARTS for part in intent.required_parts)
            or len(set(intent.required_parts)) != len(intent.required_parts)):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')


def validate_page(page):
    if not isinstance(page, RawPageInput) or type(page.payload) is not bytes:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    for name in ('page_key', 'content_type', 'request_fingerprint'):
        text(getattr(page, name))
    if page.item is not None:
        item_key(page.item)
    if type(page.partial) is not bool:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    if page.error_code is not None:
        text(page.error_code)


def item_key(item):
    for value in (item.provider_id, item.endpoint_id, item.stable_id, item.display_key):
        text(value)
    return item.provider_id, item.endpoint_id, item.stable_id


def validate_part(part, count):
    if not isinstance(part.state, str):
        raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')
    for value in (part.source_version, part.reason_code):
        if value is not None:
            text(value)
    if part.state not in STATES:
        raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')
    for value in (part.observed_count, part.total_count):
        if value is not None and (type(value) is not int or value < 0):
            raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')
    if part.observed_count is not None and part.observed_count != count:
        raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')
    if part.total_count is not None and part.total_count < count:
        raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')
    if part.state == 'complete' and (part.total_count != count or part.observed_count != count):
        raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')
    if part.state in {'unsupported', 'access_lost', 'not_requested'} and count:
        raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')


def validate_snapshot(snapshot):
    item_key(snapshot.identity)
    if type(snapshot.consistent) is not bool or not isinstance(snapshot.facts, Mapping):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    validate_part(snapshot.coverage.facts, 1 if snapshot.facts else 0)
    for name in ('comments', 'history', 'attachments', 'dependencies'):
        records = getattr(snapshot, name + '_by_id')
        if not isinstance(records, Mapping):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        for key, row in records.items():
            text(key)
            if not isinstance(row, Mapping) or ('id' in row and row['id'] != key):
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        validate_part(getattr(snapshot.coverage, name), len(records))
    if len(set(snapshot.raw_page_ids)) != len(snapshot.raw_page_ids):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    if any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value) for value in snapshot.raw_page_ids):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')


def validate_membership(membership):
    keys = [item_key(item) for item in membership.items]
    if len(set(keys)) != len(keys):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    validate_part(membership.coverage, len(keys))
