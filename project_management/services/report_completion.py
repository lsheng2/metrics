from datetime import UTC, datetime, timedelta
import re

from project_management.app.domain.report_completion import (
    CompletionError,
    CompletionOption,
    CompletionResult,
    ReferenceObservation,
)
from project_management.app.domain.report_authoring import AuthoredEdit
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_continuity_edits import validate_continuity_authored_edits
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError, ReportSelection
from project_management.app.domain.report_edits import original_target_text, text_hash, validate_edit_targets
from project_management.app.domain.report_presentation import ReportEdit
from project_management.app.domain.report_templates import validate_template_document_snapshot
from provider_sync.app.api.access_contracts import AccessError


JIRA_ID = re.compile(r'#[A-Z][A-Z0-9_]*-[1-9][0-9]*\Z')
HSD_ID = re.compile(r'#[0-9]+\Z')
MAX_ID = 31


class ReportCompletionService:
    def __init__(self, draft_service, source_reader, reference_reader, receipt_verifier,
                 admission_store, *, clock=None):
        self.draft_service = draft_service
        self.source_reader = source_reader
        self.reference_reader = reference_reader
        self.receipt_verifier = receipt_verifier
        self.admission_store = admission_store
        self.clock = clock or (lambda: datetime.now(UTC))

    def suggest(self, actor, project_id, stage_id, draft_id, request):
        try:
            with self.draft_service.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
                stage = repository.stage
                draft = self.draft_service._store(repository).read_draft(draft_id)
                self._draft_editable(draft)
                self._draft_matches(draft, request)
                self._target_is_editable(draft, request.region_target)
                self._validate_token(stage.descriptor.provider_id, request.token)
                membership = self.source_reader.membership(actor, project_id, stage_id, draft.snapshot)
                if membership.state != 'complete':
                    return self._error(request, draft, 'COMPLETION_SCOPE_UNVERIFIED')
                member = self._member(membership, request.token[1:])
                if member is None:
                    return self._error(request, draft, 'COMPLETION_OUTSIDE_REPORT_SCOPE')
                if not self.reference_reader.supports(stage, membership.principal_id):
                    return self._error(request, draft, 'COMPLETION_PROVIDER_UNQUALIFIED')
                admitted = self.admission_store.admit(actor, repository, request.request_id, self.clock())
                if admitted is not None:
                    return self._error(request, draft, admitted.code, admitted.retry_after_seconds)
            try:
                observation = self._reference_observation(
                    self.reference_reader.read(self._context(actor, project_id, stage, request, membership), member.identity)
                )
            except AccessError as error:
                return self._provider_error(request, draft, error)
            refreshed_stage = self._stage(actor, project_id, stage_id)
            refreshed = self.draft_service.get(actor, project_id, stage_id, draft_id)
            self._draft_editable(refreshed)
            self._draft_matches(refreshed, request)
            if refreshed_stage.descriptor != stage.descriptor or refreshed_stage.definition_hash != stage.definition_hash:
                return self._error(request, draft, 'COMPLETION_SOURCE_CHANGED')
            options = self._options(actor, project_id, stage_id, draft, request.region_target, observation, membership)
            return CompletionResult(
                request.request_id,
                request.editor_epoch,
                request.local_version,
                'ready',
                draft.snapshot_hash,
                observation.observed_at,
                options,
                None,
            )
        except ProjectError:
            return self._error(request, None, 'REPORT_NOT_FOUND')
        except ArchiveError as error:
            return self._error(request, None, 'REPORT_NOT_FOUND' if error.code == 'ARCHIVE_RAW_PAGE_MISSING' else 'COMPLETION_SCOPE_UNAVAILABLE')
        except ReportError as error:
            return self._error(request, None, error.code)

    def _stage(self, actor, project_id, stage_id):
        _, stage = self.draft_service.archive._stage_for_read(actor, project_id, stage_id)
        if stage.source_status != 'current':
            raise ReportError('COMPLETION_SOURCE_CHANGED')
        return stage

    def _draft_matches(self, draft, request):
        if (draft.revision != request.expected_revision
                or draft.revision_hash != request.expected_revision_hash
                or draft.snapshot_hash != request.snapshot_hash):
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _draft_editable(self, draft):
        if draft.state != 'draft':
            raise ReportError('REPORT_FINALIZING' if draft.state == 'finalizing' else 'REPORT_FINALIZED')

    def _validate_token(self, provider_id, token):
        if type(token) is not str or not token.startswith('#') or len(token) < 3:
            raise ReportError('COMPLETION_INVALID_ID')
        if len(token) - 1 > MAX_ID:
            raise ReportError('COMPLETION_ID_TOO_LONG')
        pattern = JIRA_ID if provider_id == 'jira' else HSD_ID if provider_id == 'hsdes' else None
        if pattern is None:
            raise ReportError('COMPLETION_PROVIDER_UNQUALIFIED')
        other = HSD_ID if provider_id == 'jira' else JIRA_ID
        if other.fullmatch(token):
            raise ReportError('COMPLETION_PROVIDER_MISMATCH')
        if pattern.fullmatch(token) is None:
            raise ReportError('COMPLETION_INVALID_ID')

    def _target_is_editable(self, draft, target):
        if self._continuity_target(draft, target):
            return
        if self._template_slot_target(draft, target):
            return
        marker = '10000000-0000-4000-8000-000000000001'
        try:
            validate_edit_targets(draft.snapshot, (ReportEdit(marker, 'note', target, 'x'),))
            return
        except ReportError:
            original = original_target_text(draft.snapshot, target)
            if original is None:
                raise
            validate_edit_targets(draft.snapshot, (
                ReportEdit(marker, 'narrative_override', target, 'x', text_hash(original)),
            ))

    def _continuity_target(self, draft, target):
        if not isinstance(target, dict) or target.get('scope') not in {'daily_note', 'persistent_note', 'report_action'}:
            return False
        context = getattr(draft, 'authoring_context', None)
        if context is None:
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        if context.get('report_role') != 'daily':
            raise ReportError('REPORT_EDIT_TARGET_INVALID')
        marker = '10000000-0000-4000-8000-000000000001'
        try:
            validate_continuity_authored_edits(context, (
                AuthoredEdit(marker, 'note', target, plain_text_fragment('x'), None, 'completion-check', '2026-11-03T01:00:00+00:00'),
            ))
        except ReportError:
            raise ReportError('REPORT_EDIT_TARGET_INVALID') from None
        return True

    def _template_slot_target(self, draft, target):
        if not isinstance(target, dict) or set(target) != {'scope', 'slot_id'}:
            return False
        if target.get('scope') != 'template_slot':
            return False
        snapshot = getattr(draft, 'template_snapshot', None)
        if not snapshot:
            return False
        document = validate_template_document_snapshot(snapshot)['resolved_document']
        return target['slot_id'] in {
            block['slot_id'] for block in document['blocks'] if block['kind'] == 'slot'
        }

    def _member(self, membership, key):
        matches = [
            member for member in membership.members
            if key in {member.identity.display_key, member.identity.stable_id}
        ]
        return matches[0] if len(matches) == 1 else None

    def _context(self, actor, project_id, stage, request, membership):
        return {
            'actor': actor.subject,
            'actor_object': actor,
            'project_id': project_id,
            'stage_id': stage.id,
            'frozen_descriptor': stage.descriptor,
            'principal_id': membership.principal_id,
            'membership_proof_hash': membership.proof_hash,
            'rule_hash': membership.rule_hash,
            'deadline_at': self.clock() + timedelta(seconds=10),
            'request_id': request.request_id,
        }

    def _options(self, actor, project_id, stage_id, draft, target, observation, membership):
        rows = []
        for option_id in ('id', 'id_title', 'id_title_owner'):
            disabled = self._disabled(option_id, observation)
            if disabled:
                rows.append(CompletionOption(option_id, False, disabled, None, None))
                continue
            signed = self.receipt_verifier.issue_option(
                actor,
                project_id,
                stage_id,
                draft,
                target,
                option_id,
                observation,
                membership_proof_hash=membership.proof_hash,
                principal_id=membership.principal_id,
            )
            rows.append(CompletionOption(option_id, True, None, signed.fragment, signed.receipt))
        return tuple(rows)

    def _disabled(self, option_id, observation):
        if option_id == 'id_title' and not observation.title:
            return 'title_unavailable'
        if option_id == 'id_title_owner':
            if not observation.title:
                return 'title_unavailable'
            if observation.assignee_state == 'unassigned':
                return 'unassigned'
            if observation.assignee_state != 'assigned':
                return 'owner_unavailable'
            assignee = observation.assignee or {}
            if not assignee.get('display_name'):
                return 'owner_unavailable'
        return None

    def _provider_error(self, request, draft, error):
        if error.code in {'PROVIDER_HTTP_ERROR', 'PROVIDER_PERMISSION_DENIED'} and error.provider_status in {403, 404}:
            return self._error(request, draft, 'COMPLETION_ITEM_UNAVAILABLE')
        if error.code == 'PROVIDER_RATE_LIMITED':
            return self._error(request, draft, 'COMPLETION_RATE_LIMITED', error.retry_after_seconds or 60)
        if error.code == 'PROVIDER_AUTH_FAILED':
            return self._error(request, draft, 'COMPLETION_AUTH_REQUIRED')
        if error.code == 'PRINCIPAL_CHANGED':
            return self._error(request, draft, 'COMPLETION_PRINCIPAL_CHANGED')
        if error.code in {'CAPTURE_DEADLINE_EXPIRED'}:
            return self._error(request, draft, 'COMPLETION_TIMEOUT')
        if error.code in {'PROVIDER_RESPONSE_INVALID', 'CAPTURE_RESPONSE_LIMIT', 'CAPTURE_DOWNLOAD_LIMIT'}:
            return self._error(request, draft, 'COMPLETION_RESPONSE_INVALID')
        return self._error(request, draft, 'COMPLETION_NETWORK_ERROR')

    def _error(self, request, draft, code, retry_after=None):
        return CompletionResult(
            request.request_id,
            request.editor_epoch,
            request.local_version,
            'error',
            draft.snapshot_hash if draft is not None else '',
            None,
            (),
            CompletionError(code, code, retry_after),
        )

    def _reference_observation(self, value):
        if isinstance(value, ReferenceObservation):
            return value
        identity = value.identity
        return ReferenceObservation(
            {
                'provider_id': identity.provider_id,
                'endpoint_id': identity.endpoint_id,
                'stable_id': identity.stable_id,
                'display_key': identity.display_key,
            },
            value.requested_key,
            value.current_key,
            value.canonical_url,
            value.title,
            value.assignee,
            value.assignee_state,
            value.observed_at,
            value.source_updated_at,
            value.lookup_kind,
            value.scope_snapshot_hash,
        )
