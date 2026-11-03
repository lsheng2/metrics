from datetime import UTC, datetime

from project_management.app.api.capture_archive import CaptureCoverage, PartCoverage, SnapshotInput
from provider_sync.app.api.access_contracts import AccessError, ItemObservation, ProviderPrincipal
from provider_sync.out.jira_consistency import consistent_responses
from provider_sync.out.jira_pages import identifier, read_pages, record_map
from provider_sync.out.jira_scope import JiraScopeResolver, marker
from provider_sync.out.jql import JqlParser
from provider_sync.services.capture_session import fingerprint


CORE_FIELDS = frozenset({
    'summary', 'description', 'status', 'resolution', 'assignee', 'reporter', 'priority',
    'created', 'updated', 'fixVersions', 'versions', 'labels', 'issuelinks',
})


def comment_record(row):
    identifier(row.get('id'))
    if ('body' not in row or not isinstance(row.get('created'), str)
            or not isinstance(row.get('updated'), str)):
        raise AccessError('PROVIDER_RECORD_INVALID')
    return row


def history_record(row):
    identifier(row.get('id'))
    if not isinstance(row.get('created'), str) or not isinstance(row.get('items'), list):
        raise AccessError('PROVIDER_RECORD_INVALID')
    return row


def missing_part(state='not_requested', reason=None):
    return PartCoverage(state, None, 0, None, reason)


def collection_part(rows, failure, *, total=None, complete=False, reason=None):
    if total is not None and (type(total) is not int or total < len(rows)):
        total = None
    return PartCoverage('complete' if complete and not failure else 'partial',
                        fingerprint(rows) if complete and not failure else None,
                        len(rows), total, failure or reason)


class JiraCaptureAdapter:
    def __init__(self, parser=None):
        self.parser = parser

    def verify(self, connection, session):
        if connection.info.endpoint.auth_mode != 'server_pat':
            raise AccessError('PART_CONTRACT_UNQUALIFIED')
        captured = session.get_json('/rest/api/2/myself', {}, page_key=f'identity:{session.usage.requests + 1}')
        key = captured.value.get('key')
        if not isinstance(key, str) or not key or len(key) > 256 or any(ord(c) < 32 for c in key):
            raise AccessError('PRINCIPAL_UNVERIFIED')
        return ProviderPrincipal('jira', connection.info.endpoint.endpoint_id, key, datetime.now(UTC),
                                 captured.raw_page_id)

    def resolve(self, descriptor, principal, session):
        return JiraScopeResolver(self.parser or JqlParser()).resolve(descriptor, principal, session)

    def enumerate(self, descriptor, principal, session):
        return JiraScopeResolver(self.parser).enumerate(descriptor, principal, session)

    def capture(self, source_marker, descriptor, principal, session):
        identity = source_marker.identity
        path = f'/rest/api/2/issue/{identifier(identity.stable_id)}'
        prior = len(session.page_ids)
        try:
            before = self._detail(path, identity, principal, session)
        except AccessError as error:
            state = 'access_lost' if error.code in {'PROVIDER_PERMISSION_DENIED', 'PROVIDER_AUTH_FAILED'} else 'partial'
            coverage = CaptureCoverage(missing_part(state, error.code), *(missing_part() for _ in range(4)))
            return ItemObservation(None, identity, source_marker, coverage, (error.code,), session.usage)
        facts = before['fields']
        comments = read_pages(session, path + '/comment', {}, array_name='comments',
                              maximum=session.context.limits.max_comments_per_item, validate=comment_record,
                              item=identity)
        histories, history_coverage = self._history(before.get('changelog'), session.context.limits)
        attachments, attachment_failure = record_map(facts.get('attachment'), session.context.limits.max_comments_per_item, lambda row: row)
        dependencies, dependency_failure = record_map(facts.get('issuelinks'), session.context.limits.max_members, lambda row: row)
        complete_facts = CORE_FIELDS.issubset(facts)
        coverage = CaptureCoverage(
            PartCoverage('complete' if complete_facts else 'partial', fingerprint(facts), 1, 1,
                         None if complete_facts else 'PROVIDER_FIELDS_PARTIAL'),
            comments.coverage, history_coverage,
            self._metadata_coverage(attachments, attachment_failure),
            self._metadata_coverage(dependencies, dependency_failure),
        )
        failures = [part.reason_code for part in (coverage.facts, coverage.comments, coverage.history)
                    if part.reason_code is not None]
        consistent = False
        try:
            after = self._detail(path, identity, principal, session)
            consistent = consistent_responses(before, after)
            if not consistent:
                failures.append('SOURCE_UNSTABLE')
        except AccessError as error:
            failures.append(error.code)
        snapshot = SnapshotInput(
            marker(before, principal).identity, facts, {row['id']: row for row in comments.rows},
            histories, attachments, dependencies, coverage, session.page_ids[prior:], consistent,
        )
        return ItemObservation(snapshot, snapshot.identity, source_marker, coverage, tuple(failures), session.usage)

    def _detail(self, path, identity, principal, session):
        value = session.get_json(path, {'fields': '*all', 'expand': 'changelog,names,schema'}, item=identity,
                                 page_key=f'detail:{identity.stable_id}:{session.usage.requests + 1}').value
        observed = marker(value, principal)
        if observed.identity.stable_id != identity.stable_id:
            raise AccessError('PROVIDER_RECORD_INVALID')
        return value

    def _history(self, value, limits):
        if not isinstance(value, dict):
            return {}, PartCoverage('partial', None, 0, None, 'PROVIDER_HISTORY_PARTIAL')
        rows, failure = record_map(value.get('histories'), limits.max_history_per_item, history_record)
        total = value.get('total')
        complete = (failure is None and type(value.get('startAt')) is int and value['startAt'] == 0
                    and type(total) is int and total == len(rows))
        return rows, collection_part(rows, failure, total=total, complete=complete,
                                     reason=None if complete else 'PROVIDER_HISTORY_PARTIAL')

    def _metadata_coverage(self, rows, failure):
        if not rows and failure is None:
            return PartCoverage('not_requested', None, 0, 0, 'BODY_NOT_REQUESTED')
        return collection_part(rows, failure, total=len(rows) if not failure else None,
                               reason='BODY_NOT_REQUESTED')
