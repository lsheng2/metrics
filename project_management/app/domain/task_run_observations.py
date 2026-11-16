from .task_runs import TaskRunSnapshot


def execution_is_settled(snapshot):
    if not isinstance(snapshot, TaskRunSnapshot):
        raise TypeError('Typed task-run snapshot is required')
    return (snapshot.status in {'succeeded', 'failed', 'canceled', 'timed_out'}
            and snapshot.dispatch.uncertainty != 'unknown')


def submit_was_rejected(observation):
    return (observation.get('operation') == 'submit'
            and observation.get('retry') == 'correct')
