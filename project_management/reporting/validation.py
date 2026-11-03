from html.parser import HTMLParser
from urllib.parse import urlsplit

from project_management.app.domain.report_contracts import ReportError


ALLOWED_TAGS = {
    'html',
    'head',
    'meta',
    'title',
    'body',
    'main',
    'header',
    'section',
    'div',
    'h1',
    'h2',
    'h3',
    'p',
    'span',
    'strong',
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
    'ul',
    'li',
    'br',
    'a',
}
ALLOWED_ATTRS = {'style', 'lang', 'charset', 'href'}
FORBIDDEN_STYLE_PARTS = ('url(', 'expression', '@import', 'javascript:', 'behavior:', '-moz-binding')


class _SafetyParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.declarations = []
        self.body_count = 0
        self.html_count = 0
        self.errors = []

    def handle_decl(self, decl):
        self.declarations.append(decl.lower())

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.errors.append(f'unsupported tag {tag}')
        if tag == 'body':
            self.body_count += 1
        if tag == 'html':
            self.html_count += 1
        for name, value in attrs:
            self._validate_attr(tag, name.lower(), value or '')

    def _validate_attr(self, tag, name, value):
        if name.startswith('on') or name not in ALLOWED_ATTRS:
            self.errors.append(f'unsupported attr {name}')
            return
        if name == 'style' and any(part in value.lower() for part in FORBIDDEN_STYLE_PARTS):
            self.errors.append('unsafe style')
        if name == 'href':
            try:
                require_safe_https_url(value, 'REPORT_ARTIFACT_INVALID')
            except ReportError as error:
                self.errors.append(error.code)


def validate_rendered_html(document: str) -> None:
    if not document.lower().startswith('<!doctype html>'):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    parser = _SafetyParser()
    parser.feed(document)
    if parser.declarations[:1] != ['doctype html']:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if parser.html_count != 1 or parser.body_count != 1 or parser.errors:
        raise ReportError('REPORT_ARTIFACT_INVALID')


def require_safe_https_url(value: str, error_code: str = 'REPORT_INVALID') -> str:
    if type(value) is not str or _has_control(value):
        raise ReportError(error_code)
    if '\\' in value or any(character.isspace() for character in value):
        raise ReportError(error_code)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (AttributeError, ValueError):
        raise ReportError(error_code) from None
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or not parsed.netloc or not host or port is False:
        raise ReportError(error_code)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ReportError(error_code)
    if host == 'localhost' or host.endswith('.localhost'):
        raise ReportError(error_code)
    if _has_control(parsed.netloc) or _has_control(parsed.path):
        raise ReportError(error_code)
    return value


def _has_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
