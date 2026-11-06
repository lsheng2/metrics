from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from django.test import Client, override_settings
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.translation import override
import pytest

from project_management.app.api import reports as report_api
from ui_web.report_template_forms import TemplateLibraryActionForm
from ui_web.report_template_view_model import editor_payload
from ui_web.tests.project_fixtures import ProjectRouteTestSupport, basic_header
from ui_web.tests.test_report_export_views import draft_url, environment


@pytest.mark.parametrize('kind', ['daily', 'weekly'])
def test_shouldCreateConciseTemplateThroughLibraryFormAndConstrainItsDataMenu(kind):
    form = TemplateLibraryActionForm({'action': f'standup_{kind}', 'command_id': str(uuid4()), 'name': 'Standup'})
    assert form.is_valid(), form.errors
    document, policy = form.template_payload()
    assert document['presentation_profile'] == 'standup/1'
    assert document['report_kind'] == kind
    revision = report_api.validate_report_template_revision('Standup', document, policy)
    assert revision.readiness == 'ready'
    payload = editor_payload(revision)
    assert [key for key, _ in payload['data_sources']] == ['meeting_matrix']
    assert payload['document']['presentation_profile'] == 'standup/1'


def test_shouldLocalizeStandupAndAuditChoicesWithoutChangingTheirValues():
    with override('zh-hans'):
        choices = dict(TemplateLibraryActionForm().fields['action'].choices)
        assert str(choices['standup_daily']) == '精简每日站会'
        markup = render_to_string('projects/reports/export_controls.html',
                                  {'export_url': '/local/export/', 'audit_available': True})
        assert 'value="audit_zip"' in markup and '完整审计附件' in markup


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldDownloadAuditOnlyFromAuthorizedPublication(tmp_path, monkeypatch):
    archive, service, draft, _ = environment(tmp_path, monkeypatch)
    client = Client()
    auth = {'HTTP_AUTHORIZATION': basic_header('alice', 'wonder')}
    publication = service.finalize_and_commit(
        archive.actor, archive.project.id, archive.stage.id, draft.draft_id,
        command_id=str(uuid4()), expected_revision=1,
    )
    url = reverse('ui_web:report_publication_export', kwargs={
        'project_id': archive.project.id, 'stage_id': archive.stage.id,
        'publication_id': publication.manifest.publication_id,
    })
    response = client.get(url, {'format': 'audit_zip'}, **auth)
    assert response.status_code == 200, response.content[:300]
    assert response.headers['Content-Type'] == 'application/zip'
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.headers['X-Report-Export-Revision'] == 'report-audit/1'
    assert response.headers['X-Report-Source-SHA256'] == publication.manifest_sha256
    with ZipFile(BytesIO(response.content)) as bundle:
        assert len(bundle.namelist()) == 8
    assert client.get(url, {'format': 'audit_zip'}).status_code == 401
    assert client.get(url, {'format': 'audit_zip'},
                      HTTP_AUTHORIZATION=basic_header('bob', 'builder')).status_code == 404
    assert client.post(url, **auth).status_code == 405
    assert client.get(url + '?format=audit_zip&format=markdown', **auth).status_code == 400
    assert client.get(url, {'format': 'audit_zip', 'revision': 1}, **auth).status_code == 400
    assert client.get(draft_url(archive, draft), {'revision': 1, 'format': 'audit_zip'}, **auth).status_code == 400
