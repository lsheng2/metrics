from hashlib import sha256
import importlib
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from django.test import Client, override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_draft_fixtures import StaticSourceReader
from ui_web.facades.project_reports import ProjectReportFacade
from ui_web.tests.project_fixtures import ProjectRouteTestSupport, basic_header
from ui_web.tests.test_report_authoring_views import AuthoringUiArchive


def environment(tmp_path, monkeypatch):
    views = importlib.import_module('ui_web.views.report_exports')
    archive = AuthoringUiArchive(tmp_path / 'archive')
    service = report_api.ReportDraftService(
        archive, StaticSourceReader(rule_hash=archive.stage.definition_hash), report_api.ReportRenderer(),
    )
    args = (archive.actor, archive.project.id, archive.stage.id)
    draft = service.create_authored(
        *args, command_id=str(uuid4()),
        selection=report_api.ReportSelection(capture_id=archive.capture_id, timezone='Asia/Shanghai'),
        template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2'),
    )
    facade = ProjectReportFacade(ProjectApiStub(archive.project, archive.stage, archive.actor.subject), service, archive)
    for cls in (views.ReportDraftExportView, views.ReportPublicationExportView):
        monkeypatch.setattr(cls, 'facade_factory', staticmethod(lambda: facade))
    return archive, service, draft, facade


def draft_url(archive, draft):
    return reverse('ui_web:report_draft_export', kwargs={
        'project_id': archive.project.id, 'stage_id': archive.stage.id, 'draft_id': draft.draft_id,
    })


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldReturnRealDraftAndPublicationExportsWithPrivateHashes(tmp_path, monkeypatch):
    archive, service, draft, facade = environment(tmp_path, monkeypatch)
    client = Client()
    auth = {'HTTP_AUTHORIZATION': basic_header('alice', 'wonder')}
    url = draft_url(archive, draft)
    for format_name in ('markdown', 'xlsx'):
        response = client.get(url, {'revision': 1, 'format': format_name}, **auth)
        assert response.status_code == 200, response.content[:500]
        assert response.headers['Cache-Control'] == 'private, no-store'
        assert response.headers['X-Report-Export-SHA256'] == sha256(response.content).hexdigest()
        assert response.headers['X-Report-Export-Revision'] == 'report-derived/1'
        assert 'attachment;' in response.headers['Content-Disposition']
        if format_name == 'markdown':
            assert b'DEMO-101' in response.content
        else:
            assert ZipFile(BytesIO(response.content)).testzip() is None
    publication = service.finalize_and_commit(
        archive.actor, archive.project.id, archive.stage.id, draft.draft_id,
        command_id=str(uuid4()), expected_revision=1,
    )
    original = service.read_artifact(archive.actor, archive.project.id, archive.stage.id,
                                     publication.manifest.publication_id, 'html')
    published_url = reverse('ui_web:report_publication_export', kwargs={
        'project_id': archive.project.id, 'stage_id': archive.stage.id,
        'publication_id': publication.manifest.publication_id,
    })
    response = client.get(published_url, {'format': 'markdown'}, **auth)
    assert response.status_code == 200, response.content[:500]
    assert response.headers['X-Report-Source-SHA256'] == sha256(original).hexdigest()
    assert service.read_artifact(archive.actor, archive.project.id, archive.stage.id,
                                 publication.manifest.publication_id, 'html') == original


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldRefuseForeignOwnerMethodsAndAmbiguousQueries(tmp_path, monkeypatch):
    archive, _, draft, facade = environment(tmp_path, monkeypatch)
    client = Client()
    url = draft_url(archive, draft)
    auth = {'HTTP_AUTHORIZATION': basic_header('alice', 'wonder')}
    assert client.get(url, {'revision': 1, 'format': 'markdown'}).status_code == 401
    assert client.get(url, {'revision': 1, 'format': 'markdown'},
                      HTTP_AUTHORIZATION=basic_header('bob', 'builder')).status_code == 404
    assert client.post(url, {}, **auth).status_code == 405
    for query in ('', 'format=markdown', 'revision=1', 'revision=0&format=markdown',
                  'revision=1&format=pdf', 'revision=1&format=markdown&endpoint=x',
                  'revision=1&revision=2&format=markdown', 'revision=1&format=xlsx&format=markdown'):
        assert client.get(url + '?' + query, **auth).status_code == 400, query

    def unavailable(*args, **kwargs):
        raise report_api.ReportError('REPORT_EXPORT_UNAVAILABLE')

    monkeypatch.setattr(facade, 'export_draft', unavailable)
    response = client.get(url, {'revision': 1, 'format': 'markdown'}, **auth)
    assert response.status_code == 503
