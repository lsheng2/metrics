from dataclasses import asdict, dataclass
import hashlib
import json
from datetime import date, timedelta

from django.conf import settings

from provider_sync.models import ProviderAggregateArtifact, ProviderSyncCursor


class ProviderFreshnessStatus:
    LIVE_SYNCED = 'live_synced'
    SEEDED_PREVIEW = 'seeded_preview'
    STALE = 'stale'
    UNAVAILABLE = 'unavailable'
    CONFIGURATION_REQUIRED = 'configuration_required'
    RUNNING = 'running'
    FAILED = 'failed'


@dataclass(frozen=True, slots=True)
class ProviderCachedArtifactResult:
    artifact: ProviderAggregateArtifact | None
    freshness_status: str
    cache_age_seconds: int
    reason: str = ''


@dataclass(frozen=True, slots=True)
class ProviderRefreshStartResult:
    acquired: bool
    status: str
    cursor: ProviderSyncCursor | None = None
    reason: str = ''


@dataclass(frozen=True, slots=True)
class ProviderCacheIdentity:
    provider_id: str
    profile_id: str
    source_query_ownership: str
    source_query_ref: str
    source_query_hash: str
    tenant_or_space: str
    subject_or_item_type: str
    field_set_hash: str
    mapping_version_hash: str
    chart_id: str
    chart_version: int
    begin_ww: str
    end_ww: str
    range_mode: str = 'ww'
    range_start: str = ''
    range_end: str = ''
    range_grain: str = ''
    range_label_start: str = ''
    range_label_end: str = ''
    fact_snapshot_id: str = ''

    def cache_key(self) -> str:
        payload = asdict(self)
        if payload['range_mode'] != 'ww':
            payload['begin_ww'] = ''
            payload['end_ww'] = ''
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ProviderCacheSettings:
    cache_enabled: bool
    cache_ttl_seconds: int
    metadata_cache_seconds: int
    sync_stale_after_seconds: int

    @classmethod
    def for_provider(cls, provider_id: str) -> 'ProviderCacheSettings':
        generic = cls(
            cache_enabled=getattr(settings, 'METRICS_PROVIDER_CACHE_ENABLED', True),
            cache_ttl_seconds=getattr(settings, 'METRICS_PROVIDER_CACHE_TTL_SECONDS', 900),
            metadata_cache_seconds=getattr(settings, 'METRICS_PROVIDER_METADATA_CACHE_SECONDS', 300),
            sync_stale_after_seconds=getattr(settings, 'METRICS_PROVIDER_SYNC_STALE_AFTER_SECONDS', 1800),
        )
        override = getattr(settings, 'METRICS_PROVIDER_CACHE_OVERRIDES', {}).get(provider_id, {})
        return cls(
            cache_enabled=override.get('cache_enabled', generic.cache_enabled),
            cache_ttl_seconds=override.get('cache_ttl_seconds', generic.cache_ttl_seconds),
            metadata_cache_seconds=override.get('metadata_cache_seconds', generic.metadata_cache_seconds),
            sync_stale_after_seconds=override.get('sync_stale_after_seconds', generic.sync_stale_after_seconds),
        )


def normalized_artifact_range(
    range_mode: str,
    begin_ww: str,
    end_ww: str,
    range_start: str = '',
    range_end: str = '',
    range_grain: str = '',
    range_label_start: str = '',
    range_label_end: str = '',
) -> dict:
    normalized_mode = (range_mode or 'ww').strip().lower()
    if normalized_mode == 'ww':
        start = ww_to_monday(begin_ww)
        end = ww_to_monday(end_ww) + timedelta(days=6)
        return {
            'range_mode': 'ww',
            'range_start': start.isoformat(),
            'range_end': end.isoformat(),
            'range_grain': range_grain or 'week',
            'range_label_start': range_label_start or begin_ww,
            'range_label_end': range_label_end or end_ww,
        }
    if normalized_mode == 'date':
        if not range_start or not range_end:
            raise ValueError('range_start and range_end are required when range_mode=date.')
        return {
            'range_mode': 'date',
            'range_start': iso_date_label(range_start),
            'range_end': iso_date_label(range_end),
            'range_grain': range_grain or 'day',
            'range_label_start': range_label_start or iso_date_label(range_start),
            'range_label_end': range_label_end or iso_date_label(range_end),
        }
    raise ValueError('range_mode must be ww or date.')


def iso_date_label(value: str) -> str:
    return date.fromisoformat(value[:10]).isoformat()


def ww_to_monday(value: str) -> date:
    normalized = value.strip()
    if len(normalized) != 6 or normalized[2:4].upper() != 'WW':
        raise ValueError('WW values must use YYWWNN format.')
    year = 2000 + int(normalized[:2])
    week = int(normalized[4:])
    return date.fromisocalendar(year, week, 1)
