import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bug_metrics.container import bug_metrics_container
from bug_metrics.models import JiraScopeConfig
from jira_history.container import jira_history_container
from jira_sync.app.api.issue_payload_materializer import JiraIssuePayloadMaterializer
from jira_sync.out.jira_scope_issue_adapter import JiraScopeIssueAdapter, create_jira_client


class Command(BaseCommand):
    help = 'Read Jira issues and dump a bounded real REST-shaped fixture for bug trend validation.'

    def add_arguments(self, parser):
        parser.add_argument('--project', required=True)
        parser.add_argument('--name', default='Real Intel Jira Bug Trend Fixture')
        parser.add_argument('--jql', default='')
        parser.add_argument('--issue-limit', type=int, default=200)
        parser.add_argument('--page-size', type=int, default=50)
        parser.add_argument('--output', default='state/real_jira_bug_trend_fixture.json')
        parser.add_argument('--coverage-start', default='2025-04-07')
        parser.add_argument('--coverage-end', default='2026-08-09')
        parser.add_argument('--seed-db', action='store_true')
        parser.add_argument('--recalculate', action='store_true')

    def handle(self, *args, **options):
        self._validate_options(options)
        scope = self._build_scope_config(options)
        materializer = JiraIssuePayloadMaterializer()
        field_names = materializer.field_names(scope)
        jql = options['jql'] or f'project = {options["project"]} ORDER BY updated DESC'
        adapter = JiraScopeIssueAdapter(create_jira_client(settings), page_size=options['page_size'])
        issue_payloads = adapter.fetch_issues(jql, field_names, issue_limit=options['issue_limit'])
        output_path = Path(options['output'])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self._fixture_payload(scope, jql, field_names, issue_payloads), indent=2), encoding='utf-8')

        if options['seed_db']:
            scope = self._upsert_scope(options)
            self._seed_database(scope, materializer, issue_payloads, options['recalculate'], options['coverage_start'], options['coverage_end'])

        self.stdout.write(self.style.SUCCESS(f'Dumped {len(issue_payloads)} Jira issues to {output_path}'))

    def _validate_options(self, options):
        if options['issue_limit'] < 1 or options['issue_limit'] > 1000:
            raise CommandError('--issue-limit must be between 1 and 1000')
        if options['page_size'] < 1 or options['page_size'] > 100:
            raise CommandError('--page-size must be between 1 and 100')
        if options['recalculate'] and not options['seed_db']:
            raise CommandError('--recalculate requires --seed-db')

    def _build_scope_config(self, options):
        scope = JiraScopeConfig(name=options['name'], **self._scope_defaults(options))
        scope.config_version_hash = scope.calculate_config_version_hash()
        return scope

    def _upsert_scope(self, options):
        scope, _ = JiraScopeConfig.objects.update_or_create(
            name=options['name'],
            defaults=self._scope_defaults(options),
        )
        return scope

    def _scope_defaults(self, options):
        return {
            'ip': 'Intel Jira',
            'project_label': options['project'],
            'jql': options['jql'] or f'project = {options["project"]}',
            'bug_type_values': ['Bug'],
            'fixed_status_values': ['Fixed', 'Resolved', 'Done'],
            'closed_status_values': ['Closed'],
            'fixed_resolution_values': ['Fixed', 'Done'],
            'severity_field': 'priority',
            'critical_high_values': ['P1-Critical', 'P2-High', 'Critical', 'High'],
            'medium_low_values': ['P3-Medium', 'P4-Low', 'Medium', 'Low'],
            'component_field': 'components',
            'owner_field': 'assignee',
            'fix_version_field': 'fixVersions',
            'display_fields': ['priority', 'components', 'fixVersions'],
            'bucket_granularity': JiraScopeConfig.GRANULARITY_WEEKLY,
            'enabled': True,
        }

    def _fixture_payload(self, scope, jql, field_names, issue_payloads):
        return {
            'source': 'jira-rest-read-only',
            'scope': {
                'name': scope.name,
                'project_label': scope.project_label,
                'jql': scope.jql,
                'config_version_hash': scope.config_version_hash,
            },
            'query': {
                'jql': jql,
                'fields': field_names,
                'expand': 'changelog',
                'issue_count': len(issue_payloads),
            },
            'issues': issue_payloads,
        }

    def _seed_database(self, scope, materializer, issue_payloads, recalculate, coverage_start, coverage_end):
        history_api = jira_history_container.jira_history_api
        with transaction.atomic():
            history_api.clear_current_scope_state(scope)
            for issue_payload in issue_payloads:
                materializer.store_issue(history_api, scope, issue_payload, is_in_current_scope=True)
            if recalculate:
                bug_metrics_container.bug_trend_api.recalculate_scope(
                    scope.id,
                    date.fromisoformat(coverage_start),
                    date.fromisoformat(coverage_end),
                )