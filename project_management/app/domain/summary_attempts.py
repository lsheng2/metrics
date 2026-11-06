from datetime import datetime

from project_management.app.domain.summary_contracts import AnalysisError


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
            return not _settled(snapshot)
        if 'cancel' in observation:
            if not attempt.cancel_requested or not observation.get('run_id'):
                raise AnalysisError('ANALYSIS_INVALID')
            snapshot = contract.validate_cancel(attempt, observation['cancel'],
                                                expected_run_id=observation['run_id'])
            return not _settled(snapshot)
        if observation.get('operation') == 'result':
            continue
        if (observation.get('operation') == 'submit' and observation.get('state') == 'rejected'
                and observation.get('recovery') == 'correct_request'
                and type(observation.get('status')) is int and observation['status'] in {400, 413, 422}):
            return False
        return True
    return True


def _settled(snapshot):
    if (snapshot.get('state') not in {'succeeded', 'failed', 'canceled', 'timed_out'}
            or snapshot.get('unresolvedExposure') is not False):
        return False
    try:
        terminal = datetime.fromisoformat(snapshot['terminalAt'])
        if terminal.tzinfo is None or terminal.utcoffset() is None:
            return False
    except (KeyError, ValueError, TypeError):
        return False
    dispatch = snapshot.get('dispatch', {})
    return (
        dispatch.get('remoteStop') == 'confirmed'
        or dispatch.get('knowledge') == 'response_received'
        or (dispatch.get('knowledge') == 'not_dispatched' and dispatch.get('attemptCount') == 0)
    )
