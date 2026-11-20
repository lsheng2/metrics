from django.utils.translation import gettext_lazy as _


SEMANTIC_METADATA_HINT_LIMIT = 8

SEMANTIC_METADATA_HINT_DEFINITIONS = (
    ('item_types', _('Issue types'), _('Bug type values')),
    ('priorities', _('Priorities'), _('Critical/high and medium/low values')),
    ('statuses', _('Workflow statuses'), _('Open, fixed, closed and reopen status values')),
    ('resolutions', _('Resolutions'), _('Fixed and closed resolution values')),
    ('fields', _('Fields'), _('Severity, component, owner, milestone and fix version fields')),
    ('components', _('Components'), _('Component values')),
    ('versions', _('Versions'), _('Milestone and fix version values')),
)


def semantic_mapping_metadata_hint_context(scope_metadata, provider_id: str = 'jira') -> dict:
    if provider_id and provider_id != 'jira':
        return {
            'supported': False,
            'loaded': False,
            'status': 'unsupported',
            'message': _('Jira metadata reference is available for Jira scopes only.'),
            'warnings': [],
            'groups': [],
            'choice_count': 0,
        }
    warnings, metadata_options = metadata_context_parts(scope_metadata)
    groups = semantic_metadata_hint_groups(metadata_options)
    has_error = any('failed' in str(warning).casefold() for warning in warnings)
    if scope_metadata is None:
        status = 'not_loaded'
        message = _('No metadata reference loaded yet.')
    elif has_error:
        status = 'error'
        message = _('Metadata refresh could not load the reference.')
    elif warnings:
        status = 'warning'
        message = _('Metadata reference loaded with warnings.')
    elif groups:
        status = 'ready'
        message = _('Metadata reference loaded.')
    else:
        status = 'empty'
        message = _('No discovered metadata values are available for this Jira context.')
    return {
        'supported': True,
        'loaded': scope_metadata is not None,
        'status': status,
        'message': message,
        'warnings': warnings,
        'groups': groups,
        'choice_count': sum(group['count'] for group in groups),
    }


def metadata_context_parts(scope_metadata) -> tuple[list[str], object]:
    if scope_metadata is None:
        return [], None
    if isinstance(scope_metadata, dict):
        warnings = [str(warning) for warning in scope_metadata.get('warnings', []) or []]
        metadata_options = scope_metadata.get('options')
    else:
        warnings = []
        metadata_options = scope_metadata
    if metadata_options is not None:
        warnings.extend(str(warning) for warning in getattr(metadata_options, 'warnings', []) or [])
    return warnings, metadata_options


def semantic_metadata_hint_groups(metadata_options) -> list[dict]:
    if metadata_options is None:
        return []
    groups = []
    for attribute_name, label, help_text in SEMANTIC_METADATA_HINT_DEFINITIONS:
        choices = semantic_metadata_hint_choices(getattr(metadata_options, attribute_name, []) or [])
        if choices:
            groups.append({
                'label': label,
                'help_text': help_text,
                'choices': choices[:SEMANTIC_METADATA_HINT_LIMIT],
                'count': len(choices),
                'more_count': max(0, len(choices) - SEMANTIC_METADATA_HINT_LIMIT),
            })
    return groups


def semantic_metadata_hint_choices(metadata_items: list) -> list[dict]:
    choices = []
    seen = set()
    for item in metadata_items:
        item_id = str(getattr(item, 'id', '') or '').strip()
        item_name = str(getattr(item, 'name', '') or '').strip()
        label = str(getattr(item, 'label', '') or item_name or item_id).strip()
        if not label or label in seen:
            continue
        source = str(getattr(item, 'source', '') or '').strip()
        title = source or item_id or label
        choices.append({'label': label, 'title': title})
        seen.add(label)
    return choices
