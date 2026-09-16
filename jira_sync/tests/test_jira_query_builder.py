from django.test import SimpleTestCase

from jira_sync.app.api.jira_query_builder import JiraScopeQueryBuilder


class TestJiraScopeQueryBuilder(SimpleTestCase):
    def test_shouldGenerateStableJqlFromCommonFiltersAndCustomFields(self):
        # Given
        builder_state = {
            'project': 'STDEL',
            'issue_types': ['Story'],
            'components': ['team_int_prc', 'team_int_simics'],
            'affected_versions': ['crc_2a'],
            'fix_versions': ['crc_2a'],
            'priorities': ['Undecided'],
            'resolutions': ['Done'],
            'security_levels': ['Public'],
            'labels': ['wired_interrupt'],
            'custom_fields': [
                {'field': 'customfield_31601', 'values': ['2026 ww 36-37']},
                {'field': 'customfield_22600', 'values': ['Emulation']},
            ],
        }

        # When
        jql = JiraScopeQueryBuilder().build(builder_state)

        # Then
        self.assertEqual(
            'project = STDEL AND issuetype = Story AND components in (team_int_prc, team_int_simics) '
            'AND versions = crc_2a AND fixVersions = crc_2a AND priority = Undecided '
            'AND resolution = Done AND security = Public AND labels = wired_interrupt '
            'AND customfield_31601 = "2026 ww 36-37" AND customfield_22600 = Emulation',
            jql,
        )

    def test_shouldSkipEmptyFiltersWhenBuildingJql(self):
        # Given
        builder_state = {
            'project': 'STDEL',
            'issue_types': ['Story', ''],
            'components': [],
            'custom_fields': [{'field': 'customfield_31601', 'values': []}],
        }

        # When
        jql = JiraScopeQueryBuilder().build(builder_state)

        # Then
        self.assertEqual('project = STDEL AND issuetype = Story', jql)
