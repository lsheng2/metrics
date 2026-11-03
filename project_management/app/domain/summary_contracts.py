from dataclasses import dataclass
from typing import Mapping

from project_management.app.domain.captures import SourceChainKey


MESSAGES = {
    'ANALYSIS_INVALID': 'Analysis arguments or stored data are invalid.',
    'ANALYSIS_SOURCE_INCOMPLETE': 'The source is not complete and consistent.',
    'ANALYSIS_SOURCE_CHANGED': 'The analysis source has changed.',
    'ANALYSIS_INPUT_LIMIT': 'The complete analysis input exceeds this profile limit.',
    'ANALYSIS_CHAIN_LIMIT': 'The retained source chain exceeds this analysis limit.',
    'ANALYSIS_DELTA_REQUIRED': 'This source requires cumulative delta analysis.',
    'ANALYSIS_PART_UNSUPPORTED': 'This analysis profile cannot consume the requested source parts.',
    'ANALYSIS_CONTRACT_INVALID': 'The selected AI contract or response is invalid.',
    'ANALYSIS_BACKEND_MISMATCH': 'The AI endpoint, scope, or store differs from the persisted attempt.',
    'ANALYSIS_DEADLINE_EXPIRED': 'The original analysis deadline has expired.',
    'ANALYSIS_ATTEMPT_PENDING': 'A prior analysis attempt for this source remains unresolved.',
    'ANALYSIS_OBSERVATION_LIMIT': 'The analysis observation limit has been reached.',
    'ANALYSIS_CANCELED': 'The analysis attempt has been canceled.',
    'ANALYSIS_RESULT_INVALID': 'The AI result does not match this analysis attempt.',
    'ANALYSIS_EVIDENCE_INVALID': 'The summary evidence or quoted source is invalid.',
    'ANALYSIS_OWNER_INVALID': 'The proposed action owner is not grounded in the source.',
    'ANALYSIS_LANGUAGE_INVALID': 'Generated summary text must use English.',
    'ANALYSIS_ACCEPTANCE_CONFLICT': 'The accepted summary or target source has changed.',
}


class AnalysisError(Exception):
    def __init__(self, code):
        self.code = code if code in MESSAGES else 'ANALYSIS_INVALID'
        self.message = MESSAGES[self.code]
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class AiBackendTarget:
    base_url: str
    source_app_id: str
    run_store_id: str
    scope_key: str
    grant_revision: str
    limit_policy_revision: str


@dataclass(frozen=True, slots=True)
class PreparedAnalysis:
    source_key: SourceChainKey
    target_capture_id: str
    source_hash: str
    expected_revision: int
    base_summary_id: str | None
    input_content: str
    input_hash: str


@dataclass(frozen=True, slots=True)
class AnalysisAttempt:
    attempt_id: str
    project_id: str
    stage_id: str
    source_key: SourceChainKey
    backend: AiBackendTarget
    prepared: PreparedAnalysis
    request: Mapping
    profile_definition_hash: str
    output_schema_hash: str
    dispatched: bool = False
    cancel_requested: bool = False


@dataclass(frozen=True, slots=True)
class AcceptedSummary:
    summary_id: str
    revision: int
    target_capture_id: str
    source_hash: str
    profile_definition_hash: str
    input_hash: str
    candidate: Mapping
    run_result: Mapping


@dataclass(frozen=True, slots=True)
class AnalysisPreparation:
    kind: str
    attempt: AnalysisAttempt | None = None
    accepted: AcceptedSummary | None = None


@dataclass(frozen=True, slots=True)
class AnalysisStep:
    state: str
    attempt_id: str
    accepted: AcceptedSummary | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisCancellation:
    state: str
    attempt_id: str
    run_id: str | None
    remote_stop: str
    error_code: str | None = None
