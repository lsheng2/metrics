from dataclasses import dataclass
from pathlib import Path

from project_management.app.domain.capture_values import canonical_bytes, decode_json, limits_hash
from project_management.app.domain.captures import ArchiveError, ArchiveLimits
from project_management.storage.paths import read_bytes, tree_usage, write_bytes


@dataclass(frozen=True, slots=True)
class GrowthEstimate:
    bytes: int
    files: int


def admit_initialization(root, stage, limits):
    root_bytes, root_files = tree_usage(root)
    stage_bytes, stage_files = tree_usage(stage)
    if (root_bytes + 1024**2 > limits.max_root_bytes or root_files + 32 > limits.max_root_files
            or stage_bytes + 1024**2 > limits.max_stage_bytes or stage_files + 32 > limits.max_stage_files):
        raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')


def page_growth(payload_size: int) -> GrowthEstimate:
    return GrowthEstimate(payload_size + 1024 * 1024 + 8 * 1024 * 4, 8)


def finalize_growth(file_count: int, bytes_count: int) -> GrowthEstimate:
    return GrowthEstimate(bytes_count + 1024 * 1024 + file_count * 8 * 1024, 8 + file_count * 4)


def admit(root: Path, stage_root: Path, capture_root: Path, limits: ArchiveLimits, growth: GrowthEstimate,
          *, consume_reserved=False) -> None:
    root_bytes, root_files = tree_usage(root)
    stage_bytes, stage_files = tree_usage(stage_root)
    capture_bytes, capture_files = tree_usage(capture_root)
    logical_bytes, logical_files = referenced_usage(capture_root)
    root_reserve = stage_reserve = capture_reserve = 0
    root_file_reserve = stage_file_reserve = capture_file_reserve = 0
    for directory in root.glob('projects/*/stages/*/runtime/pending/*'):
        if consume_reserved and directory == capture_root:
            continue
        reserve_bytes, reserve_files = outstanding(directory)
        root_reserve += reserve_bytes
        root_file_reserve += reserve_files
        if directory.is_relative_to(stage_root):
            stage_reserve += reserve_bytes
            stage_file_reserve += reserve_files
        if directory == capture_root:
            capture_reserve += reserve_bytes
            capture_file_reserve += reserve_files
    if (
        root_bytes + root_reserve + growth.bytes > limits.max_root_bytes
        or root_files + root_file_reserve + growth.files > limits.max_root_files
        or stage_bytes + stage_reserve + growth.bytes > limits.max_stage_bytes
        or stage_files + stage_file_reserve + growth.files > limits.max_stage_files
        or capture_bytes + logical_bytes + capture_reserve + growth.bytes > limits.max_capture_bytes
        or capture_files + logical_files + capture_file_reserve + growth.files > limits.max_capture_files
    ):
        raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')


def write_reservation(capture_root: Path, limits: ArchiveLimits, state: str, admitted_pages: int, remaining_git_bytes: int, remaining_git_files: int) -> None:
    snapshots = tuple((capture_root / 'snapshots').glob('*.json'))
    snapshot_bytes = sum(path.stat().st_size for path in snapshots)
    stage = capture_root.parents[2]
    root = stage.parents[3]
    intent = decode_json(read_bytes(capture_root, 'intent.json'))
    payload = {
        'schema_version': 1,
        'intent_hash': intent['intent_hash'],
        'limits_hash': limits_hash(limits),
        'admitted_page_count': admitted_pages,
        'actual_root_usage': tree_usage(root),
        'actual_stage_usage': tree_usage(stage),
        'remaining_git_bytes': remaining_git_bytes + snapshot_bytes + 8192 * (len(snapshots) + admitted_pages) if state == 'reserved' else 0,
        'remaining_git_files': 2 * (len(snapshots) + admitted_pages + 2) + remaining_git_files if state == 'reserved' else 0,
        'sealing_reserve_bytes': max(1024 * 1024, 64 * 1024 * admitted_pages) if state == 'reserved' else 0,
        'sealing_reserve_files': 8 + 4 * admitted_pages + 2 * len(snapshots) if state == 'reserved' else 0,
        'state': state,
    }
    write_bytes(capture_root, 'reservation.json', canonical_bytes(payload))


def referenced_usage(capture_root):
    total = 0
    count = 0
    for path in (capture_root / 'pages').glob('*/intent.json'):
        value = decode_json(read_bytes(capture_root, path.relative_to(capture_root).as_posix()))
        size = value.get('size_bytes')
        if type(size) is not int or size < 0:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        total += size
        count += 1
    return total, count


def outstanding(directory):
    if not (directory / 'reservation.json').exists():
        if not (directory / 'intent.json').exists():
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        raw, pages = referenced_usage(directory)
        physical, files = tree_usage(directory)
        return max(2 * 1024**2, raw + physical + files * 8192), 16 + files * 2 + pages * 4
    value = decode_json(read_bytes(directory, 'reservation.json'))
    if value.get('state') not in {'settled', 'reserved'}:
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    fields = ('remaining_git_bytes', 'sealing_reserve_bytes', 'remaining_git_files', 'sealing_reserve_files')
    if any(type(value.get(key)) is not int or value[key] < 0 for key in fields):
        raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
    return value[fields[0]] + value[fields[1]], value[fields[2]] + value[fields[3]]
