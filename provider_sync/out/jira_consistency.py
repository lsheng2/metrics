from collections.abc import Mapping
import json
import re

from provider_sync.services.capture_session import canonical_bytes, fingerprint


POLICY_VERSION = 'devsummary-bean-identities-v1'
DEV_PLUGIN = 'com.atlassian.jira.plugins.jira-development-integration-plugin:devsummary'
REST = 'com.atlassian.jira.plugin.devstatus.rest.'
BEANS = 'com.atlassian.jira.plugin.devstatus.summary.beans.'
ROOT_BEAN = REST + 'SummaryBean'
KNOWN_CLASSES = frozenset({ROOT_BEAN, REST + 'SummaryItemBean'} | {
    BEANS + name for name in (
        'BranchOverallBean', 'BuildOverallBean', 'CommitOverallBean', 'DeploymentOverallBean',
        'ReviewsOverallBean', 'PullRequestOverallBean', 'ObjectByInstanceTypeBean',
    )
})
IDENTITY = re.compile(r'(?P<class>[A-Za-z_$][A-Za-z0-9_.$]*)@(?P<address>[a-fA-F0-9]{1,8})(?=\[)')


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError('Non-finite JSON')


def _quoted_ranges(text):
    ranges, quote, start, escaped = [], None, 0, False
    for index, char in enumerate(text):
        if quote is None:
            if char in ("'", '"'):
                quote, start = char, index
        elif escaped:
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == quote:
            ranges.append((start, index))
            quote = None
    return ranges if quote is None else None


def _prefix_projection(value):
    if not isinstance(value, str) or not value.startswith('{summaryBean=' + ROOT_BEAN + '@'):
        return None
    prefix, separator, suffix = value.partition(', devSummaryJson=')
    if (not separator or not prefix.endswith(']')
            or prefix.count('[') != prefix.count(']')
            or prefix.count('{') != prefix.count('}') + 1):
        return None
    try:
        embedded, end = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_nonfinite).raw_decode(suffix)
    except (ValueError, RecursionError):
        return None
    if (suffix[end:] != '}' or not isinstance(embedded, dict)
            or not isinstance(embedded.get('cachedValue'), dict) or type(embedded.get('isStale')) is not bool):
        return None
    matches = list(IDENTITY.finditer(prefix))
    quoted = _quoted_ranges(prefix)
    if not matches or prefix.count('@') != len(matches) or quoted is None:
        return None
    for match in matches:
        if (match['class'] not in KNOWN_CLASSES or prefix[match.start() - 1:match.start()] != '='
                or any(start < match.start() < end for start, end in quoted)):
            return None
    projected, start = [], 0
    for match in matches:
        projected.extend((prefix[start:match.start('address')], '<identity>'))
        start = match.end('address')
    return ''.join(projected) + prefix[start:] + separator + suffix


def _verified_schema(field, schema):
    match = re.fullmatch(r'customfield_([1-9][0-9]*)', field)
    return bool(match and isinstance(schema, Mapping) and schema.get('type') == 'any'
                and schema.get('custom') == DEV_PLUGIN
                and type(schema.get('customId')) is int and schema['customId'] == int(match[1]))


def consistent_responses(before, after):
    first, second = dict(before), dict(after)
    fields_before, fields_after = before.get('fields'), after.get('fields')
    schemas_before, schemas_after = before.get('schema', {}), after.get('schema', {})
    if all(isinstance(value, Mapping) for value in (fields_before, fields_after, schemas_before, schemas_after)):
        first['fields'], second['fields'] = dict(fields_before), dict(fields_after)
        for field in sorted(fields_before.keys() & fields_after.keys()):
            schema = schemas_before.get(field)
            if not _verified_schema(field, schema) or canonical_bytes(schema) != canonical_bytes(schemas_after.get(field)):
                continue
            left, right = _prefix_projection(fields_before[field]), _prefix_projection(fields_after[field])
            if left is not None and right is not None:
                first['fields'][field], second['fields'][field] = left, right
    return fingerprint(first) == fingerprint(second)
