from pathlib import Path
import uuid

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError, ArchiveLimits
from project_management.app.domain.report_authoring_revision import validate_authored_revision_payload
from project_management.app.domain.report_draft_values import (
    ReportDraft, ReportDraftLimits, bytes_hash, read_json, revision_from_mapping, selection_from_mapping,
    snapshot_from_mapping, template_selection_from_mapping, validate_hash_text, validate_time_text, validate_uuid_text,
)
from project_management.app.domain.report_edits import validate_edit_targets
from project_management.app.domain.report_templates import validate_template_document_snapshot
from project_management.storage.admission import GrowthEstimate, admit
from project_management.storage.paths import read_bytes, validate_uuid, write_bytes
from project_management.storage.report_draft_preparation_bindings import (
    binding_fields,
    preparation_binding,
    ReportDraftCreateMixin,
)
from project_management.storage.report_draft_projection import draft_from_revision
from project_management.storage.report_publication_packets import ReportFinalizationPacketStore


SNAPSHOT_READ_LIMIT = 8_388_608


class ReportDraftStore(ReportDraftCreateMixin):
    def __init__(self, repository, archive_root: Path, archive_limits: ArchiveLimits, limits: ReportDraftLimits):
        self.repository = repository
        self.archive_root = archive_root
        self.archive_limits = archive_limits
        self.limits = limits
        self.runtime_root = repository.runtime
        self.publications = ReportFinalizationPacketStore(repository, archive_root, archive_limits, limits)

    def draft_id_for_command(self, stage_id: str, command_id: str) -> str:
        return str(uuid.uuid5(uuid.UUID(stage_id), f'draft:{validate_uuid(command_id)}'))

    def root(self, draft_id: str) -> Path:
        return self.runtime_root / 'report-drafts' / validate_uuid(draft_id)

    def command(self, draft_id: str, command_id: str):
        try:
            return self._command_payload(read_json(read_bytes(self.root(draft_id), f'commands/{validate_uuid(command_id)}.json')))
        except ArchiveError as error:
            if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                return None
            raise

    def intent_exists(self, draft_id: str) -> bool:
        return (self.root(draft_id) / 'intent.json').exists()

    def read_intent(self, draft_id: str):
        return self._intent(self.root(draft_id), draft_id)

    def current_exists(self, draft_id: str) -> bool:
        return (self.root(draft_id) / 'current.json').exists()

    def revision_payload(self, draft_id: str, revision: int):
        root = self.root(draft_id)
        expected = self._verified_revision_hash(root, draft_id, revision, self._intent(root, draft_id))
        return self._read_revision(root, revision, expected_hash=expected)

    def write_command(self, draft_id: str, command_id: str, command_payload) -> None:
        write_bytes(self.root(draft_id), f'commands/{validate_uuid(command_id)}.json', canonical_bytes(command_payload),
                    immutable=True, conflict_code='ARCHIVE_CAPTURE_CONFLICT')

    def read_draft(self, draft_id: str, revision: int | None = None) -> ReportDraft:
        root = self.root(draft_id)
        intent = self._intent(root, draft_id)
        head = self._current(root)
        selected_revision = head['revision'] if revision is None else self._positive_revision(revision)
        expected_hash = self._verified_revision_hash(root, draft_id, selected_revision, intent)
        selected = self._read_revision(root, selected_revision, expected_hash=expected_hash)
        if revision is None and selected[1] != head['revision_hash']:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        snapshot_bytes = read_bytes(root, 'snapshot.json', limit=SNAPSHOT_READ_LIMIT)
        snapshot_hash = bytes_hash(snapshot_bytes)
        if snapshot_hash != selected[0]['snapshot_hash'] or snapshot_hash != intent['snapshot_hash']:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        snapshot = snapshot_from_mapping(read_json(snapshot_bytes))
        if canonical_bytes(snapshot) != snapshot_bytes:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        self._validate_binding(draft_id, intent, selected[0], snapshot)
        return draft_from_revision(
            selected[0], selected[1], snapshot, self._state(root),
            self._preservation_review_issues(root, intent),
        )

    def write_save_command(self, draft_id: str, command_id: str, *, revision_payload, revision_hash: str,
                           command_payload) -> None:
        root = self.root(draft_id)
        self._admit(root, len(canonical_bytes(revision_payload)) + len(canonical_bytes(command_payload)) + 4096, 3)
        self.write_command(draft_id, command_id, command_payload)
        self.write_revision(draft_id, revision_payload, revision_hash)

    def write_revision(self, draft_id: str, payload, revision_hash: str) -> None:
        data = canonical_bytes(payload)
        if bytes_hash(data) != revision_hash:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        write_bytes(self.root(draft_id), f"revisions/{payload['revision']:08d}.json", data,
                    immutable=True, conflict_code='ARCHIVE_CAPTURE_CONFLICT')

    def recover_revision(self, draft_id: str, payload, revision_hash: str) -> None:
        root = self.root(draft_id)
        self._admit(root, len(canonical_bytes(payload)) + 4096, 2)
        self.write_revision(draft_id, payload, revision_hash)

    def write_finalization_files(self, draft_id: str, publication_id: str, files) -> None:
        self.publications.write_files(draft_id, publication_id, files)

    def write_finalization_intent(self, draft_id: str, payload) -> None:
        self.publications.write_intent(draft_id, payload)

    def finalization_packet(self, draft_id: str):
        return self.publications.packet(draft_id)

    def finalization_intent_exists(self, draft_id: str) -> bool:
        return self.publications.intent_exists(draft_id)

    def admit_finalization_commit(self, draft_id: str, files) -> None:
        self.publications.admit_commit(draft_id, files)

    def admit_new_finalization(self, draft_id: str, files, payload) -> None:
        self.publications.admit_new(draft_id, files, payload)

    def publish_current(self, draft_id: str, revision: int, revision_hash: str, *, expected_revision: int | None) -> None:
        root = self.root(draft_id)
        if expected_revision is not None:
            current = self._current(root)
            if current['revision'] != expected_revision:
                raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')
            self._read_revision(root, expected_revision, expected_hash=current['revision_hash'])
        self._read_revision(root, revision, expected_hash=revision_hash)
        write_bytes(root, 'current.json', canonical_bytes({
            'schema_version': 1,
            'revision': revision,
            'revision_hash': revision_hash,
        }), immutable=False)

    def revision_count(self, draft_id: str) -> int:
        revisions = self.root(draft_id) / 'revisions'
        return len(tuple(revisions.glob('*.json'))) if revisions.exists() else 0

    def edit_history_bytes(self, draft_id: str, extra_payload=None) -> int:
        total = 0
        revisions = self.root(draft_id) / 'revisions'
        if revisions.exists():
            for path in revisions.glob('*.json'):
                total += path.stat().st_size
        if extra_payload is not None:
            total += len(canonical_bytes(extra_payload))
        return total

    def revision_history(self, draft_id: str, through_revision: int, *, full_payload: bool = False):
        root = self.root(draft_id)
        intent = self._intent(root, draft_id)
        history = []
        for revision in range(1, through_revision + 1):
            expected_hash = self._verified_revision_hash(root, draft_id, revision, intent)
            payload, revision_hash = self._read_revision(root, revision, expected_hash=expected_hash)
            if full_payload:
                history.append({'revision': revision, 'revision_hash': revision_hash, 'payload': payload})
            else:
                history.append({
                    'revision': revision,
                    'revision_hash': revision_hash,
                    'updated_at': payload['updated_at'],
                    'edits': payload['edits'],
                })
        return tuple(history)

    def _intent(self, root: Path, draft_id: str):
        value = read_json(read_bytes(root, 'intent.json'))
        expected_v1 = {
            'schema_version', 'command_id', 'request_hash', 'project_id', 'stage_id',
            'owner_subject', 'draft_id', 'snapshot_hash', 'created_at', 'selection',
            'template', 'revision_payload', 'revision_hash',
        }
        expected_v2 = expected_v1 | {'preparation_binding_kind', 'preparation_binding_hash'}
        if not isinstance(value, dict) or (set(value.keys()) != expected_v1 and set(value.keys()) != expected_v2):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if value['schema_version'] == 1 and set(value.keys()) != expected_v1:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if value['schema_version'] == 2 and set(value.keys()) != expected_v2:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if value['schema_version'] not in {1, 2}:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        command_id = validate_uuid(value['command_id'])
        request_hash = validate_hash_text(value['request_hash'])
        if value['project_id'] != self.repository.project.id or value['stage_id'] != self.repository.stage.id:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if value['owner_subject'] != self.repository.owner_subject:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if value['draft_id'] != draft_id or self.draft_id_for_command(self.repository.stage.id, command_id) != draft_id:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        revision_payload = revision_from_mapping(value['revision_payload'])
        revision_hash = validate_hash_text(value['revision_hash'])
        if revision_payload['draft_id'] != draft_id or revision_payload['revision'] != 1:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if bytes_hash(canonical_bytes(self._json_revision(revision_payload))) != revision_hash:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        selection = selection_from_mapping(value['selection'])
        template = template_selection_from_mapping(value['template'])
        if selection != revision_payload['selection'] or template != revision_payload['template']:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        intent = {
            'schema_version': value['schema_version'],
            'command_id': command_id,
            'request_hash': request_hash,
            'project_id': value['project_id'],
            'stage_id': value['stage_id'],
            'owner_subject': value['owner_subject'],
            'draft_id': draft_id,
            'snapshot_hash': validate_hash_text(value['snapshot_hash']),
            'created_at': validate_time_text(value['created_at']),
            'selection': selection,
            'template': template,
            'revision_payload': revision_payload,
            'revision_hash': revision_hash,
        }
        if value['schema_version'] == 2:
            intent.update(binding_fields(value))
            preparation_binding(root, intent)
        return intent

    def _command_payload(self, value):
        expected = {
            'schema_version', 'kind', 'command_id', 'request_hash', 'draft_id',
            'expected_revision', 'prior_revision', 'prior_revision_hash',
            'revision', 'revision_hash', 'revision_payload',
        }
        if set(value.keys()) != expected or value['schema_version'] != 1:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        kind = value['kind']
        if kind not in {'create', 'create_authored', 'save', 'save_authored'}:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        command_id = validate_uuid(value['command_id'])
        draft_id = validate_uuid(value['draft_id'])
        revision_payload = revision_from_mapping(value['revision_payload'])
        revision = self._positive_revision(value['revision'])
        revision_hash = validate_hash_text(value['revision_hash'])
        if revision_payload['draft_id'] != draft_id or revision_payload['revision'] != revision:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if bytes_hash(canonical_bytes(self._json_revision(revision_payload))) != revision_hash:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        prior_revision = value['prior_revision']
        expected_revision = value['expected_revision']
        prior_revision_hash = value['prior_revision_hash']
        if kind in {'create', 'create_authored'}:
            if revision != 1 or prior_revision is not None or expected_revision is not None or prior_revision_hash is not None:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        else:
            if type(prior_revision) is not int or prior_revision < 1 or expected_revision != prior_revision:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
            prior_revision_hash = validate_hash_text(prior_revision_hash)
            if revision != prior_revision + 1:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return {
            'schema_version': 1,
            'kind': kind,
            'command_id': command_id,
            'request_hash': validate_hash_text(value['request_hash']),
            'draft_id': draft_id,
            'expected_revision': expected_revision,
            'prior_revision': prior_revision,
            'prior_revision_hash': prior_revision_hash,
            'revision': revision,
            'revision_hash': revision_hash,
            'revision_payload': revision_payload,
        }

    def _verified_revision_hash(self, root: Path, draft_id: str, revision: int, intent) -> str:
        if revision == 1:
            command = self.command(draft_id, intent['command_id'])
            if command is not None and (
                command['kind'] not in {'create', 'create_authored'}
                or command['request_hash'] != intent['request_hash']
                or command['revision_hash'] != intent['revision_hash']
            ):
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
            return intent['revision_hash']
        prior_hash = self._verified_revision_hash(root, draft_id, revision - 1, intent)
        matches = []
        commands_root = root / 'commands'
        if commands_root.exists():
            for path in sorted(commands_root.glob('*.json')):
                command = self._command_payload(read_json(read_bytes(root, path.relative_to(root).as_posix())))
                if command['draft_id'] == draft_id and command['revision'] == revision:
                    matches.append(command)
        if len(matches) != 1:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        command = matches[0]
        if (command['kind'] not in {'save', 'save_authored'}
                or command['prior_revision'] != revision - 1
                or command['prior_revision_hash'] != prior_hash):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return command['revision_hash']

    def _validate_binding(self, draft_id: str, intent, payload, snapshot) -> None:
        if payload['draft_id'] != draft_id:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if payload['parent_publication_id'] != payload['selection'].parent_publication_id:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if payload['template_definition'].template_id != payload['template'].template_id:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if payload['template_definition'].version != payload['template'].version:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if payload['template_definition'].options != payload['template'].options:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if payload['revision'] == 1 and payload != intent['revision_payload']:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if (snapshot.project_id != self.repository.project.id
                or snapshot.stage_id != self.repository.stage.id
                or snapshot.owner_subject != self.repository.owner_subject
                or snapshot.rule_hash != self.repository.stage.definition_hash
                or snapshot.capture_id != payload['selection'].capture_id
                or snapshot.baseline_publication_id != payload['selection'].baseline_publication_id):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if (payload['snapshot_hash'] != intent['snapshot_hash']
                or payload['selection'] != intent['selection']
                or payload['created_at'] != intent['created_at']):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if payload['schema_version'] == 2:
            self._validate_pinned_template_binding(payload)
            validate_authored_revision_payload(snapshot, payload)
        else:
            validate_edit_targets(snapshot, payload['edits'])

    def _validate_pinned_template_binding(self, payload) -> None:
        if payload['template_snapshot'].get('renderer_version') != 'template-document/1':
            return
        snapshot = validate_template_document_snapshot(payload['template_snapshot'])
        selection = snapshot['selection']
        if (payload['template'].template_id != selection['template_id']
                or payload['template'].version != str(selection['revision'])
                or payload['template'].options != {}
                or payload['template_definition'].template_hash != snapshot['presentation_hash']
                or payload['template_definition'].renderer_version != snapshot['renderer_version']):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')

    def _read_revision(self, root: Path, revision: int, expected_hash: str | None = None):
        data = read_bytes(root, f'revisions/{revision:08d}.json', limit=self.limits.max_edit_history_bytes + SNAPSHOT_READ_LIMIT)
        actual_hash = bytes_hash(data)
        if expected_hash is not None and actual_hash != expected_hash:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        payload = revision_from_mapping(read_json(data))
        if canonical_bytes(self._json_revision(payload)) != data:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if payload['revision'] != revision:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return payload, actual_hash

    def _current(self, root: Path):
        value = read_json(read_bytes(root, 'current.json'))
        if set(value.keys()) != {'schema_version', 'revision', 'revision_hash'} or value.get('schema_version') != 1:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return {'revision': self._positive_revision(value['revision']), 'revision_hash': validate_hash_text(value['revision_hash'])}

    def _preservation_review_issues(self, root: Path, intent):
        if intent['schema_version'] == 1:
            return ()
        binding = preparation_binding(root, intent)
        return tuple(binding.get('preservation_review_issues', ()))

    def _json_revision(self, payload):
        value = {
            'schema_version': payload['schema_version'],
            'draft_id': payload['draft_id'],
            'revision': payload['revision'],
            'selection': payload['selection'],
            'snapshot_hash': payload['snapshot_hash'],
            'template': payload['template'],
            'template_definition': payload['template_definition'],
            'edits': payload['edits'],
            'created_at': payload['created_at'],
            'updated_at': payload['updated_at'],
            'parent_publication_id': payload['parent_publication_id'],
        }
        if payload['schema_version'] == 2:
            value.update({
                'authoring_schema': payload['authoring_schema'],
                'template_snapshot': payload['template_snapshot'],
                'authoring_context': payload['authoring_context'],
            })
        return value

    def _state(self, root: Path) -> str:
        return self.publications.state(root.name)

    def _admit(self, draft_root: Path, bytes_count: int, files_count: int) -> None:
        admit(self.archive_root, self.repository.stage_root, draft_root, self.archive_limits,
              GrowthEstimate(bytes_count + files_count * 8192, files_count * 2))

    def _positive_revision(self, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return value
