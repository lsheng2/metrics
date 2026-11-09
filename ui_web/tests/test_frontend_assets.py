import hashlib
import json
import re

from django.test import SimpleTestCase

from ui_web.static_assets import SCRIPTS, STYLESHEETS
from ui_web.tests.dashboard_asset_support import STATIC_DIR

UI_WEB_DIR = STATIC_DIR.parent
REPO_ROOT = UI_WEB_DIR.parent
VENDOR_DIR = STATIC_DIR / 'vendor'
ICON_CLASS = re.compile(r'\biconoir-([a-z0-9]+(?:-[a-z0-9]+)*)')
DYNAMIC_ICON_CLASS = re.compile(r'\biconoir-(?:\{|\$\{|[\'"`]\s*\+)')
TEMPLATE_ASSET = re.compile(r"\{%\s*static\s+'((?:css|js)/[^']+\.(?:css|js))'\s*%\}")


class TestFrontendAssets(SimpleTestCase):
    def test_shouldMatchEveryVendoredFileToTheAssetManifest(self):
        # Given
        manifest = self._manifest()
        files_on_disk = {
            path.relative_to(VENDOR_DIR).as_posix()
            for path in VENDOR_DIR.rglob('*')
            if path.is_file() and path.name != 'asset-manifest.json'
        }

        # When
        self.assertEqual(set(manifest['files']), files_on_disk)
        drifted = sorted(
            name for name, entry in manifest['files'].items()
            if hashlib.sha256((VENDOR_DIR / name).read_bytes()).hexdigest() != entry['sha256']
        )

        # Then
        self.assertEqual([], drifted, 'Rebuild with: cd ui_web/frontend && npm run build:vendor')

    def test_shouldVendorEveryLiteralIconClassUsedByTheDashboard(self):
        # Given
        icons = set(self._manifest()['icons'])
        sources = {path: path.read_text(encoding='utf-8') for path in self._icon_sources()}

        # When
        used = {name for text in sources.values() for name in ICON_CLASS.findall(text)}
        dynamic = sorted(
            path.relative_to(REPO_ROOT).as_posix()
            for path, text in sources.items()
            if DYNAMIC_ICON_CLASS.search(text)
        )

        # Then
        self.assertEqual([], sorted(used - icons), 'Rebuild with: cd ui_web/frontend && npm run build:vendor')
        self.assertEqual([], dynamic, 'Write literal iconoir-<name> classes so the vendor subset can find them')

    def test_shouldLoadEveryLayeredStylesheetThroughTheAssetManifest(self):
        # Given
        listed = set(STYLESHEETS) | set(SCRIPTS)
        layered = {
            path.relative_to(STATIC_DIR).as_posix()
            for folder in ('css/foundation', 'css/shell', 'css/pages')
            for path in (STATIC_DIR / folder).glob('*.css')
        }

        # When
        missing = sorted(path for path in listed if not (STATIC_DIR / path).is_file())
        unregistered = sorted(layered - listed)

        # Then
        self.assertEqual([], missing)
        self.assertEqual([], unregistered, 'Register split stylesheets in ui_web/static_assets.py')

    def test_shouldLoadEveryTopLevelAssetOnceThroughTheManifestOrItsPageTemplate(self):
        # Given
        manifest = set(SCRIPTS) | set(STYLESHEETS)
        page_assets = {
            asset
            for template in (UI_WEB_DIR / 'templates').rglob('*.html')
            for asset in TEMPLATE_ASSET.findall(template.read_text(encoding='utf-8'))
        }
        top_level = {
            path.relative_to(STATIC_DIR).as_posix()
            for folder, pattern in (('js', '*.js'), ('css', '*.css'))
            for path in (STATIC_DIR / folder).glob(pattern)
        }

        # When
        orphaned = sorted(top_level - manifest - page_assets)
        doubled = sorted(page_assets & manifest)

        # Then
        self.assertEqual([], orphaned, 'Register shared assets in ui_web/static_assets.py or load report-only assets from their page template')
        self.assertEqual([], doubled, 'base.html loads manifest assets once; page templates add only report-only assets')

    def _manifest(self):
        return json.loads((VENDOR_DIR / 'asset-manifest.json').read_text(encoding='utf-8'))

    def _icon_sources(self):
        yield from (UI_WEB_DIR / 'templates').rglob('*.html')
        yield from (REPO_ROOT / 'project_management' / 'reporting' / 'templates').rglob('*.html')
        editor_vendor = STATIC_DIR / 'js' / 'report_editor' / 'vendor'
        yield from (
            path for path in (STATIC_DIR / 'js').rglob('*.js')
            if editor_vendor not in path.parents
        )
        skipped = (UI_WEB_DIR / 'tests', UI_WEB_DIR / 'frontend')
        yield from (
            path for path in UI_WEB_DIR.rglob('*.py')
            if not any(root in path.parents for root in skipped)
        )
