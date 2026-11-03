from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from referencing import Registry, Resource

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.app.domain.summary_validation import validate_candidate


MANIFEST_SHA = 'e7386f82d2bf3963feccc28cfbfda732b9eddb829831d5ba660b50554e5f81c4'
PROFILE_ID = 'project-reporting.summary@review-1'


def _deny_schema(uri):
    raise AnalysisError('ANALYSIS_CONTRACT_INVALID')


def _instant(value):
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError
    return instant


class AiTaskContract:
    def __init__(self, profile, selected, schemas):
        self._profile = profile
        self.definition_hash = selected['definitionSha256']
        self.output_schema_hash = selected['outputSchemaSha256']
        self._schemas = schemas
        self._registry = Registry(retrieve=_deny_schema)
        for uri, schema in profile['schemaDocuments'].items():
            self._registry = self._registry.with_resource(uri, Resource.from_contents(schema))

    @property
    def profile_ref(self):
        return {'key': self._profile['key'], 'revision': self._profile['revision']}

    @classmethod
    def load(cls, pack_root):
        try:
            root = Path(pack_root).resolve(strict=True)
            manifest_bytes = cls._read(root, 'manifest.json')
            if version('ai-base-application-sdk') != '0.1.0a2' or sha256_bytes(manifest_bytes) != MANIFEST_SHA:
                raise ValueError
            manifest = decode_json(manifest_bytes)
            if manifest['qualification'] != 'synthetic_only' or len(manifest['files']) != 21:
                raise ValueError
            documents = {}
            for name, expected in manifest['files'].items():
                payload = cls._read(root, name)
                if sha256_bytes(payload) != expected:
                    raise ValueError
                documents[name] = decode_json(payload)
            selected = manifest['profiles'][PROFILE_ID]
            return cls(documents[selected['profile']], selected, {
                key: documents[f'schemas/{key}.json']
                for key in ('RunSubmit', 'RunSnapshot', 'RunResult', 'RunCancelResponse')
            })
        except (OSError, ValueError, KeyError, TypeError, ArchiveError, PackageNotFoundError):
            raise AnalysisError('ANALYSIS_CONTRACT_INVALID') from None

    @staticmethod
    def _read(root, name):
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError
        return path.read_bytes()

    def _validate(self, schema, value):
        try:
            canonical_bytes(value)
            Draft202012Validator(schema, registry=self._registry).validate(value)
        except (ValidationError, SchemaError, ArchiveError, ValueError, TypeError, UnicodeError):
            raise AnalysisError('ANALYSIS_CONTRACT_INVALID') from None

    def validate_input(self, value):
        self._validate(self._profile['inputSchema'], value)

    def validate_request(self, request):
        self._validate(self._schemas['RunSubmit'], request)
        if re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', request['deadlineAt']) is None:
            raise AnalysisError('ANALYSIS_CONTRACT_INVALID')
        try:
            _instant(request['deadlineAt'])
        except ValueError:
            raise AnalysisError('ANALYSIS_CONTRACT_INVALID') from None
        self.validate_input(decode_json(request['input']['content'].encode('utf-8')))

    def validate_snapshot(self, attempt, value):
        self._validate(self._schemas['RunSnapshot'], value)
        expected = {
            'contractVersion': 'task-run/1', 'runStoreId': attempt.backend.run_store_id,
            'sourceAppId': attempt.backend.source_app_id, 'scopeKey': attempt.backend.scope_key,
            'clientRunKey': attempt.attempt_id,
            'profile': dict(self.profile_ref, definitionSha256=attempt.profile_definition_hash),
            'inputSha256': attempt.prepared.input_hash, 'logicalInputHash': attempt.request['logicalInputHash'],
            'grantRevision': attempt.backend.grant_revision, 'limitPolicyRevision': attempt.backend.limit_policy_revision,
            'acceptedLimits': attempt.request['limits'],
        }
        try:
            if (any(value.get(key) != expected_value for key, expected_value in expected.items())
                    or _instant(value['deadlineAt']) != _instant(attempt.request['deadlineAt'])
                    or value['resultRetentionSeconds'] < attempt.request['minimumResultRetentionSeconds']
                    or value['dispatch']['attemptCount'] > 1
                    or attempt.profile_definition_hash != self.definition_hash
                    or attempt.output_schema_hash != self.output_schema_hash):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise AnalysisError('ANALYSIS_RESULT_INVALID') from None

    def validate_result(self, attempt, snapshot, value):
        self.validate_snapshot(attempt, snapshot)
        self._validate(self._schemas['RunResult'], value)
        expected = {
            'contractVersion': 'task-run/1', 'runStoreId': attempt.backend.run_store_id,
            'runId': snapshot['runId'], 'scopeKey': attempt.backend.scope_key, 'profile': snapshot['profile'],
            'inputSha256': attempt.prepared.input_hash, 'logicalInputHash': attempt.request['logicalInputHash'],
            'effectiveInputSha256': snapshot['effectiveInputSha256'],
            'outputSchemaSha256': attempt.output_schema_hash, 'mediaType': 'application/json',
        }
        try:
            payload = value['content'].encode('utf-8')
            if (snapshot['state'] != 'succeeded' or snapshot['unresolvedExposure']
                    or snapshot['result']['availability'] != 'available'
                    or snapshot['dispatch']['attemptCount'] != 1
                    or any(value.get(key) != expected_value for key, expected_value in expected.items())
                    or value['sha256'] != sha256_bytes(payload)
                    or value['sha256'] != snapshot['result']['sha256']
                    or len(payload) > attempt.request['limits']['maxOutputBytes']):
                raise ValueError
            output = decode_json(payload)
        except (ValueError, KeyError, TypeError, UnicodeError, ArchiveError):
            raise AnalysisError('ANALYSIS_RESULT_INVALID') from None
        self._validate(self._profile['outputSchema'], output)
        return validate_candidate(attempt.prepared, output)

    def validate_cancel(self, attempt, value, *, expected_run_id):
        self._validate(self._schemas['RunCancelResponse'], value)
        try:
            snapshot = value['run']
            self.validate_snapshot(attempt, snapshot)
            if snapshot['runId'] != expected_run_id:
                raise ValueError
            return snapshot
        except (KeyError, ValueError, TypeError):
            raise AnalysisError('ANALYSIS_RESULT_INVALID') from None
