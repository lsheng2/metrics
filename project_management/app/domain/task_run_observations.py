from datetime import datetime


def execution_is_settled(snapshot):
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


def submit_was_rejected(observation):
    return (observation.get('operation') == 'submit'
            and observation.get('recovery') == 'correct_request'
            and type(observation.get('status')) is int and observation['status'] in {400, 413, 422})
