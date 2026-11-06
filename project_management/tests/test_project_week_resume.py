from copy import deepcopy

import pytest

from scripts.validation.project_week_resume import verify_resume_source, verify_retained_checkpoint


def test_shouldAllowOnlyExplicitValidatorChangesWhenResumingPublishedDays():
    original = {'commit': 'a' * 40, 'files': {
        'project_management/services/report_publication.py': 'runtime',
        'scripts/validation/project_full_stack_fixture.py': 'shared-fixture',
        'scripts/validation/project_week_assertions.py': 'old-validator',
    }}
    current = deepcopy(original)
    current['files']['scripts/validation/project_week_assertions.py'] = 'fixed-validator'
    current['files']['scripts/validation/project_week_resume.py'] = 'new-validator'
    assert verify_resume_source(original, current) == [
        'scripts/validation/project_week_assertions.py',
        'scripts/validation/project_week_resume.py',
    ]
    for path in (
        'project_management/services/report_publication.py',
        'scripts/validation/project_full_stack_fixture.py',
        'scripts/validation/project_week_fixture.py',
        'ui_web/static/js/report_editor/index.js',
        'project_management/tests/unrelated_fixture.py',
    ):
        changed = deepcopy(current)
        changed['files'][path] = 'changed'
        with pytest.raises(ValueError, match='Runtime'):
            verify_resume_source(original, changed)
    current['commit'] = 'b' * 40
    with pytest.raises(ValueError, match='commit'):
        verify_resume_source(original, current)


def test_shouldComparePublicationIdentityAndBytesIndependentlyOfCheckoutProjection():
    original = {
        'state': 'finalized', 'revision_hash': 'revision', 'context': {'notes': ['human']},
        'file_hashes': {'report.html': 'html'},
        'publication': {'manifest': {'publication_id': 'publication'}, 'commit_id': 'commit',
                        'manifest_sha256': 'manifest', 'checkout_state': 'current'},
    }
    current = deepcopy(original)
    current['publication']['checkout_state'] = 'stale'
    verify_retained_checkpoint(original, current)
    assert original['publication']['checkout_state'] == 'current'
    for key in ('revision_hash', 'context', 'file_hashes', 'state'):
        changed = deepcopy(current)
        changed[key] = 'changed'
        with pytest.raises(ValueError):
            verify_retained_checkpoint(original, changed)
    for key in ('manifest', 'commit_id', 'manifest_sha256', 'checkout_state'):
        changed = deepcopy(current)
        changed['publication'][key] = 'changed'
        with pytest.raises(ValueError):
            verify_retained_checkpoint(original, changed)
