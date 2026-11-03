from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook


def workbook_bytes(rows, *, sheet='Scope', others=True):
    book = Workbook()
    target = book.active
    target.title = sheet
    for row in rows:
        target.append(row)
    if others:
        book.create_sheet('Unselected').append(['SECRET-999'])
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def rewrite_workbook(raw, updates=None, extras=()):
    output = BytesIO()
    with ZipFile(BytesIO(raw)) as source, ZipFile(output, 'w', ZIP_DEFLATED) as target:
        for info in source.infolist():
            target.writestr(info.filename, (updates or {}).get(info.filename, source.read(info.filename)))
        for name, body in extras:
            target.writestr(name, body)
    return output.getvalue()
