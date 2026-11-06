from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

from scripts.validation.project_full_stack_support import write_json


class WeekUi:
    def __init__(self, page, base, manifest, evidence):
        self.page = page
        self.base = base
        self.manifest = manifest
        self.evidence = Path(evidence)
        self.project_id = manifest['catalog']['project_id']
        self.stage_id = manifest['catalog']['stage_id']
        self.stage_url = base + manifest['routes']['project_stage_reports']
        self.series_id = None
        self.daily_template = None
        self.weekly_template = None

    def capture_response(self, response, name):
        content_type = response.headers.get('content-type', '')
        value = {'status': response.status, 'url': response.url,
                 'location': response.headers.get('location')}
        if response.status != 302:
            if 'application/json' in content_type:
                value['body'] = response.json()
            else:
                value['body'] = redacted_html(response.text())
        write_json(self.evidence / f'{name}.json', value)
        return value

    def post(self, control, endpoint, name, expected=302):
        started = perf_counter()
        with self.page.expect_response(lambda response: response.request.method == 'POST'
                                       and urlsplit(response.url).path == urlsplit(endpoint).path,
                                       timeout=120000) as pending:
            control.click(no_wait_after=True)
        value = self.capture_response(pending.value, name)
        if value['status'] != expected:
            raise AssertionError(f'{name}: HTTP {value["status"]}, expected {expected}; response retained.')
        write_json(self.evidence / f'{name}-timing.json', {'seconds': round(perf_counter() - started, 3)})
        return value

    def create_template(self, kind):
        self.page.goto(f'{self.base}/projects/{self.project_id}/report-templates/', wait_until='domcontentloaded')
        form = self.page.locator(f'form:has(input[name="action"][value="continuity_{kind}"])')
        form.locator('[name="name"]').fill(f'Qualification {kind} template')
        response = self.post(form.locator('button[type="submit"]'), form.get_attribute('action'),
                             f'template-{kind}-create')
        self.page.wait_for_url(self.base + response['location'], wait_until='domcontentloaded')
        template_id = urlsplit(self.page.url).path.rstrip('/').rsplit('/', 1)[-1]
        if kind == 'daily':
            self.page.locator('[data-template-add="content"]').click()
            row = self.page.locator('[data-template-row]').last
            row.locator('[data-template-rich-panel] [data-template-editor-surface]').click()
            editor = row.locator('.ProseMirror')
            editor.wait_for()
            editor.fill('Synthetic daily standup qualification.')
            self.post(self.page.locator('[data-template-save-button]'),
                      f'/projects/{self.project_id}/report-templates/{template_id}/save/',
                      f'template-{kind}-save', expected=200)
            self.page.wait_for_load_state('domcontentloaded')
        self.page.screenshot(path=str(self.evidence / f'template-{kind}.png'), full_page=True)
        return template_id

    def setup(self):
        daily_id = self.create_template('daily')
        weekly_id = self.create_template('weekly')
        self.page.goto(self.stage_url, wait_until='domcontentloaded')
        series = self.page.locator('[data-report-series-form]')
        self.daily_template = matching_option(series.locator('[name="template_choice"]'), daily_id)
        self.weekly_template = matching_option(
            self.page.locator('[data-report-weekly-form] [name="template_choice"]'), weekly_id)
        self.create_series('Qualification daily series', 'series-main')
        return {'series_id': self.series_id, 'daily_template': self.daily_template,
                'weekly_template': self.weekly_template}

    def create_series(self, name, label):
        self.page.goto(self.stage_url, wait_until='domcontentloaded')
        form = self.page.locator('[data-report-series-form]')
        form.locator('[name="series_name"]').fill(name)
        form.locator('[name="calendar_choice"]').select_option('iso8601')
        form.locator('[name="timezone"]').fill('Asia/Shanghai')
        form.locator('[name="template_choice"]').select_option(self.daily_template)
        self.post(form.locator('[data-report-series-create]'), form.get_attribute('action'), label)
        self.page.wait_for_load_state('domcontentloaded')
        self.page.goto(self.stage_url, wait_until='domcontentloaded')
        options = self.page.locator('[data-report-daily-preview-form] [name="series_id"] option')
        selected = options.filter(has_text=name)
        if selected.count() != 1:
            raise AssertionError('Created series is not uniquely selectable.')
        self.series_id = selected.get_attribute('value')
        return self.series_id

    def preview(self, day, label):
        self.page.goto(self.stage_url, wait_until='domcontentloaded')
        form = self.page.locator('[data-report-daily-preview-form]')
        form.locator('[name="series_id"]').select_option(self.series_id)
        form.locator('[name="meeting_date"]').fill(day)
        form.locator('[name="template_choice"]').select_option(self.daily_template)
        endpoint = form.get_attribute('action')
        with self.page.expect_response(lambda response: response.request.method == 'GET'
                                       and urlsplit(response.url).path == endpoint, timeout=120000) as pending:
            form.locator('[data-report-daily-preview]').click(no_wait_after=True)
        result = self.capture_response(pending.value, f'{label}-preview')
        if result['status'] != 200:
            raise AssertionError('Daily preview failed; response retained.')
        self.page.wait_for_url(pending.value.url, wait_until='domcontentloaded')
        return self.page.locator('[data-report-daily-baseline]').inner_text()

    def prepare(self, day, label, *, analysis='changed_items', acknowledge_gap=False):
        baseline = self.preview(day, label)
        form = self.page.locator('[data-report-daily-prepare-form]')
        form.locator('[name="source_mode"]').select_option('refresh')
        form.locator('[name="analysis_mode"]').select_option(analysis)
        if acknowledge_gap:
            for item in form.locator('[name="acknowledge_gap_draft_ids"]').all():
                item.check()
        self.post(form.locator('[data-report-daily-generate]'), form.get_attribute('action'), f'{label}-prepare')
        self.page.wait_for_function("""() => {
            const root = document.querySelector('#project-run-status-fragment');
            return root && ['draft_ready', 'partial', 'failed', 'canceled'].includes(root.querySelector('h2')?.textContent.trim());
        }""", timeout=600000)
        status = self.page.locator('#project-run-status-fragment')
        state = status.locator('h2').inner_text().strip()
        operation_id = status.get_attribute('data-operation-id')
        write_json(self.evidence / f'{label}-operation.json', {
            'state': state, 'operation_id': operation_id, 'analysis_mode': analysis, 'text': status.inner_text(),
        })
        if not terminal_is_eligible(state, analysis):
            self.page.screenshot(path=str(self.evidence / f'{label}-failed.png'), full_page=True)
            raise AssertionError(f'Daily operation ended as {state}.')
        link = self.page.get_by_role('link', name='Open latest draft', exact=True)
        with self.page.expect_navigation(wait_until='domcontentloaded', timeout=120000):
            link.click()
        draft_id = self.page.locator('[data-report-editor]').get_attribute('data-draft-id')
        return {'draft_id': draft_id, 'operation_id': operation_id, 'state': state, 'baseline': baseline,
                'url': self.page.url}

    def save(self, draft_id, label):
        response = self.post(self.page.locator('[data-report-save-button]'),
                             f'/projects/{self.project_id}/stages/{self.stage_id}/reports/drafts/{draft_id}/save/',
                             label, expected=200)
        revision = str(response['body']['revision'])
        self.page.wait_for_function("revision => document.querySelector('[data-report-editor]')?.dataset.revision === revision",
                                    arg=revision)
        return response['body']

    def reopen(self, draft_id):
        self.page.goto(f'{self.stage_url}drafts/{draft_id}/', wait_until='domcontentloaded')
        self.page.locator('[data-report-editor]').wait_for()

    def finalize(self, draft_id, label):
        self.page.locator('[data-report-finalize-confirm]').check()
        result = self.post(self.page.locator('[data-report-finalize-button]'),
                           f'/projects/{self.project_id}/stages/{self.stage_id}/reports/drafts/{draft_id}/finalize/',
                           label)
        self.page.wait_for_url(self.base + result['location'], wait_until='domcontentloaded')
        self.page.screenshot(path=str(self.evidence / f'{label}.png'), full_page=True)
        return urlsplit(self.page.url).path.rstrip('/').rsplit('/', 1)[-1]

    def note(self, index):
        region = self.page.locator('[data-continuity-current-note-id] [data-report-wysiwyg-region]').nth(index)
        region.locator('[data-report-editor-surface]').click()
        editor = region.locator('.ProseMirror')
        editor.wait_for()
        editor.click()
        return region, editor

    def download_exports(self, directory):
        controls = self.page.locator('[data-report-exports]')
        for value, suffix in (('markdown', 'md'), ('xlsx', 'xlsx')):
            controls.locator('[data-report-export-format]').select_option(value)
            with self.page.expect_download(timeout=120000) as pending:
                controls.locator('[data-report-export-link]').click()
            pending.value.save_as(directory / f'report.{suffix}')

    def weekly(self, publications):
        self.page.goto(self.stage_url, wait_until='domcontentloaded')
        form = self.page.locator('[data-report-weekly-form]')
        form.locator('[name="series_id"]').select_option(self.series_id)
        form.locator('[name="period_key"]').select_option('iso8601:1:2026:ww44')
        form.locator('[name="template_choice"]').select_option(self.weekly_template)
        for control in form.locator('[name="publication_id"]').all():
            control.set_checked(control.get_attribute('value') in publications)
        result = self.post(form.locator('[data-report-weekly-create]'), form.get_attribute('action'), 'weekly-create')
        self.page.wait_for_url(self.base + result['location'], wait_until='domcontentloaded')
        draft_id = self.page.locator('[data-report-editor]').get_attribute('data-draft-id')
        return draft_id


def matching_option(select, template_id):
    options = select.locator('option').evaluate_all('(items) => items.map(item => item.value)')
    selected = [value for value in options if value.split('|')[1:2] == [template_id]]
    if len(selected) != 1:
        raise AssertionError('Expected one exact template revision.')
    return selected[0]


def terminal_is_eligible(state, analysis):
    return state == 'draft_ready' or analysis == 'manual_only' and state == 'partial'


def redacted_html(value):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(value, 'html.parser')
    for element in soup.select('input[name="csrfmiddlewaretoken"], input[type="password"]'):
        element['value'] = 'REDACTED'
    return str(soup)
