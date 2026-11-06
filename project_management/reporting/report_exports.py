import importlib
from importlib.metadata import PackageNotFoundError, version
import re

from project_management.app.domain.capture_values import sha256_bytes
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_exports import (
    GENERATOR_REVISION, MAX_CELLS, MAX_EXPORT_BYTES, MAX_SOURCE_BYTES, MAX_TABLES, ReportExport,
)
from project_management.reporting.validation import validate_rendered_html


DEPENDENCIES = {'beautifulsoup4': '4.15.0', 'markdownify': '1.2.3', 'openpyxl': '3.1.5'}
MIME_TYPES = {
    'markdown': 'text/markdown; charset=utf-8',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


def dependency(module, distribution=None):
    distribution = distribution or module
    try:
        if version(distribution) != DEPENDENCIES[distribution]:
            raise ImportError
        return importlib.import_module(module)
    except (ImportError, PackageNotFoundError):
        raise ReportError('REPORT_EXPORT_UNAVAILABLE') from None


def compile_export(html, *, source_sha256, format_name, filename_stem):
    if (type(html) is not bytes or type(format_name) is not str or format_name not in MIME_TYPES
            or type(filename_stem) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,96}', filename_stem) is None):
        raise ReportError('REPORT_INVALID')
    if len(html) > MAX_SOURCE_BYTES:
        raise ReportError('REPORT_LIMIT')
    if source_sha256 != sha256_bytes(html):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    try:
        source = html.decode('utf-8')
    except UnicodeError:
        raise ReportError('REPORT_EXPORT_UNSUPPORTED') from None
    validate_rendered_html(source)
    bs4 = dependency('bs4', 'beautifulsoup4')
    soup = bs4.BeautifulSoup(source, 'html.parser')
    body = soup.body
    if body is None or body.find(['img', 'audio', 'video', 'iframe', 'object']):
        raise ReportError('REPORT_EXPORT_UNSUPPORTED')
    for comment in body.find_all(string=lambda item: isinstance(item, bs4.Comment)):
        comment.extract()
    tables = body.find_all('table')
    cells = body.find_all(['td', 'th'])
    if len(tables) > MAX_TABLES or len(cells) > MAX_CELLS:
        raise ReportError('REPORT_LIMIT')
    for cell in cells:
        if any(str(cell.get(name, '1')) != '1' for name in ('rowspan', 'colspan')):
            raise ReportError('REPORT_EXPORT_UNSUPPORTED')
    warnings = ('paint_omitted',)
    if format_name == 'markdown':
        if any(table.find_parent('table') for table in tables):
            raise ReportError('REPORT_EXPORT_UNSUPPORTED')
        from project_management.reporting.export_markdown import render_markdown
        content = render_markdown(body, source_sha256, dependency('markdownify'))
        suffix = 'md'
    else:
        from project_management.reporting.export_excel import render_excel
        warnings += ('xlsx_text_cells',)
        content = render_excel(body, source_sha256, dependency('openpyxl'), warnings)
        suffix = 'xlsx'
    if len(content) > MAX_EXPORT_BYTES:
        raise ReportError('REPORT_LIMIT')
    return ReportExport(format_name, MIME_TYPES[format_name], f'{filename_stem}.{suffix}', content,
                        sha256_bytes(content), source_sha256, GENERATOR_REVISION, warnings)
