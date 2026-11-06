import base64
import re

from project_management.app.domain.capture_values import (
    canonical_bytes, content_hash, decode_json, decode_snapshot, manifest_from_bytes, sha256_bytes,
)
from project_management.app.domain.captures import (
    ArchiveError, CaptureMetadata, CaptureMetadataPage, CapturePage, CaptureReceipt, SourceChainPage,
)
from project_management.storage.objects import ObjectStore
from project_management.storage.paths import validate_uuid
from project_management.app.spi.archive_reads import ArchiveBlobRequest


class ArchiveReads:
    def _capture_read_requests(self, view, after):
        head, _ = self._cursor(view, after, None)
        return tuple(ArchiveBlobRequest(head, path) for path in view.list_files('captures', head)
                     if path.endswith('/manifest.json'))

    def _limit(self, value):
        if type(value) is not int or not 1 <= value <= 100:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return value

    def _read_repository(self, actor, project_id, stage_id):
        project, stage = self._stage_for_read(actor, project_id, stage_id)
        self._validate_root_before_lock()
        repository = self.repository_factory.open(self.config, project, stage, actor.subject)
        repository.verify_identity()
        return repository

    def read_capture(self, actor, project_id, stage_id, capture_id):
        repository = self._read_repository(actor, project_id, stage_id)
        return self._read_manifest(repository, capture_id)

    def read_page(self, actor, project_id, stage_id, capture_id, page_id):
        repository = self._read_repository(actor, project_id, stage_id)
        manifest = self._read_manifest(repository, capture_id)
        reference = next((page for page in manifest.pages if page.page_id == page_id), None)
        if reference is None:
            raise ArchiveError('ARCHIVE_RAW_PAGE_MISSING')
        admitted = decode_json(repository.read_file(f'captures/{capture_id}/admission.json'))
        limit = admitted.get('limits', {}).get('max_object_bytes')
        if (admitted.get('intent_hash') != content_hash(manifest.intent)
                or type(limit) is not int or limit <= 0 or reference.size_bytes > limit):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return ObjectStore(repository.objects, limit).read(reference)

    def read_snapshot(self, actor, project_id, stage_id, capture_id, source_key):
        repository = self._read_repository(actor, project_id, stage_id)
        manifest = self._read_manifest(repository, capture_id)
        reference = next((row for row in manifest.snapshots
                          if self._source_key(manifest.intent, row.identity) == source_key), None)
        if reference is None:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        snapshot = decode_snapshot(repository.read_file(reference.git_path))
        if self._source_hash(snapshot) != reference.source_hash:
            raise ArchiveError('ARCHIVE_RAW_PAGE_INTEGRITY_FAILED')
        return snapshot

    def list_captures(self, actor, project_id, stage_id, *, limit=100, after=None):
        repository, head, selected, cursor = self._capture_listing(actor, project_id, stage_id, limit, after)
        return CapturePage(tuple(self._receipt_from_manifest(repository, row, head) for row in selected), cursor)

    def list_capture_metadata(self, actor, project_id, stage_id, *, limit=100, after=None, _read_view=None, allow_absent=False):
        if type(allow_absent) is not bool:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if _read_view is None:
            with self._report_read_view(actor, project_id, stage_id, allow_absent=allow_absent) as view:
                if view is None:
                    self._limit(limit)
                    if after is not None:
                        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
                    return CaptureMetadataPage((), None)
                return self.list_capture_metadata(actor, project_id, stage_id, limit=limit, after=after, _read_view=view)
        repository, head, selected, cursor = self._capture_listing(actor, project_id, stage_id, limit, after, _read_view)
        return CaptureMetadataPage(tuple(
            CaptureMetadata(self._receipt_from_manifest(repository, row, head), row.finalized_at)
            for row in selected
        ), cursor)

    def _capture_listing(self, actor, project_id, stage_id, limit, after, read_view=None):
        repository = read_view or self._read_repository(actor, project_id, stage_id)
        head, last = self._cursor(repository, after, None)
        tail = self._after(list(self._manifests(repository, head)), last, lambda row: row.intent.capture_id)
        selected = tail[:self._limit(limit)]
        cursor = self._next(head, selected[-1].intent.capture_id, None) if len(tail) > len(selected) else None
        return repository, head, selected, cursor

    def source_chain(self, actor, project_id, stage_id, source_key, *, after_capture_id=None, limit=100):
        repository = self._read_repository(actor, project_id, stage_id)
        key_hash = content_hash(source_key)
        if after_capture_id and re.fullmatch(r'[0-9a-f-]{36}', after_capture_id):
            head, last = repository.head(), validate_uuid(after_capture_id)
        else:
            head, last = self._cursor(repository, after_capture_id, key_hash)
        tail = self._after(self._source_chain(repository, source_key, head), last, lambda row: row.capture_id)
        selected = tail[:self._limit(limit)]
        cursor = self._next(head, selected[-1].capture_id, key_hash) if len(tail) > len(selected) else None
        return SourceChainPage(tuple(selected), cursor)

    def _source_chain(self, repository, source_key, head=None):
        items = [row for manifest in self._manifests(repository, head) for row in manifest.snapshots
                 if self._source_key(manifest.intent, row.identity) == source_key]
        items.sort(key=lambda row: row.sequence)
        previous = None
        for number, row in enumerate(items, 1):
            if row.sequence != number or row.previous_capture_id != previous:
                raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')
            previous = row.capture_id
        return items

    def _read_manifest(self, repository, capture_id, commit='main'):
        path = f'captures/{validate_uuid(capture_id)}/manifest.json'
        value = manifest_from_bytes(repository.read_file(path, commit))
        if (value.intent.capture_id != capture_id or value.intent.project_id != repository.project.id
                or value.intent.stage_id != repository.stage.id):
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
        return value

    def _manifests(self, repository, head=None):
        head = head or repository.head()
        paths = repository.list_files('captures', head)
        selected = tuple(path for path in paths if path.endswith('/manifest.json'))
        data = repository.read_files(tuple(ArchiveBlobRequest(head, path) for path in selected))
        values = []
        for path, content in zip(selected, data):
            value = manifest_from_bytes(content)
            if (value.intent.capture_id != path.split('/')[1] or value.intent.project_id != repository.project.id
                    or value.intent.stage_id != repository.stage.id):
                raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
            values.append(value)
        return tuple(sorted(values, key=lambda row: (row.finalized_at, row.intent.capture_id)))

    def _receipt_from_manifest(self, repository, manifest, head=None):
        path = f'captures/{manifest.intent.capture_id}/manifest.json'
        commit = repository.commit_for_path(path)
        return CaptureReceipt(
            manifest.intent.capture_id, commit, sha256_bytes(repository.read_file(path, head or 'main')),
            repository.parent_for_commit(commit), manifest.membership.coverage.state == 'complete',
            manifest.complete, manifest.failure_code, manifest.snapshots, repository.checkout_state(commit),
        )

    def _cursor(self, repository, cursor, key_hash):
        head = repository.head()
        if cursor is None:
            return head, None
        try:
            if not isinstance(cursor, str) or len(cursor) > 1368:
                raise ValueError
            payload = decode_json(base64.b64decode(cursor.encode('ascii'), altchars=b'-_', validate=True))
            if (set(payload) != {'v', 'head_commit', 'last_capture_id', 'source_key_hash'}
                    or type(payload['v']) is not int or payload['v'] != 1
                    or payload['source_key_hash'] != key_hash
                    or not re.fullmatch(r'[0-9a-f]{40,64}', payload['head_commit'])):
                raise ValueError
            validate_uuid(payload['last_capture_id'])
            result = repository.git.run(
                ['merge-base', '--is-ancestor', payload['head_commit'], head], check=False,
            )
            if result.returncode:
                raise ValueError
            return payload['head_commit'], payload['last_capture_id']
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None

    def _next(self, head, last, key_hash):
        return base64.urlsafe_b64encode(canonical_bytes({
            'v': 1, 'head_commit': head, 'last_capture_id': last, 'source_key_hash': key_hash,
        })).decode('ascii')

    def _after(self, items, last, identity):
        if last is None:
            return items
        for index, item in enumerate(items):
            if identity(item) == last:
                return items[index + 1:]
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
