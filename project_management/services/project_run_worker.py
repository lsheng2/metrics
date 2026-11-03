from dataclasses import replace
import asyncio
import time
import uuid

from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError, ReportSelection
from project_management.app.domain.run_contracts import ItemRunResult, RunError
from project_management.app.domain.run_values import draft_command_id, parse_instant
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.summary_input import complete_source
from project_management.services.project_runs import replace_item


class ProjectRunWorker:
    def __init__(self, run_service, *, monotonic=None):
        self.run_service = run_service
        self.monotonic = monotonic or time.monotonic

    def execute(self, actor, project_id, stage_id, operation_id):
        try:
            with self.run_service.execution_lock(actor, project_id, stage_id):
                operation = self.run_service.get(actor, project_id, stage_id, operation_id)
                if operation.state in {'draft_ready', 'partial', 'canceled', 'failed'}:
                    return operation
                if operation.cancel_requested:
                    return self._finish_canceled(actor, project_id, stage_id, operation, self._cancel_phase())
                operation = self._claim_capture(actor, project_id, stage_id, operation)
                receipt = self._capture(actor, project_id, stage_id, operation)
                if not receipt.complete:
                    return self._partial(actor, project_id, stage_id, operation.operation_id,
                                         'RUN_CAPTURE_UNCERTAIN', operation.item_results)
                manifest = self.run_service.archive.read_capture(actor, project_id, stage_id, operation.capture_id)
                operation = self._transition(actor, project_id, stage_id, operation.operation_id,
                                             lambda current: replace(current, state='analyzing',
                                                                     revision=current.revision + 1))
                operation = self._analyze(actor, project_id, stage_id, operation, manifest)
                if operation.state in {'draft_ready', 'partial', 'canceled', 'failed'}:
                    return operation
                if operation.cancel_requested:
                    return self._finish_canceled(actor, project_id, stage_id, operation, self._cancel_phase())
                return self._draft(actor, project_id, stage_id, operation)
        except RunError:
            raise
        except ArchiveError as error:
            raise self.run_service._run_error(error) from None

    def _claim_capture(self, actor, project_id, stage_id, operation):
        if operation.state not in {'queued', 'interrupted'}:
            return operation
        return self._transition(actor, project_id, stage_id, operation.operation_id,
                                lambda current: replace(current, state='capturing',
                                                        revision=current.revision + 1))

    def _capture(self, actor, project_id, stage_id, operation):
        try:
            manifest = self.run_service.archive.read_capture(actor, project_id, stage_id, operation.capture_id)
            return self.run_service.archive._receipt_from_manifest(
                self.run_service.archive._read_repository(actor, project_id, stage_id),
                manifest,
            )
        except ArchiveError as error:
            if error.code not in {'ARCHIVE_MANIFEST_INVALID', 'ARCHIVE_RAW_PAGE_MISSING'}:
                raise
        context = self.run_service.capture_context(operation)
        return self.run_service.capture_service.capture(
            context,
            cancel_requested=lambda: self.run_service.get(actor, project_id, stage_id, operation.operation_id).cancel_requested,
        )

    def _analyze(self, actor, project_id, stage_id, operation, manifest):
        cancel_phase = self._cancel_phase(start=False)
        results = self._membership_results(operation, manifest, actor, project_id, stage_id)
        operation = self._transition(actor, project_id, stage_id, operation.operation_id,
                                     lambda current: replace(current, item_results=results,
                                                             revision=current.revision + 1))
        prepared_count = sum(1 for item in operation.item_results
                             if item.attempt_id is not None or item.state in {'accepted', 'no_work'})
        unresolved = any(item.attempt_id is not None and item.state == 'pending'
                         for item in operation.item_results)
        for identity in manifest.membership.items:
            operation = self.run_service.get(actor, project_id, stage_id, operation.operation_id)
            if operation.cancel_requested:
                return self._finish_canceled(actor, project_id, stage_id, operation, cancel_phase)
            source_key = self.run_service.archive._source_key(manifest.intent, identity)
            key_hash = content_hash(source_key)
            current_result = next(row for row in operation.item_results if row.source_key_hash == key_hash)
            if current_result.state in {'accepted', 'no_work', 'canceled'} or current_result.error_code == 'ANALYSIS_SOURCE_INCOMPLETE':
                continue
            if current_result.attempt_id is not None:
                operation = self._advance_attempt(actor, project_id, stage_id, operation, current_result, key_hash, cancel_phase)
                unresolved = self._unresolved(operation, key_hash)
                if unresolved:
                    break
                continue
            if unresolved:
                continue
            if prepared_count >= self.run_service.operation_request(actor, project_id, stage_id, operation.operation_id)[1].max_analysis_items:
                operation = self._record_item(actor, project_id, stage_id, operation, key_hash,
                                              ItemRunResult(key_hash, 'pending', error_code='ANALYSIS_INPUT_LIMIT'))
                continue
            prepared_count += 1
            operation = self._prepare_and_advance(actor, project_id, stage_id, operation, source_key, key_hash, cancel_phase)
            unresolved = self._unresolved(operation, key_hash)
            if unresolved:
                break
        return operation

    def _membership_results(self, operation, manifest, actor, project_id, stage_id):
        existing = {item.source_key_hash: item for item in operation.item_results}
        results = []
        for identity in manifest.membership.items:
            source_key = self.run_service.archive._source_key(manifest.intent, identity)
            key_hash = content_hash(source_key)
            if key_hash in existing:
                results.append(existing.pop(key_hash))
                continue
            snapshot = self._snapshot(actor, project_id, stage_id, manifest, identity)
            if snapshot is None or not complete_source(snapshot):
                results.append(ItemRunResult(key_hash, 'pending', error_code='ANALYSIS_SOURCE_INCOMPLETE'))
            else:
                results.append(ItemRunResult(key_hash, 'pending'))
        if existing:
            raise RunError('RUN_STORAGE_INVALID')
        return tuple(results)

    def _prepare_and_advance(self, actor, project_id, stage_id, operation, source_key, key_hash, cancel_phase):
        _, policy, backend, _, _ = self.run_service.operation_request(actor, project_id, stage_id, operation.operation_id)
        try:
            prepared = self.run_service.analysis_service.prepare(
                actor,
                project_id,
                stage_id,
                source_key,
                backend=backend,
                deadline_at=parse_instant(operation.deadline_at),
                cancel_requested=lambda: self._cancel_requested(actor, project_id, stage_id, operation.operation_id),
            )
        except AnalysisError as error:
            return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                     ItemRunResult(key_hash, 'pending', error_code=error.code))
        if prepared.kind == 'no_work':
            return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                     ItemRunResult(key_hash, 'no_work',
                                                   accepted_summary_id=prepared.accepted.summary_id))
        operation = self._record_item(actor, project_id, stage_id, operation, key_hash,
                                      ItemRunResult(key_hash, 'running', prepared.attempt.attempt_id))
        if self._cancel_requested(actor, project_id, stage_id, operation.operation_id):
            return self._cancel_attempt(actor, project_id, stage_id, operation, key_hash,
                                        prepared.attempt.attempt_id, cancel_phase)
        return self._advance_attempt(actor, project_id, stage_id, operation,
                                     ItemRunResult(key_hash, 'running', prepared.attempt.attempt_id), key_hash,
                                     cancel_phase)

    def _advance_attempt(self, actor, project_id, stage_id, operation, current_result, key_hash, cancel_phase):
        _, policy, backend, _, _ = self.run_service.operation_request(actor, project_id, stage_id, operation.operation_id)
        step = None
        for _ in range(policy.max_observations_per_attempt):
            try:
                step = asyncio.run(self.run_service.analysis_service.advance(
                    actor,
                    project_id,
                    stage_id,
                    current_result.attempt_id,
                    backend=backend,
                    cancel_requested=lambda: self._cancel_requested(actor, project_id, stage_id, operation.operation_id),
                ))
            except AnalysisError as error:
                return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                         ItemRunResult(key_hash, 'pending', current_result.attempt_id,
                                                       error_code=error.code))
            if step.state not in {'queued', 'running'}:
                break
        if step is None or step.state in {'queued', 'running'}:
            return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                     ItemRunResult(key_hash, 'pending', current_result.attempt_id,
                                                   error_code='ANALYSIS_ATTEMPT_PENDING'))
        if step.state == 'accepted':
            return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                     ItemRunResult(key_hash, 'accepted', current_result.attempt_id,
                                                   step.accepted.summary_id))
        if step.state == 'canceled':
            return self._cancel_attempt(actor, project_id, stage_id, operation, key_hash,
                                        current_result.attempt_id, cancel_phase)
        return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                 ItemRunResult(key_hash, 'pending', current_result.attempt_id,
                                               error_code=step.error_code or f'ANALYSIS_{step.state.upper()}'))

    def _draft(self, actor, project_id, stage_id, operation):
        request, _, _, _, _ = self.run_service.operation_request(actor, project_id, stage_id, operation.operation_id)
        selection = ReportSelection(operation.capture_id, None, None, 'standup', request.timezone)
        draft_command = draft_command_id(operation.operation_id)
        template = request.template
        payload = {
            'schema_version': 1,
            'selection': selection,
            'template': template,
            'payload_hash': content_hash({'selection': selection, 'template': template}),
            'command_id': draft_command,
        }
        self.run_service.write_draft_selection(actor, project_id, stage_id, operation.operation_id, payload)
        try:
            draft = self.run_service.draft_service.create(
                actor,
                project_id,
                stage_id,
                command_id=draft_command,
                selection=selection,
                template=template,
            )
        except ReportError as error:
            return self._partial(actor, project_id, stage_id, operation.operation_id,
                                 self._report_error(error), operation.item_results)
        final_state = 'draft_ready'
        if any(item.state not in {'accepted', 'no_work'} for item in operation.item_results):
            final_state = 'partial'
        return self._transition(
            actor,
            project_id,
            stage_id,
            operation.operation_id,
            lambda current: replace(
                current,
                state=final_state,
                revision=current.revision + 1,
                draft_id=draft.draft_id,
                draft_revision=draft.revision,
                draft_revision_hash=draft.revision_hash,
                snapshot_hash=draft.snapshot_hash,
                template_hash=draft.template_definition.template_hash,
                error_code=None,
            ),
        )

    def _snapshot(self, actor, project_id, stage_id, manifest, identity):
        source_key = self.run_service.archive._source_key(manifest.intent, identity)
        try:
            return self.run_service.archive.read_snapshot(
                actor,
                project_id,
                stage_id,
                manifest.intent.capture_id,
                source_key,
            )
        except Exception:
            reference = next((row for row in manifest.snapshots if row.identity == identity), None)
            if reference is None:
                return None
            repository = self.run_service.archive._read_repository(
                actor,
                project_id,
                stage_id,
            )
            from project_management.app.domain.capture_values import decode_snapshot

            return decode_snapshot(repository.read_file(reference.git_path))

    def _record_item(self, actor, project_id, stage_id, operation, key_hash, item):
        return self._transition(actor, project_id, stage_id, operation.operation_id,
                                lambda current: replace(replace_item(current, key_hash, item),
                                                        revision=current.revision + 1))

    def _finish_canceled(self, actor, project_id, stage_id, operation, cancel_phase):
        for item in operation.item_results:
            if item.attempt_id is not None and item.state not in {'accepted', 'no_work'}:
                operation = self._cancel_attempt(actor, project_id, stage_id, operation,
                                                 item.source_key_hash, item.attempt_id, cancel_phase)
        final_state = 'canceled'
        if any(item.attempt_id is not None and item.state == 'pending' for item in operation.item_results):
            final_state = 'partial'
        return self._transition(actor, project_id, stage_id, operation.operation_id,
                                lambda current: replace(current, state=final_state,
                                                        revision=current.revision + 1,
                                                        cancel_requested=True))

    def _cancel_attempt(self, actor, project_id, stage_id, operation, key_hash, attempt_id, cancel_phase):
        _, _, backend, _, _ = self.run_service.operation_request(actor, project_id, stage_id, operation.operation_id)
        remaining = self._remaining_cancel_seconds(cancel_phase)
        if remaining <= 0:
            return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                     ItemRunResult(key_hash, 'pending', attempt_id,
                                                   error_code='ANALYSIS_CANCELED'))
        try:
            result = asyncio.run(self.run_service.analysis_service.cancel(
                actor, project_id, stage_id, attempt_id, backend=backend, timeout_seconds=remaining,
            ))
        except AnalysisError as error:
            return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                     ItemRunResult(key_hash, 'pending', attempt_id, error_code=error.code))
        state = 'canceled' if result.state == 'canceled' else 'pending'
        return self._record_item(actor, project_id, stage_id, operation, key_hash,
                                 ItemRunResult(key_hash, state, attempt_id, error_code=result.error_code))

    def _partial(self, actor, project_id, stage_id, operation_id, code, item_results):
        return self._transition(actor, project_id, stage_id, operation_id,
                                lambda current: replace(current, state='partial',
                                                        revision=current.revision + 1,
                                                        item_results=item_results,
                                                        error_code=code))

    def _transition(self, actor, project_id, stage_id, operation_id, updater):
        return self.run_service.transition(actor, project_id, stage_id, operation_id, updater)

    def _cancel_requested(self, actor, project_id, stage_id, operation_id):
        return self.run_service.get(actor, project_id, stage_id, operation_id).cancel_requested

    def _cancel_phase(self, *, start=True):
        return {'deadline': self.monotonic() + 10 if start else None}

    def _remaining_cancel_seconds(self, cancel_phase):
        if cancel_phase['deadline'] is None:
            cancel_phase['deadline'] = self.monotonic() + 10
        return max(0, min(10, cancel_phase['deadline'] - self.monotonic()))

    def _unresolved(self, operation, key_hash):
        item = next(row for row in operation.item_results if row.source_key_hash == key_hash)
        return item.attempt_id is not None and item.state == 'pending'

    def _report_error(self, error):
        if error.code == 'REPORT_LIMIT':
            return 'RUN_LIMIT'
        if error.code in {'REPORT_SOURCE_CHANGED', 'REPORT_NOT_FOUND'}:
            return 'RUN_SOURCE_CHANGED'
        return 'RUN_STORAGE_INVALID'
