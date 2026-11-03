from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.storage.admission import GrowthEstimate, admit
from project_management.storage.paths import write_bytes
from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario


class TestArchiveAdmissionContract(CaptureArchiveScenario, TestCase):
    def test_other_stage_reservation_counts_toward_root_capacity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pending = root / 'projects/p/stages/s/runtime/pending/c'
            write_bytes(pending, 'reservation.json', canonical_bytes({
                'state': 'reserved', 'remaining_git_bytes': 20 * 1024**2,
                'remaining_git_files': 10, 'sealing_reserve_bytes': 1024**2, 'sealing_reserve_files': 10,
            }))
            with self.assertRaises(ArchiveError):
                admit(root, root / 'projects/other/stages/other', root / 'empty', self.limits(max_root_bytes=8 * 1024**2),
                      GrowthEstimate(1024, 1))

    def test_capture_accounts_referenced_object_bytes_outside_pending_tree(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pending = root / 'projects/p/stages/s/runtime/pending/c'
            for page in ('one', 'two'):
                write_bytes(pending, f'pages/{page}/intent.json', canonical_bytes({'size_bytes': 5 * 1024**2}))
            with self.assertRaises(ArchiveError):
                admit(root, root / 'projects/p/stages/s', pending, self.limits(max_capture_bytes=8 * 1024**2),
                      GrowthEstimate(0, 0))
