from collections.abc import Mapping
from uuid import UUID

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.url_validation import require_safe_https_url


MAX_FRAGMENT_BYTES = 16_384
MAX_FRAGMENT_NODES = 1000
MAX_FRAGMENT_DEPTH = 6
MAX_TABLE_COLUMNS = 20
MAX_TABLE_ROWS = 100
MARKS = ('strong', 'em', 'strike', 'code')
CODE_LANGUAGES = {'', 'text', 'plain', 'python', 'json', 'markdown', 'yaml', 'sql', 'bash', 'powershell'}


def validate_rich_text_fragment(value):
    seen = set()
    counter = [0]
    fragment = _fragment(value, seen, counter)
    try:
        if len(canonical_bytes(fragment)) > MAX_FRAGMENT_BYTES:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
    except ArchiveError:
        raise ReportError('REPORT_EDIT_TARGET_INVALID') from None
    return fragment


def plain_text_fragment(value: str):
    _text(value)
    if value == '':
        return {'schema_version': 2, 'blocks': ()}
    return {
        'schema_version': 2,
        'blocks': ({
            'type': 'paragraph',
            'content': ({
                'type': 'text',
                'text': value,
                'marks': (),
                'foreground': None,
                'background': None,
            },),
        },),
    }


def rich_text_fragment_plain_text(fragment) -> str:
    return '\n'.join(_block_text(block) for block in validate_rich_text_fragment(fragment)['blocks'])


def _fragment(value, seen, counter):
    _guard(value, seen, counter, 0)
    _keys(value, {'schema_version', 'blocks'})
    version = value['schema_version']
    if type(version) is not int or version not in {1, 2}:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    blocks = tuple(_block(item, version, seen, counter, 1) for item in _list(value['blocks']))
    return {'schema_version': 2, 'blocks': blocks}


def _block(value, version, seen, counter, depth):
    _guard(value, seen, counter, depth)
    node_type = _node_type(value)
    if node_type == 'paragraph':
        _keys(value, {'type', 'content'})
        return {'type': 'paragraph', 'content': _inlines(value['content'], version, seen, counter, depth + 1)}
    if node_type == 'heading':
        _keys(value, {'type', 'level', 'content'})
        level = value['level']
        if type(level) is not int or level not in {1, 2, 3}:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        return {'type': 'heading', 'level': level, 'content': _inlines(value['content'], version, seen, counter, depth + 1)}
    if node_type == 'quote':
        _keys(value, {'type', 'blocks'})
        return {'type': 'quote', 'blocks': tuple(_block(item, version, seen, counter, depth + 1) for item in _list(value['blocks']))}
    if node_type == 'list':
        _keys(value, {'type', 'ordered', 'items'})
        ordered = _bool(value['ordered'])
        items = tuple(_list_item(item, ordered, version, seen, counter, depth + 1) for item in _list(value['items']))
        return {'type': 'list', 'ordered': ordered, 'items': items}
    if node_type == 'table':
        return _table(value, version, seen, counter, depth)
    if node_type == 'code':
        _keys(value, {'type', 'language', 'text'})
        language = _text(value['language'])
        if language not in CODE_LANGUAGES:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        return {'type': 'code', 'language': language, 'text': _text(value['text'])}
    raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _table(value, version, seen, counter, depth):
    _keys(value, {'type', 'headers', 'rows'})
    headers = tuple(_inline_cell(cell, version, seen, counter, depth + 1) for cell in _list(value['headers']))
    rows = tuple(tuple(_inline_cell(cell, version, seen, counter, depth + 1) for cell in _list(row)) for row in _list(value['rows']))
    if not headers or len(headers) > MAX_TABLE_COLUMNS or len(rows) > MAX_TABLE_ROWS:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if any(len(row) != len(headers) for row in rows):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return {'type': 'table', 'headers': headers, 'rows': rows}


def _list_item(value, ordered, version, seen, counter, depth):
    _guard(value, seen, counter, depth)
    _keys(value, {'checked', 'blocks'})
    checked = value['checked']
    if checked is not None and type(checked) is not bool:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if ordered and checked is not None:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return {'checked': checked, 'blocks': tuple(_block(item, version, seen, counter, depth + 1) for item in _list(value['blocks']))}


def _inlines(value, version, seen, counter, depth):
    return tuple(_inline(item, version, seen, counter, depth) for item in _list(value))


def _inline_cell(value, version, seen, counter, depth):
    return _inlines(value, version, seen, counter, depth)


def _inline(value, version, seen, counter, depth):
    _guard(value, seen, counter, depth)
    node_type = _node_type(value)
    if node_type == 'text':
        return _text_inline(value, version)
    if node_type == 'link':
        return _link_inline(value, version, seen, counter, depth)
    if node_type == 'break':
        _keys(value, {'type'})
        return {'type': 'break'}
    raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _text_inline(value, version):
    required = {'type', 'text', 'marks'} if version == 1 else {'type', 'text', 'marks', 'foreground', 'background'}
    _keys(value, required)
    return {
        'type': 'text',
        'text': _text(value['text']),
        'marks': _marks(value['marks']),
        'foreground': None if version == 1 else _color(value['foreground']),
        'background': None if version == 1 else _color(value['background']),
    }


def _link_inline(value, version, seen, counter, depth):
    if version == 1:
        keys = {'type', 'href', 'text'} | ({'reference_id'} if 'reference_id' in value else set())
        _keys(value, keys)
        content = (_plain_text_inline(value['text']),)
    else:
        keys = {'type', 'href', 'content'} | ({'reference_id'} if 'reference_id' in value else set())
        _keys(value, keys)
        content = tuple(_link_text_inline(item, seen, counter, depth + 1) for item in _list(value['content']))
        if not content:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
    result = {'type': 'link', 'href': require_safe_https_url(value['href']), 'content': content}
    if 'reference_id' in value:
        result['reference_id'] = _uuid(value['reference_id'])
    return result


def _link_text_inline(value, seen, counter, depth):
    _guard(value, seen, counter, depth)
    if _node_type(value) != 'text':
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return _text_inline(value, 2)


def _plain_text_inline(value):
    return {'type': 'text', 'text': _text(value), 'marks': (), 'foreground': None, 'background': None}


def _guard(value, seen, counter, depth):
    if depth > MAX_FRAGMENT_DEPTH:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if isinstance(value, (Mapping, list, tuple)):
        identity = id(value)
        if identity in seen:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        seen.add(identity)
    counter[0] += 1
    if counter[0] > MAX_FRAGMENT_NODES:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _node_type(value):
    if not isinstance(value, Mapping) or type(value.get('type')) is not str:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value['type']


def _keys(value, expected):
    if not isinstance(value, Mapping) or set(value.keys()) != expected:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')


def _list(value):
    if not isinstance(value, (list, tuple)):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value


def _bool(value):
    if type(value) is not bool:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value


def _text(value):
    if type(value) is not str:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    for character in value:
        codepoint = ord(character)
        if codepoint < 32 and character not in {'\n', '\r', '\t'}:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value


def _marks(value):
    if not isinstance(value, (list, tuple)) or any(type(item) is not str or item not in MARKS for item in value):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return tuple(mark for mark in MARKS if mark in value)


def _color(value):
    if value is None:
        return None
    if type(value) is not str or len(value) != 7 or value[0] != '#':
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    if any(character not in '0123456789abcdef' for character in value[1:]):
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value


def _uuid(value):
    if type(value) is not str:
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise ReportError('REPORT_EDIT_TARGET_INVALID') from None
    if str(parsed) != value.lower():
        raise ReportError('REPORT_EDIT_TARGET_INVALID')
    return value


def _block_text(block):
    node_type = block['type']
    if node_type in {'paragraph', 'heading'}:
        return _inlines_text(block['content'])
    if node_type == 'quote':
        return '\n'.join(_block_text(item) for item in block['blocks'])
    if node_type == 'list':
        return '\n'.join(_list_item_text(item) for item in block['items'])
    if node_type == 'table':
        header = '\t'.join(_inlines_text(cell) for cell in block['headers'])
        rows = ['\t'.join(_inlines_text(cell) for cell in row) for row in block['rows']]
        return '\n'.join((header, *rows))
    if node_type == 'code':
        return block['text']
    return ''


def _list_item_text(item):
    marker = ''
    if item['checked'] is True:
        marker = '[x] '
    if item['checked'] is False:
        marker = '[ ] '
    return marker + '\n'.join(_block_text(block) for block in item['blocks'])


def _inlines_text(inlines):
    parts = []
    for inline in inlines:
        if inline['type'] == 'break':
            parts.append('\n')
        elif inline['type'] == 'link':
            parts.append(_inlines_text(inline['content']))
        else:
            parts.append(inline['text'])
    return ''.join(parts)
