from contextlib import contextmanager
from datetime import datetime

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_time_text, validate_uuid_text
from project_management.app.domain.report_recovery import REQUEST_KEYS, validate_recovery_request
from project_management.storage.report_recovery import ReportRecoveryStore, expired


class ReportRecoveryService:
    def __init__(self, draft_service):
        self.drafts = draft_service

    def list(self, actor, project_id, stage_id, draft_id):
        with self._store(actor, project_id, stage_id, draft_id) as (drafts, store):
            current = drafts.read_draft(draft_id)
            return tuple(self._response(self._owned(item, actor, project_id, stage_id, draft_id), current, content=False)
                         for item in store.items())

    def get(self, actor, project_id, stage_id, draft_id, client_id):
        validate_uuid_text(client_id)
        with self._store(actor, project_id, stage_id, draft_id) as (drafts, store):
            payload = store.read(client_id)
            if payload is None:
                raise ReportError('REPORT_NOT_FOUND')
            self._owned(payload, actor, project_id, stage_id, draft_id)
            base = drafts.read_draft(draft_id, payload['base_revision'])
            validate_recovery_request({key: payload[key] for key in (
                'client_id', 'sequence', 'base_revision', 'base_revision_hash', 'snapshot_hash', 'template_hash', 'content',
            )}, base)
            return self._response(payload, drafts.read_draft(draft_id), content=True)

    def put(self, actor, project_id, stage_id, draft_id, **request):
        if type(request.get('base_revision')) is not int or request['base_revision'] < 1:
            raise ReportError('REPORT_INVALID')
        with self._store(actor, project_id, stage_id, draft_id, write=True) as (drafts, store):
            base = drafts.read_draft(draft_id, request['base_revision'])
            value = validate_recovery_request(request, base)
            old = store.read(value['client_id'])
            digest = sha256_bytes(canonical_bytes(value))
            current = drafts.read_draft(draft_id)
            if old is not None:
                self._owned(old, actor, project_id, stage_id, draft_id)
                if value['sequence'] < old['sequence']:
                    raise ReportError('REPORT_REVISION_CONFLICT')
                if value['sequence'] == old['sequence']:
                    if digest != old['request_hash']:
                        raise ReportError('REPORT_REVISION_CONFLICT')
                    return self._response(old, current, content=False)
            now = datetime.fromisoformat(self.drafts._now())
            items = store.items()
            for item in items:
                self._owned(item, actor, project_id, stage_id, draft_id)
                if expired(item, now) and item['client_id'] != value['client_id']:
                    store.remove(item['client_id'])
            active = [item for item in items if not expired(item, now)]
            if old is None and len(active) >= 4:
                raise ReportError('REPORT_LIMIT')
            payload = {
                **value, 'schema_version': 1, 'owner_subject': actor.subject,
                'project_id': str(project_id), 'stage_id': str(stage_id), 'draft_id': draft_id,
                'saved_at': self.drafts._now(), 'request_hash': digest,
            }
            store.write(payload)
            return self._response(payload, current, content=False)

    def discard(self, actor, project_id, stage_id, draft_id, client_id, *, expected_sequence):
        validate_uuid_text(client_id)
        with self._store(actor, project_id, stage_id, draft_id, write=True) as (drafts, store):
            drafts.read_draft(draft_id)
            item = store.read(client_id)
            if item is None:
                return
            self._owned(item, actor, project_id, stage_id, draft_id)
            if type(expected_sequence) is not int or item['sequence'] != expected_sequence:
                raise ReportError('REPORT_REVISION_CONFLICT')
            store.remove(client_id)

    @contextmanager
    def _store(self, actor, project_id, stage_id, draft_id, write=False):
        validate_uuid_text(draft_id)
        try:
            with self.drafts.archive._report_repository(actor, project_id, stage_id, write=write) as repository:
                store = self.drafts._store(repository)
                yield store, ReportRecoveryStore(store, draft_id)
        except (ArchiveError, ProjectError) as error:
            raise self.drafts._report_error(error, missing_as_not_found=True) from None

    def _owned(self, payload, actor, project_id, stage_id, draft_id):
        fields = REQUEST_KEYS | {'schema_version', 'owner_subject', 'project_id', 'stage_id', 'draft_id', 'saved_at', 'request_hash'}
        if (set(payload) != fields or payload.get('owner_subject') != actor.subject or payload.get('project_id') != str(project_id)
                or payload.get('stage_id') != str(stage_id) or payload.get('draft_id') != draft_id
                or type(payload.get('schema_version')) is not int or payload.get('schema_version') != 1
                or type(payload.get('sequence')) is not int or payload['sequence'] < 1
                or type(payload.get('base_revision')) is not int or payload['base_revision'] < 1):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        validate_time_text(payload['saved_at'])
        if sha256_bytes(canonical_bytes({key: payload[key] for key in REQUEST_KEYS})) != payload['request_hash']:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return payload

    def _response(self, payload, current, *, content):
        old = expired(payload, datetime.fromisoformat(self.drafts._now()))
        restorable = (not old and current.state == 'draft'
                      and current.revision == payload['base_revision'] and current.revision_hash == payload['base_revision_hash']
                      and current.snapshot_hash == payload['snapshot_hash']
                      and current.template_definition.template_hash == payload['template_hash'])
        return {**{key: value for key, value in payload.items() if key != 'content' or content},
                'restorable': restorable, 'expired': old}
