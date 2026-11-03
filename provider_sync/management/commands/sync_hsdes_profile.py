import json

from django.conf import settings
from django.core.management.base import BaseCommand

from bug_metrics.app.api.provider_connections import ConnectionError, create_provider_connection_resolver
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from provider_sync.app.api import ProviderFreshnessStatus
from provider_sync.app.api.hsdes import HsdesHttpClient, HsdesSavedQueryAdapter, HsdesSavedQuerySyncService


class Command(BaseCommand):
    help = 'Sync an HSD-ES provider profile into local provider facts and aggregate artifacts.'

    def add_arguments(self, parser):
        parser.add_argument('--profile-id', default='nvu-ttl-hsdes')
        parser.add_argument('--begin-ww', required=True)
        parser.add_argument('--end-ww', required=True)
        parser.add_argument('--force-refresh', action='store_true')

    def handle(self, *args, **options):
        try:
            return self._handle(*args, **options)
        except ConnectionError:
            self.stdout.write(json.dumps({
                'status': 'failed', 'profile_id': options['profile_id'],
                'error_category': 'provider_error',
            }, sort_keys=True))

    def _handle(self, *args, **options):
        registry = ProjectProviderProfileRegistry.load_default()
        resolution = registry.resolve_profile(options['profile_id'])
        if resolution.profile is None:
            self.stdout.write(json.dumps({
                'status': resolution.status,
                'profile_id': options['profile_id'],
                'provider_id': resolution.provider_id,
                'blockers': resolution.blockers,
            }, sort_keys=True))
            return
        if resolution.profile.provider_id != 'hsdes':
            self.stdout.write(json.dumps({
                'status': 'unsupported',
                'profile_id': resolution.profile.profile_id,
                'provider_id': resolution.profile.provider_id,
                'blockers': [{
                    'code': 'provider_sync_adapter_not_available',
                    'message': f'Provider {resolution.profile.provider_id} is not supported by sync_hsdes_profile.',
                }],
            }, sort_keys=True))
            return
        if not getattr(settings, 'METRICS_HSDES_LIVE_SYNC_ENABLED', False):
            self.stdout.write(json.dumps({
                'status': 'skipped',
                'freshness_status': ProviderFreshnessStatus.CONFIGURATION_REQUIRED,
                'profile_id': resolution.profile.profile_id,
                'provider_id': resolution.profile.provider_id,
                'reason': 'Set METRICS_HSDES_LIVE_SYNC_ENABLED=true and configure backend HSD-ES credentials to run live sync.',
            }, sort_keys=True))
            return
        client = create_provider_connection_resolver(settings, registry).resolve_record(resolution.profile).open_hsdes_client(HsdesHttpClient)
        result = HsdesSavedQuerySyncService(
            adapter=HsdesSavedQueryAdapter(client),
            profile_registry=registry,
        ).sync_profile(
            profile_id=resolution.profile.profile_id,
            begin_ww=options['begin_ww'],
            end_ww=options['end_ww'],
            force_refresh=options['force_refresh'],
        )
        self.stdout.write(json.dumps(result, sort_keys=True))
