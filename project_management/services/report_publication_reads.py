from dataclasses import replace

from project_management.app.domain.capture_values import canonical_bytes, decode_snapshot
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_queries import ReportPublicationListItem
from project_management.app.domain.report_draft_values import read_json, snapshot_from_mapping
from project_management.app.domain.report_publication_contracts import (
    PUBLICATION_FILES,
    ReportPublication,
    ReportPublicationArtifacts,
    publication_path,
)
from project_management.app.domain.report_publication_validation import (
    PublicationValidationContext,
    validate_publication_files,
)
from project_management.app.domain.summary_input import complete_source
from project_management.app.spi.archive_reads import ArchiveBlobRequest
from project_management.storage.publication_validation import verified_packet


PUBLIC_ARTIFACTS = {'html': 'report.html', 'plain_text': 'report.txt'}


def prefetch_publications(repository, publication_ids, *, extra_requests=()):
    requests = list(extra_requests)
    for publication_id in dict.fromkeys(publication_ids):
        commit = repository.find_commit_for_path(publication_path(publication_id, 'manifest.json'))
        if commit is not None:
            requests.extend(ArchiveBlobRequest(commit, publication_path(publication_id, name)) for name in PUBLICATION_FILES)
    repository.read_files(tuple(requests))


def read_publication_artifacts(service, actor, project_id, stage_id, publication_id):
    publication_id = service._uuid(publication_id)
    try:
        with service.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
            return ReportPublicationReader(repository).read_artifacts(publication_id, actor.subject)
    except (ArchiveError, ProjectError) as error:
        raise service._report_error(error, missing_as_not_found=True) from None


class ReportPublicationReader:
    def __init__(self, repository):
        self.repository = repository

    def get(self, publication_id: str, actor_subject: str | None = None) -> ReportPublication:
        return self.read_artifacts(publication_id, actor_subject).publication

    def read_artifacts(self, publication_id: str, actor_subject: str | None = None) -> ReportPublicationArtifacts:
        manifest, manifest_hash, commit_id, files = self._verified_files(publication_id, actor_subject)
        publication = ReportPublication(manifest, manifest_hash, commit_id, self.repository.checkout_state(commit_id))
        return ReportPublicationArtifacts(publication, files)

    def list_item(self, publication_id: str, actor_subject: str) -> ReportPublicationListItem:
        manifest, manifest_hash, commit_id, _ = self._verified_files(publication_id, actor_subject)
        return ReportPublicationListItem(manifest, manifest_hash, commit_id)

    def _verified_files(self, publication_id, actor_subject):
        manifest_path = publication_path(publication_id, 'manifest.json')
        commit_id = self.repository.commit_for_path(manifest_path)
        contents = self.repository.read_files(tuple(
            ArchiveBlobRequest(commit_id, publication_path(publication_id, name)) for name in PUBLICATION_FILES
        ))
        files = dict(zip(PUBLICATION_FILES, contents))
        manifest, manifest_hash = verified_packet(self.repository, publication_id, files, self._context(), actor_subject)
        return manifest, manifest_hash, commit_id, files

    def read_public_artifact(self, publication_id: str, format: str, actor_subject: str | None = None) -> bytes:
        if format in PUBLIC_ARTIFACTS:
            name = PUBLIC_ARTIFACTS[format]
            return self.read_artifacts(publication_id, actor_subject).files[name]
        if format not in PUBLICATION_FILES:
            raise ReportError('REPORT_INVALID')
        packet = self.read_artifacts(publication_id, actor_subject)
        if packet.publication.manifest.schema_version != 2:
            raise ReportError('REPORT_INVALID')
        name = format
        return packet.files[name]

    def snapshot(self, publication_id: str):
        packet = self.read_artifacts(publication_id)
        publication, data = packet.publication, packet.files['snapshot.json']
        snapshot = snapshot_from_mapping(read_json(data))
        if canonical_bytes(snapshot) != data:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return publication, snapshot

    def list(self):
        with self.repository.open_read_view() as view:
            ids = tuple(path.split('/')[1] for path in view.list_files('report_publications')
                        if path.endswith('/manifest.json'))
            prefetch_publications(view, ids)
            reader = ReportPublicationReader(view)
            publications = [reader.get(publication_id) for publication_id in ids]
        return tuple(sorted(publications, key=lambda item: (item.manifest.finalized_at, item.manifest.publication_id)))

    def _context(self):
        return PublicationValidationContext(
            self.repository.project.id,
            self.repository.stage.id,
            self.repository.owner_subject,
            self.repository.stage.definition_hash,
        )


class ReportPublicationResolver:
    def __init__(self, archive):
        self.archive = archive

    def parent_snapshot(self, actor, project_id, stage_id, selection):
        if selection.parent_publication_id is None:
            raise ReportError('REPORT_INVALID')
        if selection.purpose != 'standup':
            raise ReportError('REPORT_COMPARISON_UNAVAILABLE')
        with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
            _, snapshot = ReportPublicationReader(repository).snapshot(selection.parent_publication_id)
        if snapshot.capture_id != selection.capture_id:
            raise ReportError('REPORT_SOURCE_CHANGED')
        return replace(snapshot, baseline_publication_id=selection.baseline_publication_id)

    def same_source_baseline(self, repository, snapshot, baseline_publication_id):
        if baseline_publication_id is None:
            return snapshot
        _, baseline = ReportPublicationReader(repository).snapshot(baseline_publication_id)
        if _source_identity(baseline) != _source_identity(snapshot):
            raise ReportError('REPORT_COMPARISON_UNAVAILABLE')
        self._verify_intermediate_chain(repository, baseline, snapshot)
        coverage = dict(snapshot.coverage)
        coverage['comparison_state'] = 'no_change'
        return replace(snapshot, baseline_publication_id=baseline_publication_id, coverage=coverage, events=())

    def _verify_intermediate_chain(self, repository, baseline, snapshot):
        baseline_rows = {canonical_bytes(row.source_key): row for row in baseline.rows}
        for row in snapshot.rows:
            baseline_row = baseline_rows[canonical_bytes(row.source_key)]
            chain = self._source_chain(repository, row.source_key)
            segment = self._chain_segment(chain, baseline.capture_id, snapshot.capture_id)
            if not segment or segment[0].capture_id != baseline.capture_id or segment[-1].capture_id != snapshot.capture_id:
                raise ReportError('REPORT_COMPARISON_UNAVAILABLE')
            for reference in segment:
                if reference.source_hash != baseline_row.source_hash or not self._complete_chain_reference(repository, reference):
                    raise ReportError('REPORT_COMPARISON_UNAVAILABLE')

    def _source_chain(self, repository, source_key):
        return repository.publication_source_chain(source_key)

    def _chain_segment(self, chain, start_capture_id, end_capture_id):
        started = False
        segment = []
        for reference in chain:
            if reference.capture_id == start_capture_id:
                started = True
            if started:
                segment.append(reference)
            if started and reference.capture_id == end_capture_id:
                return tuple(segment)
        return ()

    def _complete_chain_reference(self, repository, reference):
        if hasattr(reference, 'complete'):
            return bool(reference.complete)
        source = decode_snapshot(repository.read_file(reference.git_path))
        return self.archive._source_hash(source) == reference.source_hash and complete_source(source)


def _source_identity(snapshot):
    if snapshot.coverage.get('complete') is False:
        raise ReportError('REPORT_COMPARISON_UNAVAILABLE')
    rows = tuple(sorted((_row_identity(row) for row in snapshot.rows), key=lambda item: item[0]))
    messages = tuple((message.message_id, tuple(message.source_refs)) for message in snapshot.key_messages)
    return canonical_bytes({
        'project_id': snapshot.project_id,
        'stage_id': snapshot.stage_id,
        'owner_subject': snapshot.owner_subject,
        'rule_hash': snapshot.rule_hash,
        'comparison_policy_hash': snapshot.comparison_policy_hash,
        'rows': rows,
        'messages': messages,
    })


def _row_identity(row):
    summary = None
    if row.summary_ref is not None:
        summary = {
            'summary_id': row.summary_ref.summary_id,
            'revision': row.summary_ref.revision,
            'source_hash': row.summary_ref.source_hash,
            'input_hash': row.summary_ref.input_hash,
            'result_hash': row.summary_ref.result_hash,
        }
    return (
        canonical_bytes(row.source_key).decode('utf-8'),
        row.identity,
        row.source_hash,
        summary,
    )
