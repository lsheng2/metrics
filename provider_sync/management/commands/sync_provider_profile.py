import json
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from bug_metrics.container import bug_metrics_container
from bug_metrics.app.api.provider_aggregate_common import ww_range_to_dates
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.provider_profile_connection import first_profile_credential_value, profile_connection_value, profile_credential_value
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
        if profile.provider_id == 'jira':
            self.stdout.write(json.dumps(self._sync_jira_profile(profile, options), sort_keys=True))
            return
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
            base_url=profile_connection_value(profile.connection_settings, 'base_url', settings.METRICS_HSDES_API_BASE_URL),
            auth_mode=profile_connection_value(profile.connection_settings, 'auth_mode', settings.METRICS_HSDES_AUTH_MODE),
            username=profile_credential_value(profile.connection_settings, 'username', settings.METRICS_HSDES_USERNAME),
            password=profile_credential_value(profile.connection_settings, 'password', settings.METRICS_HSDES_PASSWORD),
            token=first_profile_credential_value(profile.connection_settings, ['token', 'api_token'], settings.METRICS_HSDES_TOKEN),
            timeout_seconds=int(profile_connection_value(profile.connection_settings, 'timeout_seconds', settings.METRICS_HSDES_TIMEOUT_SECONDS)),
            transport=profile_connection_value(profile.connection_settings, 'transport', settings.METRICS_HSDES_HTTP_TRANSPORT),
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

    def _sync_jira_profile(self, profile, options):
        scope, binding = self._jira_scope_for_profile(profile)
        if scope is None:
            return {
                'status': binding.status if binding else 'configuration_required',
                'freshness_status': ProviderFreshnessStatus.CONFIGURATION_REQUIRED,
                'profile_id': profile.profile_id,
                'provider_id': profile.provider_id,
                'blockers': binding.blockers if binding and binding.blockers else [{
                    'code': 'jira_scope_not_mapped',
                    'message': f'No enabled Jira scope is bound to provider profile {profile.profile_id}.',
                }],
            }
        coverage_start, coverage_end = ww_range_to_dates(options['begin_ww'], options['end_ww'])
        sync_output = StringIO()
        command_args = [
            'sync_jira_scope',
            str(scope.id),
            '--coverage-start',
            coverage_start.isoformat(),
            '--coverage-end',
            coverage_end.isoformat(),
        ]
        if options['force_refresh']:
            command_args.append('--full')
        call_command(*command_args, stdout=sync_output)
        return {
            'status': 'success',
            'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED,
            'profile_id': profile.profile_id,
            'provider_id': profile.provider_id,
            'scope_id': scope.id,
            'coverage_start': coverage_start.isoformat(),
            'coverage_end': coverage_end.isoformat(),
            'sync_summary': sync_output.getvalue().strip(),
        }

    def _jira_scope_for_profile(self, profile):
        bug_trend_api = bug_metrics_container.bug_trend_api
        blocked_binding = None
        for scope, relaxed_binding in bug_trend_api.list_scope_provider_bindings():
            if not scope.enabled or not self._binding_targets_profile(relaxed_binding, profile):
                continue
            binding = bug_trend_api.resolve_scope_provider_binding(scope)
            if binding.is_resolved:
                return scope, binding
            blocked_binding = binding
        return None, blocked_binding

    def _binding_targets_profile(self, binding, profile) -> bool:
        profile_id = binding.profile_id or binding.provenance.get('compatibility_profile_id', '')
        provider_id = binding.provider_id or binding.provenance.get('compatibility_provider_id', '')
        return profile_id == profile.profile_id and provider_id == profile.provider_id
