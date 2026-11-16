from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.task_run_observations import execution_is_settled, submit_was_rejected
from project_management.app.domain.task_run_codec import snapshot_from_record


def attempt_blocks_new_input(attempt, observations, contract, *, accepted_attempt_ids, target_capture_id):
    if attempt.attempt_id in accepted_attempt_ids:
        return False
    if not attempt.dispatched:
        return attempt.prepared.target_capture_id == target_capture_id and not attempt.cancel_requested
    for observation in reversed(observations):
        if not isinstance(observation, dict):
            raise AnalysisError('ANALYSIS_INVALID')
        if 'snapshot' in observation:
            snapshot = snapshot_from_record(observation['snapshot'])
            contract.validate_snapshot(attempt.request, snapshot)
            return not execution_is_settled(snapshot)
        if 'cancel' in observation:
            if not attempt.cancel_requested or not observation.get('run_id'):
                raise AnalysisError('ANALYSIS_INVALID')
            # An acknowledgement alone does not prove a terminal execution.
            return True
        if observation.get('operation') == 'result':
            continue
        if observation.get('state') == 'rejected' and submit_was_rejected(observation):
            return False
        return True
    return True
