import hashlib

from .provider_aggregate_contracts import MAPPING_VERSION, SOURCE_POPULATION_FIELDS


class ProviderAggregateSourceMixin:
    def _jira_source_population_without_scope(self, query):
        return self._source_population_from_profile(query)

    def _jira_source_population(self, query, scope, run):
        source_query_hash = hashlib.sha256(scope.jql.encode('utf-8')).hexdigest()
        fact_snapshot_id = self._fact_snapshot_id(scope, run) if run else ''
        return self._source_population_from_profile(query, {
            'source_query_ref': f'jira_scope:{scope.id}',
            'source_query_hash': source_query_hash,
            'source_query_name': scope.name,
            'native_query_text': scope.jql,
            'subject_or_issue_type': 'jira_issue',
            'criteria_operator': 'JQL',
            'criteria_snapshot': scope.jql,
            'mapping_version_hash': run.config_version_hash if run else scope.config_version_hash,
            'fact_snapshot_id': fact_snapshot_id,
        })

    def _hsdes_source_population(self, query):
        return self._source_population_from_profile(query)

    def _empty_source_population(self, query):
        return self._source_population({
            'profile_id': query.profile_id,
            'provider_id': query.provider_id,
            'ownership_type': '',
            'source_query_ref': '',
            'source_query_hash': '',
            'source_query_name': '',
            'native_query_text': '',
            'tenant_or_site': '',
            'subject_or_issue_type': '',
            'criteria_operator': '',
            'criteria_snapshot': '',
            'exclusion_snapshot': '',
            'permission_assumptions': '',
            'observed_result_contract': '',
            'mapping_version': '',
            'mapping_version_hash': '',
            'fact_snapshot_id': '',
        })

    def _source_population(self, values):
        return {
            field_name: values.get(field_name, '')
            for field_name in SOURCE_POPULATION_FIELDS
        }

    def _source_population_from_profile(self, query, overrides=None):
        values = {
            'profile_id': query.profile_id,
            'provider_id': query.provider_id,
            'mapping_version': str(MAPPING_VERSION),
            'mapping_version_hash': '',
            'fact_snapshot_id': '',
        }
        resolution = self._profile_registry.resolve_profile(query.profile_id)
        if resolution.profile is not None:
            profile = resolution.profile
            values.update(profile.source_population)
            values['profile_id'] = profile.profile_id
            values['provider_id'] = profile.provider_id
            values['mapping_version'] = str(profile.mapping_version)
            values['mapping_version_hash'] = profile.mapping_version_hash
        if overrides:
            values.update(overrides)
        return self._source_population(values)

    def _fact_snapshot_id(self, scope, run):
        return f'jira-scope-{scope.id}-{run.config_version_hash[:12]}-{run.id}'
