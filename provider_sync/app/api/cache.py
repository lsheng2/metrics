from datetime import timedelta

from django.db.models import Q
from django.db import transaction
from django.utils import timezone

from provider_sync.models import ProviderAggregateArtifact, ProviderFact, ProviderFactSnapshot, ProviderSyncCursor
from .cache_contracts import (
    ProviderCachedArtifactResult,
    ProviderCacheIdentity,
    ProviderCacheSettings,
    ProviderFreshnessStatus,
    ProviderRefreshStartResult,
    normalized_artifact_range,
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
        range_mode: str = 'ww',
        range_start: str = '',
        range_end: str = '',
        now=None,
    ) -> ProviderCachedArtifactResult:
        artifact = self.latest_aggregate_artifact(
            provider_id,
            profile_id,
            chart_id,
            chart_version,
            begin_ww,
            end_ww,
            range_mode=range_mode,
            range_start=range_start,
            range_end=range_end,
        )
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
        range_mode: str = 'ww',
        range_start: str = '',
        range_end: str = '',
        range_grain: str = '',
        range_label_start: str = '',
        range_label_end: str = '',
    ) -> ProviderAggregateArtifact:
        range_identity = normalized_artifact_range(
            range_mode=range_mode,
            begin_ww=begin_ww,
            end_ww=end_ww,
            range_start=range_start,
            range_end=range_end,
            range_grain=range_grain,
            range_label_start=range_label_start,
            range_label_end=range_label_end,
        )
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
            range_mode=range_identity['range_mode'],
            range_start=range_identity['range_start'],
            range_end=range_identity['range_end'],
            range_grain=range_identity['range_grain'],
            range_label_start=range_identity['range_label_start'],
            range_label_end=range_identity['range_label_end'],
            fact_snapshot_id=str(snapshot.id),
        )
        return ProviderAggregateArtifact.objects.update_or_create(
            provider_id=snapshot.provider_id,
            profile_id=snapshot.profile_id,
            chart_id=chart_id,
            chart_version=chart_version,
            begin_ww=begin_ww,
            end_ww=end_ww,
            range_mode=range_identity['range_mode'],
            range_start=range_identity['range_start'],
            range_end=range_identity['range_end'],
            cache_identity_hash=identity.cache_key(),
            defaults={
                'snapshot': snapshot,
                'range_grain': range_identity['range_grain'],
                'range_label_start': range_identity['range_label_start'],
                'range_label_end': range_identity['range_label_end'],
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

    def facts_for_snapshot(self, snapshot: ProviderFactSnapshot) -> list[dict]:
        return [
            {
                'source_item_id': fact.source_item_id,
                'source_item_revision': fact.source_item_revision,
                'canonical_fields': fact.canonical_fields_json,
                'project_fields': fact.project_fields_json,
                'field_values': fact.field_values_json,
                'provider_fields': fact.provider_fields_json,
                'mapping_version': fact.mapping_version,
            }
            for fact in ProviderFact.objects.filter(snapshot=snapshot).order_by('source_item_id', 'source_item_revision')
        ]

    def latest_aggregate_artifact(
        self,
        provider_id: str,
        profile_id: str,
        chart_id: str,
        chart_version: int,
        begin_ww: str,
        end_ww: str,
        range_mode: str = 'ww',
        range_start: str = '',
        range_end: str = '',
    ) -> ProviderAggregateArtifact | None:
        query = ProviderAggregateArtifact.objects.filter(
            provider_id=provider_id,
            profile_id=profile_id,
            chart_id=chart_id,
            chart_version=chart_version,
            status='supported',
        )
        range_identity = normalized_artifact_range(
            range_mode=range_mode,
            begin_ww=begin_ww,
            end_ww=end_ww,
            range_start=range_start,
            range_end=range_end,
        )
        if range_identity['range_mode'] == 'ww':
            query = query.filter(
                begin_ww=begin_ww,
                end_ww=end_ww,
            ).filter(Q(range_mode='ww') | Q(range_mode=''))
        else:
            query = query.filter(
                range_mode=range_identity['range_mode'],
                range_start=range_identity['range_start'],
                range_end=range_identity['range_end'],
            )
        return query.select_related('snapshot').order_by('-created_at').first()

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
