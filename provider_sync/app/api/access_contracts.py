from dataclasses import dataclass, fields
from datetime import datetime
from typing import Mapping
from uuid import UUID

from project_management.app.api import ProjectActor, ScopeDescriptor
from project_management.app.api.capture_archive import (
    CaptureCoverage, PartCoverage, SnapshotInput, WorkItemIdentity,
)


ERROR_MESSAGES = {
    'INVALID_ARGUMENTS': 'Provider access arguments are invalid.',
    'CAPABILITY_UNAVAILABLE': 'This provider access capability is unavailable.',
    'PART_CONTRACT_UNQUALIFIED': 'The provider response contract is not qualified.',
    'CAPTURE_DEADLINE_EXPIRED': 'The original capture deadline has expired.',
    'CAPTURE_REQUEST_LIMIT': 'The capture request limit has been reached.',
    'CAPTURE_DOWNLOAD_LIMIT': 'The capture download limit has been reached.',
    'CAPTURE_RESPONSE_LIMIT': 'The provider response exceeded its byte limit.',
    'CAPTURE_SINK_CONFLICT': 'The archive sink does not match this capture.',
    'CAPTURE_CLOSED': 'This capture connection is closed.',
    'CAPTURE_PAGE_CONFLICT': 'This capture page key has already been used.',
    'PROVIDER_RESPONSE_INVALID': 'The provider response is invalid.',
    'PROVIDER_AUTH_FAILED': 'Provider authentication failed.',
    'PROVIDER_PERMISSION_DENIED': 'Provider permission was denied.',
    'PROVIDER_RATE_LIMITED': 'The provider refused this request due to its rate limit.',
    'PROVIDER_NETWORK_ERROR': 'The provider request failed.',
    'PROVIDER_PROFILE_UNAVAILABLE': 'The selected provider profile is unavailable.',
    'PROVIDER_UNSUPPORTED': 'The selected provider connection is unsupported.',
    'PROVIDER_TRUST_INVALID': 'The provider TLS trust configuration is invalid.',
    'PROVIDER_ENDPOINT_CREDENTIAL_MISMATCH': 'The provider endpoint and credential source do not match.',
    'PROVIDER_CREDENTIAL_UNAVAILABLE': 'The selected provider credential is unavailable.',
    'PROVIDER_CREDENTIAL_INVALID': 'The selected provider credential is invalid.',
    'PROVIDER_CREDENTIAL_UNPROTECTED': 'The selected provider credential is not protected.',
    'PROVIDER_CREDENTIAL_PLATFORM_UNSUPPORTED': 'Protected credentials are unavailable on this platform.',
    'PROVIDER_CREDENTIAL_CONFLICT': 'The selected provider credentials conflict.',
    'PROVIDER_CREDENTIAL_CAS_MISMATCH': 'The selected provider credential preview is stale.',
    'PROVIDER_BUSY': 'The provider credential store is busy.',
    'PROVIDER_METHOD_FORBIDDEN': 'The provider request method is forbidden.',
    'PROVIDER_ENDPOINT_INVALID': 'The provider endpoint does not match the selected source.',
    'PROVIDER_REDIRECT_UNSUPPORTED': 'Provider redirects are not supported.',
    'PROVIDER_HTTP_ERROR': 'The provider returned an unsuccessful response.',
    'PRINCIPAL_UNVERIFIED': 'The provider identity could not be verified.',
    'PRINCIPAL_CHANGED': 'The provider identity changed during capture.',
    'SCOPE_UNVERIFIABLE': 'The source rule could not be verified.',
    'SOURCE_CHANGED': 'The source definition changed.',
    'SOURCE_UNSTABLE': 'Source observations changed during capture.',
    'PROVIDER_PAGE_INVALID': 'Provider pagination is invalid or incomplete.',
    'PROVIDER_RECORD_INVALID': 'A provider record is invalid.',
    'PROVIDER_RECORD_LIMIT': 'The provider record limit has been reached.',
    'PROVIDER_DUPLICATE_ID': 'The provider returned duplicate record identities.',
    'PROVIDER_QUERY_WARNING': 'The provider could not strictly validate the source query.',
    'PROVIDER_HISTORY_PARTIAL': 'The provider did not return complete field history.',
    'PROVIDER_FIELDS_PARTIAL': 'The provider did not return the required fact fields.',
    'CAPTURE_DETAILS_PENDING': 'Some scoped work items still require detail capture.',
    'CAPTURE_CANCELED': 'The capture was canceled.',
}


class AccessError(Exception):
    def __init__(self, code):
        self.code = code if code in ERROR_MESSAGES else 'PROVIDER_NETWORK_ERROR'
        self.message = ERROR_MESSAGES[self.code]
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class CaptureLimits:
    max_requests: int = 256
    max_download_bytes: int = 268435456
    max_response_bytes: int = 16777216
    max_members: int = 500
    max_details: int = 100
    max_comments_per_item: int = 10000
    max_history_per_item: int = 20000
    page_size: int = 100

    def __post_init__(self):
        if any(type(getattr(self, f.name)) is not int or getattr(self, f.name) <= 0 for f in fields(self)):
            raise AccessError('INVALID_ARGUMENTS')


@dataclass(frozen=True, slots=True)
class ProviderRequestContext:
    actor: ProjectActor
    project_id: str
    request_id: str
    deadline_at: datetime
    limits: CaptureLimits


@dataclass(frozen=True, slots=True)
class AccessContext:
    actor: ProjectActor
    project_id: str
    stage_id: str
    capture_id: str
    request_id: str
    deadline_at: datetime
    limits: CaptureLimits


def validate_context(context):
    if not isinstance(context, AccessContext):
        raise AccessError('INVALID_ARGUMENTS')
    _validate_context_fields(context, ('project_id', 'stage_id', 'capture_id', 'request_id'))


def validate_request_context(context):
    if not isinstance(context, ProviderRequestContext):
        raise AccessError('INVALID_ARGUMENTS')
    _validate_context_fields(context, ('project_id', 'request_id'))


def _validate_context_fields(context, names):
    if not isinstance(context.limits, CaptureLimits):
        raise AccessError('INVALID_ARGUMENTS')
    for name in names:
        value = getattr(context, name)
        try:
            valid = type(value) is str and str(UUID(value)) == value
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise AccessError('INVALID_ARGUMENTS')
    date = context.deadline_at
    if not isinstance(date, datetime) or date.tzinfo is None or date.utcoffset() is None:
        raise AccessError('INVALID_ARGUMENTS')
    if not isinstance(context.actor, ProjectActor):
        raise AccessError('INVALID_ARGUMENTS')
    subject = context.actor.subject
    if (not isinstance(subject, str) or not subject or len(subject) > 160
            or subject != subject.strip() or any(ord(char) < 32 for char in subject)):
        raise AccessError('INVALID_ARGUMENTS')


@dataclass(frozen=True, slots=True)
class RequestUsage:
    requests: int
    downloaded_bytes: int


@dataclass(frozen=True, slots=True)
class ProviderPrincipal:
    provider_id: str
    endpoint_id: str
    principal_id: str
    verified_at: datetime
    evidence_page_id: str | None


@dataclass(frozen=True, slots=True)
class WorkItemMarker:
    identity: WorkItemIdentity
    updated: str
    fields_hash: str
    fields: Mapping


@dataclass(frozen=True, slots=True)
class MembershipObservation:
    members: tuple[WorkItemMarker, ...]
    coverage: PartCoverage
    raw_page_ids: tuple[str, ...]
    definition_hash: str
    usage: RequestUsage


@dataclass(frozen=True, slots=True)
class ItemObservation:
    snapshot: SnapshotInput | None
    identity: WorkItemIdentity
    marker: WorkItemMarker
    coverage: CaptureCoverage
    failures: tuple[str, ...]
    usage: RequestUsage


@dataclass(frozen=True, slots=True)
class AccessStatus:
    profile_id: str
    provider_id: str
    readiness: str
    principal_verified: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PublicProfile:
    profile_id: str
    provider_id: str
    display_name: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class FrozenScopeStatus:
    project_id: str
    stage_id: str
    definition_hash: str
    source_status: str
    descriptor: ScopeDescriptor
    first_resolution_hash: str | None = None
    first_principal_id: str | None = None
