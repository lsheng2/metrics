from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.task_run_observations import execution_is_settled, submit_was_rejected


def attempt_blocks_new_input(attempt, observations, contract, *, accepted_attempt_ids, target_capture_id):
    if attempt.attempt_id in accepted_attempt_ids:
        return False
    if not attempt.dispatched:
        return attempt.prepared.target_capture_id == target_capture_id and not attempt.cancel_requested
    for observation in reversed(observations):
        if not isinstance(observation, dict):
            raise AnalysisError('ANALYSIS_INVALID')
        if 'snapshot' in observation:
            snapshot = observation['snapshot']
            contract.validate_snapshot(attempt, snapshot)
            return not execution_is_settled(snapshot)
        if 'cancel' in observation:
            if not attempt.cancel_requested or not observation.get('run_id'):
                raise AnalysisError('ANALYSIS_INVALID')
            snapshot = contract.validate_cancel(attempt, observation['cancel'],
                                                expected_run_id=observation['run_id'])
            return not execution_is_settled(snapshot)
        if observation.get('operation') == 'result':
            continue
        if observation.get('state') == 'rejected' and submit_was_rejected(observation):
            return False
        return True
    return True
