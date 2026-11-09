from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.views import defaults


class TestErrorPages(TestCase):

    def test_shouldRenderNotFoundPageInStandaloneFrame(self):
        # When
        response = self.client.get('/no-such-dashboard-page/')

        # Then
        content = response.content.decode()
        self.assertEqual(404, response.status_code)
        self.assertIn('class="standalone-body', content)
        self.assertIn('Page not found', content)
        self.assertIn('<code>/no-such-dashboard-page/</code>', content)
        self.assertIn(f'href="{reverse("ui_web:homepage")}"', content)
        self.assertNotIn('app-sidebar', content)

    def test_shouldRenderServerErrorPageFromAnEmptyContext(self):
        # Given
        request = RequestFactory().get('/broken/')

        # When
        response = defaults.server_error(request)

        # Then
        content = response.content.decode()
        self.assertEqual(500, response.status_code)
        self.assertIn('Something went wrong', content)
        self.assertIn('css/shell/standalone.css', content)
        self.assertIn("localStorage.getItem('dashboard-theme')", content)
        self.assertIn(f'href="{reverse("ui_web:homepage")}"', content)
