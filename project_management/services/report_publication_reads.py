from dataclasses import replace

from project_management.app.domain.capture_values import canonical_bytes, decode_snapshot
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import read_json, snapshot_from_mapping
from project_management.app.domain.report_publication_contracts import (
    PUBLICATION_FILES,
    ReportPublication,
    publication_path,
)
from project_management.app.domain.report_publication_validation import (
    PublicationValidationContext,
    validate_publication_files,
)
from project_management.app.domain.summary_input import complete_source


PUBLIC_ARTIFACTS = {'html': 'report.html', 'plain_text': 'report.txt'}


class ReportPublicationReader:
    def __init__(self, repository):
        self.repository = repository

    def get(self, publication_id: str, actor_subject: str | None = None) -> ReportPublication:
        manifest_path = publication_path(publication_id, 'manifest.json')
        commit_id = self.repository.commit_for_path(manifest_path)
        files = {name: self.repository.read_file(publication_path(publication_id, name), commit_id)
                 for name in PUBLICATION_FILES}
        manifest, manifest_hash = validate_publication_files(publication_id, files, self._context(), actor_subject)
        return ReportPublication(manifest, manifest_hash, commit_id, self.repository.checkout_state(commit_id))

    def read_public_artifact(self, publication_id: str, format: str, actor_subject: str | None = None) -> bytes:
        if format in PUBLIC_ARTIFACTS:
            name = PUBLIC_ARTIFACTS[format]
            publication = self.get(publication_id, actor_subject)
            return self.repository.read_file(publication_path(publication_id, name), publication.commit_id)
        if format not in PUBLICATION_FILES:
            raise ReportError('REPORT_INVALID')
        publication = self.get(publication_id, actor_subject)
        if publication.manifest.schema_version != 2:
            raise ReportError('REPORT_INVALID')
        name = format
        return self.repository.read_file(publication_path(publication_id, name), publication.commit_id)

    def snapshot(self, publication_id: str):
        publication = self.get(publication_id)
        data = self.repository.read_file(publication_path(publication_id, 'snapshot.json'), publication.commit_id)
        snapshot = snapshot_from_mapping(read_json(data))
        if canonical_bytes(snapshot) != data:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return publication, snapshot

    def list(self):
        publications = []
        for path in self.repository.list_files('report_publications'):
            if path.endswith('/manifest.json'):
                publication_id = path.split('/')[1]
                publications.append(self.get(publication_id))
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
