from project_management.app.domain.captures import ArchiveError
from project_management.storage.paths import validate_uuid


BRANCH = 'main'


def list_report_publication_ids(git, *, limit: int) -> tuple[str, ...]:
    if type(limit) is not int or limit < 1 or limit > 1001:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    parent = git.run(
        ['ls-tree', '-z', '--name-only', BRANCH, 'report_publications'],
        check=False,
        output_limit=len('report_publications') + 2,
    )
    if parent.returncode:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    if not parent.stdout:
        return ()
    if parent.stdout != b'report_publications\x00':
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    result = git.run(
        ['ls-tree', '-z', '--name-only', f'{BRANCH}:report_publications'],
        check=False,
        output_limit=37 * (limit + 1),
        output_limit_code='ARCHIVE_QUOTA_EXCEEDED',
    )
    if result.returncode:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    ids = []
    for raw in result.stdout.split(b'\0'):
        if not raw:
            continue
        path = raw.decode('utf-8')
        parts = path.split('/')
        if len(parts) != 1:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        ids.append(validate_uuid(parts[0]))
        if len(ids) > limit:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
    return tuple(ids)
