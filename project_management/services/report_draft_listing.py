import stat
from contextlib import nullcontext

from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import (
    ReportDraftPage,
    ReportDraftSummary,
    ReportPublicationPage,
    validate_uuid_text,
)
from project_management.services.report_publication_reads import ReportPublicationReader, prefetch_publications
from project_management.app.domain.report_publication_contracts import finalization_from_mapping
from project_management.app.domain.report_draft_values import read_json
from project_management.storage.paths import read_bytes


MAX_LIST_IDENTITIES = 1000
LIST_LOOKAHEAD = MAX_LIST_IDENTITIES + 1


class ReportDraftListingMixin:
    def list_drafts(self, actor, project_id, stage_id, *, limit=20, offset=0, _read_view=None):
        self._validate_page(limit, offset)
        try:
            with (nullcontext(_read_view) if _read_view is not None else
                  self.archive._report_repository(actor, project_id, stage_id, write=False)) as repository:
                store = self._store(repository)
                root = repository.runtime / 'report-drafts'
                draft_ids = self._draft_ids(root)
                selected = draft_ids[offset:offset + limit]
                prefetch_publications(repository, draft_publication_ids(store, selected))
                items = tuple(self._draft_summary(item) for item in repository.map_reads(store.read_draft, selected))
                return ReportDraftPage(items, self._next_offset(len(draft_ids), limit, offset))
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def list_publications(self, actor, project_id, stage_id, *, limit=20, offset=0, _read_view=None):
        self._validate_page(limit, offset)
        try:
            with (nullcontext(_read_view) if _read_view is not None else
                  self.archive._report_repository(actor, project_id, stage_id, write=False)) as repository:
                publication_ids = self._publication_ids(repository)
                reader = ReportPublicationReader(repository)
                selected = publication_ids[offset:offset + limit]
                prefetch_publications(repository, selected)
                items = tuple(reader.get(publication_id, actor.subject) for publication_id in selected)
                return ReportPublicationPage(items, self._next_offset(len(publication_ids), limit, offset))
        except (ArchiveError, ProjectError) as error:
            raise self._report_error(error, missing_as_not_found=True) from None

    def _publication_ids(self, repository):
        return self._validated_ids(repository.list_report_publication_ids(limit=LIST_LOOKAHEAD))

    def _draft_ids(self, root):
        if not root.exists():
            return ()
        self._validate_directory(root)
        ids = []
        try:
            for path in root.iterdir():
                info = path.lstat()
                if (path.is_symlink()
                        or not stat.S_ISDIR(info.st_mode)
                        or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
                    raise ArchiveError('UNSAFE_PATH')
                ids.append(path.name)
                if len(ids) > MAX_LIST_IDENTITIES:
                    break
        except OSError:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
        return self._validated_ids(ids)

    def _validate_directory(self, path):
        try:
            resolved = path.resolve()
            info = path.lstat()
        except OSError:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None
        if (path.is_symlink()
                or not stat.S_ISDIR(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
            raise ArchiveError('UNSAFE_PATH')
        runtime = path.parent.resolve()
        if not resolved.is_relative_to(runtime):
            raise ArchiveError('UNSAFE_PATH')

    def _validated_ids(self, values):
        try:
            ids = []
            for value in values:
                ids.append(validate_uuid_text(value))
                if len(ids) > MAX_LIST_IDENTITIES:
                    break
        except ReportError as error:
            raise ReportError('REPORT_ARTIFACT_INVALID') from error
        if len(ids) > MAX_LIST_IDENTITIES:
            raise ReportError('REPORT_LIMIT')
        return tuple(sorted(ids))

    def _draft_summary(self, draft):
        return ReportDraftSummary(
            draft.draft_id,
            draft.revision,
            draft.revision_hash,
            draft.snapshot.source_as_of,
            draft.updated_at,
            draft.state,
            draft.template.template_id,
            draft.parent_publication_id,
            draft.preservation_review_issues,
        )

    def _validate_page(self, limit, offset):
        if type(limit) is not int or type(offset) is not int:
            raise ReportError('REPORT_INVALID')
        if limit < 1 or limit > 100 or offset < 0:
            raise ReportError('REPORT_INVALID')

    def _next_offset(self, total, limit, offset):
        next_offset = offset + limit
        return next_offset if next_offset < total else None


def draft_publication_ids(store, draft_ids):
    result = []
    for draft_id in draft_ids:
        root = store.root(draft_id)
        if (root / 'finalization.json').exists():
            value = finalization_from_mapping(read_json(read_bytes(root, 'finalization.json')))
            if value['draft_id'] != draft_id:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
            result.append(value['publication_id'])
    return tuple(result)
