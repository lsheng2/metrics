from importlib.resources import files

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from project_management.app.domain.ai_profiles import TaskProfileDefinition
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.summary_contracts import AnalysisError


PROFILE_FILES = {
    'metrics.project_summary': 'project_summary.json',
    'metrics.report_authoring': 'report_authoring.json',
}


def _contains_reference(value):
    if isinstance(value, dict):
        return bool({'$ref', '$dynamicRef', '$recursiveRef'} & value.keys()) or any(
            _contains_reference(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_reference(item) for item in value)
    return False


def load_task_profile(profile_id):
    try:
        name = PROFILE_FILES[profile_id]
        raw = files('project_management.ai_profiles').joinpath(name).read_bytes()
        if len(raw) > 1024 * 1024:
            raise ValueError('Profile is too large')
        value = decode_json(raw)
        if value['id'] != profile_id:
            raise ValueError('Profile identity differs')
        for key in ('input_schema', 'output_schema'):
            schema = value[key]
            if _contains_reference(schema):
                raise ValueError('Profile schemas must be self-contained')
            Draft202012Validator.check_schema(schema)
        return TaskProfileDefinition(canonical_bytes(value).decode('utf-8'))
    except (KeyError, TypeError, ValueError, OSError, SchemaError, ArchiveError):
        raise AnalysisError('ANALYSIS_CONTRACT_INVALID') from None


def load_task_profiles():
    return tuple(load_task_profile(profile_id) for profile_id in PROFILE_FILES)
