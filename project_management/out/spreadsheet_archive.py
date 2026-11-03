from io import BytesIO
from pathlib import PurePosixPath
import stat
import zlib
from xml.parsers import expat
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED, ZIP_STORED

from openpyxl.utils.cell import coordinate_to_tuple

from project_management.app.domain.spreadsheet import SpreadsheetError, check_now, selected_limits


class _WorksheetOrder:
    def __init__(self):
        self.stack, self.prefix, self.row, self.column = [], None, 0, 0

    def start(self, name, attributes):
        if not self.stack and name.rsplit('}', 1)[-1] == 'worksheet':
            self.prefix = name[:-len('worksheet')]
        parent = self.stack[-1] if self.stack else None
        if self.prefix is not None:
            if name == self.prefix + 'row':
                value = attributes.get('r', str(self.row + 1))
                if (parent != self.prefix + 'sheetData' or len(value) > 7
                        or not value.isascii() or not value.isdecimal()
                        or not self.row < int(value) <= 1048576):
                    raise SpreadsheetError('SPREADSHEET_WORKBOOK_INVALID', 'Worksheet row order is ambiguous.')
                self.row, self.column = int(value), 0
            elif name == self.prefix + 'c':
                if parent != self.prefix + 'row' or self.row == 0:
                    raise SpreadsheetError('SPREADSHEET_WORKBOOK_INVALID', 'Worksheet cell placement is invalid.')
                reference = attributes.get('r')
                try:
                    if reference is None:
                        row, column = self.row, self.column + 1
                    elif len(reference) > 10 or not reference.isascii():
                        raise ValueError()
                    else:
                        row, column = coordinate_to_tuple(reference)
                except (TypeError, ValueError):
                    raise SpreadsheetError('SPREADSHEET_WORKBOOK_INVALID', 'Worksheet cell reference is invalid.') from None
                if row != self.row or not self.column < column <= 16384:
                    raise SpreadsheetError('SPREADSHEET_WORKBOOK_INVALID', 'Worksheet cell order is ambiguous.')
                self.column = column
        self.stack.append(name)

    def end(self):
        self.stack.pop()


def _xml_parser(limits, budget):
    parser = expat.ParserCreate(namespace_separator='}')
    depth = [0]
    order = _WorksheetOrder()

    def start(name, attributes):
        depth[0] += 1
        budget['elements'] += 1
        if (depth[0] > limits.xml_depth or budget['elements'] > limits.xml_elements
                or len(attributes) > 128 or any(len(key) > 256 or len(value) > 4096
                                               for key, value in attributes.items())):
            raise SpreadsheetError('SPREADSHEET_XML_LIMIT', 'Workbook XML exceeds the supported structure bound.')
        order.start(name, attributes)

    def end(name):
        depth[0] -= 1
        order.end()

    def forbidden(*args):
        raise SpreadsheetError('SPREADSHEET_XML_INVALID', 'Workbook XML declarations are not permitted.')

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    return parser


def validate_archive(data, *, limits=None, check=None):
    limits = selected_limits(limits)
    check_now(check)
    if type(data) is not bytes:
        raise SpreadsheetError('SPREADSHEET_INPUT_INVALID', 'Workbook input must be bytes.')
    if len(data) > limits.input_bytes:
        raise SpreadsheetError('SPREADSHEET_INPUT_LIMIT', 'Workbook input exceeds its byte limit.')
    if not data.startswith(b'PK\x03\x04'):
        raise SpreadsheetError('SPREADSHEET_FORMAT_UNSUPPORTED', 'An OOXML Excel workbook is required.')
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > limits.archive_entries:
                raise SpreadsheetError('SPREADSHEET_ARCHIVE_LIMIT', 'The workbook has too many archive entries.')
            seen, expanded, budget = set(), 0, {'elements': 0}
            for entry in entries:
                check_now(check)
                name = entry.filename
                path = PurePosixPath(name)
                normalized = path.as_posix() + ('/' if entry.is_dir() else '')
                if (not name or len(name) > 256 or name != entry.orig_filename or name != normalized
                        or path.is_absolute() or '..' in path.parts or ':' in name or '\\' in name
                        or any(ord(char) < 32 for char in name) or name.casefold() in seen
                        or entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16)
                        or entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}):
                    raise SpreadsheetError('SPREADSHEET_ARCHIVE_INVALID', 'Workbook archive entries cannot be verified.')
                seen.add(name.casefold())
                if entry.file_size > limits.expanded_bytes - expanded:
                    raise SpreadsheetError('SPREADSHEET_EXPANSION_LIMIT', 'Workbook expansion exceeds its byte limit.')
                parser = _xml_parser(limits, budget) if name.lower().endswith(('.xml', '.rels')) else None
                with archive.open(entry) as stream:
                    while block := stream.read(16384):
                        check_now(check)
                        expanded += len(block)
                        if expanded > limits.expanded_bytes:
                            raise SpreadsheetError('SPREADSHEET_EXPANSION_LIMIT')
                        if parser is not None:
                            parser.Parse(block, False)
                    if parser is not None:
                        parser.Parse(b'', True)
            if '[content_types].xml' not in seen:
                raise SpreadsheetError('SPREADSHEET_FORMAT_UNSUPPORTED', 'The archive is not an OOXML workbook.')
    except (BadZipFile, EOFError, NotImplementedError, zlib.error):
        raise SpreadsheetError('SPREADSHEET_ARCHIVE_INVALID', 'The workbook archive is invalid.') from None
    except (expat.ExpatError, LookupError):
        raise SpreadsheetError('SPREADSHEET_XML_INVALID', 'The workbook XML is invalid.') from None
    return limits
