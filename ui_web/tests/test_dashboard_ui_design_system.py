from pathlib import Path

from django.test import SimpleTestCase


class TestDashboardUiDesignSystem(SimpleTestCase):
    def test_shouldRequireSharedDesignSystemClassesForDirtyEditors(self):
        # Given
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        dirty_templates = [
            path
            for path in template_dir.rglob('*.html')
            if 'data-dirty-form' in path.read_text(encoding='utf-8')
        ]

        # Then
        self.assertGreaterEqual(len(dirty_templates), 2)
        for path in dirty_templates:
            content = path.read_text(encoding='utf-8')
            self.assertIn('dashboard-edit-form', content, str(path))
            self.assertIn('dashboard-action-bar', content, str(path))
            self.assertIn('dashboard-unsaved-banner', content, str(path))
            self.assertIn('Cancel Editing', content, str(path))

    def test_shouldRequireSharedRequiredTagClassInSetupEditors(self):
        # Given
        template_dir = Path(__file__).resolve().parents[1] / 'templates'
        setup_templates = [
            template_dir / 'bug_trend_scope_config.html',
            template_dir / 'partials' / 'provider_profile_editor.html',
        ]

        # Then
        for path in setup_templates:
            content = path.read_text(encoding='utf-8')
            self.assertNotIn('class="tag is-small is-danger', content, str(path))
            self.assertIn('dashboard-required-tag', content, str(path))

    def test_shouldDefineButtonTagAndEditorControlsThroughSharedCssContracts(self):
        # Given
        css_path = Path(__file__).resolve().parents[1] / 'static' / 'css' / 'main.css'
        css = css_path.read_text(encoding='utf-8')

        # Then
        self.assertIn('.dashboard-form-grid', css)
        self.assertIn('.dashboard-form-field', css)
        self.assertIn('.dashboard-action-bar', css)
        self.assertIn('.dashboard-action-group', css)
        self.assertIn('.dashboard-required-tag', css)
        self.assertIn('.dashboard-unsaved-banner', css)
        self.assertNotIn(".button,\n.input,\n.textarea,\n.select select,\n.tag", css)
