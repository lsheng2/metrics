import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validation.project_ui_fixture_guard import (
    DB_FILE_NAME,
    EXPECTED_SETTINGS,
    FIXTURE_NAME,
    FixtureSafetyError,
    record_database_marker,
    validate_bootstrap_root,
    write_owner_file,
)


def main():
    parser = argparse.ArgumentParser(description='Seed the synthetic project UI validation database.')
    parser.add_argument('--fixture-root', default='', help='Empty owned fixture root under .tmp/project-reporting-w2.')
    parser.add_argument('--migrate', action='store_true')
    args = parser.parse_args()

    try:
        fixture_root = prepare_fixture_root(args.fixture_root)
        configure_fixture_environment(fixture_root)
    except FixtureSafetyError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None

    import django
    django.setup()

    if args.migrate:
        migrate()
    record_fixture_database_marker(fixture_root)
    print(json.dumps(seed(fixture_root), indent=2, sort_keys=True))


def prepare_fixture_root(raw_root):
    fixture_root = validate_bootstrap_root(raw_root)
    fixture_root.mkdir(parents=True, exist_ok=True)
    write_owner_file(fixture_root)
    return fixture_root.resolve()


def configure_fixture_environment(fixture_root):
    (fixture_root / 'runtime-state').mkdir(parents=True, exist_ok=True)
    os.environ['DJANGO_SETTINGS_MODULE'] = EXPECTED_SETTINGS
    os.environ['METRICS_PROJECT_UI_FIXTURE_ROOT'] = str(fixture_root.resolve())
    os.environ['METRICS_PROJECT_UI_FIXTURE_NAME'] = FIXTURE_NAME
    os.environ['METRICS_PROJECT_UI_FIXTURE_BOOTSTRAP'] = '1'

def record_fixture_database_marker(fixture_root):
    from django.conf import settings

    record_database_marker(fixture_root, Path(settings.DATABASES['default']['NAME']))


def migrate():
    from django.core.management import call_command
    call_command('migrate', interactive=False, verbosity=0)


def seed(fixture_root):
    from django.conf import settings
    from django.urls import reverse

    from bug_metrics.app.api import ApiForBugTrend
    from bug_metrics.app.api.scope_config import SavedScopeConfig
    from project_management.app.api import ProjectActor, ScopeSelection
    from project_management.container import build_project_api

    bug_api = ApiForBugTrend()
    scope = bug_api.save_scope_config(SavedScopeConfig(
        id=None,
        name='SYNTHETIC Jira Scope',
        ip='SYNTH',
        project_label='SYNTH',
        jql='project = SYNTH AND issuetype = Bug',
        bug_type_values=['Bug'],
        open_status_values=['Open'],
        fixed_status_values=['Fixed'],
        closed_status_values=['Closed'],
        terminal_excluded_status_values=[],
        fixed_resolution_values=['Fixed'],
        closed_resolution_values=['Done'],
        reopen_status_values=['Reopened'],
        severity_field='priority',
        critical_high_values=['P1'],
        medium_low_values=['P3'],
        component_field='component',
        owner_field='assignee',
        team_field='team',
        milestone_field='fixVersion',
        fix_version_field='fixVersion',
        package_version_field='',
        display_fields=['summary', 'status'],
        timezone='UTC',
        bucket_granularity='weekly',
        enabled=True,
    ))
    bug_api.set_scope_provider_binding(scope.id, 'synthetic-jira', actor='synthetic_fixture')

    project_api = build_project_api()
    actor = ProjectActor('basic:SYNTHETIC_ALICE')
    project = project_api.create_project(actor, key='synthetic-alpha', name='Synthetic Alpha')
    jira_stage = project_api.add_stage(
        actor,
        project.id,
        key='jira-release',
        name='Jira Release',
        selection=ScopeSelection('synthetic-jira', scope.id),
    )
    hsd_stage = project_api.add_stage(
        actor,
        project.id,
        key='hsd-release',
        name='HSD Release',
        selection=ScopeSelection('synthetic-hsd'),
    )

    return {
        'schema_version': 1,
        'settings': EXPECTED_SETTINGS,
        'fixture_root': str(fixture_root.resolve()),
        'database': str(settings.DATABASES['default']['NAME']),
        'auth': {
            'alice': {'username': 'SYNTHETIC_ALICE', 'password': 'SYNTHETIC_ALICE_PASSWORD'},
            'bob': {'username': 'SYNTHETIC_BOB', 'password': 'SYNTHETIC_BOB_PASSWORD'},
        },
        'cookies': {
            'session': settings.SESSION_COOKIE_NAME,
            'csrf': settings.CSRF_COOKIE_NAME,
            'language': settings.LANGUAGE_COOKIE_NAME,
        },
        'commands': {
            'seed': (
                r'.\.venv\Scripts\python.exe scripts\validation\project_ui_fixture.py '
                f'--migrate --fixture-root "{fixture_root.resolve()}"'
            ),
            'runserver': (
                f'$env:METRICS_PROJECT_UI_FIXTURE_ROOT="{fixture_root.resolve()}"; '
                f'$env:METRICS_PROJECT_UI_FIXTURE_NAME="{FIXTURE_NAME}"; '
                r'.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8017 '
                f'--settings {EXPECTED_SETTINGS}'
            ),
        },
        'routes': {
            'projects': reverse('ui_web:projects'),
            'project_detail': reverse('ui_web:project_detail', kwargs={'project_id': project.id}),
        },
        'sources': {
            'jira': f'jira/synthetic-jira/{scope.id}',
            'hsdes': 'hsdes/synthetic-hsd',
        },
        'project': project_payload(project),
        'stages': [stage_payload(jira_stage), stage_payload(hsd_stage)],
    }


def project_payload(project):
    return {
        **asdict(project),
        'created_at': project.created_at.isoformat(),
    }


def stage_payload(stage):
    return {
        **asdict(stage),
        'created_at': stage.created_at.isoformat(),
    }


if __name__ == '__main__':
    main()
