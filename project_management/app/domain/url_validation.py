from urllib.parse import urlsplit

from project_management.app.domain.report_contracts import ReportError


def require_safe_https_url(value: str, error_code: str = 'REPORT_INVALID', *, allow_query_fragment: bool = True) -> str:
    if type(value) is not str or _has_control(value):
        raise ReportError(error_code)
    if '\\' in value or any(character.isspace() for character in value):
        raise ReportError(error_code)
    try:
        parsed = urlsplit(value)
        parsed.port
    except (AttributeError, ValueError):
        raise ReportError(error_code) from None
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or not parsed.netloc or not host:
        raise ReportError(error_code)
    if parsed.username or parsed.password:
        raise ReportError(error_code)
    if not allow_query_fragment and (parsed.query or parsed.fragment):
        raise ReportError(error_code)
    if host == 'localhost' or host.endswith('.localhost'):
        raise ReportError(error_code)
    if _has_control(parsed.netloc) or _has_control(parsed.path) or _has_control(parsed.query) or _has_control(parsed.fragment):
        raise ReportError(error_code)
    return value


def _has_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
