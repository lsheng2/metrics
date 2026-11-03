from project_management.app.domain.capture_values import canonical_bytes, content_hash, sha256_bytes
from project_management.app.domain.capture_validation import item_key, validate_membership, validate_snapshot
from project_management.app.domain.captures import ArchiveError, SourceChainKey
from project_management.storage.objects import ObjectStore


class ArchiveMaterial:
    def _page_id(self, intent_hash, page):
        return sha256_bytes(canonical_bytes({'intent_hash': intent_hash,
                                             'item': item_key(page.item) if page.item else None,
                                             'page_key': page.page_key}))

    def _page_intent(self, intent_hash, page_id, page):
        value = {
            'schema_version': 1, 'intent_hash': intent_hash, 'page_id': page_id,
            'sha256': sha256_bytes(page.payload), 'size_bytes': len(page.payload),
            'content_type': page.content_type, 'request_fingerprint': page.request_fingerprint,
            'item': page.item, 'page_key': page.page_key,
        }
        if page.partial or page.error_code is not None:
            value.update(partial=page.partial, error_code=page.error_code)
        return value

    def _validate_snapshot_pages(self, pending, snapshot):
        objects = ObjectStore(pending.runtime_root.parent / 'objects', self.config.limits.max_object_bytes)
        for page_id in snapshot.raw_page_ids:
            record = pending.read_page(page_id)
            if record.item_key not in {None, content_hash(item_key(snapshot.identity))}:
                raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
            objects.read(record.reference)

    def _validate_snapshot_identity(self, intent, snapshot):
        if (snapshot.identity.provider_id != intent.source.provider_id
                or snapshot.identity.endpoint_id != intent.source.endpoint_id):
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')

    def _validate_finalize(self, intent, membership, pages, snapshots, complete, failure_code):
        if type(complete) is not bool:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        validate_membership(membership)
        page_ids = {page.page_id for page in pages}
        if not set(membership.raw_page_ids).issubset(page_ids):
            raise ArchiveError('ARCHIVE_RAW_PAGE_MISSING')
        members = {item_key(item) for item in membership.items}
        snapshot_members = {item_key(snapshot.identity) for snapshot, _ in snapshots}
        if len(snapshot_members) != len(snapshots):
            raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
        for member in membership.items:
            if member.provider_id != intent.source.provider_id or member.endpoint_id != intent.source.endpoint_id:
                raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
        for snapshot, _ in snapshots:
            validate_snapshot(snapshot)
            self._validate_snapshot_identity(intent, snapshot)
        if not snapshot_members.issubset(members):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if complete:
            if failure_code is not None or membership.coverage.state != 'complete' or members != snapshot_members:
                raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')
            for snapshot, _ in snapshots:
                if not snapshot.consistent or any(getattr(snapshot.coverage, part).state != 'complete'
                                                  for part in intent.required_parts):
                    raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')
        elif failure_code is None:
            raise ArchiveError('ARCHIVE_COVERAGE_INCOMPLETE')

    def _source_hash(self, snapshot):
        return content_hash({
            'identity': snapshot.identity, 'facts': snapshot.facts, 'comments_by_id': snapshot.comments_by_id,
            'history_by_id': snapshot.history_by_id, 'attachments_by_id': snapshot.attachments_by_id,
            'dependencies_by_id': snapshot.dependencies_by_id,
        })

    def _source_key(self, intent, identity):
        return SourceChainKey(identity.provider_id, identity.endpoint_id, identity.stable_id,
                              intent.source.principal_id, intent.source.rule_hash)
