from datetime import UTC, datetime
import hashlib
from uuid import UUID

from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.report_completion import CompletionError
from project_management.storage.admission import GrowthEstimate, admit
from project_management.storage.paths import read_bytes, write_bytes


class CompletionAdmissionStore:
    def __init__(self, root):
        self.root = root

    def admit(self, actor, repository, request_id, now):
        now = now.astimezone(UTC)
        relative = 'report-reference-budget.json'
        try:
            value = decode_json(read_bytes(repository.runtime, relative, limit=65536))
        except ArchiveError as error:
            if error.code != 'ARCHIVE_RAW_PAGE_MISSING':
                return CompletionError('COMPLETION_SCOPE_UNAVAILABLE', 'Reference budget is unavailable.')
            value = {'schema_version': 1, 'last_observed_at': now.isoformat(), 'buckets': []}
        parsed = _budget(value)
        if parsed is None:
            return CompletionError('COMPLETION_SCOPE_UNAVAILABLE', 'Reference budget is unavailable.')
        previous, parsed_buckets = parsed
        if now < previous:
            return CompletionError('COMPLETION_SCOPE_UNAVAILABLE', 'Reference budget is unavailable.')
        try:
            if str(UUID(request_id)) != request_id:
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            return CompletionError('COMPLETION_SCOPE_UNAVAILABLE', 'Reference budget is unavailable.')
        actor_hash = hashlib.sha256(actor.subject.encode('utf-8')).hexdigest()
        cutoff = now.timestamp() - 60
        buckets = []
        selected = None
        for bucket in parsed_buckets:
            admissions = [
                item for item in bucket['admissions']
                if _timestamp(item['admitted_at']) >= cutoff
            ]
            if not admissions:
                continue
            next_bucket = {'actor_hash': bucket['actor_hash'], 'admissions': admissions}
            if next_bucket['actor_hash'] == actor_hash:
                selected = next_bucket
            buckets.append(next_bucket)
        if selected is None:
            if len(buckets) >= 64:
                return CompletionError('COMPLETION_SCOPE_UNAVAILABLE', 'Reference budget is unavailable.')
            selected = {'actor_hash': actor_hash, 'admissions': []}
            buckets.append(selected)
        if any(item['request_id'] == request_id for item in selected['admissions']):
            return CompletionError('COMPLETION_REQUEST_REPLAY', 'Reference lookup already used this request.')
        if len(selected['admissions']) >= 30:
            oldest = min(_timestamp(item['admitted_at']) for item in selected['admissions'])
            retry = max(1, int(oldest + 60 - now.timestamp() + 0.999))
            return CompletionError('COMPLETION_RATE_LIMITED', 'Reference lookup is rate limited.', retry)
        selected['admissions'].append({'request_id': request_id, 'admitted_at': now.isoformat()})
        value = {'schema_version': 1, 'last_observed_at': now.isoformat(), 'buckets': buckets}
        data = canonical_bytes(value)
        if len(data) > 65536:
            return CompletionError('COMPLETION_SCOPE_UNAVAILABLE', 'Reference budget is unavailable.')
        try:
            admit(self.root, repository.stage_root, repository.runtime, repository.config.limits,
                  GrowthEstimate(len(data) + 8192, 2))
        except ArchiveError:
            return CompletionError('COMPLETION_SCOPE_UNAVAILABLE', 'Reference budget is unavailable.')
        write_bytes(repository.runtime, relative, data, immutable=False)
        return None


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return -1
        return parsed.astimezone(UTC).timestamp()
    except Exception:
        return -1


def _budget(value):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'last_observed_at', 'buckets'}:
        return None
    if value['schema_version'] != 1 or not isinstance(value['buckets'], list) or len(value['buckets']) > 64:
        return None
    previous = _timestamp(value['last_observed_at'])
    if previous < 0:
        return None
    buckets = []
    seen_actor_hashes = set()
    for bucket in value['buckets']:
        if not isinstance(bucket, dict) or set(bucket) != {'actor_hash', 'admissions'}:
            return None
        if not _hash(bucket['actor_hash']) or not isinstance(bucket['admissions'], list) or len(bucket['admissions']) > 30:
            return None
        if bucket['actor_hash'] in seen_actor_hashes:
            return None
        seen_actor_hashes.add(bucket['actor_hash'])
        admissions = []
        for item in bucket['admissions']:
            if not isinstance(item, dict) or set(item) != {'request_id', 'admitted_at'}:
                return None
            try:
                if str(UUID(item['request_id'])) != item['request_id']:
                    return None
            except (TypeError, ValueError, AttributeError):
                return None
            if _timestamp(item['admitted_at']) < 0:
                return None
            admissions.append({'request_id': item['request_id'], 'admitted_at': item['admitted_at']})
        buckets.append({'actor_hash': bucket['actor_hash'], 'admissions': admissions})
    return datetime.fromtimestamp(previous, UTC), buckets


def _hash(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)
