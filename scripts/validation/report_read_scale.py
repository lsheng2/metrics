from __future__ import annotations

from datetime import UTC, datetime, timedelta

from project_management.app.domain.capture_values import canonical_bytes, content_hash, sha256_bytes
from project_management.app.domain.captures import (
    CaptureIntent,
    CaptureManifest,
    CaptureSourceIdentity,
    MembershipInput,
    PartCoverage,
    StoredSnapshotRef,
)
from scripts.validation.report_read_git import fast_import_records
from project_management.storage.objects import ObjectStore


def materialize_scale_captures(fixture, count: int, *, fixed_items, page_factory, snapshot_factory, source_hash):
    records, previous = [], {item.stable_id: None for item in fixed_items()}
    capture_ids = []
    with fixture.archive._report_repository(fixture.actor, fixture.project.id, fixture.stage.id) as repository:
        objects = ObjectStore(repository.objects, fixture.archive.config.limits.max_object_bytes)
    for index in range(count):
        capture_id = f'72000000-0000-4000-8000-{index + 1:012d}'
        intent = _capture_intent(fixture, index, capture_id)
        pages, page_intents, snapshots, files = [], [], [], {}
        for item in fixed_items():
            page = page_factory(index, item)
            page_id = sha256_bytes(canonical_bytes({'capture_id': capture_id, 'page_key': page.page_key}))
            page_ref = objects.put(page.payload, page.content_type, page.request_fingerprint, page_id)
            source = snapshot_factory(index, item, (page_id,))
            digest = source_hash(source)
            reference = StoredSnapshotRef(
                item, capture_id, index + 1, previous[item.stable_id], digest,
                f'captures/{capture_id}/snapshots/{digest}.json',
            )
            previous[item.stable_id] = capture_id
            pages.append(page_ref)
            page_intents.append({
                'schema_version': 1,
                'intent_hash': content_hash(intent),
                'page_id': page_id,
                'sha256': page_ref.sha256,
                'size_bytes': page_ref.size_bytes,
                'content_type': page_ref.content_type,
                'request_fingerprint': page_ref.request_fingerprint,
                'item': item,
                'page_key': page.page_key,
            })
            snapshots.append(reference)
            files[reference.git_path] = canonical_bytes(source)
        membership = MembershipInput(fixed_items(), PartCoverage('complete', 'fixture-source', 3, 3, None),
                                     tuple(page.page_id for page in pages))
        captured = datetime(2026, 11, 6, tzinfo=UTC) + timedelta(minutes=index)
        manifest = CaptureManifest(
            1, intent, membership, tuple(snapshots), tuple(pages), True, None,
            captured.isoformat(),
            (captured + timedelta(seconds=30)).isoformat(),
        )
        manifest_bytes = canonical_bytes(manifest)
        files.update({
            f'captures/{capture_id}/manifest.json': manifest_bytes,
            f'captures/{capture_id}/pages.json': canonical_bytes(tuple(pages)),
            f'captures/{capture_id}/page-intents.json': canonical_bytes(tuple(page_intents)),
            f'captures/{capture_id}/admission.json': canonical_bytes({
                'schema_version': 1,
                'intent_hash': content_hash(intent),
                'limits': {'max_object_bytes': fixture.archive.config.limits.max_object_bytes},
            }),
        })
        records.append((capture_id, files, sha256_bytes(manifest_bytes), ''))
        capture_ids.append(capture_id)
    with fixture.archive._report_repository(fixture.actor, fixture.project.id, fixture.stage.id, write=True) as repository:
        fast_import_records(repository, records)
    return tuple(capture_ids)


def _capture_intent(fixture, index: int, capture_id: str) -> CaptureIntent:
    return CaptureIntent(
        fixture.project.id,
        fixture.stage.id,
        capture_id,
        f'72100000-0000-4000-8000-{index + 1:012d}',
        CaptureSourceIdentity(
            'jira',
            'team-jira',
            fixture.stage.descriptor.endpoint,
            f'principal:{fixture.actor.subject}',
            'synthetic-fixture-credential',
            fixture.stage.definition_hash,
        ),
        f'{index + 1:064x}',
        ('facts', 'comments'),
        datetime.now(UTC) + timedelta(minutes=10),
    )
