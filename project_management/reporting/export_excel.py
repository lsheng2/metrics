from datetime import datetime
from io import BytesIO
import re
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_exports import GENERATOR_REVISION, MAX_CELLS, MAX_TEXT_LINES


BLOCKS = {'p', 'div', 'section', 'article', 'header', 'footer', 'h1', 'h2', 'h3',
          'h4', 'li', 'blockquote', 'pre', 'tr', 'table', 'ul', 'ol'}
WHITESPACE = re.compile(r'[ \t\r\n\f]+')
ILLEGAL_XML = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')


def render_excel(body, source_sha256, openpyxl, warnings):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.writer.excel import ExcelWriter

    workbook = openpyxl.Workbook()
    workbook.properties.creator = 'Metrics Dashboard'
    workbook.properties.lastModifiedBy = 'Metrics Dashboard'
    workbook.properties.created = datetime(2000, 1, 1)
    workbook.properties.modified = datetime(2000, 1, 1)
    info = workbook.active
    info.title = 'Information'
    used_cells = 0

    def put(sheet, row, column, value):
        nonlocal used_cells
        used_cells += 1
        if used_cells > MAX_CELLS:
            raise ReportError('REPORT_LIMIT')
        validate_cell_text(value)
        cell = sheet.cell(row, column, value)
        cell.data_type = 's'
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        return cell

    for index, values in enumerate((
        ('Generator', GENERATOR_REVISION),
        ('Source HTML SHA256', source_sha256),
        ('Representation', 'Derived text tables; original HTML and JSON retain full formatting.'),
        ('Warnings', ', '.join(warnings)),
    ), 1):
        for column, value in enumerate(values, 1):
            put(info, index, column, value)
    report = workbook.create_sheet('Report text')
    lines = visible_text(body).splitlines()
    if len(lines) > MAX_TEXT_LINES:
        raise ReportError('REPORT_LIMIT')
    for index, text in enumerate(lines, 1):
        put(report, index, 1, text)
    for index, table in enumerate(body.find_all('table'), 1):
        sheet = workbook.create_sheet(f'Table {index}')
        rows = [row for row in table.find_all('tr') if row.find_parent('table') is table]
        for row_number, row in enumerate(rows, 1):
            for column, element in enumerate(row.find_all(['td', 'th'], recursive=False), 1):
                cell = put(sheet, row_number, column, visible_text(element))
                links = {link['href'] for link in element.find_all('a', href=True)}
                if len(links) == 1:
                    cell.hyperlink = next(iter(links))
                    cell.style = 'Hyperlink'
                    cell.alignment = Alignment(wrap_text=True, vertical='top')
                if element.name == 'th':
                    cell.font = Font(bold=True)
                    cell.fill = PatternFill('solid', fgColor='E0F2F1')
        sheet.freeze_panes = 'B2'
    links = workbook.create_sheet('Links')
    put(links, 1, 1, 'Label')
    put(links, 1, 2, 'URL')
    for index, link in enumerate(body.find_all('a', href=True), 2):
        put(links, index, 1, visible_text(link))
        cell = put(links, index, 2, link['href'])
        cell.hyperlink = link['href']
        cell.style = 'Hyperlink'
    for sheet in workbook:
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = 48 if len(column) else 20
    stream = BytesIO()
    # The public writer avoids Workbook.save's wall-clock modified property.
    ExcelWriter(workbook, ZipFile(stream, 'w', ZIP_STORED)).save()
    return stable_zip(stream.getvalue())


def validate_cell_text(value):
    if ILLEGAL_XML.search(value):
        raise ReportError('REPORT_EXPORT_UNSUPPORTED')
    if len(value.encode('utf-16-le')) // 2 > 32767:
        raise ReportError('REPORT_LIMIT')


def visible_text(element):
    parts = []

    def visit(node, pre=False):
        name = getattr(node, 'name', None)
        if name is None:
            value = str(node)
            if not pre:
                value = WHITESPACE.sub(' ', value)
                if not parts or parts[-1].endswith('\n'):
                    value = value.lstrip(' ')
            if value:
                parts.append(value)
            return
        if name == 'br':
            parts.append('\n')
            return
        pre = pre or name == 'pre' or 'white-space:pre-wrap' in str(node.get('style', '')).replace(' ', '')
        block = name in BLOCKS
        if block and parts and not parts[-1].endswith('\n'):
            parts.append('\n')
        if name == 'li':
            marker = f'{len(node.find_previous_siblings("li")) + 1}. ' if node.parent.name == 'ol' else '- '
            parts.append(marker)
        for child in node.children:
            visit(child, pre)
        if name in {'td', 'th'} and node is not element:
            parts.append('\t')
        if block and parts and not parts[-1].endswith('\n'):
            parts.append('\n')

    visit(element)
    return ''.join(parts).strip('\n')


def stable_zip(content):
    output = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(output, 'w', ZIP_STORED) as target:
        for name in sorted(source.namelist()):
            member = ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            member.compress_type = ZIP_STORED
            target.writestr(member, source.read(name))
    return output.getvalue()
