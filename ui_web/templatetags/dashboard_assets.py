from django import template
from django.templatetags.static import static
from django.utils.html import format_html_join

from ui_web.static_assets import SCRIPTS, STYLESHEETS

register = template.Library()


@register.simple_tag
def dashboard_stylesheets() -> str:
    return format_html_join('\n    ', '<link rel="stylesheet" href="{}">', ((static(path),) for path in STYLESHEETS))


@register.simple_tag
def dashboard_scripts() -> str:
    return format_html_join('\n    ', '<script src="{}"></script>', ((static(path),) for path in SCRIPTS))
