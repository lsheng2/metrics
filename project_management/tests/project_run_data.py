def default_item():
    return {
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'assignee': {'key': 'dev-a', 'displayName': 'Alice'},
        'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
        'comments': {
            '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
            '202': {'id': '202', 'body': 'Logs attached. Failure reproduced on build r7.'},
            '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
        },
    }


def second_item():
    return {
        'stable_id': 'ALPHA-2',
        'summary': 'Second item',
        'status': 'Open',
        'assignee': {'key': 'dev-b', 'displayName': 'Bob'},
        'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
        'comments': {
            '401': {'id': '401', 'body': 'Failure observed.', 'author': {'key': 'dev-b'}},
            '402': {'id': '402', 'body': 'Logs attached. Failure reproduced on build r7.'},
            '403': {'id': '403', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
        },
    }
