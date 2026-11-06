from hashlib import sha256
import importlib
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from openpyxl import load_workbook
import pytest

from project_management.app.domain.report_contracts import ReportError
from project_management.tests.report_export_fixtures import HTML, html_cell


def export(requested_format, html=HTML, **changes):
    compiler = importlib.import_module('project_management.reporting.report_exports')
    args = {'source_sha256': sha256(html).hexdigest(), 'format_name': requested_format,
            'filename_stem': 'draft-70000000-0000-4000-8000-000000000001-r2'}
    return compiler.compile_export(html, **dict(args, **changes))


def test_shouldPreserveMarkdownRowsDailyBreaksLinksAndLiteralMarkup():
    result = export('markdown')
    text = result.content.decode('utf-8')
    row = next(line for line in text.splitlines() if '[ALPHA-1]' in line)
    assert 'ww44.1(Fixed):' in row and 'ww44.2(Fixed):' in row
    assert '<br>' in row[row.index('Initial update.'):row.index('ww44.2')]
    assert '[ALPHA-1](https://tracker.example.test/browse/ALPHA-1)' in row
    assert '\\<script\\>' in text and '<script>' not in text
    assert 'AR: @Alice review the validation result.' in text
    assert text.index('ALPHA-1') < text.index('ALPHA-2') < text.index('15000000003')
    assert result.source_sha256 == sha256(HTML).hexdigest()
    assert result.sha256 == sha256(result.content).hexdigest()
    assert result.media_type == 'text/markdown; charset=utf-8'
    assert result.filename.endswith('.md')
    assert 'paint_omitted' in result.warnings
    assert '#aa0000' not in text


def test_shouldWriteExcelTextRowsLinksAndNeverFormulas():
    result = export('xlsx')
    workbook = load_workbook(BytesIO(result.content), data_only=False)
    table = workbook['Table 1']
    assert [table.cell(row, 1).value for row in (2, 3, 4)] == ['ALPHA-1', 'ALPHA-2', '15000000003']
    assert 'ww44.1(Fixed): Initial update.\nww44.2(Fixed): Human follow-up.' in table['B2'].value
    assert table['A2'].hyperlink.target == 'https://tracker.example.test/browse/ALPHA-1'
    assert table['B3'].value == '=HYPERLINK("https://outside.example.test","run")'
    assert table['B3'].data_type == 's'
    assert all(cell.data_type != 'f' for sheet in workbook for row in sheet for cell in row)
    values = '\n'.join(str(cell.value) for sheet in workbook for row in sheet for cell in row if cell.value is not None)
    assert 'Manual <script> & literal | text.' in values
    assert 'AR: @Alice review the validation result.' in values
    assert result.source_sha256 in values and 'paint_omitted' in values
    with ZipFile(BytesIO(result.content)) as package:
        assert not any('externalLinks/' in name or 'vbaProject' in name or 'connections.xml' in name for name in package.namelist())
        for name in package.namelist():
            if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                root = ElementTree.fromstring(package.read(name))
                assert not root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}f')
    assert result.filename.endswith('.xlsx')
    assert 'xlsx_text_cells' in result.warnings


@pytest.mark.parametrize('format_name', ('markdown', 'xlsx'))
def test_shouldProduceSameBytesForRepeatedExport(format_name, monkeypatch):
    monkeypatch.setattr('zipfile.time.localtime', lambda *args: (2020, 1, 1, 1, 1, 0, 2, 1, -1))
    first = export(format_name)
    monkeypatch.setattr('zipfile.time.localtime', lambda *args: (2021, 2, 2, 2, 2, 0, 1, 33, -1))
    assert first.content == export(format_name).content


@pytest.mark.parametrize('value', ('x' * 32768, '&#128512;' * 16384, 'before\x01after'),
                         ids=('ascii-overflow', 'utf16-overflow', 'illegal-xml'))
def test_shouldRejectExcelTruncationAndIllegalXmlInsteadOfDroppingText(value):
    with pytest.raises(ReportError) as failed:
        export('xlsx', html_cell(value))
    assert failed.value.code in {'REPORT_LIMIT', 'REPORT_EXPORT_UNSUPPORTED'}


@pytest.mark.parametrize('format_name', ('markdown', 'xlsx'))
def test_shouldRejectUnqualifiedSpanStructure(format_name):
    with pytest.raises(ReportError) as failed:
        export(format_name, b'<!doctype html><html lang="en"><body><table><tr><td colspan="2">spanning</td></tr></table></body></html>')
    assert failed.value.code == 'REPORT_ARTIFACT_INVALID'


def test_shouldRejectNestedMarkdownTableExplicitly():
    with pytest.raises(ReportError) as failed:
        export('markdown', html_cell('<table><tr><td>nested</td></tr></table>'))
    assert failed.value.code == 'REPORT_EXPORT_UNSUPPORTED'


@pytest.mark.parametrize('changes', (
    {'source_sha256': '0' * 64}, {'format_name': 'pdf'}, {'filename_stem': '../outside'},
))
def test_shouldRejectInvalidDescriptor(changes):
    with pytest.raises(ReportError):
        export('markdown', **changes)


def test_shouldRejectUnsafeHtmlBeforeConversion():
    with pytest.raises(ReportError):
        export('markdown', b'<!doctype html><html><body><script>alert(1)</script></body></html>')


def test_shouldRejectMarkdownLineLimitWithoutTruncation():
    html = b'<!doctype html><html><body>' + b'<p>line</p>' * 50001 + b'</body></html>'
    with pytest.raises(ReportError) as failed:
        export('markdown', html)
    assert failed.value.code == 'REPORT_LIMIT'


def test_shouldCountMarkdownTableCellBreaksAgainstTheSameLineBudget(monkeypatch):
    adapter = importlib.import_module('project_management.reporting.export_markdown')
    monkeypatch.setattr(adapter, 'MAX_TEXT_LINES', 20)
    with pytest.raises(ReportError) as failed:
        export('markdown', html_cell('line<br>' * 21))
    assert failed.value.code == 'REPORT_LIMIT'


def test_shouldReportMissingExportDependencyWithoutBreakingHtmlRenderer(monkeypatch):
    compiler = importlib.import_module('project_management.reporting.report_exports')
    original = importlib.import_module

    def missing(name, *args, **kwargs):
        if name == 'markdownify':
            raise ImportError('Synthetic missing export dependency')
        return original(name, *args, **kwargs)

    monkeypatch.setattr(importlib, 'import_module', missing)
    with pytest.raises(ReportError) as failed:
        compiler.compile_export(HTML, source_sha256=sha256(HTML).hexdigest(),
                                format_name='markdown', filename_stem='saved')
    assert failed.value.code == 'REPORT_EXPORT_UNAVAILABLE'
    from project_management.reporting.html import ReportRenderer
    from project_management.tests.report_render_fixtures import safe_snapshot
    from project_management.app.domain.report_presentation import TemplateSelection
    report = ReportRenderer().render(safe_snapshot(days=()), TemplateSelection('daily-standup', '2', {}),
                                     draft_id='70000000-0000-4000-8000-000000000001', revision=1)
    assert b'<html' in report.html_document
