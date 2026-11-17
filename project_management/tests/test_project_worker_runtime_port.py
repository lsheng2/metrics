import hashlib
import json
import uuid

from project_management.app.api.project_runs import RunPolicy
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.task_runs import (
    TaskDispatch,
    TaskPrincipal,
    TaskRunAdmissionMetadata,
    TaskResultSummary,
    TaskRunCancellation,
    TaskRunRequest,
    TaskRunResult,
    TaskRunSnapshot,
)
from project_management.tests.project_run_fixtures import ManualRunEnvironment, default_item, second_item


class TypedTaskRunPort:
    def __init__(self, environment, *, snapshot_mode='succeeded', on_result=None):
        self.environment = environment
        self.snapshot_mode = snapshot_mode
        self.on_result = on_result
        self.calls = []
        self.snapshots = {}
        self.canceled_run_ids = set()

    def admission_metadata(self):
        return TaskRunAdmissionMetadata(
            model_identity={'provider': 'typed-test-port', 'model': 'scripted'},
            runtime_version='0.1.0-test',
        )

    def start(self, principal, request):
        self._record('start', principal, request)
        if self.snapshot_mode == 'unknown':
            snapshot = self._snapshot(
                request,
                status='indeterminate',
                uncertainty='unknown',
                error_code='runtime_outcome_unknown',
                retry='observe',
            )
        else:
            snapshot = self._snapshot(request, status='succeeded')
        self.snapshots[request.client_run_key] = snapshot
        return snapshot

    def lookup(self, principal, request, *, timeout=None):
        self._record('lookup', principal, request, timeout=timeout)
        return self.snapshots.get(request.client_run_key)

    def get(self, principal, request, run_id, *, timeout=None):
        self._record('get', principal, request, run_id, timeout=timeout)
        snapshot = self.snapshots[request.client_run_key]
        if run_id in self.canceled_run_ids:
            snapshot = self._snapshot(request, run_id=run_id, status='canceled')
            self.snapshots[request.client_run_key] = snapshot
        return snapshot

    def result(self, principal, request, run_id):
        self._record('result', principal, request, run_id)
        if self.on_result is not None:
            callback = self.on_result
            self.on_result = None
            callback()
        return self._result(request, run_id)

    def cancel(self, principal, run_id, *, timeout=None):
        self._record('cancel', principal, None, run_id, timeout=timeout)
        self.canceled_run_ids.add(run_id)
        return TaskRunCancellation(run_id=run_id, canceled=True)

    def _record(self, method, principal, request, run_id=None, *, timeout=None):
        assert isinstance(principal, TaskPrincipal)
        assert principal.subject == self.environment.actor.subject
        if request is not None:
            assert isinstance(request, TaskRunRequest)
        if timeout is not None:
            assert type(timeout) in {int, float}
            assert timeout >= 0
        self.calls.append((method, principal, request, run_id, timeout))

    def _snapshot(self, request, *, run_id=None, status, uncertainty='dispatched', error_code=None, retry=None):
        run_id = run_id or f'run-{request.client_run_key}'
        output_hash = None
        output_schema = None
        if status == 'succeeded' and uncertainty == 'dispatched':
            content = self._content(request)
            output_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
            output_schema = request.output_schema_sha256
        dispatch = self._dispatch(request, dispatched=uncertainty == 'dispatched', uncertainty=uncertainty)
        return TaskRunSnapshot(
            run_id=run_id,
            profile_id=request.profile_id,
            profile_version=request.profile_version,
            status=status,
            source_input_sha256=request.input_sha256,
            input_sha256=request.input_sha256,
            effective_input_sha256=request.input_sha256,
            dispatch=dispatch,
            result=TaskResultSummary(output_sha256=output_hash, output_schema_sha256=output_schema, usage=None),
            error_code=error_code,
            retry=retry,
        )

    def _result(self, request, run_id):
        content = self._content(request)
        output_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        return TaskRunResult(
            run_id=run_id,
            profile_id=request.profile_id,
            profile_version=request.profile_version,
            status='succeeded',
            source_input_sha256=request.input_sha256,
            input_sha256=request.input_sha256,
            effective_input_sha256=request.input_sha256,
            output_schema_sha256=request.output_schema_sha256,
            output_sha256=output_hash,
            content_json=content,
            dispatch=self._dispatch(request, dispatched=True, uncertainty='dispatched'),
            usage=None,
            error_code=None,
            retry=None,
        )

    def _dispatch(self, request, *, dispatched, uncertainty):
        return TaskDispatch(
            provider='typed-test-port',
            model='scripted',
            runtime_version='0.1.0-test',
            profile_definition_sha256=request.profile_definition_sha256,
            tool_definition_sha256=None,
            dispatched=dispatched,
            uncertainty=uncertainty,
            usage=None,
        )

    def _content(self, request):
        return canonical_bytes(self._summary_output(request)).decode('utf-8')

    def _summary_output(self, request):
        value = json.loads(request.input_json)
        return {
            'kind': 'summary',
            'binding': value['binding'],
            'profile_revision': value['profile_revision'],
            'base_summary_id': None,
            'target_capture_id': value['target_capture_id'],
            'output_language': 'en',
            'what': 'Intermittent failure during validation.',
            'current_position': 'The item is marked Fixed. A validation rerun on build r8 is requested.',
            'verification': 'The supplied evidence does not confirm that the rerun passed.',
            'next_actions': [{
                'action': 'Rerun validation on build r8.',
                'owner_id': 'qa-b',
                'owner_basis': 'explicit',
                'owner_quote': 'Bob (qa-b), please rerun validation on build r8.',
                'owner_confirmed': False,
                'state': 'open',
                'evidence': ['comment:203'],
            }],
            'blockers': [],
            'limitations': [],
            'evidence': ['fields', 'comment:201', 'comment:202', 'comment:203'],
        }


def submit_run(environment):
    return environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        environment.request(str(uuid.uuid4())),
    )


def execute_run(environment, operation):
    return environment.worker.execute(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        operation.operation_id,
    )


def test_project_run_worker_completes_summary_with_typed_task_run_port(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    port = TypedTaskRunPort(environment)
    environment.install_summary_service(port)
    operation = submit_run(environment)

    completed = execute_run(environment, operation)

    assert completed.state == 'draft_ready'
    assert completed.draft_id is not None
    assert completed.item_results[0].state == 'accepted'
    assert [call[0] for call in port.calls] == ['start', 'result']
    request = port.calls[0][2]
    snapshot = port.snapshots[request.client_run_key]
    assert snapshot.source_input_sha256 == request.input_sha256
    assert completed.item_results[0].attempt_id == request.client_run_key


def test_project_run_worker_keeps_unknown_dispatch_partial_without_admitting_later_items(tmp_path):
    environment = ManualRunEnvironment(
        tmp_path / 'archive-root',
        items=(default_item(), second_item()),
        policy=RunPolicy(max_analysis_items=2),
    )
    port = TypedTaskRunPort(environment, snapshot_mode='unknown')
    environment.install_summary_service(port)
    operation = submit_run(environment)

    completed = execute_run(environment, operation)

    assert completed.state == 'partial'
    assert [item.state for item in completed.item_results] == ['pending', 'pending']
    assert completed.item_results[0].error_code == 'runtime_outcome_unknown'
    assert completed.item_results[1].attempt_id is None
    assert [call[0] for call in port.calls] == ['start']


def test_project_run_worker_cancels_observed_run_without_accepting_late_result(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    operation = submit_run(environment)

    def cancel_current_operation():
        current = environment.run_service.get(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
        )
        environment.run_service.cancel(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            operation.operation_id,
            expected_revision=current.revision,
        )

    port = TypedTaskRunPort(environment, on_result=cancel_current_operation)
    environment.install_summary_service(port)

    completed = execute_run(environment, operation)

    assert completed.state == 'canceled'
    assert completed.cancel_requested is True
    assert completed.draft_id is None
    assert completed.item_results[0].state == 'canceled'
    assert [call[0] for call in port.calls] == ['start', 'result', 'cancel', 'get']
