"""Static-asset helpers for Playwright checks that render dashboard HTML without a static server."""
import re
from pathlib import Path

from ui_web.static_assets import FEATURE_SCRIPTS, STYLESHEETS

STATIC_DIR = Path(__file__).resolve().parents[1] / 'static'
STATIC_ASSET_TAG = re.compile(
    r'\s*<(?:script src|link rel="(?:stylesheet|preload|icon)" href)="/static/[^"]*"[^>]*>(?:</script>)?'
)


def read_static(relative_path: str) -> str:
    return (STATIC_DIR / relative_path).read_text(encoding='utf-8')


def dashboard_css() -> str:
    return '\n'.join(read_static(path) for path in STYLESHEETS)


def feature_scripts_source() -> str:
    return '\n'.join(read_static(path) for path in FEATURE_SCRIPTS)


def strip_static_asset_tags(html: str) -> str:
    """Drop /static/ tags so routed pages never block on unresolvable asset requests."""
    return STATIC_ASSET_TAG.sub('', html)


def inline_dashboard_assets(html: str, scripts: tuple[str, ...] = FEATURE_SCRIPTS) -> str:
    html = strip_static_asset_tags(html).replace('</head>', f'<style>{dashboard_css()}</style></head>', 1)
    if scripts:
        script_source = '\n'.join(read_static(path) for path in scripts)
        html = html.replace('</body>', f'<script>{script_source}</script></body>', 1)
    return html


def shell_fragment_html(fragment: str, theme: str = 'dark') -> str:
    """Wrap a partial in the same shell landmarks that base.html renders."""
    return (
        f'<!doctype html><html lang="en" data-theme="{theme}">'
        '<head></head>'
        '<body class="app-body"><div class="app-shell" data-dashboard-layout><div class="app-main">'
        '<main class="app-content" id="app-content"><div class="app-content__inner" id="main-content">'
        f'{fragment}'
        '</div></main></div></div></body></html>'
    )
