import unittest

from scripts.validation.project_summary_support import worker_record_matches


class TestProjectSummarySupport(unittest.TestCase):
    def test_shouldMatchWorkerToKernelParentAndExactFixtureArguments(self):
        command = ['D:/venv/python.exe', '-I', 'D:/fixture.py', '--run-dir', 'D:/owned']
        record = {
            'ProcessId': 124,
            'ParentProcessId': 123,
            'ExecutablePath': 'C:/Python314/python.exe',
            'CommandLine': '"C:/Python314/python.exe" -I D:/fixture.py --run-dir D:/owned',
        }
        self.assertTrue(worker_record_matches(record, 124, 123, command))
        self.assertFalse(worker_record_matches({**record, 'ParentProcessId': 999}, 124, 123, command))
        self.assertFalse(worker_record_matches(
            {**record, 'CommandLine': record['CommandLine'].replace('D:/owned', 'D:/another')},
            124,
            123,
            command,
        ))
