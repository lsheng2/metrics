from dataclasses import dataclass
from uuid import UUID, uuid5

from project_management.app.domain.capture_values import canonical_bytes, decode_json, decode_snapshot
from project_management.app.domain.summary_contracts import AcceptedSummary, AnalysisAttempt, AnalysisError, PreparedAnalysis
from project_management.app.domain.summary_delta import build_analysis_input
from project_management.app.domain.summary_input import MAX_CHAIN


@dataclass(frozen=True, slots=True)
class VerifiedSummaryMaterial:
    summary: AcceptedSummary
    attempt: AnalysisAttempt
    snapshot: dict
    prepared: PreparedAnalysis


def verified_accepted_material(archive, repository, source_key, contract, chain, snapshots=None, *, through_revision=None):
    history = archive._analysis_accepted_history(repository, source_key)
    if through_revision is not None:
        if type(through_revision) is not int or not 1 <= through_revision <= len(history):
            raise AnalysisError('ANALYSIS_RESULT_INVALID')
        history = history[:through_revision]
    if not history:
        return ()
    if len(chain) > MAX_CHAIN:
        raise AnalysisError('ANALYSIS_CHAIN_LIMIT')
    if snapshots is None:
        snapshots = tuple(decode_snapshot(repository.read_file(reference.git_path)) for reference in chain)
    if len(snapshots) != len(chain):
        raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
    for reference, source in zip(chain, snapshots):
        if archive._source_hash(source) != reference.source_hash or source.identity != reference.identity:
            raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
    positions = {reference.capture_id: index for index, reference in enumerate(chain)}
    if len(positions) != len(chain):
        raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
    verified = []
    previous_index = -1
    for accepted, envelope in history:
        attempt = archive._analysis_attempt(repository, envelope['attempt_id'])
        try:
            snapshot = envelope['payload']['snapshot']
            candidate = contract.validate_result(attempt, snapshot, accepted.run_result)
            contract.validate_request(attempt.request)
            baseline = verified[-1].summary if verified else None
            expected_revision = 0 if baseline is None else baseline.revision
            if (not attempt.dispatched or attempt.source_key != source_key
                    or accepted.summary_id != str(uuid5(UUID(attempt.attempt_id), 'accepted'))
                    or accepted.revision != expected_revision + 1
                    or attempt.prepared.expected_revision != expected_revision
                    or attempt.prepared.base_summary_id != (None if baseline is None else baseline.summary_id)
                    or accepted.profile_definition_hash != contract.definition_hash
                    or accepted.input_hash != attempt.prepared.input_hash
                    or accepted.target_capture_id != attempt.prepared.target_capture_id
                    or accepted.source_hash != attempt.prepared.source_hash
                    or canonical_bytes(candidate) != canonical_bytes(accepted.candidate)):
                raise AnalysisError('ANALYSIS_RESULT_INVALID')
            index = positions[accepted.target_capture_id]
            if index <= previous_index:
                raise AnalysisError('ANALYSIS_SOURCE_CHANGED')
            profile = contract.profile_ref
            prepared = build_analysis_input(
                repository.project.id, repository.stage, source_key, chain[:index + 1], snapshots[:index + 1],
                f"{profile['key']}@{profile['revision']}", baseline,
            )
            if prepared != attempt.prepared:
                raise AnalysisError('ANALYSIS_RESULT_INVALID')
            verified.append(VerifiedSummaryMaterial(accepted, attempt, decode_json(canonical_bytes(snapshot)), prepared))
            previous_index = index
        except (KeyError, TypeError, ValueError, AttributeError):
            raise AnalysisError('ANALYSIS_RESULT_INVALID') from None
    return tuple(verified)
