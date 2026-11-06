from collections.abc import Mapping
import re

from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json, sha256_bytes
from project_management.app.domain.summary_contracts import AnalysisError


def validate_candidate(prepared, candidate):
    if sha256_bytes(prepared.input_content.encode('utf-8')) != prepared.input_hash:
        raise AnalysisError('ANALYSIS_RESULT_INVALID')
    source = decode_json(prepared.input_content.encode('utf-8'))
    if (candidate['binding'] != source['binding']
            or candidate['profile_revision'] != source['profile_revision']
            or candidate['target_capture_id'] != prepared.target_capture_id
            or candidate['base_summary_id'] != prepared.base_summary_id):
        raise AnalysisError('ANALYSIS_RESULT_INVALID')
    references = {}
    for row in source['evidence']:
        if (row['ref_id'] in references or row['source_hash'] != content_hash(row['value'])
                or not _valid_evidence_identity(row, prepared.target_capture_id)):
            raise AnalysisError('ANALYSIS_EVIDENCE_INVALID')
        references[row['ref_id']] = row
    selected = _selected(candidate['evidence'], references)
    for field in ('blockers', 'limitations'):
        if candidate[field]:
            _selected(candidate[field], references)
    known = _people(tuple(row['value'] for row in source['evidence']))
    for action in candidate['next_actions']:
        cited = _selected(action['evidence'], references)
        _owner(action, cited, known)
    passages = tuple(_strings(tuple(row['value'] for row in selected)))
    names = tuple(name for name in known.values() if name)
    for text in (candidate['what'], candidate['current_position'], candidate['verification'],
                 *(action['action'] for action in candidate['next_actions'])):
        _narrative(text, passages, names)
    local = decode_json(canonical_bytes(candidate))
    local['input_hash'] = prepared.input_hash
    return local


def _valid_evidence_identity(row, target_capture_id):
    if row['kind'] == 'field':
        key, pointer = 'fields', '/fields'
        if row['source_id'] != 'fields':
            return False
    else:
        collection = {'comment': 'comments', 'history': 'history'}.get(row['kind'])
        if collection is None:
            return False
        key = f"{row['kind']}:{row['source_id']}"
        pointer = '/' + collection + '/' + row['source_id'].replace('~', '~0').replace('/', '~1')
    expected = key if row['capture_id'] == target_capture_id else f"archived:{row['capture_id']}:{key}"
    return row['ref_id'] == expected and row['json_pointer'] == pointer


def _selected(ids, references):
    if not ids or any(ref_id not in references for ref_id in ids):
        raise AnalysisError('ANALYSIS_EVIDENCE_INVALID')
    return tuple(references[ref_id] for ref_id in ids)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _people(values):
    result = {}

    def visit(value):
        if isinstance(value, Mapping):
            for role in ('assignee', 'reporter', 'author', 'updateAuthor'):
                person = value.get(role)
                if isinstance(person, Mapping):
                    key = person.get('accountId') or person.get('key') or person.get('name')
                    if isinstance(key, str):
                        result[key] = person.get('displayName')
            for field in ('author_id', 'update_author_id', 'assignee_id', 'reporter_id'):
                if isinstance(value.get(field), str):
                    result.setdefault(value[field], None)
            for item in value.values():
                visit(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(values)
    return result


def _body_text(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        if value.get('type') == 'text' and isinstance(value.get('text'), str):
            yield value['text']
        yield from _body_text(value.get('content'))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _body_text(item)


def _passages(evidence):
    for row in evidence:
        value = row['value']
        if row['kind'] == 'comment':
            yield from _body_text(value.get('body'))
        elif row['kind'] == 'field':
            for field in ('summary', 'description', 'environment'):
                yield from _body_text(value.get(field))


def _owner(action, evidence, known):
    owner, basis, quote = action['owner_id'], action['owner_basis'], action['owner_quote']
    if action['owner_confirmed'] is not False:
        raise AnalysisError('ANALYSIS_OWNER_INVALID')
    if basis == 'unknown':
        if owner is not None or quote is not None:
            raise AnalysisError('ANALYSIS_OWNER_INVALID')
        return
    if owner not in known:
        raise AnalysisError('ANALYSIS_OWNER_INVALID')
    if basis == 'explicit' or quote is not None:
        if (not isinstance(quote, str) or not quote.strip()
                or not any(quote in passage for passage in _passages(evidence))
                or not any(name and re.search(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', quote)
                           for name in (owner, known[owner]))):
            raise AnalysisError('ANALYSIS_OWNER_INVALID')


def _narrative(text, passages, names):
    def replace_quote(match):
        if not any(match.group(2) in passage for passage in passages):
            raise AnalysisError('ANALYSIS_EVIDENCE_INVALID')
        return ' evidence '

    narrative = re.sub(r'(["`])(.+?)\1', replace_quote, text)
    for name in sorted(names, key=len, reverse=True):
        narrative = narrative.replace(name, 'person')
    if (not any(char.isalpha() for char in narrative)
            or any(char.isalpha() and not char.isascii() for char in narrative)):
        raise AnalysisError('ANALYSIS_LANGUAGE_INVALID')
