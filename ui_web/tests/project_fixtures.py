import base64
from datetime import datetime, timezone
from unittest.mock import patch

from django.urls import reverse

from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig
from project_management.app.api import ApiForProjectManagement, ProjectActor
from project_management.out.dashboard_scope_catalog import DashboardScopeCatalog


def basic_header(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def synthetic_profile_records():
    return [
        {
            'profile_id': 'alpha-jira',
            'provider_id': 'jira',
            'display_name': 'Alpha Jira',
            'enabled': True,
            'connection_settings': {'base_url': 'https://jira.example.test', 'api_token': 'secret-jira-token'},
            'source_population': {'native_query_text': 'project = ALPHA'},
        },
        {
            'profile_id': 'beta-hsd',
            'provider_id': 'hsdes',
            'display_name': 'Beta HSD',
            'enabled': True,
            'connection_settings': {'base_url': 'https://hsdes.example.test', 'token': 'secret-hsd-token'},
            'source_population': {
                'source_query_ref': 'saved-query-42',
                'source_query_hash': 'hsd-version-42',
                'criteria_snapshot': '{"tenant":"beta"}',
                'exclusion_snapshot': '[]',
                'tenant_or_site': 'beta.intel.com',
                'subject_or_issue_type': 'bug',
            },
        },
        {
            'profile_id': 'disabled-hsd',
            'provider_id': 'hsdes',
            'display_name': 'Disabled HSD',
            'enabled': False,
            'connection_settings': {'base_url': 'https://disabled.example.test'},
            'source_population': {'source_query_ref': 'disabled', 'source_query_hash': 'disabled-version'},
        },
    ]


class ProjectRouteTestSupport:
    basic_auth_users = {'alice': 'wonder', 'bob': 'builder'}

    def start_profile_registry(self):
        self.profile_records = synthetic_profile_records()
        self.registry_patch = patch.object(
            ProjectProviderProfileRegistry,
            'load_default',
            side_effect=lambda: ProjectProviderProfileRegistry.from_records(self.profile_records),
        )
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)

    def create_jira_scope(self, *, name='Alpha Jira Scope', profile_id='alpha-jira',
                          provider_id='jira', status='explicit', enabled=True):
        scope = JiraScopeConfig.objects.create(name=name, jql='project = ALPHA', enabled=enabled)
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id=profile_id,
            provider_id=provider_id,
            status=status,
        )
        return scope

    def auth(self, username='alice'):
        password = self.basic_auth_users[username]
        return {'HTTP_AUTHORIZATION': basic_header(username, password)}

    def actor(self, username='alice'):
        return ProjectActor(f'basic:{username}')

    def api(self):
        return ApiForProjectManagement(DashboardScopeCatalog())

    def create_project(self, username='alice', key='alpha', name='Alpha'):
        return self.api().create_project(self.actor(username), key=key, name=name)

    def source_key(self, scope, profile_id='alpha-jira'):
        return f'jira/{profile_id}/{scope.id}'

    def create_preview(self, project, scope, username='alice', stage_key='release-1'):
        return self.client.post(
            reverse('ui_web:project_stage_preview', kwargs={'project_id': project.id}),
            {
                'key': stage_key,
                'name': 'Release 1',
                'source': self.source_key(scope),
            },
            **self.auth(username),
        )

    def preview_id(self):
        return self.client.session['project_stage_preview']['preview_id']

    def expire_preview(self, seconds=601):
        session = self.client.session
        preview = dict(session['project_stage_preview'])
        preview['issued_at'] = int(datetime.now(tz=timezone.utc).timestamp()) - seconds
        session['project_stage_preview'] = preview
        session.save()
