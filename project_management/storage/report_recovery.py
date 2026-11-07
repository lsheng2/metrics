from datetime import datetime, timedelta

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_recovery import RECOVERY_LIMIT
from project_management.storage.paths import controlled_path, inspect_components, read_bytes, validate_uuid, write_bytes


class ReportRecoveryStore:
    def __init__(self, draft_store, draft_id):
        self.store = draft_store
        self.root = draft_store.root(draft_id)
        self.directory = self.root / 'recovery'

    def read(self, client_id):
        try:
            value = decode_json(read_bytes(self.root, self.path(client_id), limit=RECOVERY_LIMIT + 4096))
        except ArchiveError as error:
            if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                return None
            raise
        if (not isinstance(value, dict) or set(value) != {'payload', 'sha256'}
                or not isinstance(value['payload'], dict) or value['payload'].get('client_id') != client_id
                or sha256_bytes(canonical_bytes(value['payload'])) != value['sha256']):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return value['payload']

    def items(self):
        inspect_components(self.directory)
        if not self.directory.exists():
            return ()
        files = tuple(self.directory.iterdir())
        if len(files) > 8:
            raise ReportError('REPORT_LIMIT')
        values = []
        for path in files:
            if path.suffix == '.json':
                values.append(self.read(validate_uuid(path.stem)))
        return tuple(values)

    def write(self, payload):
        data = canonical_bytes({'payload': payload, 'sha256': sha256_bytes(canonical_bytes(payload))})
        self.store._admit(self.root, len(data) + 4096, 1)
        write_bytes(self.root, self.path(payload['client_id']), data)

    def remove(self, client_id):
        path = controlled_path(self.root, self.path(client_id))
        try:
            path.unlink(missing_ok=True)
        except OSError:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None

    @staticmethod
    def path(client_id):
        return f'recovery/{validate_uuid(client_id)}.json'


def expired(payload, now):
    return datetime.fromisoformat(payload['saved_at']) + timedelta(days=7) <= now
