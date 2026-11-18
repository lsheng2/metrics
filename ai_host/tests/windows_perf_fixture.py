"""Current-contract adaptation of the signed S0b data and idle-worker fixture."""
from pathlib import Path
from types import ModuleType
import sys


PAGES = {}
WORKER = {'reconcile_calls': 0, 'executed': [], 'started': False}
PATCHES = []


def configure(root, instance, *, debug):
    from django.conf import settings
    from scripts.validation.run_report_authoring_tests import test_settings

    values = test_settings(instance)
    values.update({
        'DATABASES': {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(root / 'catalog.sqlite3')}},
        'METRICS_SQLITE_DATABASE_PATH': root / 'catalog.sqlite3',
        'DEBUG': debug, 'COMPRESS_ENABLED': not debug,
        'METRICS_BASE_URL': '',
        'METRICS_BASIC_AUTH_USERS': {'alice': 'wonder', 'bob': 'builder'},
        'METRICS_PROJECT_RUN_ENABLED': True,
        'METRICS_PROJECT_ARCHIVE_AUTHOR_NAME': 'S0 Synthetic',
        'METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL': 's0@example.test',
        'METRICS_PROJECT_LOCAL_OPERATOR_USERNAME': '',
        'METRICS_AI_MODEL_BASE_URL': '', 'METRICS_AI_MODEL_NAME': '', 'METRICS_AI_MODEL_API_KEY': '',
        'SESSION_COOKIE_NAME': 's0_coinstall_sessionid', 'CSRF_COOKIE_NAME': 's0_coinstall_csrftoken',
        'LANGUAGE_COOKIE_NAME': 's0_coinstall_language',
        'METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE': [
            {
                'profile_id': 'synthetic-jira', 'provider_id': 'jira', 'display_name': 'Synthetic Jira',
                'enabled': True, 'connection_settings': {
                    'base_url': 'https://tracker.example.test', 'api_token': 'SYNTHETIC_ONLY_NOT_REAL',
                }, 'source_population': {'native_query_text': 'project = SYNTH'},
            },
            {
                'profile_id': 'synthetic-hsd', 'provider_id': 'hsdes', 'display_name': 'Synthetic HSD',
                'enabled': True, 'connection_settings': {
                    'base_url': 'https://synthetic-hsdes.example.test/rest', 'token': 'SYNTHETIC_ONLY_NOT_REAL',
                }, 'source_population': {
                    'source_query_ref': 'synthetic-saved-query', 'source_query_hash': 'synthetic-hsd-version',
                    'criteria_snapshot': '{"project":"SYNTH"}', 'exclusion_snapshot': '[]',
                    'tenant_or_site': 'synthetic.intel.example', 'subject_or_issue_type': 'bug',
                },
            },
        ],
    })
    values['INSTALLED_APPS'] += ('scripts.validation.project_ui_fixture_app.ProjectUiFixtureAppConfig',)
    Path(values['METRICS_PROJECT_ARCHIVE_ROOT']).mkdir(parents=True)
    settings.configure(**values)


def seed_projects():
    from django.urls import reverse
    from bug_metrics.app.api import ApiForBugTrend
    from bug_metrics.app.api.scope_config import SavedScopeConfig
    from project_management.app.api import ProjectActor, ScopeSelection
    from project_management.container import build_project_api

    api = ApiForBugTrend()
    scope = api.save_scope_config(SavedScopeConfig(
        id=None, name='S0 Synthetic Jira Scope', ip='SYNTH', project_label='SYNTH',
        jql='project = SYNTH AND issuetype = Bug', bug_type_values=['Bug'], open_status_values=['Open'],
        fixed_status_values=['Fixed'], closed_status_values=['Closed'], terminal_excluded_status_values=[],
        fixed_resolution_values=['Fixed'], closed_resolution_values=['Done'], reopen_status_values=['Reopened'],
        severity_field='priority', critical_high_values=['P1'], medium_low_values=['P3'],
        component_field='component', owner_field='assignee', team_field='team', milestone_field='fixVersion',
        fix_version_field='fixVersion', package_version_field='', display_fields=['summary', 'status'],
        timezone='UTC', bucket_granularity='weekly', enabled=True,
    ))
    api.set_scope_provider_binding(scope.id, 'synthetic-jira', actor='s0_fixture')
    projects = build_project_api()
    actor = ProjectActor('basic:alice')
    project = projects.create_project(actor, key='s0-alpha', name='S0 Alpha')
    jira = projects.add_stage(actor, project.id, key='jira-release', name='Jira Release',
                              selection=ScopeSelection('synthetic-jira', scope.id))
    hsd = projects.add_stage(actor, project.id, key='hsd-release', name='HSD Release',
                             selection=ScopeSelection('synthetic-hsd'))
    return {
        'scope_id': scope.id, 'project_id': str(project.id),
        'jira_stage_id': str(jira.id), 'hsd_stage_id': str(hsd.id),
        'pages': {
            'home': reverse('ui_web:homepage'), 'projects': reverse('ui_web:projects'),
            'project_detail': reverse('ui_web:project_detail', kwargs={'project_id': project.id}),
            'bug_trend': reverse('ui_web:bug_trend'),
        },
    }


def bootstrap(seed, instance):
    from unittest.mock import patch
    from django.urls import reverse
    from project_management.app.api import reports as api
    from project_management.tests.capture_archive_fixtures import ProjectApiStub
    from project_management.tests.report_draft_fixtures import FixedClock, StaticSourceReader, draft_command
    from ui_web.facades.project_reports import ProjectReportFacade
    from ui_web.facades.project_runs import ProjectRunFacade
    from ui_web.tests.test_report_authoring_views import AuthoringUiArchive
    from ui_web.views import project_reports
    from ui_web.views.project_run_views import ProjectRunSubmitView

    archive = AuthoringUiArchive(instance / 'report-archive')
    service = api.ReportDraftService(
        archive, StaticSourceReader(rule_hash=archive.stage.definition_hash), api.ReportRenderer(), clock=FixedClock(),
    )
    facade = ProjectReportFacade(
        ProjectApiStub(archive.project, archive.stage, owner_subject=archive.actor.subject), service, archive,
    )
    for view in (project_reports.ProjectStageReportView, project_reports.ReportDraftEditView):
        PATCHES.append(patch.object(view, 'facade_factory', staticmethod(lambda: facade)))
    PATCHES.append(patch.object(
        ProjectRunSubmitView, 'facade_factory', staticmethod(lambda: ProjectRunFacade(None, None, runtime_ready=False)),
    ))
    for patcher in PATCHES:
        patcher.start()
    draft = service.create_authored(
        archive.actor, archive.project.id, archive.stage.id, command_id=draft_command(700),
        selection=api.ReportSelection(capture_id=archive.capture_id, timezone='Asia/Shanghai'),
        template=api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {}),
    )
    PAGES.update(seed['pages'])
    PAGES.update({
        'stage_reports': reverse('ui_web:project_stage_reports', kwargs={
            'project_id': archive.project.id, 'stage_id': archive.stage.id,
        }),
        'draft_edit': reverse('ui_web:report_draft_edit', kwargs={
            'project_id': archive.project.id, 'stage_id': archive.stage.id, 'draft_id': draft.draft_id,
        }),
    })
    install_probe_urls()


def install_probe_urls():
    from django.conf import settings
    from django.http import JsonResponse
    from django.urls import include, path

    def pages(request):
        return JsonResponse({'pages': PAGES, 'worker_started': WORKER['started'],
                             'worker_executed': WORKER['executed'], 'debug': settings.DEBUG,
                             'collected_static_files': sum(path.is_file() for path in Path(settings.STATIC_ROOT).rglob('*'))})

    module = ModuleType('windows_qualification_urls')
    module.urlpatterns = [path('qualification/pages/', pages), path('', include(settings.ROOT_URLCONF))]
    sys.modules[module.__name__] = module
    settings.ROOT_URLCONF = module.__name__


class ReadService:
    def __init__(self, inner):
        self.inner, self.notifier = inner, None

    def reconcile_interrupted(self):
        WORKER['reconcile_calls'] += 1
        return ()

    def __getattr__(self, name):
        return getattr(self.inner, name)


class NoDispatchWorker:
    def execute(self, actor, project_id, stage_id, operation_id):
        WORKER['executed'].append(str(operation_id))


def build_idle_runtime(**kwargs):
    from project_management.app.api.run_factories import build_run_read_service
    from project_management.runtime import ProjectRunRuntime

    runtime = ProjectRunRuntime(ReadService(build_run_read_service()), NoDispatchWorker())
    original_start = runtime.start

    def start():
        original_start()
        WORKER['started'] = True

    runtime.start = start
    return runtime
