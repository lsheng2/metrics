from project_management.app.domain.capture_values import canonical_bytes, content_hash
from project_management.app.domain.report_assists import available_targets
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.services.report_assist_wire import result_reference, wire_attempt
from project_management.storage.report_assists import ReportAssistStore


class ReportAssistReceiptVerifier:
    def __init__(self, contract=None, *, contract_loader=None):
        self.contract = contract
        self.contract_loader = contract_loader

    def verify_requests(self, repository, draft, requests):
        if not any(request.assist_receipt_id is not None for request in requests):
            return {}
        try:
            contract = self.contract or self.contract_loader()
        except (AnalysisError, OSError, TypeError):
            raise ReportError('REPORT_AI_UNAVAILABLE') from None
        store = ReportAssistStore(repository)
        targets = {item.target_id: item for item in available_targets(draft)}
        verified = {}
        for request in requests:
            assist_id = request.assist_receipt_id
            if assist_id is None:
                continue
            intent = store.read(assist_id, 'intent')
            candidate = store.read(assist_id, 'candidate')
            if intent is None or candidate is None or store.read(assist_id, 'cancel') is not None:
                raise ReportError('REPORT_AI_RESULT_INVALID')
            expected = intent['draft']
            if (expected['actor'], expected['project_id'], expected['stage_id'], expected['draft_id'],
                    expected['revision'], expected['revision_hash'], expected['snapshot_hash']) != (
                    repository.owner_subject, repository.project.id, repository.stage.id, draft.draft_id,
                    draft.revision, draft.revision_hash, draft.snapshot_hash):
                raise ReportError('REPORT_REVISION_CONFLICT')
            if expected['template_hash'] != content_hash(draft.template_snapshot):
                raise ReportError('REPORT_AI_RESULT_INVALID')
            target_id = content_hash(request.target)
            target = targets.get(target_id)
            admitted = next((item for item in intent['input']['targets'] if item['target_id'] == target_id), None)
            if (target is None or admitted is None or admitted['fragment_hash'] != target.fragment_hash
                    or request.kind != target.kind or request.expected_original_hash != target.expected_original_hash):
                raise ReportError('REPORT_AI_RESULT_INVALID')
            output = contract.validate_result(wire_attempt(intent, contract),
                                              candidate['snapshot'], candidate['result'])
            selected = next((item for item in output['targets'] if item['target_id'] == target_id), None)
            if (selected is None or selected['status'] != 'filled'
                    or canonical_bytes(selected['fragment']) != canonical_bytes(request.fragment)):
                raise ReportError('REPORT_AI_RESULT_INVALID')
            verified[request.edit_id] = result_reference(intent, candidate['snapshot'], candidate['result'], target_id)
        return verified
