from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from project_management.app.domain.ai_profiles import TaskProfileDefinition
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_assists import validate_assist_output
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.summary_validation import validate_candidate
from project_management.app.domain.task_runs import TaskRunRequest, TaskRunResult, TaskRunSnapshot


class TaskProfileContract:
    def __init__(self, profile):
        if not isinstance(profile, TaskProfileDefinition):
            raise TypeError('Metrics task profile definition is required')
        self.profile = profile
        self.definition_hash = profile.definition_sha256
        self.output_schema_hash = profile.output_schema_sha256
        self._input = Draft202012Validator(profile.input_schema)
        self._output = Draft202012Validator(profile.output_schema)

    @property
    def profile_ref(self):
        return f'{self.profile.id}@{self.profile.version}'

    def _validate(self, validator, value):
        try:
            canonical_bytes(value)
            validator.validate(value)
        except (ValidationError, SchemaError, ArchiveError, ValueError, TypeError):
            raise AnalysisError('ANALYSIS_CONTRACT_INVALID') from None

    def validate_input(self, value):
        self._validate(self._input, value)

    def make_request(self, prepared, client_run_key, deadline_at):
        self.validate_input(decode_json(prepared.input_content.encode('utf-8')))
        return TaskRunRequest(
            profile_id=self.profile.id, profile_version=self.profile.version,
            profile_definition_sha256=self.definition_hash,
            output_schema_sha256=self.output_schema_hash,
            input_json=prepared.input_content, input_sha256=prepared.input_hash,
            client_run_key=client_run_key, deadline_at=deadline_at,
            limits=self.profile.limits, minimum_result_retention_seconds=60,
        )

    def validate_request(self, request):
        if (not isinstance(request, TaskRunRequest)
                or request.profile_id != self.profile.id
                or request.profile_version != self.profile.version
                or request.profile_definition_sha256 != self.definition_hash
                or request.output_schema_sha256 != self.output_schema_hash):
            raise AnalysisError('ANALYSIS_CONTRACT_INVALID')
        self.validate_input(decode_json(request.input_json.encode('utf-8')))

    def validate_snapshot(self, request, snapshot):
        self.validate_request(request)
        if (not isinstance(snapshot, TaskRunSnapshot)
                or snapshot.profile_id != request.profile_id
                or snapshot.profile_version != request.profile_version
                or snapshot.source_input_sha256 != request.input_sha256
                or snapshot.dispatch.profile_definition_sha256 != self.definition_hash
                or snapshot.result.output_schema_sha256 not in (None, self.output_schema_hash)):
            raise AnalysisError('ANALYSIS_RESULT_INVALID')

    def validate_result_envelope(self, request, snapshot, result):
        self.validate_snapshot(request, snapshot)
        if (not isinstance(result, TaskRunResult)
                or snapshot.status != 'succeeded' or result.status != 'succeeded'
                or snapshot.error_code is not None or result.error_code is not None
                or not snapshot.dispatch.dispatched or not result.dispatch.dispatched
                or snapshot.dispatch.uncertainty != 'dispatched'
                or result.dispatch.uncertainty != 'dispatched'
                or result.run_id != snapshot.run_id
                or result.profile_id != request.profile_id
                or result.profile_version != request.profile_version
                or result.source_input_sha256 != request.input_sha256
                or result.input_sha256 != snapshot.input_sha256
                or result.effective_input_sha256 != snapshot.effective_input_sha256
                or result.dispatch.profile_definition_sha256 != self.definition_hash
                or result.output_schema_sha256 != self.output_schema_hash
                or result.output_sha256 != snapshot.result.output_sha256
                or len(result.content_json.encode('utf-8')) > request.limits['max_output_bytes']):
            raise AnalysisError('ANALYSIS_RESULT_INVALID')
        output = decode_json(result.content_json.encode('utf-8'))
        self._validate(self._output, output)
        return output


class SummaryTaskContract(TaskProfileContract):
    def validate_result(self, prepared, request, snapshot, result):
        return validate_candidate(prepared, self.validate_result_envelope(request, snapshot, result))


class AuthoringTaskContract(TaskProfileContract):
    def validate_result(self, prepared, request, snapshot, result):
        output = self.validate_result_envelope(request, snapshot, result)
        return validate_assist_output(decode_json(prepared.input_content.encode('utf-8')), output)
