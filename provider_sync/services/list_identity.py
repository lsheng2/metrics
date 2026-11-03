from dataclasses import dataclass
from datetime import UTC, datetime
import re

from bug_metrics.app.api.provider_connections import ConnectionError, source_endpoint_matches
from project_management.app.api import ProjectError
from project_management.app.api.capture_archive import WorkItemIdentity
from provider_sync.app.api.access_contracts import (
    AccessError, ProviderPrincipal, RequestUsage, validate_request_context,
)
from provider_sync.out.capture_reader import BoundCaptureReader
from provider_sync.out.jira_capture import JiraCaptureAdapter
from provider_sync.out.jira_pages import identifier, issue_key
from provider_sync.out.jira_scope import marker
from provider_sync.services.capture_session import ProviderReadSession


@dataclass(frozen=True, slots=True)
class IdentifierBinding:
    requested: str
    identity: WorkItemIdentity
    updated: str


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    profile_id: str
    provider_id: str
    endpoint_id: str
    principal: ProviderPrincipal
    bindings: tuple[IdentifierBinding, ...]
    usage: RequestUsage


class ResolutionFailure(AccessError):
    def __init__(self, code, usage, failed_index=None):
        super().__init__(code)
        self.usage = usage
        self.failed_index = failed_index


class ProviderListIdentityResolver:
    def __init__(self, project_api, registry_loader, resolver_factory, *,
                 reader_factory=BoundCaptureReader, clock=None):
        self.project_api = project_api
        self.registry_loader = registry_loader
        self.resolver_factory = resolver_factory
        self.reader_factory = reader_factory
        self.clock = clock or (lambda: datetime.now(UTC))

    def resolve(self, context, *, profile_id, provider_id, expected_endpoint_url, identifiers, online=False):
        self._admit(context, profile_id, provider_id, identifiers, online)
        self._project(context)
        reader, session, failed_index = None, None, None
        try:
            info, resolver = self._describe(profile_id, provider_id)
            if not source_endpoint_matches(info, expected_endpoint_url):
                raise AccessError('PROVIDER_ENDPOINT_INVALID')
            if info.endpoint.auth_mode != 'server_pat':
                raise AccessError('PART_CONTRACT_UNQUALIFIED')
            connection = resolver.resolve_profile(profile_id, expected_provider_id=provider_id)
            self._same_connection(info, connection.info)
            reader = connection.open_capture_reader(self.reader_factory)
            session = ProviderReadSession(
                context, reader, timeout_seconds=info.endpoint.timeout_seconds, clock=self.clock,
                authorize=lambda: self._authorize(context, profile_id, provider_id, info),
            )
            adapter = JiraCaptureAdapter()
            principal = adapter.verify(connection, session)
            bindings, seen = [], set()
            for failed_index, token in enumerate(identifiers):
                captured = session.get_json(
                    f'/rest/api/2/issue/{token}', {'fields': 'id,key,updated'},
                    page_key=f'list-item:{failed_index}',
                )
                observed = marker(captured.value, principal)
                if token.isdecimal() and observed.identity.stable_id != token:
                    raise AccessError('PROVIDER_RECORD_INVALID')
                if len(observed.identity.display_key) > 256:
                    raise AccessError('PROVIDER_RECORD_INVALID')
                if observed.identity.stable_id in seen:
                    raise AccessError('PROVIDER_DUPLICATE_ID')
                seen.add(observed.identity.stable_id)
                bindings.append(IdentifierBinding(token, observed.identity, observed.updated))
            failed_index = None
            final_principal = adapter.verify(connection, session)
            if final_principal.principal_id != principal.principal_id:
                raise AccessError('PRINCIPAL_CHANGED')
            self._authorize(context, profile_id, provider_id, info)
            session.remaining_seconds()
            return IdentityResolution(profile_id, provider_id, info.endpoint.endpoint_id,
                                      final_principal, tuple(bindings), session.usage)
        except (AccessError, ConnectionError) as error:
            usage = session.usage if session is not None else RequestUsage(0, 0)
            raise ResolutionFailure(error.code, usage, failed_index) from None
        finally:
            if session is not None:
                session.close()
            elif reader is not None:
                reader.close()

    def _admit(self, context, profile_id, provider_id, identifiers, online):
        if online is not True:
            raise AccessError('CAPABILITY_UNAVAILABLE')
        validate_request_context(context)
        if provider_id != 'jira':
            raise AccessError('PART_CONTRACT_UNQUALIFIED')
        if (not isinstance(profile_id, str) or not re.fullmatch('[a-z0-9][a-z0-9._-]{0,159}', profile_id)
                or not isinstance(identifiers, tuple) or not 0 < len(identifiers) <= context.limits.max_members):
            raise AccessError('INVALID_ARGUMENTS')
        seen = set()
        for token in identifiers:
            if not isinstance(token, str) or not 0 < len(token) <= 256 or token in seen:
                raise AccessError('INVALID_ARGUMENTS')
            try:
                identifier(token) if token.isdecimal() else issue_key(token)
            except AccessError:
                raise AccessError('INVALID_ARGUMENTS') from None
            seen.add(token)
        if context.deadline_at <= self.clock():
            raise AccessError('CAPTURE_DEADLINE_EXPIRED')

    def _project(self, context):
        detail = self.project_api.get_project(context.actor, context.project_id)
        if detail.project.archived:
            raise ProjectError('PROJECT_ARCHIVED')

    def _describe(self, profile_id, provider_id):
        registry = self.registry_loader()
        profile = registry.resolve_profile(profile_id).profile
        if profile is None or profile.provider_id != provider_id:
            raise AccessError('SOURCE_CHANGED')
        resolver = self.resolver_factory(registry)
        return resolver.describe_profile(profile_id, expected_provider_id=provider_id), resolver

    def _authorize(self, context, profile_id, provider_id, expected):
        self._project(context)
        try:
            observed, _ = self._describe(profile_id, provider_id)
        except ConnectionError:
            raise AccessError('SOURCE_CHANGED') from None
        self._same_connection(expected, observed)

    def _same_connection(self, expected, observed):
        if (expected.profile_id != observed.profile_id or expected.endpoint != observed.endpoint
                or expected.credential != observed.credential):
            raise AccessError('SOURCE_CHANGED')
