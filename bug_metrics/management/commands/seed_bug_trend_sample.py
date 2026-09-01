from datetime import date, datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from bug_metrics.container import bug_metrics_container
from bug_metrics.models import JiraScopeConfig
from jira_history.models import JiraIssue, JiraTransition


class Command(BaseCommand):
    help = 'Seed local sample data for the bug trend dashboard.'

    def handle(self, *args, **options):
        with transaction.atomic():
            self._seed_scope(
                name='Local STDEL Bug Trend',
                ip='NVU',
                project_label='STDEL',
                milestone_field='',
                jql='project = STDEL AND issuetype = Bug',
                component_value='team_emulation',
            )
            parity_scope = self._seed_scope(
                name='chiplet-2a-jira',
                ip='chiplet_ip',
                project_label='chiplet',
                milestone_field='2a',
                jql='project = "131600" AND component = "team_int_qemu"',
                component_value='team_int_qemu',
            )
        self.stdout.write(self.style.SUCCESS(f'Seeded provider parity sample scope {parity_scope.id}: {parity_scope.name}'))

    def _seed_scope(self, name, ip, project_label, milestone_field, jql, component_value):
        scope, _ = JiraScopeConfig.objects.update_or_create(
            name=name,
            defaults={
                'ip': ip,
                'project_label': project_label,
                'milestone_field': milestone_field,
                'jql': jql,
                'bug_type_values': ['Bug'],
                'open_status_values': ['Open'],
                'fixed_status_values': ['Fixed'],
                'closed_status_values': ['Closed'],
                'fixed_resolution_values': ['Fixed'],
                'severity_field': 'priority',
                'critical_high_values': ['P1-Critical', 'P2-High'],
                'medium_low_values': ['P3-Medium'],
                'component_field': 'components',
                'owner_field': 'assignee',
                'bucket_granularity': JiraScopeConfig.GRANULARITY_WEEKLY,
                'enabled': True,
            },
        )
        scope.jira_issues.all().delete()
        scope.jira_transitions.all().delete()
        scope.calculation_runs.all().delete()

        coverage_start = date(2025, 4, 7)
        coverage_end = date(2026, 8, 30)
        self._create_sample_history(scope, coverage_start, coverage_end, component_value)

        bug_metrics_container.bug_trend_api.recalculate_scope(scope.id, coverage_start, coverage_end)
        return scope

    def _create_sample_history(self, scope, coverage_start, coverage_end, component_value):
        issue_records = []
        open_issue_keys = []
        issue_number = 9000
        week_index = 0
        week_start = coverage_start
        while week_start <= coverage_end:
            new_medium_count = self._medium_count_for_week(week_index)
            new_critical_count = self._critical_count_for_week(week_index)
            for index in range(new_medium_count):
                issue_number += 1
                issue_key = f'STDEL-{issue_number}'
                created_at = self._week_datetime(week_start, 1 + (index % 4), 10)
                issue_records.append({
                    'issue_key': issue_key,
                    'summary': f'Medium bug opened in {self._week_label(week_start)}',
                    'priority': 'P3-Medium',
                    'created_at': created_at,
                    'fixed_at': None,
                })
                open_issue_keys.append(issue_key)
            for index in range(new_critical_count):
                issue_number += 1
                issue_key = f'STDEL-{issue_number}'
                created_at = self._week_datetime(week_start, 2 + (index % 3), 11)
                priority = 'P1-Critical' if (week_index + index) % 3 == 0 else 'P2-High'
                issue_records.append({
                    'issue_key': issue_key,
                    'summary': f'Critical/high bug opened in {self._week_label(week_start)}',
                    'priority': priority,
                    'created_at': created_at,
                    'fixed_at': None,
                })
                open_issue_keys.append(issue_key)
            fixed_count = min(self._fixed_count_for_week(week_index), max(0, len(open_issue_keys) - self._minimum_open_backlog(week_index)))
            for index in range(fixed_count):
                issue_key = open_issue_keys.pop(0)
                record = next(item for item in issue_records if item['issue_key'] == issue_key)
                fixed_at = self._week_datetime(week_start, 4 + (index % 2), 9)
                if fixed_at <= record['created_at']:
                    fixed_at = record['created_at'] + timedelta(days=1)
                record['fixed_at'] = fixed_at
            week_index += 1
            week_start += timedelta(days=7)

        issue_objects = []
        transition_objects = []
        for record in issue_records:
            if record['fixed_at']:
                issue_objects.append(self._issue(scope, record['issue_key'], record['summary'], 'Fixed', 'Fixed', record['priority'], record['created_at'], record['fixed_at'], component_value))
                transition_objects.append(self._transition(scope, record['issue_key'], record['fixed_at'], 'Open', 'Fixed'))
            else:
                issue_objects.append(self._issue(scope, record['issue_key'], record['summary'], 'Open', '', record['priority'], record['created_at'], record['created_at'], component_value))

        JiraIssue.objects.bulk_create(issue_objects, batch_size=1000)
        JiraTransition.objects.bulk_create(transition_objects, batch_size=1000)

    def _medium_count_for_week(self, week_index):
        if week_index < 8:
            return [1, 1, 2, 3, 1, 2, 1, 0][week_index]
        if week_index < 24:
            return [0, 1, 0, 2, 1, 0, 1, 2][week_index % 8]
        if week_index < 42:
            return [1, 2, 4, 5, 3, 4, 2, 6, 3][week_index % 9]
        if week_index < 56:
            return [2, 1, 3, 4, 5, 3, 8][week_index % 7]
        return [3, 5, 4, 7, 6, 5, 4][week_index % 7]

    def _critical_count_for_week(self, week_index):
        if week_index < 20:
            return 1 if week_index in {10, 16, 18} else 0
        if week_index < 42:
            return [0, 1, 1, 0, 2, 0, 1][week_index % 7]
        if week_index < 56:
            return [1, 2, 0, 2, 3, 1, 0][week_index % 7]
        return [2, 3, 1, 3, 2, 1, 0][week_index % 7]

    def _fixed_count_for_week(self, week_index):
        if week_index < 12:
            return [0, 0, 1, 0, 2, 0][week_index % 6]
        if week_index < 36:
            return [1, 2, 0, 3, 2, 4][week_index % 6]
        if week_index < 58:
            return [2, 4, 3, 5, 6, 2, 4][week_index % 7]
        return [3, 5, 4, 6, 5, 8, 3][week_index % 7]

    def _minimum_open_backlog(self, week_index):
        if week_index < 20:
            return 2
        if week_index < 42:
            return 8
        if week_index < 58:
            return 16
        return 24

    def _issue(self, scope, issue_key, summary, status, resolution, priority, created_at, updated_at, component_value):
        return JiraIssue(
            scope=scope,
            issue_key=issue_key,
            summary=summary,
            issue_type='Bug',
            status=status,
            resolution_value=resolution,
            severity_value=priority,
            component_value=component_value,
            owner_value='Alice',
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=updated_at if resolution else None,
            raw_fields_json={'priority': {'name': priority}, 'components': [{'name': component_value}]},
            is_in_current_scope=True,
        )

    def _transition(self, scope, issue_key, changed_at, from_status, to_status):
        return JiraTransition(
            scope=scope,
            issue_key=issue_key,
            transitioned_at=changed_at,
            field='status',
            from_value=from_status,
            to_value=to_status,
        )

    def _week_datetime(self, week_start, day_offset, hour):
        return datetime.combine(week_start + timedelta(days=day_offset), datetime.min.time(), tzinfo=timezone.utc).replace(hour=hour)

    def _week_label(self, week_start):
        year, week, _ = week_start.isocalendar()
        return f'{str(year)[2:]}WW{week:02d}'
