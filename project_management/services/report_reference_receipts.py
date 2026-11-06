from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Mapping
from uuid import UUID, uuid4

from django.core import signing

from project_management.app.domain.report_authoring_fragments import rich_text_fragment_plain_text
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import canonical_hash


SALT = 'project-reporting.reference/1'
EXPIRY_SECONDS = 300
ENVELOPE_KEYS = {
    'schema_version', 'reference_id', 'option_id', 'variant_fragment_hash',
    'actor_subject', 'project_id', 'stage_id', 'draft_id', 'target_hash',
    'snapshot_hash', 'rule_hash', 'principal_id', 'membership_proof_hash',
    'observation', 'issued_at', 'expires_at',
}


@dataclass(frozen=True, slots=True)
class SignedReferenceOption:
    reference_id: str
    option_id: str
    fragment: Mapping
    receipt: str


class ReferenceReceiptVerifier:
    def __init__(self, secret: str, *, clock=None):
        self.secret = secret
        self.clock = clock or (lambda: datetime.now(UTC))

    def issue_option(self, actor, project_id, stage_id, draft, target, option_id, observation,
                     *, membership_proof_hash, principal_id):
        reference_id = str(uuid4())
        observed = _observation_mapping(observation)
        if observed.get('scope_snapshot_hash') != membership_proof_hash:
            raise ReportError('REFERENCE_INVALID')
        fragment = _option_fragment(reference_id, option_id, observed)
        issued_at = self.clock().astimezone(UTC)
        envelope = {
            'schema_version': 1,
            'reference_id': reference_id,
            'option_id': option_id,
            'variant_fragment_hash': canonical_hash(fragment),
            'actor_subject': actor.subject,
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': draft.draft_id,
            'target_hash': canonical_hash(target),
            'snapshot_hash': draft.snapshot_hash,
            'rule_hash': draft.snapshot.rule_hash,
            'principal_id': principal_id,
            'membership_proof_hash': membership_proof_hash,
            'observation': observed,
            'issued_at': issued_at.isoformat(),
            'expires_at': (issued_at + timedelta(seconds=EXPIRY_SECONDS)).isoformat(),
        }
        return SignedReferenceOption(
            reference_id,
            option_id,
            fragment,
            signing.dumps(envelope, key=self.secret, salt=SALT, compress=False),
        )

    def verify_requests(self, actor_subject, project_id, stage_id, draft, requests, current_edits, membership, now=None,
                        historical_resolver=None):
        now = (now or self.clock()).astimezone(UTC)
        previous = self._previous_observations(current_edits)
        seen = set()
        verified = {}
        for request in requests:
            records = []
            links = tuple(_reference_links(request.fragment))
            for reference_id, href, key_text in links:
                if reference_id in seen:
                    raise ReportError('REFERENCE_INVALID')
                seen.add(reference_id)
                target_hash = canonical_hash(request.target)
                old = previous.get((target_hash, reference_id))
                if old is not None:
                    self._validate_record(old, membership, historical_resolver)
                    self._validate_link(old['observation'], href, key_text)
                    records.append(old)
                    continue
                envelope = self._receipt_for(reference_id, request.reference_receipts, now)
                self._validate_envelope(envelope, actor_subject, project_id, stage_id, draft, target_hash, membership)
                self._validate_link(envelope['observation'], href, key_text)
                records.append({
                    'reference_id': reference_id,
                    'option_id': envelope['option_id'],
                    'issued_fragment_hash': envelope['variant_fragment_hash'],
                    'content_basis': 'human_composed',
                    'observation': envelope['observation'],
                })
            verified[request.edit_id] = tuple(records)
        return verified

    def _receipt_for(self, reference_id, receipts, now):
        expired = False
        for receipt in tuple(receipts or ()):
            try:
                envelope = signing.loads(receipt, key=self.secret, salt=SALT)
            except signing.BadSignature:
                continue
            if _envelope_reference_id(envelope) != reference_id:
                continue
            if _time(envelope['expires_at']) < now:
                expired = True
                continue
            return envelope
        raise ReportError('REFERENCE_RECEIPT_EXPIRED' if expired else 'REFERENCE_INVALID')

    def _validate_envelope(self, envelope, actor_subject, project_id, stage_id, draft, target_hash, membership):
        if set(envelope) != ENVELOPE_KEYS or envelope.get('schema_version') != 1:
            raise ReportError('REFERENCE_INVALID')
        expected = {
            'actor_subject': actor_subject,
            'project_id': project_id,
            'stage_id': stage_id,
            'draft_id': draft.draft_id,
            'target_hash': target_hash,
            'snapshot_hash': draft.snapshot_hash,
            'rule_hash': membership.rule_hash,
            'principal_id': membership.principal_id,
            'membership_proof_hash': membership.proof_hash,
        }
        if any(envelope.get(key) != value for key, value in expected.items()):
            raise ReportError('REFERENCE_INVALID')
        _uuid(envelope['reference_id'])
        _hash(envelope['variant_fragment_hash'])
        self._validate_observation(envelope.get('observation'), membership)

    def _validate_record(self, record, membership, historical_resolver=None):
        if isinstance(record, Mapping) and record.get('schema_version') == 2:
            return self._validate_historical_record(record, historical_resolver)
        if not isinstance(record, Mapping) or set(record) != {
            'reference_id', 'option_id', 'issued_fragment_hash', 'content_basis', 'observation',
        }:
            raise ReportError('REFERENCE_INVALID')
        _uuid(record['reference_id'])
        _hash(record['issued_fragment_hash'])
        if record['option_id'] not in {'id', 'id_title', 'id_title_owner'} or record['content_basis'] != 'human_composed':
            raise ReportError('REFERENCE_INVALID')
        self._validate_observation(record.get('observation'), membership)

    def _validate_historical_record(self, record, historical_resolver):
        expected = {
            'schema_version', 'reference_id', 'option_id', 'issued_fragment_hash', 'content_basis',
            'observation', 'historical_association',
        }
        if not isinstance(record, Mapping) or set(record) != expected or record['schema_version'] != 2:
            raise ReportError('REFERENCE_INVALID')
        legacy = {key: record[key] for key in (
            'reference_id', 'option_id', 'issued_fragment_hash', 'content_basis', 'observation',
        )}
        _uuid(legacy['reference_id'])
        _hash(legacy['issued_fragment_hash'])
        if legacy['option_id'] not in {'id', 'id_title', 'id_title_owner'} or legacy['content_basis'] != 'human_composed':
            raise ReportError('REFERENCE_INVALID')
        self._validate_historical_observation(legacy['observation'])
        association = record['historical_association']
        if not isinstance(association, Mapping):
            raise ReportError('REFERENCE_INVALID')
        self._validate_association_shape(association)
        if (association['schema_version'] != 1
                or association['reference_id'] != legacy['reference_id']
                or association['record_hash'] != canonical_hash(legacy)):
            raise ReportError('REFERENCE_INVALID')
        if historical_resolver is None or not historical_resolver(record):
            raise ReportError('REFERENCE_INVALID')

    def _validate_association_shape(self, association):
        common = {'schema_version', 'kind', 'target_hash', 'reference_id', 'record_hash'}
        if association.get('kind') == 'parent_draft_revision':
            if set(association) != common | {'parent_draft_id', 'parent_draft_revision', 'parent_draft_revision_hash'}:
                raise ReportError('REFERENCE_INVALID')
            _uuid(association['parent_draft_id'])
            if type(association['parent_draft_revision']) is not int or association['parent_draft_revision'] < 1:
                raise ReportError('REFERENCE_INVALID')
            _hash(association['parent_draft_revision_hash'])
        elif association.get('kind') == 'source_publication':
            if set(association) != common | {'publication_id', 'manifest_hash', 'commit'}:
                raise ReportError('REFERENCE_INVALID')
            _uuid(association['publication_id'])
            _hash(association['manifest_hash'])
            _commit(association['commit'])
        else:
            raise ReportError('REFERENCE_INVALID')
        _hash(association['target_hash'])
        _uuid(association['reference_id'])
        _hash(association['record_hash'])

    def _validate_historical_observation(self, observation):
        if not isinstance(observation, Mapping):
            raise ReportError('REFERENCE_INVALID')
        identity = observation.get('identity')
        if not isinstance(identity, Mapping):
            raise ReportError('REFERENCE_INVALID')
        if not all(isinstance(identity.get(key), str) for key in ('provider_id', 'endpoint_id', 'stable_id')):
            raise ReportError('REFERENCE_INVALID')
        if not all(isinstance(observation.get(key), str) for key in (
                'requested_key', 'current_key', 'canonical_url', 'observed_at', 'lookup_kind', 'scope_snapshot_hash')):
            raise ReportError('REFERENCE_INVALID')
        _hash(observation['scope_snapshot_hash'])

    def _validate_observation(self, observation, membership):
        if not isinstance(observation, Mapping):
            raise ReportError('REFERENCE_INVALID')
        if observation.get('scope_snapshot_hash') != membership.proof_hash:
            raise ReportError('REFERENCE_INVALID')
        identity = observation.get('identity')
        if not isinstance(identity, Mapping):
            raise ReportError('REFERENCE_INVALID')
        if (identity.get('provider_id'), identity.get('endpoint_id'), identity.get('stable_id')) not in {
            (member.identity.provider_id, member.identity.endpoint_id, member.identity.stable_id)
            for member in membership.members
        }:
            raise ReportError('REFERENCE_INVALID')
        if not all(isinstance(observation.get(key), str) for key in (
                'requested_key', 'current_key', 'canonical_url', 'observed_at', 'lookup_kind', 'scope_snapshot_hash')):
            raise ReportError('REFERENCE_INVALID')

    def _validate_link(self, observation, href, key_text):
        if observation.get('canonical_url') != href or observation.get('current_key') != key_text:
            raise ReportError('REFERENCE_CONTENT_CHANGED')

    def _previous_observations(self, current_edits):
        result = {}
        for edit in tuple(current_edits or ()):
            target_hash = canonical_hash(edit.target)
            for record in tuple(edit.reference_observations or ()):
                if isinstance(record, Mapping) and isinstance(record.get('reference_id'), str):
                    result[(target_hash, record['reference_id'])] = record
        return result


def _option_fragment(reference_id, option_id, observation):
    content = [_link(observation, reference_id)]
    if option_id in {'id_title', 'id_title_owner'} and observation.get('title'):
        content.append(_text(' ' + observation['title']))
    if option_id == 'id_title_owner' and observation.get('assignee_state') == 'assigned':
        assignee = observation.get('assignee') or {}
        display = assignee.get('display_name') if isinstance(assignee, Mapping) else None
        if display:
            content.append(_text(' @' + display))
    return {'schema_version': 2, 'blocks': ({'type': 'paragraph', 'content': tuple(content)},)}


def _link(observation, reference_id):
    return {
        'type': 'link',
        'href': observation['canonical_url'],
        'reference_id': reference_id,
        'content': (_text(observation['current_key']),),
    }


def _text(value):
    return {'type': 'text', 'text': value, 'marks': (), 'foreground': None, 'background': None}


def _reference_links(fragment):
    for inline in _inlines(fragment):
        if inline.get('type') == 'link' and 'reference_id' in inline:
            yield inline['reference_id'], inline['href'], rich_text_fragment_plain_text({
                'schema_version': 2,
                'blocks': ({'type': 'paragraph', 'content': inline['content']},),
            })


def _inlines(value):
    if isinstance(value, Mapping):
        if value.get('type') in {'paragraph', 'heading'}:
            yield from value.get('content', ())
            return
        elif value.get('type') == 'link':
            yield value
            return
        for child in value.values():
            yield from _inlines(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from _inlines(child)


def _observation_mapping(value):
    return asdict(value) if hasattr(value, '__dataclass_fields__') else dict(value)


def _envelope_reference_id(envelope):
    if set(envelope) != ENVELOPE_KEYS:
        raise ReportError('REFERENCE_INVALID')
    return _uuid(envelope['reference_id'])


def _uuid(value):
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise ReportError('REFERENCE_INVALID') from None
    if str(parsed) != value:
        raise ReportError('REFERENCE_INVALID')
    return value


def _hash(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ReportError('REFERENCE_INVALID')
    return value


def _commit(value):
    if type(value) is not str or len(value) != 40 or any(c not in '0123456789abcdef' for c in value):
        raise ReportError('REFERENCE_INVALID')
    return value


def _time(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ReportError('REFERENCE_INVALID') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReportError('REFERENCE_INVALID')
    return parsed.astimezone(UTC)
