from dataclasses import asdict
import re
from urllib.parse import urlsplit
from uuid import UUID

from .contracts import ProjectActor, ProjectError, ScopeDescriptor, ScopeSelection


KEY = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}')
PROFILE_KEY = re.compile(r'[a-z0-9][a-z0-9._-]{0,159}')


def bounded_text(value, maximum, code, allow_newlines=False):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ProjectError(code)
    if any(ord(char) < 32 and not (allow_newlines and char in '\r\n\t') for char in value):
        raise ProjectError(code)
    return value


def validate_actor(actor):
    if not isinstance(actor, ProjectActor):
        raise ProjectError('INVALID_PROJECT')
    bounded_text(actor.subject, 160, 'INVALID_PROJECT')
    if actor.subject != actor.subject.strip():
        raise ProjectError('INVALID_PROJECT')


def validate_key_name(key, name):
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ProjectError('INVALID_PROJECT')
    return bounded_text(name, 160, 'INVALID_PROJECT').strip()


def project_uuid(value):
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ProjectError('PROJECT_NOT_FOUND') from None


def validate_selection(selection):
    if not isinstance(selection, ScopeSelection):
        raise ProjectError('INVALID_SELECTION')
    if not isinstance(selection.profile_id, str) or not PROFILE_KEY.fullmatch(selection.profile_id):
        raise ProjectError('INVALID_SELECTION')
    if selection.scope_id is not None and (type(selection.scope_id) is not int or selection.scope_id <= 0):
        raise ProjectError('INVALID_SELECTION')


def validate_endpoint(endpoint):
    bounded_text(endpoint, 2048, 'SOURCE_UNAVAILABLE')
    try:
        parts = urlsplit(endpoint)
        port = parts.port
        invalid = (
            parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment
            or any(char.isspace() for char in endpoint) or '\\' in endpoint
        )
        if invalid or port == 0:
            raise ValueError
    except (ValueError, TypeError):
        raise ProjectError('SOURCE_UNAVAILABLE') from None


def validate_descriptor(descriptor, selection):
    if not isinstance(descriptor, ScopeDescriptor):
        raise ProjectError('SOURCE_UNAVAILABLE')
    if descriptor.profile_id != selection.profile_id:
        raise ProjectError('SOURCE_UNAVAILABLE')
    for key, value in asdict(descriptor).items():
        bounded_text(value, 16384 if key == 'query' else 2048, 'SOURCE_UNAVAILABLE', key == 'query')
    validate_endpoint(descriptor.endpoint)
    if descriptor.provider_id == 'jira':
        valid = selection.scope_id is not None and descriptor.query_kind == 'jql'
    elif descriptor.provider_id == 'hsdes':
        valid = selection.scope_id is None and descriptor.query_kind == 'saved_query'
    else:
        valid = False
    if not valid:
        raise ProjectError('INVALID_SELECTION')
