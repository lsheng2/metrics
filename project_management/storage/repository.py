from datetime import UTC, datetime
from pathlib import Path
import uuid
import hashlib
import re

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError, ArchiveStorageConfig
from project_management.app.domain.contracts import ProjectSummary, StageSummary
from project_management.app.spi.archive import CommitReceipt, StageRepository
from project_management.storage.git import ATTRIBUTES, GitRunner
from project_management.storage.git_safety import validate_configuration, write_configuration
from project_management.storage.admission import admit_initialization
from project_management.storage.report_publication_listing import list_report_publication_ids
from project_management.storage.paths import (
    controlled_path,
    ensure_configured_archive_root,
    ensure_empty_or_identity_root,
    read_bytes,
    safe_relative_path,
    validate_uuid,
    write_bytes,
)


BRANCH = 'main'
NAMESPACES = {'captures', 'bootstrap', 'source_resolution', 'analysis_attempts', 'accepted_summaries', 'report_publications'}
REPORT_PUBLICATION_FILES = {'snapshot.json', 'template.json', 'edits.json', 'report.html', 'report.txt', 'manifest.json'}


class CaptureArchiveRepository(StageRepository):
    def open_read_view(self):
        from project_management.storage.archive_read_view import GitArchiveReadView
        return GitArchiveReadView(self)

    def read_files(self, requests):
        with self.open_read_view() as view:
            return view.read_files(requests)

    def validated(self, key, load):
        return load()

    def __init__(self, config: ArchiveStorageConfig, project: ProjectSummary, stage: StageSummary, owner_subject: str):
        self.config = config
        self.project = project
        self.stage = stage
        self.owner_subject = owner_subject
        self.root = config.root.absolute()
        self.stage_root = self.root / 'projects' / validate_uuid(project.id) / 'stages' / validate_uuid(stage.id)
        self.archive = self.stage_root / 'archive'
        self.objects = self.stage_root / 'objects'
        self.runtime = self.stage_root / 'runtime'
        self.hooks = self.runtime / 'empty-hooks'
        self.git = GitRunner(self.archive, self.hooks)

    def initialize(self) -> str | None:
        ensure_empty_or_identity_root(self.root)
        if not (self.archive / '.git').exists():
            admit_initialization(self.root, self.stage_root, self.config.limits)
        self._ensure_root_identity()
        self._ensure_git_repository()
        head = self.head()
        if head is None:
            receipt = self.append_record(
                self.stage.id,
                'bootstrap',
                {
                    '.gitattributes': ATTRIBUTES,
                    f'bootstrap/stages/{self.stage.id}.json': canonical_bytes(self._stage_identity()),
                },
                expected_head=None,
                record_fingerprint=sha256_bytes(canonical_bytes(self._stage_identity())),
            )
            return receipt.commit_id
        self._check_stage_identity()
        return head

    def verify_identity(self) -> None:
        ensure_configured_archive_root(self.root)
        self._read_root_identity()
        if not (self.archive / '.git').is_dir():
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
        validate_configuration(self.archive, self.hooks, self.config.author_name, self.config.author_email)
        self._check_stage_identity()

    def head(self) -> str | None:
        if not (self.archive / '.git').exists():
            return None
        result = self.git.run(['rev-parse', '--verify', f'refs/heads/{BRANCH}'], check=False)
        if result.returncode:
            return None
        return result.stdout.decode('ascii').strip()

    def read_file(self, git_path: str, commit: str = BRANCH) -> bytes:
        safe_relative_path(git_path)
        result = self.git.run(['show', f'{commit}:{git_path}'], check=False)
        if result.returncode:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return result.stdout

    def list_files(self, prefix: str, commit: str = BRANCH) -> tuple[str, ...]:
        safe_relative_path(prefix)
        result = self.git.run(['ls-tree', '-r', '--name-only', commit, prefix], check=False)
        if result.returncode:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return tuple(line for line in result.stdout.decode('utf-8').splitlines() if line)

    def list_report_publication_ids(self, *, limit: int) -> tuple[str, ...]:
        return list_report_publication_ids(self.git, limit=limit)

    def commit_for_path(self, git_path: str) -> str:
        commit = self.find_commit_for_path(git_path)
        if commit is None:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return commit

    def find_commit_for_path(self, git_path: str, commit: str = BRANCH) -> str | None:
        safe_relative_path(git_path)
        result = self.git.run(['log', '-n', '1', '--format=%H', commit, '--', git_path], check=False)
        if result.returncode:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        value = result.stdout.decode('ascii').strip()
        if not value:
            return None
        if re.fullmatch('[a-f0-9]{40}', value) is None:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return value

    def parent_for_commit(self, commit_id: str) -> str | None:
        result = self.git.run(['rev-list', '--parents', '-n', '1', commit_id], check=False)
        if result.returncode:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        parts = result.stdout.decode('ascii').strip().split()
        if len(parts) <= 1:
            return None
        return parts[1]

    def checkout_state(self, commit_id: str) -> str:
        return 'current' if self._existing_checkout_matches(commit_id) else 'stale'

    def append_record(
        self,
        record_id: str,
        namespace: str,
        files,
        *,
        expected_head: str | None,
        record_fingerprint: str,
    ) -> CommitReceipt:
        self._ensure_git_repository()
        self._validate_record(record_id, namespace, files)
        parent = self.head()
        file_bytes = {path: bytes(data) for path, data in files.items()}
        finalize_intent = self._finalize_intent_path(namespace, record_id)
        candidate_path = finalize_intent + '.candidate'
        if (self.runtime / candidate_path).exists():
            candidate = decode_json(read_bytes(self.runtime, candidate_path))
            if candidate['record_fingerprint'] != record_fingerprint or candidate['files'] != {
                    path: sha256_bytes(data) for path, data in file_bytes.items()}:
                raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
            if parent not in {candidate['parent_commit'], candidate['commit_id']}:
                raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')
            if parent != candidate['commit_id']:
                self._publish(candidate['commit_id'], parent)
            state = self._materialize(candidate['commit_id'], candidate['parent_commit'], file_bytes)
            return CommitReceipt(candidate['commit_id'], candidate['parent_commit'], candidate['tree_id'],
                                 record_fingerprint, state)
        if parent != expected_head:
            raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')
        self._write_finalize_intent(finalize_intent, parent, record_fingerprint, file_bytes)
        index = self.runtime / f'index-{uuid.uuid4().hex}'
        index_env = {'GIT_INDEX_FILE': str(index)}
        try:
            self._prepare_index(parent, index_env)
            for path, data in file_bytes.items():
                existing = self._read_existing(parent, path)
                if existing is not None and existing != data:
                    raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')
                if existing is None:
                    blob = self.git.run(['hash-object', '-w', '--stdin'], input_data=data).stdout.decode('ascii').strip()
                    self.git.run(['update-index', '--add', '--cacheinfo', f'100644,{blob},{path}'], extra_env=index_env)
            tree_id = self.git.run(['write-tree'], extra_env=index_env).stdout.decode('ascii').strip()
            commit_id = self._commit_tree(tree_id, parent, record_id, record_fingerprint)
            write_bytes(self.runtime, candidate_path, canonical_bytes({
                'commit_id': commit_id, 'parent_commit': parent, 'tree_id': tree_id,
                'record_fingerprint': record_fingerprint,
                'files': {path: sha256_bytes(data) for path, data in file_bytes.items()},
            }), immutable=True)
            self._publish(commit_id, parent)
        finally:
            try:
                if index.exists():
                    index.unlink()
            except OSError:
                pass
        checkout_state = self._materialize(commit_id, parent, file_bytes)
        return CommitReceipt(commit_id, parent, tree_id, record_fingerprint, checkout_state)

    def _ensure_root_identity(self) -> None:
        payload = {
            'schema_version': 1,
            'root_id': str(uuid.uuid4()),
            'canonical_root': str(self.root),
            'author_name': self.config.author_name,
            'author_email': self.config.author_email,
            'branch': BRANCH,
        }
        identity = self.root / 'archive-root.json'
        if identity.exists():
            self._read_root_identity()
            return
        write_bytes(self.root, 'archive-root.json', canonical_bytes(payload), immutable=True)

    def _read_root_identity(self) -> None:
        existing = decode_json(read_bytes(self.root, 'archive-root.json'))
        if not isinstance(existing, dict) or existing.get('schema_version') != 1:
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
        try:
            validate_uuid(existing.get('root_id'))
        except ArchiveError:
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH') from None
        expected = {
            'canonical_root': str(self.root),
            'author_name': self.config.author_name,
            'author_email': self.config.author_email,
            'branch': BRANCH,
        }
        comparable = {key: existing.get(key) for key in expected}
        if comparable != expected:
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')

    def _ensure_git_repository(self) -> None:
        self.hooks.mkdir(parents=True, exist_ok=True)
        self.archive.mkdir(parents=True, exist_ok=True)
        if not (self.archive / '.git').exists():
            if next(self.archive.iterdir(), None) is not None:
                raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
            self.git.run(['init', f'--template={self.hooks}', '--initial-branch=main'])
            self.git.run(['symbolic-ref', 'HEAD', f'refs/heads/{BRANCH}'])
            write_configuration(self.archive, self.hooks, self.config.author_name, self.config.author_email)
        validate_configuration(self.archive, self.hooks, self.config.author_name, self.config.author_email)

    def _stage_identity(self):
        return {
            'schema_version': 1,
            'root_id': decode_json(read_bytes(self.root, 'archive-root.json'))['root_id'],
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'owner_subject': self.owner_subject,
            'descriptor_hash': self.stage.definition_hash,
            'descriptor': self.stage.descriptor,
        }

    def _check_stage_identity(self) -> None:
        path = f'bootstrap/stages/{self.stage.id}.json'
        existing = decode_json(self.read_file(path))
        if existing != decode_json(canonical_bytes(self._stage_identity())):
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')

    def _validate_record(self, record_id: str, namespace: str, files) -> None:
        if namespace not in NAMESPACES:
            raise ArchiveError('UNSAFE_PATH')
        if type(record_id) is not str or not record_id:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if not files:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if namespace == 'source_resolution' and (record_id != 'first' or set(files) != {'source_resolution/first.json'}):
            raise ArchiveError('UNSAFE_PATH')
        if namespace in {'analysis_attempts', 'accepted_summaries'}:
            validate_uuid(record_id)
        if namespace == 'report_publications':
            validate_uuid(record_id)
            expected = {f'report_publications/{record_id}/{name}' for name in REPORT_PUBLICATION_FILES}
            if set(files) != expected:
                raise ArchiveError('UNSAFE_PATH')
        for path, data in files.items():
            parts = safe_relative_path(path)
            if parts[0] != namespace and not (namespace == 'bootstrap' and path == '.gitattributes'):
                raise ArchiveError('UNSAFE_PATH')
            if type(data) is not bytes:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
            if namespace == 'analysis_attempts':
                if len(parts) < 3:
                    raise ArchiveError('UNSAFE_PATH')
                validate_uuid(parts[1])
                valid = (len(parts) == 3 and parts[2] in {'intent.json', 'dispatch.json', 'cancel.json'}) or (
                    len(parts) == 4 and parts[2] == 'observations'
                    and re.fullmatch('[0-9]{8}\\.json', parts[3]) and int(parts[3][:8]) > 0
                )
                if not valid:
                    raise ArchiveError('UNSAFE_PATH')
            if namespace == 'accepted_summaries' and not (
                len(parts) == 3 and re.fullmatch('[a-f0-9]{64}', parts[1])
                and re.fullmatch('[0-9]{8}\\.json', parts[2]) and int(parts[2][:8]) > 0
            ):
                raise ArchiveError('UNSAFE_PATH')
            if namespace == 'report_publications' and not (
                len(parts) == 3 and parts[1] == record_id and parts[2] in REPORT_PUBLICATION_FILES
            ):
                raise ArchiveError('UNSAFE_PATH')

    def _finalize_intent_path(self, namespace: str, record_id: str) -> str:
        safe_id = record_id.replace('-', '')
        return f'finalize/{namespace}/{safe_id}.json'

    def _write_finalize_intent(self, relative: str, parent: str | None, fingerprint: str, files) -> None:
        payload = {
            'schema_version': 1,
            'parent_commit': parent,
            'record_fingerprint': fingerprint,
            'files': {path: sha256_bytes(data) for path, data in files.items()},
        }
        write_bytes(self.runtime, relative, canonical_bytes(payload), immutable=True, conflict_code='ARCHIVE_CHAIN_CONFLICT')

    def _prepare_index(self, parent: str | None, index_env: dict[str, str]) -> None:
        if parent is None:
            self.git.run(['read-tree', '--empty'], extra_env=index_env)
        else:
            self.git.run(['read-tree', parent], extra_env=index_env)

    def _read_existing(self, parent: str | None, path: str) -> bytes | None:
        if parent is None:
            return None
        result = self.git.run(['show', f'{parent}:{path}'], check=False)
        if result.returncode:
            return None
        return result.stdout

    def _commit_tree(self, tree_id: str, parent: str | None, record_id: str, fingerprint: str) -> str:
        arguments = ['commit-tree', tree_id]
        if parent is not None:
            arguments.extend(['-p', parent])
        now = datetime.now(UTC).isoformat()
        env = {
            'GIT_AUTHOR_NAME': self.config.author_name,
            'GIT_AUTHOR_EMAIL': self.config.author_email,
            'GIT_AUTHOR_DATE': now,
            'GIT_COMMITTER_NAME': self.config.author_name,
            'GIT_COMMITTER_EMAIL': self.config.author_email,
            'GIT_COMMITTER_DATE': now,
        }
        message = f'archive {record_id}\n\nfingerprint {fingerprint}\n'.encode('utf-8')
        return self.git.run(arguments, input_data=message, extra_env=env).stdout.decode('ascii').strip()

    def _publish(self, commit_id: str, parent: str | None) -> None:
        arguments = ['update-ref', f'refs/heads/{BRANCH}', commit_id]
        arguments.append(parent or '0' * 40)
        result = self.git.run(arguments, check=False)
        if result.returncode:
            raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')

    def _materialize(self, commit_id: str, parent: str | None, files) -> str:
        try:
            if parent is not None and not self._existing_checkout_matches(parent):
                return 'stale'
            untracked = self.git.run(['ls-files', '--others', '--exclude-standard', '-z']).stdout
            if any(path.decode('utf-8') not in files for path in untracked.split(b'\0') if path):
                return 'stale'
            for path, data in files.items():
                target = controlled_path(self.archive, path)
                if target.exists() and target.read_bytes() != data:
                    return 'stale'
                if not target.exists():
                    write_bytes(self.archive, path, data, immutable=True, conflict_code='ARCHIVE_GIT_DIRTY')
            self.git.run(['read-tree', commit_id])
        except ArchiveError:
            return 'stale'
        return 'current'

    def _existing_checkout_matches(self, parent: str) -> bool:
        result = self.git.run(['ls-tree', '-r', '-z', parent], check=False)
        if result.returncode:
            return False
        if self.git.run(['diff-index', '--cached', '--quiet', parent, '--'], check=False).returncode:
            return False
        for entry in result.stdout.split(b'\0'):
            if not entry:
                continue
            metadata, raw_path = entry.split(b'\t', 1)
            mode, kind, blob = metadata.split()
            if mode != b'100644' or kind != b'blob':
                return False
            path = raw_path.decode('utf-8')
            target = controlled_path(self.archive, path)
            if not target.exists():
                return False
            data = read_bytes(self.archive, path)
            if hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest().encode() != blob:
                return False
        return True
