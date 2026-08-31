import json

from django.conf import settings
from django.core.management.base import BaseCommand

from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from provider_sync.app.api import ProviderFreshnessStatus
from provider_sync.app.api.hsdes import HsdesHttpClient, HsdesSavedQueryAdapter, HsdesSavedQuerySyncService


class Command(BaseCommand):
    help = 'Sync a configured provider profile into local provider facts and aggregate artifacts.'

    def add_arguments(self, parser):
        parser.add_argument('--profile-id', required=True)
        parser.add_argument('--begin-ww', required=True)
        parser.add_argument('--end-ww', required=True)
        parser.add_argument('--force-refresh', action='store_true')

    def handle(self, *args, **options):
        profile_id = options['profile_id']
        registry = ProjectProviderProfileRegistry.load_default()
        resolution = registry.resolve_profile(profile_id)
        if resolution.profile is None:
            self.stdout.write(json.dumps({
                'status': resolution.status,
                'profile_id': profile_id,
                'provider_id': resolution.provider_id,
                'blockers': resolution.blockers,
            }, sort_keys=True))
            return
        profile = resolution.profile
        if profile.provider_id != 'hsdes':
            self.stdout.write(json.dumps({
                'status': 'unsupported',
                'profile_id': profile.profile_id,
                'provider_id': profile.provider_id,
                'blockers': [{
                    'code': 'provider_sync_adapter_not_available',
                    'message': f'Provider {profile.provider_id} does not have a provider_sync adapter in this command.',
                }],
            }, sort_keys=True))
            return
        if not getattr(settings, 'METRICS_HSDES_LIVE_SYNC_ENABLED', False):
            self.stdout.write(json.dumps({
                'status': 'skipped',
                'freshness_status': ProviderFreshnessStatus.CONFIGURATION_REQUIRED,
                'profile_id': profile.profile_id,
                'provider_id': profile.provider_id,
                'reason': 'Set METRICS_HSDES_LIVE_SYNC_ENABLED=true and configure backend HSD-ES credentials to run live sync.',
            }, sort_keys=True))
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
            profile_registry=registry,
        ).sync_profile(
            profile_id=profile.profile_id,
            begin_ww=options['begin_ww'],
            end_ww=options['end_ww'],
            force_refresh=options['force_refresh'],
        )
        self.stdout.write(json.dumps(result, sort_keys=True))
