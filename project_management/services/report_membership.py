from dataclasses import dataclass

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json, sha256_bytes
from project_management.app.domain.capture_validation import item_key, validate_membership
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportSourceError
from project_management.storage.objects import ObjectStore


@dataclass(frozen=True, slots=True)
class ScopeMember:
    identity: object
    source_key: object


@dataclass(frozen=True, slots=True)
class ScopeMembershipSnapshot:
    schema_version: int
    capture_id: str
    source_commit: str
    manifest_sha256: str
    source_as_of: str
    rule_hash: str
    principal_id: str
    state: str
    observed_count: int | None
    total_count: int | None
    members: tuple[ScopeMember, ...]
    proof_hash: str


def read_report_membership(archive, actor, project_id, stage_id, snapshot) -> ScopeMembershipSnapshot:
    if snapshot.project_id != project_id or snapshot.stage_id != stage_id or snapshot.owner_subject != actor.subject:
        raise ReportSourceError('REPORT_SOURCE_CHANGED')
    project, stage = archive._stage_for_read(actor, project_id, stage_id)
    if stage.source_status != 'current' or stage.definition_hash != snapshot.rule_hash:
        raise ReportSourceError('REPORT_SOURCE_CHANGED')
    repository = archive.repository_factory.open(archive.config, project, stage, actor.subject)
    repository.verify_identity()
    selected = archive._read_manifest(repository, snapshot.capture_id, snapshot.source_commit)
    _manifest_matches(stage, selected, snapshot)
    try:
        validate_membership(selected.membership)
    except ArchiveError:
        return _unknown_membership(archive, selected, repository, snapshot)
    pages_by_id = {page.page_id: page for page in selected.pages}
    complete = _complete_membership(repository, selected, pages_by_id, snapshot.source_commit)
    members = tuple(
        ScopeMember(identity, archive._source_key(selected.intent, identity))
        for identity in sorted(selected.membership.items, key=item_key)
    )
    payload = {
        'schema_version': 1,
        'capture_id': selected.intent.capture_id,
        'source_commit': snapshot.source_commit,
        'manifest_sha256': sha256_bytes(repository.read_file(f'captures/{snapshot.capture_id}/manifest.json',
                                                             snapshot.source_commit)),
        'source_as_of': selected.finalized_at,
        'rule_hash': selected.intent.source.rule_hash,
        'principal_id': selected.intent.source.principal_id,
        'state': 'complete' if complete else 'unknown',
        'observed_count': selected.membership.coverage.observed_count,
        'total_count': selected.membership.coverage.total_count,
        'members': members,
    }
    return ScopeMembershipSnapshot(**payload, proof_hash=content_hash(payload))


def _unknown_membership(archive, selected, repository, snapshot):
    members = tuple(
        ScopeMember(identity, archive._source_key(selected.intent, identity))
        for identity in sorted(selected.membership.items, key=item_key)
    )
    payload = {
        'schema_version': 1,
        'capture_id': selected.intent.capture_id,
        'source_commit': snapshot.source_commit,
        'manifest_sha256': sha256_bytes(repository.read_file(f'captures/{snapshot.capture_id}/manifest.json',
                                                             snapshot.source_commit)),
        'source_as_of': selected.finalized_at,
        'rule_hash': selected.intent.source.rule_hash,
        'principal_id': selected.intent.source.principal_id,
        'state': 'unknown',
        'observed_count': selected.membership.coverage.observed_count,
        'total_count': selected.membership.coverage.total_count,
        'members': members,
    }
    return ScopeMembershipSnapshot(**payload, proof_hash=content_hash(payload))


def _manifest_matches(stage, manifest, snapshot):
    source = manifest.intent.source
    if (
        manifest.intent.capture_id != snapshot.capture_id
        or manifest.intent.project_id != snapshot.project_id
        or manifest.intent.stage_id != snapshot.stage_id
        or manifest.finalized_at != snapshot.source_as_of
        or source.provider_id != stage.descriptor.provider_id
        or source.endpoint_url != stage.descriptor.endpoint
        or source.rule_hash != snapshot.rule_hash
        or not source.principal_id
        or not source.endpoint_id
    ):
        raise ReportSourceError('REPORT_SOURCE_CHANGED')
    for identity in manifest.membership.items:
        if identity.provider_id != source.provider_id or identity.endpoint_id != source.endpoint_id:
            raise ReportSourceError('REPORT_SOURCE_CHANGED')


def _complete_membership(repository, manifest, pages_by_id, commit):
    coverage = manifest.membership.coverage
    keys = {(item.provider_id, item.endpoint_id, item.stable_id) for item in manifest.membership.items}
    if not manifest.membership.raw_page_ids:
        return False
    if any(page_id not in pages_by_id for page_id in manifest.membership.raw_page_ids):
        return False
    if any(not _json_content_type(pages_by_id[page_id].content_type) for page_id in manifest.membership.raw_page_ids):
        return False
    try:
        admission = decode_json(repository.read_file(f'captures/{manifest.intent.capture_id}/admission.json', commit))
        page_intents = {
            row.get('page_id'): row
            for row in decode_json(repository.read_file(f'captures/{manifest.intent.capture_id}/page-intents.json', commit))
            if isinstance(row, dict)
        }
        if admission.get('intent_hash') != content_hash(manifest.intent):
            return False
        store = ObjectStore(repository.objects, _object_limit(admission))
        for page_id in manifest.membership.raw_page_ids:
            intent = page_intents.get(page_id)
            if not _page_intent_ok(intent, manifest.intent, pages_by_id[page_id]):
                return False
            store.read(pages_by_id[page_id])
    except (ArchiveError, AttributeError):
        return False
    return (
        coverage.state == 'complete'
        and coverage.observed_count == coverage.total_count == len(keys) == len(manifest.membership.items)
    )


def _json_content_type(value):
    if type(value) is not str:
        return False
    media = value.split(';', 1)[0].strip().lower()
    return media == 'application/json' or media.endswith('+json')


def _object_limit(admission):
    limit = admission.get('limits', {}).get('max_object_bytes')
    if type(limit) is not int or limit <= 0:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return limit


def _page_intent_ok(intent, capture_intent, page):
    if not isinstance(intent, dict):
        return False
    if intent.get('partial') or intent.get('error_code') is not None:
        return False
    expected = {
        'schema_version': 1,
        'page_id': page.page_id,
        'sha256': page.sha256,
        'size_bytes': page.size_bytes,
        'content_type': page.content_type,
        'request_fingerprint': page.request_fingerprint,
        'page_key': intent.get('page_key'),
    }
    if any(intent.get(key) != value for key, value in expected.items()):
        return False
    if intent.get('intent_hash') != content_hash(capture_intent):
        return False
    item = intent.get('item')
    if item is not None and (
        item.get('provider_id') != capture_intent.source.provider_id
        or item.get('endpoint_id') != capture_intent.source.endpoint_id
    ):
        return False
    return True
