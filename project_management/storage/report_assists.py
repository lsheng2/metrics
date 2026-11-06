from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_assists import MAX_OBSERVATIONS
from project_management.app.domain.report_contracts import ReportError
from project_management.storage.admission import GrowthEstimate, admit
from project_management.storage.paths import controlled_path, read_bytes, validate_uuid, write_bytes


class ReportAssistStore:
    def __init__(self, repository):
        self.repository = repository

    def read(self, assist_id, name):
        path = self._path(assist_id, name)
        try:
            envelope = decode_json(read_bytes(self.repository.runtime, path, limit=524288))
        except ArchiveError as error:
            if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                return None
            raise ReportError('REPORT_ARTIFACT_INVALID') from None
        if (not isinstance(envelope, dict) or set(envelope) != {'schema_version', 'payload', 'sha256'}
                or type(envelope['schema_version']) is not int or envelope['schema_version'] != 1
                or envelope['sha256'] != content_hash(envelope['payload'])):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        value = envelope['payload']
        if not isinstance(value, dict):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if name.startswith('observation-') and (
                type(value.get('state')) is not str or value['state'] not in {
                    'prepared', 'observing', 'unknown', 'failed', 'canceled', 'cancel_requested', 'candidate_ready'}):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return value

    def write(self, assist_id, name, value, *, immutable=True):
        payload = canonical_bytes({'schema_version': 1, 'payload': value, 'sha256': content_hash(value)})
        if len(payload) > 524288:
            raise ReportError('REPORT_LIMIT')
        repo = self.repository
        try:
            admit(repo.config.root, repo.stage_root, repo.runtime, repo.config.limits,
                  GrowthEstimate(len(payload) + 8192, 2))
            write_bytes(repo.runtime, self._path(assist_id, name), payload, immutable=immutable)
        except ArchiveError:
            raise ReportError('REPORT_STORAGE_UNAVAILABLE') from None

    def observations(self, assist_id):
        values = []
        for index in range(MAX_OBSERVATIONS + 1):
            value = self.read(assist_id, f'observation-{index:02d}')
            if value is None:
                return tuple(values)
            values.append(value)
        raise ReportError('REPORT_LIMIT')

    def append(self, assist_id, value):
        index = len(self.observations(assist_id))
        if index >= MAX_OBSERVATIONS:
            raise ReportError('REPORT_LIMIT')
        self.write(assist_id, f'observation-{index:02d}', value)

    def active(self, draft_id):
        value = self.read(draft_id, 'active')
        if value is None:
            return None
        try:
            if set(value) != {'assist_id'}:
                raise ValueError
            validate_uuid(value['assist_id'])
        except (ArchiveError, KeyError, TypeError, ValueError):
            raise ReportError('REPORT_ARTIFACT_INVALID') from None
        return value['assist_id']

    def set_active(self, draft_id, assist_id):
        validate_uuid(assist_id)
        self.write(draft_id, 'active', {'assist_id': assist_id}, immutable=False)

    def exchange_count(self, assist_id):
        used = len(self.observations(assist_id))
        for index in range(MAX_OBSERVATIONS):
            value = self.read(assist_id, f'exchange-{index:02d}')
            if value is not None:
                if (set(value) != {'operation'} or type(value['operation']) is not str
                        or value['operation'] not in {'submit', 'observe', 'cancel', 'settle_cancel'}):
                    raise ReportError('REPORT_ARTIFACT_INVALID')
                used = max(used, index + 1)
        return used

    def claim_exchange(self, assist_id, operation):
        index = self.exchange_count(assist_id)
        if index >= MAX_OBSERVATIONS:
            return False
        self.write(assist_id, f'exchange-{index:02d}', {'operation': operation})
        return True

    def _path(self, assist_id, name):
        validate_uuid(assist_id)
        numbered = any(name.startswith(prefix) and len(name) == len(prefix) + 2 and name[-2:].isdigit()
                       for prefix in ('observation-', 'exchange-'))
        if name not in {'intent', 'dispatch', 'candidate', 'cancel', 'active'} and not numbered:
            raise ReportError('REPORT_INVALID')
        return f'report-assists/{assist_id}/{name}.json'
