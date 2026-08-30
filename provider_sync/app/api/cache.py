from dataclasses import asdict, dataclass
import hashlib
import json
from datetime import timedelta

from django.db import transaction
from django.conf import settings
from django.utils import timezone

from provider_sync.models import ProviderAggregateArtifact, ProviderFact, ProviderFactSnapshot, ProviderSyncCursor


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
    fact_snapshot_id: str = ''

    def cache_key(self) -> str:
        payload = asdict(self)
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


class ProviderSyncCacheService:
    def should_bypass_cache(self, provider_id: str, force_refresh: bool = False) -> bool:
        settings_for_provider = ProviderCacheSettings.for_provider(provider_id)
        return force_refresh or not settings_for_provider.cache_enabled

    def try_start_refresh(self, provider_id: str, profile_id: str, source_query_ref: str = '',
                          force_refresh: bool = False, now=None) -> ProviderRefreshStartResult:
        now = now or timezone.now()
        settings_for_provider = ProviderCacheSettings.for_provider(provider_id)
        stale_cutoff = now - timedelta(seconds=settings_for_provider.sync_stale_after_seconds)
        with transaction.atomic():
            cursor = ProviderSyncCursor.objects.filter(provider_id=provider_id, profile_id=profile_id).first()
            if (
                cursor
                and cursor.status == ProviderSyncCursor.STATUS_RUNNING
                and cursor.updated_at
                and cursor.updated_at > stale_cutoff
                and not force_refresh
            ):
                return ProviderRefreshStartResult(False, ProviderFreshnessStatus.RUNNING, cursor, 'refresh_already_running')
            cursor, _ = ProviderSyncCursor.objects.update_or_create(
                provider_id=provider_id,
                profile_id=profile_id,
                defaults={
                    'status': ProviderSyncCursor.STATUS_RUNNING,
                    'last_error': '',
                    'error_category': '',
                    'source_query_ref': source_query_ref,
                },
            )
        return ProviderRefreshStartResult(True, ProviderFreshnessStatus.RUNNING, cursor)

    def cached_aggregate_artifact(
        self,
        provider_id: str,
        profile_id: str,
        chart_id: str,
        chart_version: int,
        begin_ww: str,
        end_ww: str,
        now=None,
    ) -> ProviderCachedArtifactResult:
        artifact = self.latest_aggregate_artifact(provider_id, profile_id, chart_id, chart_version, begin_ww, end_ww)
        if artifact is None:
            return ProviderCachedArtifactResult(None, ProviderFreshnessStatus.UNAVAILABLE, 0, 'no_matching_artifact')
        now = now or timezone.now()
        age_seconds = max(0, int((now - artifact.created_at).total_seconds()))
        settings_for_provider = ProviderCacheSettings.for_provider(provider_id)
        if age_seconds > settings_for_provider.cache_ttl_seconds:
            return ProviderCachedArtifactResult(artifact, ProviderFreshnessStatus.STALE, age_seconds, 'cache_ttl_expired')
        return ProviderCachedArtifactResult(artifact, artifact.freshness_status, age_seconds)

    def list_sync_health(self) -> list[dict]:
        return [self._health_payload(cursor) for cursor in ProviderSyncCursor.objects.select_related('latest_snapshot').order_by('provider_id', 'profile_id')]

    def profile_cache_status(self, provider_id: str, profile_id: str) -> dict:
        cursor = ProviderSyncCursor.objects.filter(provider_id=provider_id, profile_id=profile_id).select_related('latest_snapshot').first()
        if cursor is None:
            return {
                'provider_id': provider_id,
                'profile_id': profile_id,
                'status': ProviderFreshnessStatus.SEEDED_PREVIEW if provider_id == 'hsdes' else ProviderFreshnessStatus.CONFIGURATION_REQUIRED,
                'latest_snapshot_id': '',
                'latest_successful_sync_at': '',
                'cache_age_seconds': '',
                'error_category': '',
                'last_error': '',
            }
        return self._health_payload(cursor)

    def materialize_snapshot(
        self,
        provider_id: str,
        profile_id: str,
        source_query: dict,
        field_set_hash: str,
        mapping_version_hash: str,
        facts: list[dict],
        raw_payload: dict,
        freshness_status: str = ProviderFreshnessStatus.LIVE_SYNCED,
        completed_at=None,
    ) -> ProviderFactSnapshot:
        completed_at = completed_at or timezone.now()
        deduped_facts = self._deduped_facts(facts)
        snapshot = ProviderFactSnapshot.objects.create(
            provider_id=provider_id,
            profile_id=profile_id,
            source_query_json=source_query,
            source_query_hash=source_query.get('source_query_hash', ''),
            source_query_ref=source_query.get('source_query_ref', ''),
            field_set_hash=field_set_hash,
            mapping_version_hash=mapping_version_hash,
            raw_payload_json=raw_payload,
            freshness_status=freshness_status,
            status='completed',
            record_count=len(deduped_facts),
            completed_at=completed_at,
        )
        for fact in deduped_facts:
            ProviderFact.objects.create(
                snapshot=snapshot,
                provider_id=provider_id,
                profile_id=profile_id,
                source_item_id=str(fact.get('source_item_id', '')),
                source_item_revision=str(fact.get('source_item_revision', '')),
                canonical_fields_json=fact.get('canonical_fields', {}),
                project_fields_json=fact.get('project_fields', {}),
                field_values_json=fact.get('field_values', {}),
                provider_fields_json=fact.get('provider_fields', {}),
                mapping_version=fact.get('mapping_version', 0) or 0,
            )
        ProviderSyncCursor.objects.update_or_create(
            provider_id=provider_id,
            profile_id=profile_id,
            defaults={
                'status': ProviderSyncCursor.STATUS_SUCCESS,
                'last_successful_sync_at': completed_at,
                'last_error': '',
                'error_category': '',
                'latest_snapshot': snapshot,
                'source_query_ref': snapshot.source_query_ref,
                'source_query_hash': snapshot.source_query_hash,
                'field_set_hash': field_set_hash,
                'mapping_version_hash': mapping_version_hash,
            },
        )
        return snapshot

    def mark_running(self, provider_id: str, profile_id: str, source_query_ref: str = '') -> ProviderSyncCursor:
        cursor, _ = ProviderSyncCursor.objects.update_or_create(
            provider_id=provider_id,
            profile_id=profile_id,
            defaults={
                'status': ProviderSyncCursor.STATUS_RUNNING,
                'last_error': '',
                'error_category': '',
                'source_query_ref': source_query_ref,
            },
        )
        return cursor

    def record_failure(self, provider_id: str, profile_id: str, error_category: str, message: str) -> ProviderSyncCursor:
        cursor = ProviderSyncCursor.objects.filter(provider_id=provider_id, profile_id=profile_id).first()
        defaults = {
            'status': ProviderSyncCursor.STATUS_FAILED,
            'error_category': error_category,
            'last_error': self._redacted_message(message),
        }
        if cursor and cursor.latest_snapshot_id:
            defaults['latest_snapshot'] = cursor.latest_snapshot
        cursor, _ = ProviderSyncCursor.objects.update_or_create(provider_id=provider_id, profile_id=profile_id, defaults=defaults)
        return cursor

    def store_aggregate_artifact(
        self,
        snapshot: ProviderFactSnapshot,
        chart_id: str,
        chart_version: int,
        begin_ww: str,
        end_ww: str,
        rows: list[dict],
        grafana_rows: list[dict],
        source_population: dict,
        run_metadata: dict,
        status: str = 'supported',
        reason: str = '',
    ) -> ProviderAggregateArtifact:
        identity = ProviderCacheIdentity(
            provider_id=snapshot.provider_id,
            profile_id=snapshot.profile_id,
            source_query_ownership=source_population.get('ownership_type', ''),
            source_query_ref=source_population.get('source_query_ref', ''),
            source_query_hash=source_population.get('source_query_hash', snapshot.source_query_hash),
            tenant_or_space=source_population.get('tenant_or_site', ''),
            subject_or_item_type=source_population.get('subject_or_issue_type', ''),
            field_set_hash=snapshot.field_set_hash,
            mapping_version_hash=snapshot.mapping_version_hash,
            chart_id=chart_id,
            chart_version=chart_version,
            begin_ww=begin_ww,
            end_ww=end_ww,
            fact_snapshot_id=str(snapshot.id),
        )
        return ProviderAggregateArtifact.objects.update_or_create(
            provider_id=snapshot.provider_id,
            profile_id=snapshot.profile_id,
            chart_id=chart_id,
            chart_version=chart_version,
            begin_ww=begin_ww,
            end_ww=end_ww,
            cache_identity_hash=identity.cache_key(),
            defaults={
                'snapshot': snapshot,
                'status': status,
                'reason': reason,
                'rows_json': rows,
                'grafana_rows_json': grafana_rows,
                'source_population_json': source_population,
                'run_metadata_json': run_metadata,
                'freshness_status': run_metadata.get('freshness_status', snapshot.freshness_status),
            },
        )[0]

    def latest_successful_snapshot(self, provider_id: str, profile_id: str) -> ProviderFactSnapshot | None:
        return ProviderFactSnapshot.objects.filter(
            provider_id=provider_id,
            profile_id=profile_id,
            status='completed',
        ).order_by('-completed_at', '-created_at').first()

    def latest_aggregate_artifact(
        self,
        provider_id: str,
        profile_id: str,
        chart_id: str,
        chart_version: int,
        begin_ww: str,
        end_ww: str,
    ) -> ProviderAggregateArtifact | None:
        return ProviderAggregateArtifact.objects.filter(
            provider_id=provider_id,
            profile_id=profile_id,
            chart_id=chart_id,
            chart_version=chart_version,
            begin_ww=begin_ww,
            end_ww=end_ww,
            status='supported',
        ).select_related('snapshot').order_by('-created_at').first()

    def _deduped_facts(self, facts: list[dict]) -> list[dict]:
        deduped = {}
        for fact in facts:
            key = (str(fact.get('source_item_id', '')), str(fact.get('source_item_revision', '')))
            deduped[key] = fact
        return list(deduped.values())

    def _redacted_message(self, message: str) -> str:
        redacted = message
        for token in ['Bearer ', 'Basic ', 'password=', 'token=']:
            if token in redacted:
                redacted = redacted.split(token)[0] + token + '[redacted]'
        return redacted

    def _health_payload(self, cursor: ProviderSyncCursor) -> dict:
        latest_snapshot = cursor.latest_snapshot
        now = timezone.now()
        cache_age_seconds = ''
        freshness_status = ProviderFreshnessStatus.UNAVAILABLE
        if latest_snapshot and latest_snapshot.completed_at:
            cache_age_seconds = max(0, int((now - latest_snapshot.completed_at).total_seconds()))
            settings_for_provider = ProviderCacheSettings.for_provider(cursor.provider_id)
            freshness_status = latest_snapshot.freshness_status
            if cache_age_seconds > settings_for_provider.sync_stale_after_seconds:
                freshness_status = ProviderFreshnessStatus.STALE
        if cursor.status == ProviderSyncCursor.STATUS_RUNNING:
            freshness_status = ProviderFreshnessStatus.RUNNING
        if cursor.status == ProviderSyncCursor.STATUS_FAILED and not latest_snapshot:
            freshness_status = ProviderFreshnessStatus.FAILED
        return {
            'provider_id': cursor.provider_id,
            'profile_id': cursor.profile_id,
            'status': freshness_status if cursor.status == ProviderSyncCursor.STATUS_SUCCESS else cursor.status,
            'freshness_status': freshness_status,
            'latest_snapshot_id': str(latest_snapshot.id) if latest_snapshot else '',
            'latest_successful_sync_at': cursor.last_successful_sync_at.isoformat() if cursor.last_successful_sync_at else '',
            'cache_age_seconds': cache_age_seconds,
            'source_query_ref': cursor.source_query_ref,
            'source_query_hash': cursor.source_query_hash,
            'field_set_hash': cursor.field_set_hash,
            'mapping_version_hash': cursor.mapping_version_hash,
            'error_category': cursor.error_category,
            'last_error': cursor.last_error,
        }
