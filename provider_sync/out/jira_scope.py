from dataclasses import replace
import hashlib

from project_management.app.api.capture_archive import SourceDependencyDefinition, SourceResolutionInput, WorkItemIdentity
from provider_sync.app.api.access_contracts import AccessError, MembershipObservation, WorkItemMarker
from provider_sync.out.jira_pages import identifier, issue_key, read_pages, warnings
from provider_sync.services.capture_session import fingerprint


LIGHT_FIELDS = 'id,key,summary,updated,status,assignee,resolution,issuelinks'


def marker(row, principal):
    fields = row.get('fields')
    if not isinstance(fields, dict) or not isinstance(fields.get('updated'), str) or not fields['updated']:
        raise AccessError('PROVIDER_RECORD_INVALID')
    identity = WorkItemIdentity(principal.provider_id, principal.endpoint_id,
                                identifier(row.get('id')), issue_key(row.get('key')))
    return WorkItemMarker(identity, fields['updated'], fingerprint(fields), fields)


class JiraScopeResolver:
    def __init__(self, parser):
        self.parser = parser

    def resolve(self, descriptor, principal, session):
        if descriptor.query_kind != 'jql':
            raise AccessError('SCOPE_UNVERIFIABLE')
        filters, visiting, parsed = {}, set(), {}

        def syntax(query):
            if query not in parsed:
                parsed[query] = self.parser.parse(query, seconds=session.remaining_seconds())
            result = parsed[query]
            if result.functions:
                raise AccessError('SCOPE_UNVERIFIABLE')
            return result

        def strict(query):
            result = session.get_json('/rest/api/2/search', {
                'jql': query, 'validateQuery': 'true', 'startAt': 0, 'maxResults': 0, 'fields': 'id',
            }, page_key=f'validate:{session.usage.requests + 1}').value
            warnings(result)
            if (type(result.get('total')) is not int or result['total'] < 0
                    or type(result.get('startAt')) is not int or result['startAt'] != 0
                    or result.get('issues') != []):
                raise AccessError('PROVIDER_QUERY_WARNING')

        def visit(key):
            identifier(key)
            if key in visiting:
                raise AccessError('SCOPE_UNVERIFIABLE')
            if key in filters:
                return
            if len(filters) + len(visiting) >= 128:
                raise AccessError('SCOPE_UNVERIFIABLE')
            visiting.add(key)
            result = session.get_json(f'/rest/api/2/filter/{key}', {},
                                      page_key=f'filter:{key}:{session.usage.requests + 1}').value
            query = result.get('jql')
            if result.get('id') != key or not isinstance(query, str):
                raise AccessError('SCOPE_UNVERIFIABLE')
            for dependency in syntax(query).filter_ids:
                visit(dependency)
            strict(query)
            filters[key] = query
            visiting.remove(key)

        for key in syntax(descriptor.query).filter_ids:
            visit(key)
        strict(descriptor.query)
        dependencies = tuple(SourceDependencyDefinition(key, query, hashlib.sha256(query.encode('utf-8')).hexdigest())
                             for key, query in sorted(filters.items()))
        return SourceResolutionInput(descriptor.definition_hash(), principal.provider_id, principal.endpoint_id,
                                     principal.principal_id, descriptor.query, dependencies,
                                     self.parser.resolver_version + ':devsummary-bean-identities-v1')

    def enumerate(self, descriptor, principal, session):
        result = read_pages(session, '/rest/api/2/search',
                            {'jql': descriptor.query, 'validateQuery': 'true', 'fields': LIGHT_FIELDS},
                            array_name='issues', maximum=session.context.limits.max_members,
                            validate=lambda row: row)
        values, keys, failure = [], set(), None
        try:
            for row in result.rows:
                value = marker(row, principal)
                if value.identity.display_key in keys:
                    raise AccessError('PROVIDER_DUPLICATE_ID')
                keys.add(value.identity.display_key)
                values.append(value)
        except AccessError as error:
            failure = error.code
        coverage = result.coverage
        if failure:
            coverage = replace(coverage, state='partial', source_version=None, observed_count=len(values), reason_code=failure)
        return MembershipObservation(tuple(values), coverage, result.raw_page_ids,
                                     descriptor.definition_hash(), session.usage)
