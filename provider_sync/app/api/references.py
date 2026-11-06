from datetime import UTC, datetime
from dataclasses import dataclass

from bug_metrics.app.api.provider_connections import ConnectionError, create_provider_connection_resolver, source_endpoint_matches
from provider_sync.app.api.access_contracts import AccessError, CaptureLimits, ProviderRequestContext
from provider_sync.out.capture_reader import BoundCaptureReader
from provider_sync.services.capture_session import ProviderReadSession


ADAPTER_REVISION = 'jira-reference/1'


@dataclass(frozen=True, slots=True)
class ProviderReferenceIdentity:
    provider_id: str
    endpoint_id: str
    stable_id: str
    display_key: str


@dataclass(frozen=True, slots=True)
class ProviderReferenceObservation:
    identity: ProviderReferenceIdentity
    requested_key: str
    current_key: str
    canonical_url: str
    title: str | None
    assignee: dict | None
    assignee_state: str
    observed_at: str
    source_updated_at: str | None
    lookup_kind: str
    scope_snapshot_hash: str


class DisabledProviderReferenceReader:
    def supports(self, stage, principal_id):
        return False

    def read(self, context, member):
        raise AccessError('CAPABILITY_UNAVAILABLE')


class JiraProviderReferenceReader:
    def __init__(self, resolver, qualifications, *, clock=None, reader_factory=BoundCaptureReader):
        self.resolver = resolver
        self.qualifications = tuple(qualifications)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.reader_factory = reader_factory

    def supports(self, stage, principal_id):
        return self._qualification(stage, principal_id) is not None

    def read(self, context, member):
        stage = context['frozen_descriptor']
        qualification = self._qualification_object(stage, context['principal_id'])
        try:
            info = self.resolver.describe_profile(stage.profile_id, expected_provider_id='jira')
            if not source_endpoint_matches(info, stage.endpoint):
                raise AccessError('PROVIDER_ENDPOINT_INVALID')
            connection = self.resolver.resolve_profile(stage.profile_id, expected_provider_id='jira')
            if connection.info.endpoint != info.endpoint:
                raise AccessError('PROVIDER_ENDPOINT_INVALID')
        except ConnectionError as error:
            raise AccessError(error.code) from None
        reader = connection.open_capture_reader(self.reader_factory)
        session = ProviderReadSession(
            ProviderRequestContext(
                context['actor_object'],
                context['project_id'],
                context['request_id'],
                context['deadline_at'],
                CaptureLimits(max_requests=5, max_download_bytes=1048576, max_response_bytes=262144),
            ),
            reader,
            timeout_seconds=info.endpoint.timeout_seconds,
            clock=self.clock,
        )
        try:
            principal = session.get_json('/rest/api/2/myself', {}, page_key='identity').value.get('key')
            if principal != context['principal_id']:
                raise AccessError('PRINCIPAL_CHANGED')
            item = session.get_json(
                f'/rest/api/2/issue/{member.stable_id}',
                {'fields': 'summary,assignee,updated'},
                item=member,
                page_key='reference-item',
            ).value
        finally:
            session.close()
        return _jira_observation(stage, member, item, context['membership_proof_hash'])

    def _qualification(self, stage, principal_id):
        try:
            return self._qualification_object(stage.descriptor, principal_id)
        except AccessError:
            return None

    def _qualification_object(self, descriptor, principal_id):
        try:
            info = self.resolver.describe_profile(descriptor.profile_id, expected_provider_id='jira')
        except ConnectionError as error:
            raise AccessError(error.code) from None
        for row in self.qualifications:
            if _matches(row, descriptor, info, principal_id):
                return row
        raise AccessError('PART_CONTRACT_UNQUALIFIED')


def create_provider_reference_reader(settings_source=None, *, reader=None, resolver=None):
    if reader is not None:
        return reader
    if settings_source is None:
        from django.conf import settings

        settings_source = settings
    enabled = bool(getattr(settings_source, 'METRICS_REPORT_COMPLETION_ENABLED', False))
    qualifications = tuple(getattr(settings_source, 'METRICS_REPORT_REFERENCE_QUALIFICATIONS', ()))
    if not enabled or not qualifications:
        return DisabledProviderReferenceReader()
    resolver = resolver or create_provider_connection_resolver(settings_source=settings_source)
    return JiraProviderReferenceReader(resolver, qualifications)


def _matches(row, descriptor, info, principal_id):
    if not isinstance(row, dict):
        return False
    return (
        row.get('profile_id') == descriptor.profile_id
        and row.get('provider_id') == 'jira'
        and row.get('endpoint_id') == info.endpoint.endpoint_id
        and row.get('auth_mode') == info.endpoint.auth_mode
        and row.get('principal_id') == principal_id
        and row.get('adapter_revision') == ADAPTER_REVISION
        and isinstance(row.get('qualification_ref'), str)
        and row.get('qualification_ref')
    )


def _jira_observation(stage, member, item, proof_hash):
    if not isinstance(item, dict) or not isinstance(item.get('fields'), dict):
        raise AccessError('PROVIDER_RESPONSE_INVALID')
    key = item.get('key')
    stable_id = item.get('id')
    fields = item['fields']
    if not isinstance(key, str) or not isinstance(stable_id, str):
        raise AccessError('PROVIDER_RESPONSE_INVALID')
    if stable_id != member.stable_id:
        raise AccessError('PROVIDER_RESPONSE_INVALID')
    if not isinstance(key, str) or any(ord(c) < 32 for c in key):
        raise AccessError('PROVIDER_RESPONSE_INVALID')
    if 'assignee' in fields:
        assignee = fields['assignee']
    else:
        assignee = 'missing'
    owner = None
    state = 'unknown' if assignee == 'missing' else 'unassigned'
    if isinstance(assignee, dict):
        display = assignee.get('displayName') or assignee.get('name') or assignee.get('key')
        owner_id = assignee.get('key') or assignee.get('accountId') or assignee.get('name')
        if isinstance(display, str) and isinstance(owner_id, str):
            owner = {'id': owner_id, 'display_name': display}
            state = 'assigned'
        else:
            state = 'unknown'
    elif assignee is not None:
        state = 'unknown'
    title = fields.get('summary')
    updated = fields.get('updated')
    if title is not None and (not isinstance(title, str) or any(ord(c) < 32 for c in title)):
        raise AccessError('PROVIDER_RESPONSE_INVALID')
    if updated is not None and (not isinstance(updated, str) or any(ord(c) < 32 for c in updated) or not _valid_time(updated)):
        raise AccessError('PROVIDER_RESPONSE_INVALID')
    return ProviderReferenceObservation(
        ProviderReferenceIdentity(member.provider_id, member.endpoint_id, stable_id, key),
        member.display_key,
        key,
        stage.endpoint.rstrip('/') + '/browse/' + key,
        title,
        owner,
        state,
        datetime.now(UTC).isoformat(),
        updated,
        'live',
        proof_hash,
    )


def _valid_time(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None
