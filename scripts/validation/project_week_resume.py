from datetime import UTC, datetime
import re

from bs4 import BeautifulSoup

from scripts.validation.project_full_stack_support import read_json, write_json
from scripts.validation.project_week_assertions import verify_checkpoint
from scripts.validation.project_week_data import WEEK_DAYS


VALIDATOR_FILES = frozenset({
    'scripts/validation/project_week_browser.py',
    'scripts/validation/project_week_assertions.py',
    'scripts/validation/project_week_resume.py',
    'project_management/tests/test_project_week_assertions.py',
    'project_management/tests/test_project_week_resume.py',
})


def verify_resume_source(original, current):
    if original['commit'] != current['commit']:
        raise ValueError('Resume requires the original source commit.')
    changes = sorted(name for name in original['files'].keys() | current['files'].keys()
                     if original['files'].get(name) != current['files'].get(name))
    if set(changes) - VALIDATOR_FILES:
        raise ValueError('Runtime or shared fixture changed; published days cannot be joined.')
    return changes


def expected_notes(index):
    values = {number: f'Day {index + 1} human note for ALPHA-{number}. AR: @Bob verify retained evidence.'
              for number in ('101', '102', '103')}
    if index == 3:
        values['102'] = ''
        values['101'] += ' Retained text from the stale editor.'
    return values


def verify_retained_checkpoint(stored, fresh):
    def immutable(value):
        publication = dict(value['publication'])
        if publication.pop('checkout_state') not in {'current', 'stale'}:
            raise ValueError('Unrecognized checkout projection.')
        return {**value, 'publication': publication}

    if immutable(fresh) != immutable(stored) or fresh['state'] != 'finalized':
        raise ValueError('Retained publication or draft differs from its original checkpoint.')


def recover_published_days(run_dir, manifest, after, source, read_checkpoint, evidence, prior_name='week'):
    if after not in WEEK_DAYS[:4]:
        raise ValueError('Resume requires a published day before the weekly-view step.')
    original = run_dir / 'evidence/week'
    if re.fullmatch(r'week(?:-resume-[0-9a-f-]{36})?', prior_name) is None:
        raise ValueError('Resume evidence must be an owned week directory name.')
    prior = (run_dir / 'evidence' / prior_name).resolve(strict=True)
    if prior.parent != (run_dir / 'evidence').resolve(strict=True):
        raise ValueError('Resume evidence is outside the owned run.')
    changes = verify_resume_source(read_json(original / 'source.json'), source)
    result = read_json(prior / 'progress.json')
    stop = WEEK_DAYS.index(after) + 1
    if (result['status'] != 'running'
            or [item['date'] for item in result['days']] != list(WEEK_DAYS[:len(result['days'])])
            or len(result['days']) > stop):
        raise ValueError('Prior progress is not a compatible interrupted week.')
    for later in WEEK_DAYS[stop:]:
        if (run_dir / 'evidence/canonical' / later.replace('-', '')).exists():
            raise ValueError('A later persisted day exists outside the resume boundary.')
    previous = None
    days = []
    for index, day in enumerate(WEEK_DAYS[:stop]):
        name = day.replace('-', '')
        stored = read_json(run_dir / 'evidence/canonical' / name / 'checkpoint.json')
        publication_id = stored['publication']['manifest']['publication_id']
        fresh = read_checkpoint(run_dir, stored['draft_id'], f'{evidence.name}-{name}', publication_id)
        verify_retained_checkpoint(stored, fresh)
        if fresh['context']['series_id'] != result['templates']['series_id']:
            raise ValueError('Retained publication belongs to another series.')
        untouched = {'102'} if day == '2026-10-29' else set()
        verified = verify_checkpoint(fresh, day, expected_notes(index), previous, untouched_empty_ids=untouched)
        folders = set((original, prior))
        candidates = [folder for folder in folders if (folder / f'{name}-operation.json').is_file()]
        if len(candidates) != 1:
            raise ValueError('Original daily operation evidence is missing or ambiguous.')
        daily_evidence = candidates[0]
        operation = read_json(daily_evidence / f'{name}-operation.json')
        if operation['state'] != 'draft_ready' or operation['analysis_mode'] != 'changed_items':
            raise ValueError('Retained mainline operation was not fully accepted.')
        body = read_json(daily_evidence / f'{name}-preview.json')['body']
        baseline = BeautifulSoup(body, 'html.parser').select_one('[data-report-daily-baseline]')
        if baseline is None:
            raise ValueError('Original baseline evidence is missing.')
        days.append({
            'date': day, 'draft_id': fresh['draft_id'], 'operation_id': operation['operation_id'],
            'state': operation['state'], 'baseline': baseline.get_text('\n', strip=True),
            'saved_revision': fresh['revision'], 'publication_id': publication_id,
            'verified': verified, 'file_hashes': fresh['file_hashes'], 'dispatches': 3,
            'rechecked_canonical': f'{evidence.name}-{name}',
        })
        previous = fresh
    result.update(days=days, resumed_at=datetime.now(UTC).isoformat(), resume_after=after,
                  prior_evidence=str(prior), validator_changes=changes)
    write_json(evidence / 'resume-readback.json', result)
    return result, previous, stop
