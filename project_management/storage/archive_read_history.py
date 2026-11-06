from project_management.app.domain.captures import ArchiveError
from project_management.app.spi.archive_reads import ArchiveRecordLocation
from project_management.storage.git_read_batch import object_id
from project_management.storage.paths import safe_relative_path


MAX_COMMITS = 10000
MAX_HISTORY_BYTES = 16 * 1024 * 1024


def read_history(run, head=None):
    data = run([
        'log', f'--max-count={MAX_COMMITS + 1}', '--format=%x00R%x00%H%x00%P%x00%T%x00',
        '--raw', '--no-abbrev', '-z', '--no-renames', '--root',
        'refs/heads/main' if head is None else object_id(head), '--',
    ], output_limit=MAX_HISTORY_BYTES).stdout
    records = []
    expected = head
    try:
        parts = data.split(b'\x00R\x00')
        if parts[0] != b'' or len(parts) - 1 > MAX_COMMITS:
            raise ValueError
        for part in parts[1:]:
            commit, parents, tree, remainder = part.split(b'\0', 3)
            commit, tree = object_id(commit.decode('ascii')), object_id(tree.decode('ascii'))
            parent = object_id(parents.decode('ascii')) if parents else None
            if records and commit != expected or not records and head is not None and commit != head:
                raise ValueError
            records.append((ArchiveRecordLocation(commit, parent, tree), _changes(remainder)))
            expected = parent
        if not records or expected is not None:
            raise ValueError
    except (ValueError, UnicodeError):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None
    return tuple(records)


def _changes(remainder):
    tokens = [item for item in remainder.lstrip(b'\0\n').split(b'\0') if item]
    if len(tokens) % 2:
        raise ValueError
    changes = {}
    for metadata, raw_path in zip(tokens[::2], tokens[1::2]):
        old_mode, new_mode, old_oid, new_oid, change = metadata.decode('ascii').split(' ')
        old_mode = old_mode.removeprefix(':')
        object_id(old_oid)
        object_id(new_oid)
        if (not metadata.startswith(b':') or old_mode not in {'000000', '100644'}
                or new_mode not in {'000000', '100644'} or change not in {'A', 'M', 'D'}
                or (old_mode == '000000') != (old_oid == '0' * 40)
                or (new_mode == '000000') != (new_oid == '0' * 40)
                or change == 'A' and (old_mode != '000000' or new_mode != '100644')
                or change == 'D' and (old_mode != '100644' or new_mode != '000000')
                or change == 'M' and (old_mode != '100644' or new_mode != '100644')):
            raise ValueError
        path = raw_path.decode('utf-8')
        safe_relative_path(path)
        if path in changes or any(ord(char) < 32 or ord(char) == 127 for char in path):
            raise ValueError
        changes[path] = None if change == 'D' else new_oid
    return changes


def head_tree(history):
    tree, seen = {}, set()
    for _, changes in history:
        for path, oid in changes.items():
            if path not in seen:
                seen.add(path)
                if oid is not None:
                    tree[path] = oid
    return tree


def read_tree(run, commit):
    raw = run(['ls-tree', '-r', '-z', object_id(commit)], output_limit=MAX_HISTORY_BYTES).stdout
    values = {}
    try:
        for item in raw.split(b'\0'):
            if not item:
                continue
            metadata, path = item.split(b'\t', 1)
            mode, kind, oid = metadata.decode('ascii').split(' ')
            path = path.decode('utf-8')
            safe_relative_path(path)
            if mode != '100644' or kind != 'blob' or path in values:
                raise ValueError
            values[path] = object_id(oid)
    except (ValueError, UnicodeError):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None
    return values
