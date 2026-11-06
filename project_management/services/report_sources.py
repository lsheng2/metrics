from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json, decode_snapshot
from project_management.app.domain.capture_validation import item_key
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import (
    ReportLimits,
    ReportMessage,
    ReportError,
    ReportRow,
    ReportSelection,
    ReportSourceError,
    ReportSourceSnapshot,
    SummaryReference,
)
from project_management.app.domain.report_values import report_hash
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.summary_input import complete_source, unchanged_since
from project_management.services.summary_material import verified_accepted_material
from project_management.services.report_source_values import (
    checked_limits,
    json_copy,
    report_date,
    safe_source_url,
    tuple_json,
    validated_selection,
)
from project_management.services.report_publication_reads import ReportPublicationResolver
from project_management.services.report_membership import ScopeMember, ScopeMembershipSnapshot


COMPARISON_POLICY_HASH = report_hash({'policy': 'initial-baseline', 'version': 1})


class PinnedReadRepository:
    def __init__(self, archive, repository, commit):
        self._archive = archive
        self._repository = repository
        self._commit = commit
        self.project = repository.project
        self.stage = repository.stage
        self.owner_subject = repository.owner_subject

    def head(self):
        return self._commit

    def read_file(self, git_path: str, commit: str = 'main') -> bytes:
        return self._repository.read_file(git_path, self._commit if commit == 'main' else commit)

    def list_files(self, prefix: str, commit: str = 'main') -> tuple[str, ...]:
        return self._repository.list_files(prefix, self._commit if commit == 'main' else commit)

    def commit_for_path(self, git_path: str) -> str:
        commit = self.find_commit_for_path(git_path)
        if commit is None:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return commit

    def find_commit_for_path(self, git_path: str, commit: str = 'main') -> str | None:
        return self._repository.find_commit_for_path(git_path, self._commit if commit == 'main' else commit)

    def publication_source_chain(self, source_key):
        return self._archive._source_chain(self, source_key, self._commit)

    def parent_for_commit(self, commit_id: str) -> str | None:
        return self._repository.parent_for_commit(commit_id)

    def checkout_state(self, commit_id: str) -> str:
        return self._repository.checkout_state(commit_id)


class ReportSourceReader:
    def __init__(self, archive, contract, limits: ReportLimits | None = None):
        self.archive = archive
        self.contract = contract
        self.limits = checked_limits(limits)

    def read(self, actor, project_id, stage_id, selection: ReportSelection) -> ReportSourceSnapshot:
        timezone = validated_selection(selection)
        if selection.parent_publication_id is not None:
            snapshot = ReportPublicationResolver(self.archive).parent_snapshot(actor, project_id, stage_id, selection)
            if len(canonical_bytes(snapshot)) > self.limits.max_snapshot_bytes:
                raise ReportSourceError('REPORT_LIMIT')
            return snapshot
        project, stage = self.archive._stage_for_read(actor, project_id, stage_id)
        if stage.source_status != 'current':
            raise ReportSourceError('REPORT_SOURCE_CHANGED')
        self.archive._validate_root_before_lock()
        repository = self.archive.repository_factory.open(self.archive.config, project, stage, actor.subject)
        repository.verify_identity()
        head = repository.head()
        if head is None:
            raise ReportSourceError('REPORT_NOT_FOUND')
        try:
            snapshot = self.read_from_repository(actor, project, stage, repository, selection, head)
        except ReportSourceError:
            raise
        except (ArchiveError, AnalysisError, ReportError):
            raise ReportSourceError('REPORT_SOURCE_CHANGED') from None
        self._final_recheck(actor, project, stage, repository, head)
        if len(canonical_bytes(snapshot)) > self.limits.max_snapshot_bytes:
            raise ReportSourceError('REPORT_LIMIT')
        return snapshot

    def read_from_repository(self, actor, project, stage, repository, selection, head):
        timezone = validated_selection(selection)
        pinned = PinnedReadRepository(self.archive, repository, head)
        snapshot = self._snapshot(actor, project, stage, pinned, selection, timezone, head)
        snapshot = ReportPublicationResolver(self.archive).same_source_baseline(
            pinned, snapshot, selection.baseline_publication_id,
        )
        if len(canonical_bytes(snapshot)) > self.limits.max_snapshot_bytes:
            raise ReportSourceError('REPORT_LIMIT')
        return snapshot

    def membership(self, actor, project_id, stage_id, snapshot) -> ScopeMembershipSnapshot:
        return self.archive.read_report_membership(actor, project_id, stage_id, snapshot)

    def _snapshot(self, actor, project, stage, repository, selection, timezone, head):
        manifest_paths = [path for path in repository.list_files('captures') if path.endswith('/manifest.json')]
        if len(manifest_paths) > self.limits.max_captures:
            raise ReportSourceError('REPORT_LIMIT')
        manifests = self.archive._manifests(repository, head)
        selected = self.archive._read_manifest(repository, selection.capture_id)
        self._validate_manifest_identity(stage, selected)
        if not manifests or selected != manifests[-1]:
            raise ReportSourceError('REPORT_SOURCE_CHANGED')
        if selected.membership.coverage.state != 'complete':
            raise ReportSourceError('REPORT_SOURCE_CHANGED')
        if len(selected.membership.items) > self.limits.max_members:
            raise ReportSourceError('REPORT_LIMIT')
        rows = []
        row_bytes = 0
        for identity in sorted(selected.membership.items, key=item_key):
            row = self._row(repository, project, stage, selected, identity)
            row_bytes += len(canonical_bytes(row))
            if row_bytes > self.limits.max_snapshot_bytes:
                raise ReportSourceError('REPORT_LIMIT')
            rows.append(row)
        rows = tuple(rows)
        accepted_count = sum(1 for row in rows if row.summary_ref is not None and row.pending_reason is None)
        pending_count = len(rows) - accepted_count
        coverage = {
            'membership': json_copy(selected.membership.coverage),
            'members_count': len(rows),
            'accepted_count': accepted_count,
            'pending_count': pending_count,
            'complete': selected.membership.coverage.state == 'complete' and pending_count == 0,
            'comparison_state': 'initial_baseline',
        }
        return ReportSourceSnapshot(
            schema_version=1,
            project_id=project.id,
            stage_id=stage.id,
            project_name=project.name,
            stage_name=stage.name,
            owner_subject=actor.subject,
            rule_hash=stage.definition_hash,
            source_commit=head,
            capture_id=selected.intent.capture_id,
            source_as_of=selected.finalized_at,
            report_date=report_date(selected.finalized_at, timezone),
            timezone=selection.timezone,
            baseline_publication_id=selection.baseline_publication_id,
            comparison_policy_hash=COMPARISON_POLICY_HASH,
            coverage=coverage,
            key_messages=(self._coverage_message(accepted_count, pending_count),),
            rows=rows,
            events=(),
            days=(),
        )

    def _row(self, repository, project, stage, manifest, identity):
        source_key = self.archive._source_key(manifest.intent, identity)
        source_ref = self._snapshot_ref(manifest, identity)
        if source_ref is None:
            return self._pending_row(stage, source_key, identity, None, None, 'source_missing')
        payload = repository.read_file(source_ref.git_path)
        if len(payload) > self.limits.max_snapshot_bytes:
            raise ReportSourceError('REPORT_LIMIT')
        source = decode_snapshot(payload)
        if self.archive._source_hash(source) != source_ref.source_hash or source.identity != identity:
            raise ArchiveError('ARCHIVE_RAW_PAGE_INTEGRITY_FAILED')
        if not complete_source(source):
            return self._pending_row(stage, source_key, identity, source_ref.source_hash, source, 'source_incomplete')
        chain = tuple(self.archive._source_chain(repository, source_key, repository.head()))
        accepted, _ = self.archive._analysis_accepted(repository, source_key)
        if accepted is None:
            return self._pending_row(stage, source_key, identity, source_ref.source_hash, source, 'summary_pending')
        usable = self._accepted_material(repository, source_key, chain, accepted, source_ref, source)
        if not usable:
            return self._pending_row(stage, source_key, identity, source_ref.source_hash, source, 'summary_stale')
        attempt, summary_snapshot, candidate, original_input = usable
        evidence_by_id = {row['ref_id']: row for row in original_input['evidence']}
        evidence = tuple(json_copy(evidence_by_id[ref_id]) for ref_id in self._evidence_refs(candidate))
        key_hash = content_hash(source_key)
        summary_path = f'accepted_summaries/{key_hash}/{accepted.revision:08d}.json'
        return ReportRow(
            source_key=source_key,
            identity=identity,
            title=self._text(source.facts.get('summary')),
            status=self._text(source.facts.get('status')),
            assignee=json_copy(source.facts.get('assignee')) if source.facts.get('assignee') is not None else None,
            source_url=safe_source_url(stage.descriptor, identity),
            source_hash=source_ref.source_hash,
            coverage=json_copy(source.coverage),
            summary_ref=SummaryReference(
                accepted.summary_id,
                accepted.revision,
                accepted.target_capture_id,
                accepted.source_hash,
                accepted.input_hash,
                accepted.run_result['sha256'],
                repository.commit_for_path(summary_path),
            ),
            what=candidate['what'],
            current_position=candidate['current_position'],
            verification=candidate['verification'],
            next_actions=tuple_json(candidate['next_actions']),
            blocker_refs=tuple(candidate['blockers']),
            limitation_refs=tuple(candidate['limitations']),
            evidence=evidence,
            summary_as_of=summary_snapshot.get('terminalAt'),
            pending_reason=None,
        )

    def _accepted_material(self, repository, source_key, chain, accepted, current_reference, current_source):
        sources = tuple(current_source if reference == current_reference
                        else decode_snapshot(repository.read_file(reference.git_path)) for reference in chain)
        material = verified_accepted_material(self.archive, repository, source_key, self.contract, chain, sources)
        if not material or material[-1].summary != accepted:
            raise AnalysisError('ANALYSIS_RESULT_INVALID')
        if not unchanged_since(accepted.target_capture_id, accepted.source_hash, chain):
            return None
        start = next(index for index, row in enumerate(chain) if row.capture_id == accepted.target_capture_id)
        for source in sources[start:]:
            if not complete_source(source):
                return None
        latest = material[-1]
        return latest.attempt, latest.snapshot, accepted.candidate, decode_json(latest.prepared.input_content.encode('utf-8'))

    def _pending_row(self, stage, source_key, identity, source_hash, source, reason):
        return ReportRow(
            source_key=source_key,
            identity=identity,
            title=self._text(source.facts.get('summary')) if source else None,
            status=self._text(source.facts.get('status')) if source else None,
            assignee=json_copy(source.facts.get('assignee')) if source and source.facts.get('assignee') is not None else None,
            source_url=safe_source_url(stage.descriptor, identity),
            source_hash=source_hash,
            coverage=json_copy(source.coverage) if source else {},
            summary_ref=None,
            what=None,
            current_position=None,
            verification=None,
            next_actions=(),
            blocker_refs=(),
            limitation_refs=(),
            evidence=(),
            summary_as_of=None,
            pending_reason=reason,
        )

    def _final_recheck(self, actor, project, stage, repository, head):
        refreshed_project, refreshed_stage = self.archive._stage_for_read(actor, project.id, stage.id)
        if (repository.head() != head or refreshed_project != project or refreshed_stage != stage):
            raise ReportSourceError('REPORT_SOURCE_CHANGED')

    def _snapshot_ref(self, manifest, identity):
        key = item_key(identity)
        return next((row for row in manifest.snapshots if item_key(row.identity) == key), None)

    def _validate_manifest_identity(self, stage, manifest):
        source = manifest.intent.source
        if (source.provider_id != stage.descriptor.provider_id
                or source.endpoint_url != stage.descriptor.endpoint
                or source.rule_hash != stage.definition_hash
                or not source.principal_id
                or not source.endpoint_id):
            raise ReportSourceError('REPORT_SOURCE_CHANGED')
        for identity in manifest.membership.items:
            if identity.provider_id != source.provider_id or identity.endpoint_id != source.endpoint_id:
                raise ReportSourceError('REPORT_SOURCE_CHANGED')
        for reference in manifest.snapshots:
            if (reference.identity.provider_id != source.provider_id
                    or reference.identity.endpoint_id != source.endpoint_id):
                raise ReportSourceError('REPORT_SOURCE_CHANGED')

    def _evidence_refs(self, candidate):
        refs = []
        for ref_id in candidate['evidence']:
            if ref_id not in refs:
                refs.append(ref_id)
        for action in candidate['next_actions']:
            for ref_id in action['evidence']:
                if ref_id not in refs:
                    refs.append(ref_id)
        for field in ('blockers', 'limitations'):
            for ref_id in candidate[field]:
                if ref_id not in refs:
                    refs.append(ref_id)
        return tuple(refs)

    def _coverage_message(self, accepted_count, pending_count):
        return ReportMessage(
            'coverage',
            f'{accepted_count} accepted summaries and {pending_count} pending items.',
            (),
        )

    def _text(self, value):
        if isinstance(value, dict) and isinstance(value.get('name'), str):
            return value['name']
        return value if isinstance(value, str) else None
