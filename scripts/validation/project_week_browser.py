import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validation import project_full_stack
from scripts.validation.project_full_stack_support import base_environment, json_lines, read_json, require_owned_run_dir, write_json
from scripts.validation.project_sdk_join import source_identity
from scripts.validation.project_week_assertions import text_of, verify_checkpoint, verify_files
from scripts.validation.project_week_data import WEEK_COLORS, WEEK_DAYS
from scripts.validation.project_week_ui import WeekUi
from scripts.validation.project_week_resume import recover_published_days


def read_checkpoint(run_dir, draft_id, label, publication_id=None):
    command = [sys.executable, '-I', str(ROOT / 'scripts/validation/project_week_checkpoint.py'),
               '--run-dir', str(run_dir), '--draft-id', draft_id, '--label', label]
    if publication_id:
        command += ['--publication-id', publication_id]
    result = subprocess.run(command, cwd=ROOT, env=base_environment(run_dir / 'environment/checkpoint-env'),
                            capture_output=True, text=True, timeout=240)
    if result.returncode:
        write_json(run_dir / f'evidence/{label}-readback-error.json', {
            'code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
        })
        raise AssertionError('Read-only checkpoint failed; evidence retained.')
    return read_json(Path(result.stdout.strip().splitlines()[-1]))


def dispatch_count(run_dir):
    return len(json_lines(run_dir / 'base/store/executor-observations.jsonl'))


def edit_day(ui, index):
    page = ui.page
    expected = {}
    for position, number in enumerate(('101', '102', '103')):
        _, editor = ui.note(position)
        value = f'Day {index + 1} human note for ALPHA-{number}. AR: @Bob verify retained evidence.'
        if index == 3 and position == 1:
            value = ''
        expected[number] = value
        editor.fill(value)
        if value:
            editor.press('Control+A')
            page.locator(f'[data-report-command="foreground"][data-color="{WEEK_COLORS[index]}"]').click()
    if index == 0:
        _, editor = ui.note(0)
        editor.press('Control+End')
        page.keyboard.type(' Human link')
        editor.press('Control+Shift+ArrowLeft')
        page.once('dialog', lambda dialog: dialog.accept('https://tracker.example.test/jira/browse/ALPHA-101'))
        page.locator('[data-report-command="link"]').click()
    if index == 1:
        page.locator('[data-continuity-add-persistent][data-persistent-target="report"]').click()
        persistent = page.locator('[data-continuity-persistent-draft]')
        editor = persistent.locator('.ProseMirror')
        editor.wait_for()
        editor.fill('Carry green human context into the next week.')
        editor.press('Control+A')
        page.locator('[data-report-command="foreground"][data-color="#008000"]').click()
    if index == 2:
        _, editor = ui.note(0)
        editor.press('Control+End')
        with page.expect_response('**/completions/') as pending:
            page.keyboard.type(' #ALPHA-101')
        if pending.value.status != 200:
            ui.capture_response(pending.value, 'wednesday-completion-failed')
            raise AssertionError('Scoped completion failed.')
        page.locator('.report-completion-option').nth(2).wait_for()
        editor.press('ArrowDown')
        editor.press('ArrowDown')
        editor.press('Enter')
        page.locator('[data-report-command="undo"]').click()
        page.locator('[data-report-command="redo"]').click()
        editor.press('Control+A')
        page.locator('[data-report-command="bold"]').click()
        page.locator('[data-report-command="background"][data-color="#fff4cc"]').click()
        page.locator('[data-report-command="foreground"][data-color="#008000"]').click()
    if index == 4:
        _, editor = ui.note(0)
        editor.press('Control+End')
        page.keyboard.type(' Mixed red segment.')
        editor.press('Control+Shift+ArrowLeft')
        page.locator('[data-report-command="foreground"][data-color="#aa0000"]').click()
        details = page.locator('[data-continuity-action-control]').first
        details.locator('summary').click()
        details.locator('[data-continuity-action-done]').check()
        surface = details.locator('[data-continuity-action-editor]')
        surface.click()
        surface.locator('.ProseMirror').wait_for()
        surface.locator('.ProseMirror').fill('Human verification completed; close this AR.')
    return expected


def prepare_stale_tab(context, ui, draft_id):
    page = context.new_page()
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(120000)
    page.goto(f'{ui.stage_url}drafts/{draft_id}/', wait_until='domcontentloaded')
    stale = WeekUi(page, ui.base, ui.manifest, ui.evidence)
    _, editor = stale.note(0)
    editor.fill('Retained text from the stale editor.')
    return stale


def recover_stale_tab(stale, ui, draft_id, expected):
    page = stale.page
    response = stale.post(page.locator('[data-report-save-button]'),
                          f'/projects/{ui.project_id}/stages/{ui.stage_id}/reports/drafts/{draft_id}/save/',
                          'thursday-stale-save', expected=409)
    if response['body'].get('error_code') != 'REPORT_REVISION_CONFLICT':
        raise AssertionError('Expected explicit stale-save conflict.')
    if 'Retained text from the stale editor.' not in page.locator('.ProseMirror').first.inner_text():
        raise AssertionError('Stale Save lost local input.')
    page.screenshot(path=str(ui.evidence / 'thursday-stale-retained.png'), full_page=True)
    page.on('dialog', lambda dialog: dialog.accept())
    stale.reopen(draft_id)
    _, editor = stale.note(0)
    expected['101'] += ' Retained text from the stale editor.'
    editor.fill(expected['101'])
    saved = stale.save(draft_id, 'thursday-stale-reconciled')
    page.close()
    return saved


def pending_gap(ui, run_dir):
    main_series = ui.series_id
    ui.create_series('Qualification pending-gap series', 'series-gap')
    first = ui.prepare('2026-10-26', 'gap-monday', analysis='manual_only')
    _, editor = ui.note(0)
    editor.fill('Saved pending note must remain recoverable.')
    _, clear_editor = ui.note(1)
    clear_editor.fill('Temporary saved content to be explicitly cleared.')
    ui.save(first['draft_id'], 'gap-before-clear')
    ui.reopen(first['draft_id'])
    _, clear_editor = ui.note(1)
    clear_editor.fill('')
    ui.save(first['draft_id'], 'gap-monday-save')
    before = read_checkpoint(run_dir, first['draft_id'], 'gap-before')
    cleared = next(note for note in before['context']['notes']
                   if note['meeting']['local_date'] == '2026-10-26' and note['issue_ref']['stable_id'] == '102')
    if text_of(cleared['body_fragment']) != '':
        raise AssertionError('Saved content was not explicitly cleared.')
    ui.reopen(first['draft_id'])
    ui.page.screenshot(path=str(ui.evidence / 'gap-cleared-reopened.png'), full_page=True)
    baseline = ui.preview('2026-10-27', 'gap-tuesday-blocked')
    if first['draft_id'] not in baseline:
        raise AssertionError('The previous saved but unfinalized draft was not disclosed.')
    form = ui.page.locator('[data-report-daily-prepare-form]')
    form.locator('[name="source_mode"]').select_option('refresh')
    form.locator('[name="analysis_mode"]').select_option('manual_only')
    ui.post(form.locator('[data-report-daily-generate]'), form.get_attribute('action'),
            'gap-without-ack', expected=409)
    second = ui.prepare('2026-10-27', 'gap-tuesday-ack', analysis='manual_only', acknowledge_gap=True)
    after = read_checkpoint(run_dir, first['draft_id'], 'gap-after')
    if before != after:
        raise AssertionError('Acknowledged gap changed the original pending draft.')
    ui.series_id = main_series
    if dispatch_count(run_dir) != 3:
        raise AssertionError('Pending-gap manual branch created an AI task.')
    return {'pending_draft': first['draft_id'], 'next_draft': second['draft_id'],
            'retained_revision_hash': after['revision_hash'],
            'explicit_clear_note_id': cleared['note_id'], 'explicit_clear_hash': cleared['body_hash']}


def run_week(run_dir, *, stop_after_first=False, resume_after=None, resume_evidence='week'):
    from playwright.sync_api import sync_playwright

    manifest = project_full_stack.trusted_manifest(run_dir)
    if manifest.get('scenario') != 'full-week':
        raise ValueError('Expected full-week scenario.')
    evidence = run_dir / 'evidence' / (f'week-resume-{uuid4()}' if resume_after else 'week')
    evidence.mkdir(exist_ok=False)
    status = project_full_stack.status_result(run_dir, next_action='stop')
    base = f'http://127.0.0.1:{status["services"]["project-app"]["port"]}'
    source = source_identity()
    write_json(evidence / 'source.json', source)
    result = {'status': 'running', 'started_at': datetime.now(UTC).isoformat(), 'days': [],
              'real_provider': False, 'real_model': False}
    previous = None
    first_index = 0
    if resume_after:
        result, previous, first_index = recover_published_days(
            run_dir, manifest, resume_after, source, read_checkpoint, evidence, resume_evidence,
        )
        if dispatch_count(run_dir) != 3:
            raise AssertionError('Resume requires the same three accepted summary dispatches.')
    with sync_playwright() as engine:
        browser = engine.chromium.launch(headless=True, channel='chrome')
        context = browser.new_context(http_credentials=manifest['auth']['alice'],
                                      viewport={'width': 1440, 'height': 1000})
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(
            (base + '/', 'data:', 'blob:')) else route.abort())
        page = context.new_page()
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(120000)
        ui = WeekUi(page, base, manifest, evidence)
        try:
            if resume_after:
                ui.series_id = result['templates']['series_id']
                ui.daily_template = result['templates']['daily_template']
                ui.weekly_template = result['templates']['weekly_template']
                for record in result['days']:
                    directory = evidence / record['date'].replace('-', '')
                    directory.mkdir()
                    page.goto(f'{ui.stage_url}publications/{record["publication_id"]}/',
                              wait_until='domcontentloaded')
                    ui.download_exports(directory)
                write_json(evidence / 'progress.json', result)
            else:
                result['templates'] = ui.setup()
            for index, day in enumerate(WEEK_DAYS):
                if index < first_index:
                    continue
                if index == 2:
                    project_full_stack.restart_app(SimpleNamespace(run_dir=run_dir))
                name = day.replace('-', '')
                prepared = ui.prepare(day, name)
                duplicate = ui.prepare(day, name + '-duplicate')
                if (prepared['draft_id'], prepared['operation_id']) != (duplicate['draft_id'], duplicate['operation_id']):
                    raise AssertionError('Same meeting created another operation/draft.')
                if dispatch_count(run_dir) != 3:
                    raise AssertionError('Exactly three first-day summary dispatches must serve the full week.')
                if result['days'] and result['days'][-1]['publication_id'] not in prepared['baseline']:
                    raise AssertionError('Daily baseline is not the last finalized daily publication.')
                if index == 3:
                    _, clear_editor = ui.note(1)
                    clear_editor.fill('Temporary saved content to be explicitly cleared.')
                    ui.save(prepared['draft_id'], 'thursday-before-clear')
                    ui.reopen(prepared['draft_id'])
                stale = prepare_stale_tab(context, ui, prepared['draft_id']) if index == 3 else None
                expected = edit_day(ui, index)
                page.screenshot(path=str(evidence / f'{name}-edited.png'), full_page=True)
                saved = ui.save(prepared['draft_id'], f'{name}-save')
                if index == 3:
                    ui.reopen(prepared['draft_id'])
                    _, editor = ui.note(2)
                    editor.press('Control+A')
                    page.locator('[data-report-command="foreground"][data-color="#008000"]').click()
                    saved = ui.save(prepared['draft_id'], 'thursday-paint-only-save')
                if stale is not None:
                    saved = recover_stale_tab(stale, ui, prepared['draft_id'], expected)
                if index == 0:
                    preview = ui.preview('2026-10-27', 'monday-before-final')
                    if prepared['draft_id'] not in preview or 'Previous final' in preview:
                        raise AssertionError('Save advanced the first editorial baseline or lost pending state.')
                ui.reopen(prepared['draft_id'])
                page.screenshot(path=str(evidence / f'{name}-reopened.png'), full_page=True)
                publication_id = ui.finalize(prepared['draft_id'], f'{name}-finalized')
                checkpoint = read_checkpoint(run_dir, prepared['draft_id'], name, publication_id)
                verified = verify_checkpoint(checkpoint, day, expected, previous, new_week=index == 5)
                exports = evidence / name
                exports.mkdir()
                ui.download_exports(exports)
                record = {**prepared, 'date': day, 'saved_revision': saved['revision'],
                          'publication_id': publication_id, 'verified': verified,
                          'file_hashes': checkpoint['file_hashes'], 'dispatches': dispatch_count(run_dir)}
                result['days'].append(record)
                write_json(evidence / 'progress.json', result, replace=True)
                print(json.dumps({'event': 'day_passed', 'date': day, 'draft': prepared['draft_id'],
                                  'publication': publication_id, 'dispatches': dispatch_count(run_dir)}), flush=True)
                previous = checkpoint
                if index == 4:
                    weekly_id = ui.weekly([item['publication_id'] for item in result['days']])
                    weekly_publication = ui.finalize(weekly_id, 'weekly-finalized')
                    weekly = read_checkpoint(run_dir, weekly_id, 'weekly-view', weekly_publication)
                    if weekly['context']['report_role'] != 'weekly_view':
                        raise AssertionError('Weekly report role is not a read-only daily projection.')
                    weekly_dir = evidence / 'weekly'
                    weekly_dir.mkdir()
                    ui.download_exports(weekly_dir)
                    result['weekly'] = {'draft_id': weekly_id, 'publication_id': weekly_publication,
                                        'file_hashes': weekly['file_hashes']}
                if stop_after_first:
                    result['status'] = 'first_day_passed'
                    break
            if not stop_after_first:
                seed = previous['context']['weekly_seed']
                if not seed['persistent_note_refs'] or not seed['unresolved_action_ids']:
                    raise AssertionError('New week lost persistent context or unresolved ARs.')
                if not any('Carry green human context' in text_of(item['fragment'])
                           for item in previous['context']['persistent_notes']):
                    raise AssertionError('Persistent user note did not survive the week boundary.')
                for action in previous['context']['actions']:
                    if action['action_id'] in seed['unresolved_action_ids'] and action['tracking_state'] in {'done', 'canceled'}:
                        raise AssertionError('Resolved AR was carried as unresolved.')
                result['pending_gap'] = pending_gap(ui, run_dir)
                result['status'] = 'passed'
            if source_identity() != source:
                raise AssertionError('Runtime/fixture source changed during the matched-candidate run.')
            for record in result['days']:
                verify_files(run_dir / 'evidence/canonical' / record['date'].replace('-', ''), record['file_hashes'])
            write_json(evidence / 'result.json', result)
            result['evidence_directory'] = str(evidence)
            return result
        except Exception:
            page.screenshot(path=str(evidence / 'failure.png'), full_page=True)
            from scripts.validation.project_week_ui import redacted_html
            (evidence / 'failure.html').write_text(redacted_html(page.content()), encoding='utf-8')
            raise
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--first-day-only', action='store_true')
    parser.add_argument('--resume-after', choices=WEEK_DAYS[:4])
    parser.add_argument('--resume-evidence', default='week')
    args = parser.parse_args()
    run_dir = require_owned_run_dir(args.run_dir)
    try:
        if args.first_day_only and args.resume_after:
            raise ValueError('First-day-only and resume cannot be combined.')
        result = run_week(run_dir, stop_after_first=args.first_day_only, resume_after=args.resume_after,
                          resume_evidence=args.resume_evidence)
        print(json.dumps({'status': result['status'], 'evidence': result['evidence_directory']}))
    finally:
        stopped = project_full_stack.stop(SimpleNamespace(run_dir=run_dir))
        if not stopped['normal']:
            raise AssertionError('Owned stack did not stop normally.')


if __name__ == '__main__':
    main()
