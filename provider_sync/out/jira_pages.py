from dataclasses import dataclass
import re

from project_management.app.api.capture_archive import PartCoverage
from provider_sync.app.api.access_contracts import AccessError
from provider_sync.services.capture_session import fingerprint


@dataclass(frozen=True, slots=True)
class PageRows:
    rows: tuple
    coverage: PartCoverage
    raw_page_ids: tuple[str, ...]


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[1-9][0-9]{0,63}', value):
        raise AccessError('PROVIDER_RECORD_INVALID')
    return value


def issue_key(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]*-[1-9][0-9]*', value):
        raise AccessError('PROVIDER_RECORD_INVALID')
    return value


def warnings(value):
    if (value.get('warningMessages') not in (None, []) or value.get('errorMessages') not in (None, [])
            or value.get('errors') not in (None, {})):
        raise AccessError('PROVIDER_QUERY_WARNING')


def read_pages(session, path, params, *, array_name, maximum, validate, item=None):
    start, total, rows, seen = 0, None, [], set()
    prior = len(session.page_ids)
    failure = None
    try:
        while True:
            size = session.context.limits.page_size
            page = session.get_json(path, {**params, 'startAt': start, 'maxResults': size},
                                    item=item, page_key=f'{array_name}:{session.usage.requests + 1}').value
            warnings(page)
            current, batch = page.get('total'), page.get(array_name)
            if (type(current) is not int or current < 0 or type(page.get('startAt')) is not int
                    or page['startAt'] != start or not isinstance(batch, list) or len(batch) > size
                    or (total is not None and current != total)):
                raise AccessError('PROVIDER_PAGE_INVALID')
            total = current
            for row in batch:
                if not isinstance(row, dict):
                    raise AccessError('PROVIDER_RECORD_INVALID')
                key = identifier(row.get('id'))
                if key in seen:
                    raise AccessError('PROVIDER_DUPLICATE_ID')
                if len(rows) >= maximum:
                    raise AccessError('PROVIDER_RECORD_LIMIT')
                rows.append(validate(row))
                seen.add(key)
            start += len(batch)
            if total > maximum:
                raise AccessError('PROVIDER_RECORD_LIMIT')
            if start == total:
                break
            if not batch or start > total:
                raise AccessError('PROVIDER_PAGE_INVALID')
    except AccessError as error:
        failure = error.code
    state = 'complete' if failure is None else 'partial'
    if not rows and failure in {'PROVIDER_AUTH_FAILED', 'PROVIDER_PERMISSION_DENIED'}:
        state = 'access_lost'
    if total is not None and total < len(rows):
        total = None
    return PageRows(tuple(rows), PartCoverage(state, fingerprint(rows) if failure is None else None,
                                               len(rows), total, failure), session.page_ids[prior:])


def record_map(value, maximum, validate):
    rows, failure = {}, None
    if not isinstance(value, list):
        return rows, 'PROVIDER_RECORD_INVALID'
    try:
        for row in value:
            if not isinstance(row, dict):
                raise AccessError('PROVIDER_RECORD_INVALID')
            key = identifier(row.get('id'))
            if key in rows:
                raise AccessError('PROVIDER_DUPLICATE_ID')
            if len(rows) >= maximum:
                raise AccessError('PROVIDER_RECORD_LIMIT')
            rows[key] = validate(row)
    except AccessError as error:
        failure = error.code
    return rows, failure
