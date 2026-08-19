import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bug_metrics.container import bug_metrics_container
from jira_history.container import jira_history_container
from jira_sync.models import JiraSyncCursor
from jira_sync.out.jira_scope_issue_adapter import JiraScopeIssueAdapter, create_jira_client


class Command(BaseCommand):
    help = 'Sync one saved Jira bug trend scope into local durable history.'

    def add_arguments(self, parser):
        parser.add_argument('scope_id', type=int)
        parser.add_argument('--coverage-start', required=True)
        parser.add_argument('--coverage-end', required=True)
        parser.add_argument('--full', action='store_true')

    def handle(self, *args, **options):
        bug_trend_api = bug_metrics_container.bug_trend_api
        scope = bug_trend_api.get_scope(options['scope_id'])
        coverage_start = self._parse_date(options['coverage_start'])
        coverage_end = self._parse_date(options['coverage_end'])
        cursor = self._claim_cursor(scope, coverage_start, coverage_end, options['full'])

        try:
            adapter = JiraScopeIssueAdapter(create_jira_client(settings))
            history_api = jira_history_container.jira_history_api
            full_sync = options['full'] or cursor.last_jira_updated_cutoff is None
            current_issues, out_of_scope_issues = self._fetch_issues(adapter, history_api, scope, cursor, full_sync)
            with transaction.atomic():
                cursor = JiraSyncCursor.objects.select_for_update().get(pk=cursor.pk)
                if full_sync:
                    history_api.clear_current_scope_state(scope)
                latest_updated_at = cursor.last_jira_updated_cutoff
                for issue_payload in out_of_scope_issues:
                    updated_at = self._store_issue(history_api, scope, issue_payload, is_in_current_scope=False)
                    latest_updated_at = max(latest_updated_at, updated_at) if latest_updated_at else updated_at
                for issue_payload in current_issues:
                    updated_at = self._store_issue(history_api, scope, issue_payload, is_in_current_scope=True)
                    latest_updated_at = max(latest_updated_at, updated_at) if latest_updated_at else updated_at

                calculation_run = bug_trend_api.recalculate_scope(scope.id, coverage_start, coverage_end)
                cursor.status = JiraSyncCursor.STATUS_SUCCESS
                cursor.last_successful_sync_at = timezone.now()
                cursor.last_jira_updated_cutoff = latest_updated_at
                cursor.earliest_reliable_bucket_start = calculation_run.source_coverage_start
                cursor.latest_reliable_bucket_end = calculation_run.source_coverage_end
                cursor.changelog_coverage_status = 'covered'
                cursor.materialized_config_version_hash = scope.config_version_hash
                cursor.save()
            self.stdout.write(self.style.SUCCESS(f'Synced Jira scope {scope.id}: {len(current_issues)} issues'))
        except Exception as error:
            cursor.status = JiraSyncCursor.STATUS_FAILED
            cursor.last_error = str(error)
            cursor.save(update_fields=['status', 'last_error', 'updated_at'])
            raise

    def _claim_cursor(self, scope, coverage_start, coverage_end, full_sync):
        with transaction.atomic():
            cursor, _ = JiraSyncCursor.objects.select_for_update().get_or_create(scope=scope)
            if cursor.status == JiraSyncCursor.STATUS_RUNNING:
                raise CommandError('A sync is already running for this scope.')
            if cursor.last_jira_updated_cutoff and not full_sync:
                if cursor.materialized_config_version_hash != scope.config_version_hash:
                    raise CommandError('Scope configuration changed since the last materialization; run with --full.')
                if not cursor.earliest_reliable_bucket_start or not cursor.latest_reliable_bucket_end:
                    raise CommandError('Existing incremental cursor has no reliable coverage window; run with --full.')
                if coverage_start < cursor.earliest_reliable_bucket_start or coverage_end > cursor.latest_reliable_bucket_end:
                    raise CommandError('Incremental sync cannot expand reliable coverage; run with --full for the requested range.')
            cursor.status = JiraSyncCursor.STATUS_RUNNING
            cursor.last_error = ''
            cursor.save(update_fields=['status', 'last_error', 'updated_at'])
            return cursor

    def _build_jql(self, scope, cursor, full_sync):
        if full_sync or not cursor.last_jira_updated_cutoff:
            return scope.jql
        cutoff = cursor.last_jira_updated_cutoff - timedelta(hours=24)
        return f'({scope.jql}) AND updated >= "{cutoff.strftime("%Y-%m-%d %H:%M")}"'

    def _fetch_issues(self, adapter, history_api, scope, cursor, full_sync):
        field_names = self._field_names(scope)
        matching_issues = adapter.fetch_issues(self._build_jql(scope, cursor, full_sync), field_names)
        if full_sync:
            return matching_issues, []

        matching_by_key = {issue['key']: issue for issue in matching_issues}
        changed_known_issues = self._fetch_changed_known_issues(adapter, history_api, scope, cursor, field_names)
        out_of_scope_issues = [issue for issue in changed_known_issues if issue['key'] not in matching_by_key]
        return list(matching_by_key.values()), out_of_scope_issues

    def _fetch_changed_known_issues(self, adapter, history_api, scope, cursor, field_names):
        known_issue_keys = history_api.list_tracked_issue_keys(scope)
        if not known_issue_keys or not cursor.last_jira_updated_cutoff:
            return []

        cutoff = cursor.last_jira_updated_cutoff - timedelta(hours=24)
        issues = []
        for issue_key_batch in self._issue_key_batches(known_issue_keys):
            quoted_keys = ', '.join(f'"{issue_key}"' for issue_key in issue_key_batch)
            jql = f'issuekey in ({quoted_keys}) AND updated >= "{cutoff.strftime("%Y-%m-%d %H:%M")}"'
            issues.extend(adapter.fetch_issues(jql, field_names))
        return issues

    def _issue_key_batches(self, issue_keys):
        batch_size = 50
        for index in range(0, len(issue_keys), batch_size):
            yield issue_keys[index:index + batch_size]

    def _field_names(self, scope):
        field_names = [
            'summary', 'issuetype', 'status', 'resolution', 'priority', 'components', 'assignee',
            'created', 'updated', 'resolutiondate', scope.severity_field, scope.component_field,
            scope.owner_field, scope.team_field, scope.milestone_field, scope.fix_version_field,
            scope.package_version_field, *scope.display_fields,
        ]
        return [field_name for field_name in field_names if field_name]

    def _store_issue(self, history_api, scope, issue_payload, is_in_current_scope: bool):
        fields = issue_payload.get('fields', {})
        issue_key = issue_payload['key']
        updated_at = self._parse_datetime(fields.get('updated'))
        history_api.store_snapshot(
            scope,
            issue_key,
            updated_at,
            self._payload_hash(issue_payload),
            issue_payload,
        )
        history_api.upsert_issue(scope, issue_key, {
            'summary': fields.get('summary') or '',
            'issue_type': self._name_value(fields.get('issuetype')),
            'status': self._name_value(fields.get('status')),
            'resolution_value': self._name_value(fields.get('resolution')),
            'severity_value': self._field_value(fields.get(scope.severity_field or 'priority')),
            'component_value': self._field_value(fields.get(scope.component_field or 'components')),
            'owner_value': self._field_value(fields.get(scope.owner_field or 'assignee')),
            'team_value': self._field_value(fields.get(scope.team_field)),
            'milestone_value': self._field_value(fields.get(scope.milestone_field or scope.fix_version_field)),
            'created_at': self._parse_datetime(fields.get('created')),
            'updated_at': updated_at,
            'resolved_at': self._parse_datetime(fields.get('resolutiondate')),
            'raw_fields_json': fields,
            'is_in_current_scope': is_in_current_scope,
        })
        self._store_transitions(history_api, scope, issue_key, issue_payload.get('changelog', {}))
        return updated_at

    def _store_transitions(self, history_api, scope, issue_key, changelog):
        for history in changelog.get('histories', []):
            transitioned_at = self._parse_datetime(history.get('created'))
            for item in history.get('items', []):
                if item.get('field') in {'status', 'resolution'}:
                    history_api.store_transition(
                        scope,
                        issue_key,
                        transitioned_at,
                        item.get('field'),
                        item.get('fromString') or '',
                        item.get('toString') or '',
                    )

    def _payload_hash(self, payload):
        encoded_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(encoded_payload.encode('utf-8')).hexdigest()

    def _field_value(self, raw_value):
        if raw_value is None:
            return ''
        if isinstance(raw_value, list):
            return ', '.join(self._field_value(item) for item in raw_value if item is not None)
        if isinstance(raw_value, dict):
            return raw_value.get('name') or raw_value.get('displayName') or raw_value.get('value') or raw_value.get('key') or ''
        return str(raw_value)

    def _name_value(self, raw_value):
        return raw_value.get('name', '') if isinstance(raw_value, dict) else ''

    def _parse_datetime(self, raw_value):
        if not raw_value:
            return None
        return timezone.datetime.fromisoformat(raw_value.replace('Z', '+00:00'))

    def _parse_date(self, raw_value):
        return timezone.datetime.fromisoformat(raw_value).date()