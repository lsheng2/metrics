from datetime import date

from django.test import TestCase

from bug_metrics.app.api import bug_trend_api
from bug_metrics.app.api.provider_aggregate_contracts import ProviderChartAggregateQuery
from bug_metrics.app.api.provider_aggregates import ProviderChartAggregateService
from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig
from bug_metrics.tests.ai_publication_fixtures import seed_publication_data


def query():
    return ProviderChartAggregateQuery(
        provider_id='jira', profile_id='chiplet-2a-jira',
        begin_ww='26WW32', end_ww='26WW35', chart_id='open_bug_trend',
    )


class TestPublicationScopeAuthority(TestCase):
    def test_explicit_binding_is_used_without_a_magic_scope_name(self):
        _, run = seed_publication_data()
        result = ProviderChartAggregateService().get_aggregates(query())
        self.assertEqual('supported', result.status)
        self.assertEqual(str(run.id), result.run_metadata['calculation_run_id'])

    def test_same_name_with_different_binding_does_not_steal_the_profile(self):
        _, run = seed_publication_data()
        other = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira', jql='project = OTHER',
            bug_type_values=['Bug'], open_status_values=['Open'],
            severity_field='priority', critical_high_values=['P1-Stopper'],
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=other, profile_id='nvu-ttl-hsdes', provider_id='hsdes', status='explicit',
        )
        bug_trend_api.recalculate_scope(other.id, date(2026, 8, 3), date(2026, 8, 30))
        result = ProviderChartAggregateService().get_aggregates(query())
        self.assertEqual('supported', result.status)
        self.assertEqual(str(run.id), result.run_metadata['calculation_run_id'])

    def test_multiple_current_bindings_are_unavailable_instead_of_first_match(self):
        seed_publication_data()
        other = JiraScopeConfig.objects.create(name='Second synthetic scope', jql='project = OTHER')
        BugTrendScopeProviderBinding.objects.create(
            scope=other, profile_id='chiplet-2a-jira', provider_id='jira', status='explicit',
        )
        result = ProviderChartAggregateService().get_aggregates(query())
        self.assertEqual('unavailable', result.status)
        self.assertEqual('ambiguous', result.run_metadata['binding_status'])
        self.assertEqual([], result.grafana_rows)
