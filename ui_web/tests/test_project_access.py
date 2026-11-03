import base64

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from metrics.middleware import BasicAuthMiddleware
from project_management.app.domain.contracts import ProjectActor
from ui_web.project_access import ProjectAccessError, project_actor


def basic_header(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


class TestProjectAccess(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def verified_request(self, username, password, path='/projects/'):
        captured = {}

        def responder(request):
            captured['request'] = request
            return HttpResponse('ok')

        request = self.factory.get(path, HTTP_AUTHORIZATION=basic_header(username, password))
        response = BasicAuthMiddleware(responder)(request)
        self.assertEqual(200, response.status_code)
        return captured['request']

    def assert_access_error(self, status_code, action):
        with self.assertRaises(ProjectAccessError) as raised:
            action()
        response = raised.exception.to_response()
        self.assertEqual(status_code, response.status_code)
        return response

    @override_settings(METRICS_BASIC_AUTH_USERS={'alice': 'wonder', 'bob': 'builder'},
                       METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
    def test_shouldUseVerifiedBasicAuthUsernameAsSeparateBrowserOwner(self):
        # Given
        alice = self.verified_request('alice', 'wonder', '/projects/?actor=local_operator')
        bob = self.verified_request('bob', 'builder', '/projects/?actor=basic:alice')
        alice.META['REMOTE_USER'] = 'local_operator'
        alice.session = {'project_actor': 'local_operator'}

        # When / Then
        self.assertEqual(ProjectActor('basic:alice'), project_actor(alice))
        self.assertEqual(ProjectActor('basic:bob'), project_actor(bob))

    @override_settings(METRICS_BASIC_AUTH_USERS={'alice': 'wonder', 'Alice': 'case', 'bob': 'builder'},
                       METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='alice')
    def test_shouldMapOnlyExactConfiguredUsernameToLocalOperator(self):
        # Given
        alice = self.verified_request('alice', 'wonder')
        case_variant = self.verified_request('Alice', 'case')
        bob = self.verified_request('bob', 'builder')

        # When / Then
        self.assertEqual(ProjectActor('local_operator'), project_actor(alice))
        self.assertEqual(ProjectActor('basic:Alice'), project_actor(case_variant))
        self.assertEqual(ProjectActor('basic:bob'), project_actor(bob))

    @override_settings(METRICS_BASIC_AUTH_USERS=None, METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
    def test_shouldRequireVerifiedCredentialsEvenWhenLegacyBasicAuthIsDisabled(self):
        # Given
        captured = {}

        def responder(request):
            captured['request'] = request
            return HttpResponse('legacy open')

        response = BasicAuthMiddleware(responder)(self.factory.get('/projects/'))

        # When / Then
        self.assertEqual(200, response.status_code)
        self.assertIsNone(captured['request'].metrics_basic_auth_username)
        denied = self.assert_access_error(401, lambda: project_actor(captured['request']))
        self.assertEqual('Basic realm="Restricted"', denied['WWW-Authenticate'])

    @override_settings(METRICS_BASIC_AUTH_USERS={'alice': 'wonder'}, METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
    def test_shouldRejectInvalidCredentialsWithoutPublishingVerifiedUsername(self):
        # Given
        request = self.factory.get('/projects/', HTTP_AUTHORIZATION=basic_header('alice', 'wrong'))

        # When
        response = BasicAuthMiddleware(lambda request: HttpResponse('ok'))(request)

        # Then
        self.assertEqual(401, response.status_code)
        self.assertIsNone(request.metrics_basic_auth_username)

    @override_settings(METRICS_BASIC_AUTH_USERS={' alice': 'wonder'}, METRICS_PROJECT_LOCAL_OPERATOR_USERNAME=' alice')
    def test_shouldRejectMalformedVerifiedAccountSubjectsSafely(self):
        # Given
        request = self.verified_request(' alice', 'wonder')

        # When / Then
        response = self.assert_access_error(403, lambda: project_actor(request))
        self.assertIn('Forbidden', response.content.decode('utf-8'))
        self.assertNotIn(' alice', response.content.decode('utf-8'))
