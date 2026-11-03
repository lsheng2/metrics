from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import hashlib
import uuid
import unittest

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json, sha256_bytes
from project_management.app.domain.captures import (
    CaptureManifest,
    MembershipInput,
    PartCoverage,
    StoredSnapshotRef,
    WorkItemIdentity,
)
from project_management.app.domain.contracts import ProjectActor, ProjectError, ScopeDescriptor
from project_management.app.domain.summary_contracts import AcceptedSummary, AnalysisAttempt
from project_management.app.domain.summary_input import build_initial_input
from project_management.app.api.reports import ReportError, ReportLimits, ReportSelection
from project_management.app.api.reports import ReportSourceReader
from project_management.services.report_source_values import checked_limits, safe_source_url, validated_selection
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_source_fixtures import ReportSourceScenario
from project_management.tests.report_source_memory import (
    CountingArchive,
    DriftingProjectApi,
    MemoryCaptureArchiveService,
    MemoryRepository,
    MemoryRepositoryFactory,
)


class TestReportSourceReader(ReportSourceScenario, unittest.TestCase):
    def test_shouldReadAcceptedSummarySourceWithoutMutatingArchive(self):
        with self.archive_service() as (root, archive):
            captured = self.capture_summary_source(archive)
            _, accepted = self.accept_summary(archive, captured.source_key)
            before_head = self.archive_head(root)
            before_files = self.archive_files(root)
            before_status = self.archive_status(root)
            before_tree = self.filesystem_tree(root)

            snapshot = self.read_report_source(archive, captured.capture_id)

            self.assertEqual(before_head, self.archive_head(root))
            self.assertEqual(before_files, self.archive_files(root))
            self.assertEqual(before_status, self.archive_status(root))
            self.assertEqual(before_tree, self.filesystem_tree(root))
            self.assertEqual(1, snapshot.schema_version)
            self.assertEqual(('Alpha', 'Release 1'), (snapshot.project_name, snapshot.stage_name))
            self.assertEqual(before_head, snapshot.source_commit)
            self.assertEqual('initial_baseline', snapshot.coverage['comparison_state'])
            self.assertEqual((1, 0, True), (
                snapshot.coverage['accepted_count'],
                snapshot.coverage['pending_count'],
                snapshot.coverage['complete'],
            ))
            row = snapshot.rows[0]
            self.assertEqual('https://tracker.example.test/jira/browse/ALPHA-1', row.source_url)
            self.assertEqual(('Intermittent validation failure', 'Fixed'), (row.title, row.status))
            self.assertEqual({'key': 'dev-a', 'displayName': 'Alice'}, row.assignee)
            self.assertEqual(captured.source_hash, row.source_hash)
            self.assertIsNone(row.pending_reason)
            self.assertEqual('Bob (qa-b), please rerun validation on build r8.',
                             row.next_actions[0]['owner_quote'])
            self.assertEqual(('201', '202', '203'), tuple(
                item['source_id'] for item in row.evidence if item['kind'] == 'comment'
            ))
            self.assertEqual(('2026-11-02T00:00:30.000Z', accepted.summary_id, 1), (
                row.summary_as_of,
                row.summary_ref.summary_id,
                row.summary_ref.revision,
            ))
            self.assertRegex(sha256_bytes(canonical_bytes(snapshot)), r'^[a-f0-9]{64}$')

    def test_shouldProjectCompleteMembershipWithMissingOrIncompleteDetailsAsPending(self):
        archive, repository, capture_id = self.memory_reader_with_capture(include_snapshot=False, complete=False)

        snapshot = self.read_memory_report(archive, repository, capture_id)

        self.assertEqual((0, 1, False), (
            snapshot.coverage['accepted_count'],
            snapshot.coverage['pending_count'],
            snapshot.coverage['complete'],
        ))
        self.assertEqual('source_missing', snapshot.rows[0].pending_reason)
        self.assertEqual('ALPHA-1', snapshot.rows[0].identity.display_key)

        _, base = self.summary_source()
        partial = replace(
            base,
            facts=dict(base.facts, status={'id': '10001', 'name': 'Fixed'}),
            coverage=replace(base.coverage, history=PartCoverage('partial', None, 0, None, 'not_complete')),
        )
        capture = self.memory_capture(snapshot=partial, complete=False)
        archive, repository = self.memory_archive(capture['files'])
        partial_snapshot = self.read_memory_report(archive, repository, capture['capture_id'])
        self.assertEqual(('source_incomplete', 'Fixed'), (
            partial_snapshot.rows[0].pending_reason,
            partial_snapshot.rows[0].status,
        ))

    def test_shouldRefuseIncompleteMembershipWithoutOmittingRows(self):
        capture = self.memory_capture(include_snapshot=False, membership_state='partial')
        archive, repository = self.memory_archive(capture['files'])

        with self.assertRaises(ReportError) as caught:
            self.read_memory_report(archive, repository, capture['capture_id'])

        self.assertEqual('REPORT_SOURCE_CHANGED', caught.exception.code)

    def test_shouldReuseOriginalSummaryReferenceForSameSourceRecapture(self):
        first = self.memory_capture()
        second = self.memory_capture(previous=first['ref'], snapshot=first['snapshot'])
        files = {**first['files'], **second['files']}
        self.add_memory_acceptance(files, first['ref'], first['snapshot'], first['source_key'])
        archive, repository = self.memory_archive(files)

        snapshot = self.read_memory_report(archive, repository, second['capture_id'])

        self.assertEqual((second['capture_id'], 1, 0, True), (
            snapshot.capture_id,
            snapshot.coverage['accepted_count'],
            snapshot.coverage['pending_count'],
            snapshot.coverage['complete'],
        ))
        self.assertEqual((first['capture_id'], '2026-11-02T00:00:30.000Z'), (
            snapshot.rows[0].summary_ref.target_capture_id,
            snapshot.rows[0].summary_as_of,
        ))

    def test_shouldKeepEqualHashPartialCoveragePendingInsteadOfReusingAcceptedSummary(self):
        first = self.memory_capture()
        partial = replace(
            first['snapshot'],
            coverage=replace(first['snapshot'].coverage, history=PartCoverage('partial', None, 0, None, 'not_complete')),
        )
        second = self.memory_capture(previous=first['ref'], snapshot=partial, complete=False)
        files = {**first['files'], **second['files']}
        self.add_memory_acceptance(files, first['ref'], first['snapshot'], first['source_key'])
        archive, repository = self.memory_archive(files)

        snapshot = self.read_memory_report(archive, repository, second['capture_id'])

        self.assertEqual((0, 1, 'source_incomplete'), (
            snapshot.coverage['accepted_count'],
            snapshot.coverage['pending_count'],
            snapshot.rows[0].pending_reason,
        ))

    def test_shouldPreserveActionEvidenceWhenCandidateEvidenceIsNarrower(self):
        archive, repository, capture_id = self.memory_reader_with_capture(output='narrow_evidence')

        snapshot = self.read_memory_report(archive, repository, capture_id)

        refs = tuple(row['ref_id'] for row in snapshot.rows[0].evidence)
        self.assertEqual(('fields', 'comment:203'), refs)

    def test_shouldRefuseStoredSourceAndSummaryCorruption(self):
        cases = {
            'manifest_endpoint': lambda files, paths: self.mutate_manifest(
                files, paths['manifest'], lambda manifest: replace(
                    manifest,
                    intent=replace(manifest.intent, source=replace(
                        manifest.intent.source,
                        endpoint_url='https://evil.example.test/jira',
                    )),
                ),
            ),
            'candidate': lambda files, paths: self.mutate_accepted(
                files, paths['accepted'], lambda envelope: self.replace_summary(
                    envelope,
                    candidate=dict(envelope['payload']['summary']['candidate'], what='spoofed'),
                ),
            ),
            'result_hash': lambda files, paths: self.mutate_accepted(
                files, paths['accepted'], lambda envelope: self.replace_summary(
                    envelope,
                    run_result=dict(envelope['payload']['summary']['run_result'], sha256='0' * 64),
                ),
            ),
            'summary_id': lambda files, paths: self.mutate_accepted(
                files, paths['accepted'], lambda envelope: self.replace_summary(
                    envelope,
                    summary_id=str(uuid.uuid4()),
                ),
            ),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                archive, repository, capture_id, paths = self.memory_reader_with_capture(return_paths=True)
                mutate(repository.files, paths)

                with self.assertRaises(ReportError) as caught:
                    self.read_memory_report(archive, repository, capture_id)

                self.assertEqual('REPORT_SOURCE_CHANGED', caught.exception.code)

    def test_shouldRefuseConfiguredSourceDriftAndWrongOwnerBeforeReads(self):
        changed_stage = replace(self.stage, source_status='source_changed')
        archive, repository, capture_id = self.memory_reader_with_capture(stage=changed_stage)

        with self.assertRaises(ReportError) as caught:
            self.read_memory_report(archive, repository, capture_id, stage=changed_stage)

        self.assertEqual('REPORT_SOURCE_CHANGED', caught.exception.code)
        self.assertEqual([], repository.reads)

        archive, repository, capture_id = self.memory_reader_with_capture()
        factory = archive.repository_factory
        with self.assertRaises(ProjectError):
            archive.read_report_material(
                ProjectActor('other-owner'),
                self.project.id,
                self.stage.id,
                ReportSelection(capture_id=capture_id),
                contract=self.contract,
            )
        self.assertEqual(0, factory.opens)

    def test_shouldRefuseHeadAndCatalogMutationDuringQuery(self):
        archive, repository, capture_id = self.memory_reader_with_capture()

        def drift_head(repo, path):
            if path.endswith('/manifest.json'):
                repo.commit = 'd' * 40

        repository.on_read = drift_head
        with self.assertRaises(ReportError) as caught:
            self.read_memory_report(archive, repository, capture_id)
        self.assertEqual('REPORT_SOURCE_CHANGED', caught.exception.code)

        archive, repository, capture_id = self.memory_reader_with_capture()
        changed_descriptor = replace(self.stage.descriptor, query='project = BETA')
        changed_stage = replace(
            self.stage,
            descriptor=changed_descriptor,
            definition_hash=changed_descriptor.definition_hash(),
        )
        archive.project_api = DriftingProjectApi(self.project, self.stage, changed_stage)
        with self.assertRaises(ReportError) as caught:
            self.read_memory_report(archive, repository, capture_id)
        self.assertEqual('REPORT_SOURCE_CHANGED', caught.exception.code)

    def test_shouldReturnPendingForSameSourceRecaptureButChangedChain(self):
        first = self.memory_capture()
        second = self.memory_capture(previous=first['ref'], snapshot=replace(
            first['snapshot'],
            facts=dict(first['snapshot'].facts, status='Reopened'),
        ))
        third = self.memory_capture(previous=second['ref'], snapshot=first['snapshot'])
        files = {**first['files'], **second['files'], **third['files']}
        self.add_memory_acceptance(files, first['ref'], first['snapshot'], first['source_key'])
        archive, repository = self.memory_archive(files)

        snapshot = self.read_memory_report(archive, repository, third['capture_id'])

        self.assertEqual((0, 1, 'summary_stale'), (
            snapshot.coverage['accepted_count'],
            snapshot.coverage['pending_count'],
            snapshot.rows[0].pending_reason,
        ))

    def test_shouldRejectInvalidSelectionsLimitsAndUnsafeSourceUrls(self):
        valid_id = str(uuid.uuid4())
        self.assertIsNotNone(validated_selection(ReportSelection(capture_id=valid_id, timezone='UTC')))
        with self.assertRaises(ReportError):
            validated_selection(ReportSelection(capture_id=valid_id, timezone='Mars/Base'))
        self.assertIsNotNone(validated_selection(ReportSelection(
            capture_id=valid_id,
            baseline_publication_id=str(uuid.uuid4()),
        )))
        self.assertIsNotNone(validated_selection(ReportSelection(
            capture_id=valid_id,
            parent_publication_id=str(uuid.uuid4()),
        )))
        for limits in (ReportLimits(max_members=0), ReportLimits(max_members=-1), ReportLimits(max_members=True)):
            with self.assertRaises(ReportError):
                checked_limits(limits)
        descriptor = ScopeDescriptor('jira', 'profile', 'https://tracker.example.test/jira',
                                     'scope:1', 'jql', 'project = ALPHA', 'v1')
        good = WorkItemIdentity('jira', 'endpoint', '10001', 'ALPHA-1')
        unsafe_endpoint = replace(descriptor, endpoint='https://tracker.example.test/ji\tra')
        unsafe_key = replace(good, display_key='ALPHA-1\\x')
        unknown = replace(descriptor, provider_id='hsd')
        self.assertEqual('https://tracker.example.test/jira/browse/ALPHA-1', safe_source_url(descriptor, good))
        self.assertIsNone(safe_source_url(unsafe_endpoint, good))
        self.assertIsNone(safe_source_url(descriptor, unsafe_key))
        self.assertIsNone(safe_source_url(unknown, good))

    def test_shouldSupportPublicReaderConstructionWithoutExposingPinnedWriterHandles(self):
        archive, repository, capture_id = self.memory_reader_with_capture()
        reader = ReportSourceReader(archive, self.contract)

        snapshot = reader.read(self.actor, self.project.id, self.stage.id, ReportSelection(capture_id=capture_id))

        self.assertEqual(capture_id, snapshot.capture_id)
        from project_management.services.report_sources import PinnedReadRepository

        pinned = PinnedReadRepository(repository, repository.head())
        self.assertFalse(hasattr(pinned, 'stage_root'))
        self.assertFalse(hasattr(pinned, 'archive'))
        self.assertFalse(hasattr(pinned, 'objects'))
        self.assertFalse(hasattr(pinned, 'runtime'))
        self.assertFalse(hasattr(pinned, 'git'))

    def test_shouldRefuseAggregateRowBytesBeforeReadingAllRows(self):
        capture = self.memory_capture(include_snapshot=False, member_count=100, complete=False)
        archive, repository = self.memory_archive(capture['files'])
        counting = CountingArchive(archive, fail_after=2)

        with self.assertRaises(ReportError) as caught:
            ReportSourceReader(counting, self.contract, ReportLimits(max_snapshot_bytes=1)).read(
                self.actor,
                self.project.id,
                self.stage.id,
                ReportSelection(capture_id=capture['capture_id']),
            )

        self.assertEqual('REPORT_LIMIT', caught.exception.code)

    def memory_reader_with_capture(self, *, stage=None, output=None, include_snapshot=True,
                                   complete=True, return_paths=False):
        capture = self.memory_capture(stage=stage, include_snapshot=include_snapshot, complete=complete)
        if include_snapshot and complete:
            paths = self.add_memory_acceptance(
                capture['files'],
                capture['ref'],
                capture['snapshot'],
                capture['source_key'],
                stage=stage,
                output=output,
            )
        else:
            paths = {'manifest': capture['manifest_path']}
        archive, repository = self.memory_archive(capture['files'], stage=stage)
        if return_paths:
            return archive, repository, capture['capture_id'], paths | {'manifest': capture['manifest_path']}
        return archive, repository, capture['capture_id']

    def memory_archive(self, files, *, stage=None):
        stage = stage or self.stage
        repository = MemoryRepository(self.project, stage, files)
        archive = MemoryCaptureArchiveService(
            ProjectApiStub(self.project, stage),
            MemoryRepositoryFactory(repository),
            SimpleNamespace(
                root=Path('memory-root'),
                limits=self.limits(),
                author_name='Archive Test',
                author_email='archive@example.test',
            ),
        )
        return archive, repository

    def read_memory_report(self, archive, repository, capture_id, *, stage=None):
        return archive.read_report_material(
            self.actor,
            self.project.id,
            (stage or self.stage).id,
            ReportSelection(capture_id=capture_id),
            contract=self.contract,
        )

    def memory_capture(self, *, stage=None, previous=None, snapshot=None, include_snapshot=True,
                       complete=True, member_count=1, membership_state='complete'):
        stage = stage or self.stage
        capture_id = str(uuid.uuid4())
        intent = replace(
            self.intent(capture_id=capture_id),
            stage_id=stage.id,
            required_parts=('facts', 'comments', 'history'),
            source=replace(
                self.intent().source,
                endpoint_url=stage.descriptor.endpoint,
                rule_hash=stage.definition_hash,
            ),
        )
        _, base = self.summary_source()
        source = replace(snapshot or base, raw_page_ids=())
        members = tuple(
            replace(source.identity, stable_id=f'ALPHA-{index}', display_key=f'ALPHA-{index}')
            for index in range(1, member_count + 1)
        )
        if member_count == 1:
            members = (source.identity,)
        refs = ()
        files = {}
        source_key = self.source_key(intent, source.identity)
        sequence = 1 if previous is None else previous.sequence + 1
        if include_snapshot:
            ref = StoredSnapshotRef(
                source.identity,
                capture_id,
                sequence,
                previous.capture_id if previous else None,
                self.archive_source_hash(source),
                f'captures/{capture_id}/snapshots/{self.archive_source_hash(source)}.json',
            )
            files[ref.git_path] = canonical_bytes(source)
            refs = (ref,)
        else:
            ref = None
        membership = MembershipInput(
            members,
            PartCoverage(membership_state, 'source-version-1', len(members), len(members), None),
            (),
        )
        manifest = CaptureManifest(
            1,
            intent,
            membership,
            refs,
            (),
            complete,
            None if complete else 'SOURCE_INCOMPLETE',
            f'2026-11-02T00:00:{sequence:02d}+00:00',
            f'2026-11-02T00:00:{sequence + 30:02d}+00:00',
        )
        manifest_path = f'captures/{capture_id}/manifest.json'
        files[manifest_path] = canonical_bytes(manifest)
        return {
            'capture_id': capture_id,
            'files': files,
            'ref': ref,
            'snapshot': source,
            'source_key': source_key,
            'manifest_path': manifest_path,
        }

    def add_memory_acceptance(self, files, ref, source, source_key, *, stage=None, output=None):
        stage = stage or self.stage
        prepared = build_initial_input(
            self.project.id,
            stage,
            source_key,
            ref,
            source,
            f"{self.contract.profile_ref['key']}@{self.contract.profile_ref['revision']}",
        )
        attempt_id = str(uuid.uuid5(uuid.UUID(stage.id), prepared.input_hash))
        attempt = AnalysisAttempt(
            attempt_id,
            self.project.id,
            stage.id,
            source_key,
            self.backend(),
            prepared,
            self.request_for_attempt(attempt_id, prepared),
            self.contract.definition_hash,
            self.contract.output_schema_hash,
        )
        if output == 'narrow_evidence':
            output = self.output(prepared)
            output['evidence'] = ['fields']
        snapshot, result = self.responses(attempt, output=output)
        candidate = self.contract.validate_result(attempt, snapshot, result)
        accepted = AcceptedSummary(
            str(uuid.uuid5(uuid.UUID(attempt_id), 'accepted')),
            1,
            ref.capture_id,
            ref.source_hash,
            self.contract.definition_hash,
            prepared.input_hash,
            candidate,
            decode_json(canonical_bytes(result)),
        )
        intent = {'schema_version': 1, 'kind': 'intent', 'attempt_id': attempt_id, 'payload': attempt}
        dispatch = {
            'schema_version': 1,
            'kind': 'dispatch',
            'attempt_id': attempt_id,
            'payload': {'intent_hash': content_hash(intent)},
        }
        key_hash = content_hash(source_key)
        accepted_path = f'accepted_summaries/{key_hash}/00000001.json'
        files[f'analysis_attempts/{attempt_id}/intent.json'] = canonical_bytes(intent)
        files[f'analysis_attempts/{attempt_id}/dispatch.json'] = canonical_bytes(dispatch)
        files[accepted_path] = canonical_bytes({
            'schema_version': 1,
            'kind': 'accepted',
            'attempt_id': attempt_id,
            'payload': {'summary': accepted, 'snapshot': snapshot},
            'source_key_hash': key_hash,
            'revision': 1,
        })
        return {'accepted': accepted_path}

    def request_for_attempt(self, attempt_id, prepared):
        return {
            'clientRunKey': attempt_id,
            'scopeKey': f'projects.{self.project.id}.stages.{self.stage.id}',
            'profile': self.contract.profile_ref,
            'input': {'mediaType': 'application/json', 'content': prepared.input_content,
                      'sha256': prepared.input_hash},
            'logicalInputHash': {'algorithm': 'dashboard-json-review-1', 'digest': prepared.input_hash},
            'deadlineAt': (datetime.now(UTC) + timedelta(minutes=5)).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'limits': {'maxInputBytes': len(prepared.input_content.encode()), 'maxOutputBytes': 65536,
                       'maxInputTokens': None, 'maxOutputTokens': None},
            'minimumResultRetentionSeconds': 60,
        }

    def archive_source_hash(self, snapshot):
        return content_hash({
            'identity': snapshot.identity,
            'facts': snapshot.facts,
            'comments_by_id': snapshot.comments_by_id,
            'history_by_id': snapshot.history_by_id,
            'attachments_by_id': snapshot.attachments_by_id,
            'dependencies_by_id': snapshot.dependencies_by_id,
        })

    def mutate_manifest(self, files, path, mutate):
        from project_management.app.domain.capture_values import manifest_from_bytes

        files[path] = canonical_bytes(mutate(manifest_from_bytes(files[path])))

    def mutate_accepted(self, files, path, mutate):
        files[path] = canonical_bytes(mutate(decode_json(files[path])))

    def replace_summary(self, envelope, **changes):
        summary = dict(envelope['payload']['summary'])
        summary.update(changes)
        payload = dict(envelope['payload'], summary=summary)
        return dict(envelope, payload=payload)

    def filesystem_tree(self, root):
        rows = []
        for path in sorted(item for item in root.rglob('*') if item.is_file()):
            relative = path.relative_to(root).as_posix()
            rows.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
        return tuple(rows)
