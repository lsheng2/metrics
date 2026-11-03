from dataclasses import dataclass, fields
import re


class SpreadsheetError(Exception):
    def __init__(self, code, message=None):
        self.code = code
        self.message = message or 'Workbook input could not be verified.'
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class SpreadsheetBounds:
    input_bytes: int = 512 * 1024
    expanded_bytes: int = 8 * 1024**2
    archive_entries: int = 128
    xml_elements: int = 100000
    xml_depth: int = 64
    scan_rows: int = 10000
    diagnostics: int = 500
    worksheets: int = 32

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if type(value) is not int or not 1 <= value <= field.default:
                raise SpreadsheetError('SPREADSHEET_LIMIT_INVALID', 'Workbook limits exceed supported bounds.')


DEFAULT_BOUNDS = SpreadsheetBounds()


def selected_limits(limits):
    if limits is None:
        return DEFAULT_BOUNDS
    if not isinstance(limits, SpreadsheetBounds):
        raise SpreadsheetError('SPREADSHEET_LIMIT_INVALID')
    return limits


def check_now(check):
    if check is not None:
        if not callable(check):
            raise SpreadsheetError('SPREADSHEET_INPUT_INVALID')
        check()


def validate_provider(provider_id):
    if not isinstance(provider_id, str) or provider_id not in {'jira', 'hsdes'}:
        raise SpreadsheetError('SPREADSHEET_PROVIDER_UNSUPPORTED')


def valid_token(provider_id, token):
    if re.fullmatch(r'[1-9][0-9]{0,63}', token):
        return True
    return provider_id == 'jira' and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*-[1-9][0-9]*', token) is not None
