import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

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
        if options['profile_id'] != 'nvu-ttl-hsdes':
            raise CommandError('Only nvu-ttl-hsdes is supported by the first HSD-ES live sync command.')
        if not getattr(settings, 'METRICS_HSDES_LIVE_SYNC_ENABLED', False):
            self.stdout.write(json.dumps({
                'status': 'skipped',
                'freshness_status': ProviderFreshnessStatus.CONFIGURATION_REQUIRED,
                'profile_id': options['profile_id'],
                'reason': 'Set METRICS_HSDES_LIVE_SYNC_ENABLED=true and configure backend HSD-ES credentials to run live sync.',
            }))
            return
        client = HsdesHttpClient(
            base_url=settings.METRICS_HSDES_API_BASE_URL,
            auth_mode=settings.METRICS_HSDES_AUTH_MODE,
            username=settings.METRICS_HSDES_USERNAME,
            password=settings.METRICS_HSDES_PASSWORD,
            token=settings.METRICS_HSDES_TOKEN,
            timeout_seconds=settings.METRICS_HSDES_TIMEOUT_SECONDS,
            transport=settings.METRICS_HSDES_HTTP_TRANSPORT,
        )
        result = HsdesSavedQuerySyncService(
            adapter=HsdesSavedQueryAdapter(client),
        ).sync_nvu_ttl_profile(
            begin_ww=options['begin_ww'],
            end_ww=options['end_ww'],
            force_refresh=options['force_refresh'],
        )
        self.stdout.write(json.dumps(result, sort_keys=True))
