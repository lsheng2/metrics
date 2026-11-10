import json
import socket
import _socket
from dataclasses import dataclass, replace
from email import policy
from email.parser import BytesParser
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from project_management.app.api import reports as report_api
from project_management.app.domain.report_completion import ReferenceObservation
from project_management.services.report_completion import ReportCompletionService
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.storage.report_reference_admission import CompletionAdmissionStore
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario, ProjectApiStub
from project_management.tests.report_draft_fixtures import FixedClock, StaticSourceReader, draft_command
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.test_report_authoring_views import AuthoringUiArchive


@dataclass(frozen=True, slots=True)
class RouteResponse:
    status: int
    headers: dict
    body: bytes


class ReportAuthoringBrowserTestCase(CaptureArchiveScenario, ProjectRouteTestSupport, StaticLiveServerTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.archive = AuthoringUiArchive(Path(self.temporary.name) / 'browser-authoring-archive')
        self.actor = self.archive.actor
        self.project = self.archive.project
        self.stage = self.archive.stage
        self.source = BrowserReferenceSourceReader(rule_hash=self.stage.definition_hash)
        self.reference_verifier = ReferenceReceiptVerifier('browser-reference-secret')
        self.service = report_api.ReportDraftService(
            self.archive,
            self.source,
            report_api.ReportRenderer(),
            clock=FixedClock(),
            reference_verifier=self.reference_verifier,
        )
        self.completion = ReportCompletionService(
            self.service,
            self.source,
            BrowserReferenceReader(),
            self.reference_verifier,
            CompletionAdmissionStore(self.archive.config.root),
        )
        self.facade = None
        self._patch_report_facades()

    def report_facade(self):
        from ui_web.facades.project_reports import ProjectReportFacade

        if self.facade is None:
            self.facade = ProjectReportFacade(
                ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
                self.service,
                self.archive,
            )
        return self.facade

    def _patch_report_facades(self):
        from ui_web.views import project_reports
        from ui_web.views.report_completion import ReportDraftCompletionView

        classes = (
            project_reports.ProjectStageReportView,
            project_reports.ReportDraftCreateView,
            project_reports.ReportDraftEditView,
            project_reports.ReportDraftSaveView,
            project_reports.ReportDraftRenderView,
            project_reports.ReportDraftDownloadView,
            project_reports.ReportDraftClipboardView,
            project_reports.ReportDraftFinalizeView,
            project_reports.ReportDraftResumeView,
            project_reports.ReportPublicationView,
            project_reports.ReportPublicationRevisionView,
            project_reports.ReportPublicationDownloadView,
        )
        self.patch_view_factory(self.report_facade, *classes)
        self.patch_view_factory(lambda: self.completion, ReportDraftCompletionView, attribute='completion_factory')
        self.patch_view_factory(
            lambda: ProjectApiStub(self.project, self.stage, owner_subject=self.actor.subject),
            ReportDraftCompletionView,
            attribute='project_api_factory',
        )

    def editor_url(self, draft_id):
        from django.urls import reverse

        return self.live_server_url + reverse('ui_web:report_draft_edit', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft_id,
        })

    def create_draft(self, command=700):
        return self.service.create_authored(
            self.actor,
            self.project.id,
            self.stage.id,
            command_id=draft_command(command),
            selection=report_api.ReportSelection(capture_id=self.archive.capture_id, timezone='Asia/Shanghai'),
            template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
        )


def browser_page(url):
    return BrowserPage(url)


class BrowserReferenceSourceReader(StaticSourceReader):
    def membership(self, actor, project_id, stage_id, snapshot):
        identity = replace(snapshot.rows[0].identity, stable_id='ALPHA-1', display_key='ALPHA-1')
        source_key = replace(snapshot.rows[0].source_key, stable_id='ALPHA-1')
        return report_api.ScopeMembershipSnapshot(
            1,
            snapshot.capture_id,
            snapshot.source_commit,
            'a' * 64,
            snapshot.source_as_of,
            snapshot.rule_hash,
            'principal:browser',
            'complete',
            1,
            1,
            (report_api.ScopeMember(identity, source_key),),
            'b' * 64,
        )


class BrowserReferenceReader:
    def __init__(self):
        self.calls = []

    def supports(self, stage, principal_id):
        return True

    def read(self, context, member):
        self.calls.append((context, member))
        return ReferenceObservation(
            identity={
                'provider_id': member.provider_id,
                'endpoint_id': member.endpoint_id,
                'stable_id': member.stable_id,
                'display_key': member.display_key,
            },
            requested_key=member.display_key,
            current_key=member.display_key,
            canonical_url='https://tracker.example.test/jira/browse/' + member.display_key,
            title='Browser linked title',
            assignee={'id': 'dev-a', 'display_name': 'Alice'},
            assignee_state='assigned',
            observed_at='2026-11-03T01:00:00+00:00',
            source_updated_at='2026-11-02T23:59:00+00:00',
            lookup_kind='live',
            scope_snapshot_hash='b' * 64,
        )


class BrowserPage:
    def __init__(self, url):
        self.url = url

    def __enter__(self):
        self.original_connect = socket.socket.connect
        socket.socket.connect = local_only_connect
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True, channel='chrome')
        self.context = self.browser.new_context(
            http_credentials={'username': 'alice', 'password': 'wonder'},
            viewport={'width': 1440, 'height': 1000},
        )
        self.page = self.context.new_page()
        self.page.route('**/*', lambda route: route.continue_()
                        if route.request.url.startswith(('http://127.0.0.1:', 'http://localhost:', 'data:', 'blob:'))
                        else route.abort())
        self.page.goto(self.url, wait_until='domcontentloaded')
        self.page.wait_for_selector('[data-report-wysiwyg-region]')
        return self.page

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.browser.close()
            self.playwright.stop()
        finally:
            socket.socket.connect = self.original_connect


def form_fields_from_request(request):
    content_type = request.headers.get('content-type', '')
    data = request_body(request)
    if content_type.startswith('multipart/form-data'):
        message = BytesParser(policy=policy.default).parsebytes(
            f'Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n'.encode('utf-8') + data
        )
        return {
            part.get_param('name', header='content-disposition'): part.get_content()
            for part in message.iter_parts()
        }
    if content_type.startswith('application/x-www-form-urlencoded'):
        return {key: values[-1] for key, values in parse_qs(data.decode('utf-8')).items()}
    return {}


def fetch_local_route_response(route):
    body = request_body(route.request)
    request = Request(route.request.url, data=body, method=route.request.method)
    for key, value in route.request.headers.items():
        if key.lower() not in {'host', 'content-length'}:
            request.add_header(key, value)
    request.add_header('Authorization', 'Basic YWxpY2U6d29uZGVy')
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(request, timeout=10) as response:
            return RouteResponse(response.status, dict(response.headers.items()), response.read())
    except HTTPError as error:
        return RouteResponse(error.code, dict(error.headers.items()), error.read())


def fulfill_route_response(route, response):
    route.fulfill(status=response.status, headers=response.headers, body=response.body)


def authored_text_from_fields(fields):
    return '\n'.join(fragment_text(item['fragment']) for item in json.loads(fields['authored_edits']))


def request_body(request):
    value = getattr(request, 'post_data_buffer', None)
    if callable(value):
        value = value()
    if value is not None:
        return value
    text = request.post_data or ''
    return text.encode('utf-8')


def fragment_text(value):
    parts = []
    for block in value.get('blocks', []):
        if block.get('type') in {'paragraph', 'heading'}:
            parts.append(inline_text(block.get('content', [])))
        if block.get('type') == 'list':
            for item in block.get('items', []):
                parts.append(fragment_text({'blocks': item.get('blocks', [])}))
        if block.get('type') == 'table':
            parts.extend(inline_text(cell) for cell in block.get('headers', []))
            for row in block.get('rows', []):
                parts.extend(inline_text(cell) for cell in row)
    return '\n'.join(item for item in parts if item)


def inline_text(value):
    parts = []
    for item in value:
        if item.get('type') == 'text':
            parts.append(item.get('text', ''))
        if item.get('type') == 'link':
            parts.append(inline_text(item.get('content', [])))
    return ''.join(parts)


def local_only_connect(instance, address):
    host = address[0] if isinstance(address, tuple) else ''
    if host in {'127.0.0.1', '::1', 'localhost'}:
        return _socket.socket.connect(instance, address)
    raise AssertionError('External networking is forbidden in authoring browser tests')
