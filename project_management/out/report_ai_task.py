from pathlib import Path

from project_management.app.domain.capture_values import content_hash, decode_json, sha256_bytes
from project_management.app.domain.report_assists import validate_assist_output
from project_management.app.domain.summary_contracts import AnalysisError
from project_management.out.ai_task_contract import AiTaskContract


PROFILE_ROOT = Path(__file__).resolve().parents[1] / 'ai_bundle/report-authoring'
DEFINITION_SHA256 = '31ef07605350544cf5c67ad7624921c0cfa2dacd3fdefb096d7b57d585cca2b2'


class AuthoringTaskContract(AiTaskContract):
    @classmethod
    def load(cls, pack_root, profile_root=PROFILE_ROOT):
        wire = AiTaskContract.load(pack_root)
        root = Path(profile_root)
        try:
            manifest = decode_json(cls._read(root, 'manifest.json'))
            raw = cls._read(root, 'profile.json')
            profile = decode_json(raw)
            if (manifest['schema_version'] != 1 or manifest['sdk_version'] != '0.2.0a1'
                    or manifest['qualification'] != 'synthetic_only' or manifest['wire_version'] != 'task-run/1'
                    or sha256_bytes(raw) != manifest['profile_file_sha256']
                    or content_hash(profile) != DEFINITION_SHA256
                    or manifest['definition_sha256'] != DEFINITION_SHA256
                    or manifest['output_schema_sha256'] != content_hash(profile['outputSchema'])
                    or profile['key'] != 'project-reporting.authoring' or profile['revision'] != '1'):
                raise ValueError
        except (OSError, ValueError, KeyError, TypeError):
            raise AnalysisError('ANALYSIS_CONTRACT_INVALID') from None
        return cls(profile, {'definitionSha256': manifest['definition_sha256'],
                             'outputSchemaSha256': manifest['output_schema_sha256']}, wire._schemas)

    def validate_result(self, attempt, snapshot, value):
        output = self.validate_result_envelope(attempt, snapshot, value)
        return validate_assist_output(decode_json(attempt.prepared.input_content.encode('utf-8')), output)
