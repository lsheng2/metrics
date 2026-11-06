from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import bytes_hash, read_json, snapshot_from_mapping
from project_management.storage.paths import read_bytes
from project_management.storage.report_draft_projection import draft_from_revision


def finalization_control(root):
    try:
        return read_bytes(root, 'finalization.json')
    except ArchiveError as error:
        if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
            return None
        raise


def read_draft(store, draft_id, revision):
    root = store.root(draft_id)
    intent, head = store._intent(root, draft_id), store._current(root)
    finalization = finalization_control(root)
    selected_revision = head['revision'] if revision is None else store._positive_revision(revision)
    expected_hash = store._verified_revision_hash(root, draft_id, selected_revision, intent)
    selected = store._read_revision(root, selected_revision, expected_hash=expected_hash)
    if revision is None and selected[1] != head['revision_hash']:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    snapshot_bytes = read_bytes(root, 'snapshot.json', limit=8_388_608)
    snapshot_hash = bytes_hash(snapshot_bytes)
    if snapshot_hash != selected[0]['snapshot_hash'] or snapshot_hash != intent['snapshot_hash']:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    snapshot = snapshot_from_mapping(read_json(snapshot_bytes))
    if canonical_bytes(snapshot) != snapshot_bytes:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    store._validate_binding(draft_id, intent, selected[0], snapshot)
    result = draft_from_revision(
        selected[0], selected[1], snapshot, store._state(root),
        store._preservation_review_issues(root, intent),
    )
    if store._current(root) != head or finalization_control(root) != finalization:
        raise ReportError('REPORT_REVISION_CONFLICT')
    return result
