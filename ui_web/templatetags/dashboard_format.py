import re
from datetime import date, datetime, timezone

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import pgettext_lazy

from ..facades.bug_trend_chart_payload import series_label as chart_series_label
from ..facades.provider_scope_setup import provider_setup_template

register = template.Library()

EMPTY_VALUE = mark_safe('<span class="has-text-grey-light">—</span>')

_DANGER_WORDS = frozenset({'failed', 'failure', 'error', 'errored', 'blocked', 'invalid', 'unreachable', 'rejected', 'denied'})
_WARNING_WORDS = frozenset({
    'stale', 'partial', 'pending', 'running', 'queued', 'compatibility', 'inferred', 'missing', 'never',
    'warning', 'degraded', 'drifted', 'required', 'changed', 'insufficient', 'expired', 'outdated', 'needs',
})
_NEUTRAL_WORDS = frozenset({
    'disabled', 'not', 'no', 'none', 'unknown', 'unavailable', 'unsupported', 'unchecked', 'skipped', 'off', 'idle',
})
_SUCCESS_WORDS = frozenset({
    'fresh', 'ready', 'ok', 'success', 'succeeded', 'completed', 'complete', 'explicit', 'synced', 'healthy',
    'enabled', 'connected', 'available', 'covered', 'current', 'validated', 'supported', 'passed', 'active',
    'configured', 'live', 'published',
})
_TONES = (('is-danger', _DANGER_WORDS), ('is-warning', _WARNING_WORDS), ('', _NEUTRAL_WORDS), ('is-success', _SUCCESS_WORDS))
_SERVICE_STATES = {
    'connected': pgettext_lazy('service state', 'connected'),
    'available': pgettext_lazy('service state', 'available'),
    'ready': pgettext_lazy('service state', 'ready'),
    'configured': pgettext_lazy('service state', 'configured'),
    'starting': pgettext_lazy('service state', 'starting'),
    'degraded': pgettext_lazy('service state', 'degraded'),
    'auth required': pgettext_lazy('service state', 'auth required'),
    'unavailable': pgettext_lazy('service state', 'unavailable'),
    'unreachable': pgettext_lazy('service state', 'unreachable'),
    'disconnected': pgettext_lazy('service state', 'disconnected'),
    'disabled': pgettext_lazy('service state', 'disabled'),
    'stopped': pgettext_lazy('service state', 'stopped'),
    'aborted': pgettext_lazy('service state', 'aborted'),
    'unknown': pgettext_lazy('service state', 'unknown'),
}


@register.filter
def or_dash(value):
    """Render None or blank text as the muted em dash placeholder; other values pass through unchanged."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return EMPTY_VALUE
    return value


@register.filter
def status_tag(value):
    """Render a machine status as a tag toned by `status_tone`, or the muted dash when it is missing."""
    if value is None or not str(value).strip():
        return EMPTY_VALUE
    tone = status_tone(value)
    return format_html('<span class="{}">{}</span>', f'tag {tone}' if tone else 'tag', value)


@register.filter
def provider_tag(provider_id):
    """Render a provider identity tag (colored dot plus label), or the muted dash when the provider is missing."""
    if provider_id is None or not str(provider_id).strip():
        return EMPTY_VALUE
    provider = provider_setup_template(provider_id)
    return format_html('<span class="tag scope-provider-tag is-provider-{}">{}</span>', provider.color, provider.label)


@register.filter
def iso_datetime(value) -> str:
    """Render an ISO-8601 timestamp as a compact `YYYY-MM-DD HH:MM` label, in UTC when the value is aware."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, date) or not value:
        return '' if value is None else str(value)
    else:
        text = str(value).strip()
        if len(text) <= 10:
            return text
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return text
    if moment.tzinfo is None:
        return moment.strftime('%Y-%m-%d %H:%M')
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


@register.filter
def timestamp(value, precision: str = 'minute'):
    """Render a `<time>` element with the compact label; the exact value stays in `datetime` and `title`.

    `precision='date'` keeps only the `YYYY-MM-DD` part of the label for dense tables.
    """
    label = iso_datetime(value)
    if not label:
        return EMPTY_VALUE
    if precision == 'date':
        label = label[:10]
    exact = value.isoformat() if isinstance(value, date) else str(value).strip()
    return format_html('<time datetime="{}" title="{}">{}</time>', exact, exact, label)


@register.filter
def age_seconds(value) -> str:
    """Render an age in seconds as `45s`, `12m`, `3h 5m` or `2d 4h`."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return EMPTY_VALUE if value in (None, '') else str(value)
    if seconds < 60:
        return f'{seconds}s'
    minutes = seconds // 60
    if minutes < 60:
        return f'{minutes}m'
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f'{hours}h {minutes}m' if minutes else f'{hours}h'
    days, hours = divmod(hours, 24)
    return f'{days}d {hours}h' if hours else f'{days}d'


@register.filter
def split_csv(value) -> list[str]:
    return [item.strip() for item in str(value or '').split(',') if item.strip()]


@register.filter
def series_label(value) -> str:
    """Render chart series identifiers (one, or a comma-joined set) with the labels the chart legend uses."""
    return ', '.join(chart_series_label(name) for name in split_csv(value))


@register.filter
def status_tone(value) -> str:
    """Map a machine status such as `auth_failed` or `stale_config` to a tag tone class."""
    words = set(re.split(r'[^a-z0-9]+', str(value or '').lower())) - {''}
    for tone, vocabulary in _TONES:
        if words & vocabulary:
            return tone
    return ''


@register.filter
def service_state_label(value):
    """Translate a shell service state such as `connected`; `data-service-status` keeps the machine value.

    States outside the vocabulary (for example a new sidecar state) pass through unchanged.
    """
    return _SERVICE_STATES.get(str(value or ''), value)
