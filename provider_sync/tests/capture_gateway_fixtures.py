from dataclasses import replace
from datetime import UTC, datetime, timedelta
import io
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import uuid

import requests
from urllib3.response import HTTPResponse

from bug_metrics.app.api.provider_connections import ProviderConnectionResolver
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.app.api.capture_archive import CaptureIntent, RawPageRef
from provider_sync.app.api.access import ProviderAccessService
from provider_sync.app.api.access_contracts import AccessContext, CaptureLimits
from provider_sync.out.capture_reader import BoundCaptureReader
from provider_sync.out.jira_capture import JiraCaptureAdapter
from provider_sync.app.spi.capture import ArchivePageSink


def attach_sink(lease):
    pages = []
    context = lease.context
    intent = CaptureIntent(context.project_id, context.stage_id, context.capture_id,
                           context.request_id, lease.source_identity, 'a' * 64,
                           ('facts', 'comments', 'history'), context.deadline_at)

    def append(raw):
        pages.append(raw)
        return RawPageRef(hashlib.sha256(raw.page_key.encode()).hexdigest(),
                          hashlib.sha256(raw.payload).hexdigest(), len(raw.payload),
                          raw.content_type, raw.request_fingerprint)

    lease.attach_archive_sink(ArchivePageSink(intent, append))
    return pages


def comment(number, body):
    return {'id': str(number), 'body': body, 'created': '2026-11-01T01:00:00.000+0000',
            'updated': '2026-11-01T01:00:00.000+0000', 'author': {'key': 'engineer-1'}}


def issue(number='101', *, status='Closed', updated='2026-11-01T01:00:00.000+0000', **fields):
    return {
        'id': number, 'key': f'ALPHA-{number}',
        'fields': {'summary': 'Interface check', 'description': 'Investigate retained evidence.',
                   'updated': updated, 'status': {'name': status}, 'resolution': {'name': 'Fixed'},
                   'assignee': {'key': 'engineer-1'}, 'issuelinks': [], 'attachment': [],
                   'priority': {'name': 'High'}, 'reporter': {'key': 'reporter-1'},
                   'created': '2026-10-01T01:00:00.000+0000', 'fixVersions': [], 'versions': [],
                   'labels': [], **fields},
        'changelog': {'startAt': 0, 'maxResults': 100, 'total': 0, 'histories': []},
        'names': {}, 'schema': {},
    }


def page(rows, start=0, total=None, name='issues'):
    return {'startAt': start, 'maxResults': 100, 'total': len(rows) if total is None else total, name: rows}


class FixtureHttpAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, responder):
        super().__init__(max_retries=0)
        self.responder = responder
        self.requests = []
        self.responses = []

    def send(self, request, **kwargs):
        parsed = urlsplit(request.url)
        params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        self.requests.append((request.method, parsed.path, params))
        response_value = self.responder(parsed.path, params)
        if len(response_value) == 3:
            status, value, headers = response_value
        else:
            status, value = response_value
            headers = {}
        data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        response = requests.Response()
        response.status_code = status
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Length'] = str(len(data))
        response.headers.update(headers)
        response.raw = HTTPResponse(body=io.BytesIO(data), preload_content=False)
        response.url = request.url
        response.request = request
        self.responses.append(response)
        return response


class JiraFixture:
    def __init__(self, case, *, archive=None, responder=None, query=None):
        self.case = case
        self.rows = [issue()]
        self.comments = [comment(201, 'A'), comment(202, 'B'), comment(203, 'C')]
        self.principal = 'principal-1'
        self.filters = {}
        self.query = query or case.stage.descriptor.query
        descriptor = replace(case.stage.descriptor, query=self.query)
        self.stage = replace(case.stage, descriptor=descriptor, definition_hash=descriptor.definition_hash())
        self.project_api = ProjectApiStub(case.project, self.stage)
        self.transport = FixtureHttpAdapter(responder or self.respond)
        self.registry = ProjectProviderProfileRegistry.from_records([{
            'profile_id': descriptor.profile_id, 'provider_id': 'jira', 'display_name': 'Alpha Jira',
            'connection_settings': {'base_url': descriptor.endpoint, 'auth_mode': 'server_pat',
                                    'credentials': {'token': 'synthetic-only-token'}},
        }])
        self.resolver = ProviderConnectionResolver(SimpleNamespace(), self.registry)
        self.service = ProviderAccessService(
            self.project_api, self.resolver, {'jira': JiraCaptureAdapter()}, archive,
            reader_factory=self.reader_factory, profile_registry=self.registry,
        )

    def reader_factory(self, *, info, session):
        session.mount('https://', self.transport)
        return BoundCaptureReader(info=info, session=session)

    def context(self, **changes):
        context = AccessContext(self.case.actor, self.case.project.id, self.stage.id,
                                str(uuid.uuid4()), str(uuid.uuid4()), datetime.now(UTC) + timedelta(minutes=5),
                                CaptureLimits(page_size=2))
        return replace(context, **changes)

    def respond(self, path, params):
        if path == '/jira/rest/api/2/myself':
            return 200, {'key': self.principal, 'name': 'read-user'}
        if path.startswith('/jira/rest/api/2/filter/'):
            key = path.rsplit('/', 1)[1]
            return 200, {'id': key, 'jql': self.filters[key]}
        if path == '/jira/rest/api/2/search':
            if params.get('maxResults') == '0':
                return 200, page([], total=len(self.rows))
            start = int(params['startAt'])
            maximum = int(params['maxResults'])
            selected = params['fields'].split(',')
            rows = [{'id': row['id'], 'key': row['key'],
                     'fields': {key: value for key, value in row['fields'].items() if key in selected}}
                    for row in self.rows[start:start + maximum]]
            return 200, page(rows, start, len(self.rows))
        if path.endswith('/comment'):
            start = int(params['startAt'])
            maximum = int(params['maxResults'])
            return 200, page(self.comments[start:start + maximum], start, len(self.comments), 'comments')
        if path.startswith('/jira/rest/api/2/issue/'):
            key = path.rsplit('/', 1)[1]
            found = next((row for row in self.rows if row['id'] == key), None)
            return (200, found) if found else (404, {'errorMessages': ['Not available.']})
        raise AssertionError(f'Unexpected synthetic path: {path}')
