from datetime import date, datetime, timezone

from bug_metrics.app.api import bug_trend_api
from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig
from jira_history.models import JiraIssue


def seed_publication_data():
    scope = JiraScopeConfig.objects.create(
        name='Synthetic chart publication',
        jql='project = SAMPLE',
        bug_type_values=['Bug'],
        open_status_values=['Open'],
        fixed_status_values=['Fixed'],
        closed_status_values=['Closed'],
        severity_field='priority',
        critical_high_values=['P1-Stopper', 'P2-High'],
        medium_low_values=['P3-Medium'],
        component_field='components',
        owner_field='assignee',
        bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
    )
    BugTrendScopeProviderBinding.objects.create(
        scope=scope, profile_id='chiplet-2a-jira', provider_id='jira', status='explicit',
    )
    JiraIssue.objects.create(
        scope=scope, issue_key='SAMPLE-1', summary='Synthetic quality issue',
        issue_type='Bug', status='Open', severity_value='P1-Stopper',
        component_value='sample',
        created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )
    run = bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 30))
    return scope, run


def chart_request(**changes):
    from bug_metrics.app.api.ai_publication_contracts import ChartWorkflowRequest

    values = {
        'profile_id': 'chiplet-2a-jira',
        'chart_id': 'open_bug_trend',
        'requested_series': ('new_critical_high',),
        'range_mode': 'ww',
        'range_start': '26WW32',
        'range_end': '26WW35',
        'visualization': 'timeseries',
    }
    return ChartWorkflowRequest(**{**values, **changes})
