from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import math

import openpyxl
from openpyxl.utils.cell import column_index_from_string, get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

from project_management.app.domain.spreadsheet import SpreadsheetError, check_now, valid_token, validate_provider
from project_management.out.spreadsheet_archive import validate_archive


@contextmanager
def _workbook(data, limits, check):
    limits = validate_archive(data, limits=limits, check=check)
    try:
        book = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=False,
                                      keep_links=False, keep_vba=False)
    except MemoryError:
        raise SpreadsheetError('SPREADSHEET_RESOURCE_LIMIT', 'Workbook processing exhausted its resource bound.') from None
    except InvalidFileException:
        raise SpreadsheetError('SPREADSHEET_FORMAT_UNSUPPORTED', 'The workbook format is unsupported.') from None
    except (ValueError, TypeError, KeyError, IndexError, OSError, OverflowError):
        raise SpreadsheetError('SPREADSHEET_WORKBOOK_INVALID', 'The workbook cannot be read safely.') from None
    try:
        check_now(check)
        if (len(book.sheetnames) > limits.worksheets or
                any(not isinstance(name, str) or not name or len(name) > 128
                    or any(ord(char) < 32 for char in name) for name in book.sheetnames)):
            raise SpreadsheetError('SPREADSHEET_SHEET_LIMIT', 'Workbook sheets exceed the supported bound.')
        yield book, limits
    finally:
        book.close()


def inspect_workbook(data, *, limits=None, check=None):
    with _workbook(data, limits, check) as (book, _):
        return {'schema_version': 1, 'source_sha256': sha256(data).hexdigest(),
                'file_bytes': len(data), 'sheets': tuple(book.sheetnames)}


def _selection(sheet, column, first_row, max_items):
    if (not isinstance(sheet, str) or not 1 <= len(sheet) <= 128
            or not isinstance(column, str) or not 1 <= len(column) <= 3
            or not column.isascii() or not column.isalpha()
            or type(first_row) is not int or not 1 <= first_row <= 1048576
            or type(max_items) is not int or not 1 <= max_items <= 500):
        raise SpreadsheetError('SPREADSHEET_SELECTION_INVALID', 'Explicit worksheet, column and row are required.')
    try:
        index = column_index_from_string(column.upper())
    except ValueError:
        raise SpreadsheetError('SPREADSHEET_SELECTION_INVALID') from None
    if not 1 <= index <= 16384:
        raise SpreadsheetError('SPREADSHEET_SELECTION_INVALID')
    return index, get_column_letter(index)


def _token(cell, provider_id):
    value = cell.value
    if value is None or isinstance(value, str) and not value.strip():
        return None, None
    if cell.data_type == 'f':
        return None, 'FORMULA'
    if cell.data_type == 'e':
        return None, 'CELL_ERROR'
    if type(value) is int:
        if not 1 <= value <= 999999999999999:
            return None, 'NUMBER_PRECISION'
        value = str(value)
    elif type(value) is float:
        if not math.isfinite(value) or value != int(value) or not 1 <= value <= 999999999999999:
            return None, 'NUMBER_PRECISION'
        value = str(int(value))
    elif not isinstance(value, str):
        return None, 'CELL_TYPE'
    token = value.strip()
    if len(token) > 256:
        return None, 'TOKEN_LENGTH'
    if not valid_token(provider_id, token):
        return None, 'INVALID_TOKEN'
    return token, None


def _diagnostic(row, column, value, code, *, severity='error', duplicate_of=None):
    text = '' if value is None else str(value)
    return {'row': row, 'cell': f'{column}{row}', 'code': code, 'severity': severity,
            'value': text[:256], 'value_truncated': len(text) > 256, 'duplicate_of': duplicate_of}


def _rows(iterator):
    while True:
        try:
            row = next(iterator)
        except StopIteration:
            return
        except MemoryError:
            raise SpreadsheetError('SPREADSHEET_RESOURCE_LIMIT') from None
        except (ValueError, TypeError, KeyError, IndexError, OSError, OverflowError):
            raise SpreadsheetError('SPREADSHEET_WORKBOOK_INVALID', 'Worksheet cells cannot be read safely.') from None
        yield row


def extract_workbook(data, *, provider_id, sheet, column, first_row=2,
                     max_items=500, limits=None, check=None):
    validate_provider(provider_id)
    index, column = _selection(sheet, column, first_row, max_items)
    with _workbook(data, limits, check) as (book, limits):
        if sheet not in book.sheetnames or not hasattr(book[sheet], 'iter_rows'):
            raise SpreadsheetError('SPREADSHEET_SELECTION_INVALID', 'The selected worksheet is unavailable.')
        selected = book[sheet]
        selected.reset_dimensions()
        tokens, first, diagnostics, selected_rows = [], {}, [], []
        scanned = blanks = duplicates = 0
        rows = selected.iter_rows(min_row=first_row, min_col=index, max_col=index)
        try:
            for row_number, cells in enumerate(_rows(rows), first_row):
                check_now(check)
                scanned += 1
                if scanned > limits.scan_rows:
                    raise SpreadsheetError('SPREADSHEET_ROW_LIMIT', 'The selected range exceeds its row limit.')
                cell = cells[0]
                token, error = _token(cell, provider_id)
                if error:
                    diagnostics.append(_diagnostic(row_number, column, cell.value, error))
                elif token is None:
                    blanks += 1
                else:
                    selected_rows.append({'row': row_number, 'cell': f'{column}{row_number}',
                                          'raw_value': cell.value, 'token': token})
                    if token in first:
                        duplicates += 1
                        diagnostics.append(_diagnostic(row_number, column, cell.value, 'DUPLICATE',
                                                       severity='warning', duplicate_of=first[token]))
                    else:
                        if len(tokens) >= max_items:
                            raise SpreadsheetError('SPREADSHEET_ITEM_LIMIT', 'The candidate list exceeds its item limit.')
                        first[token] = row_number
                        tokens.append(token)
                if len(diagnostics) > limits.diagnostics:
                    raise SpreadsheetError('SPREADSHEET_DIAGNOSTIC_LIMIT', 'Too many input diagnostics require correction.')
        finally:
            rows.close()
        if not tokens and not diagnostics:
            diagnostics.append(_diagnostic(first_row, column, None, 'EMPTY_SCOPE'))
        check_now(check)
        return {
            'schema_version': 1, 'source_sha256': sha256(data).hexdigest(), 'file_bytes': len(data),
            'provider_id': provider_id, 'sheet': sheet, 'column': column, 'first_row': first_row,
            'rows_scanned': scanned, 'blank_rows': blanks, 'duplicate_rows': duplicates,
            'tokens': tuple(tokens), 'selected_rows': tuple(selected_rows), 'diagnostics': tuple(diagnostics),
            'resolved': False, 'can_confirm': bool(tokens) and not any(row['severity'] == 'error' for row in diagnostics),
        }
