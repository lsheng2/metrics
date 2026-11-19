"""Test IPC snapshots: never replace a file held by a Windows reader."""
import json
from pathlib import Path
import threading


class ObservationSnapshots:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True)
        self._state = {}
        self._sequence = 0
        self._lock = threading.Lock()

    def publish(self, **values):
        with self._lock:
            self._state.update(values)
            self._sequence += 1
            path = self.directory / f'{self._sequence:08d}.json'
            with path.open('x', encoding='utf-8') as stream:
                json.dump(self._state, stream, sort_keys=True, indent=2)


def read_observation(directory):
    latest = max(Path(directory).glob('*.json'), default=None)
    if latest is None:
        raise FileNotFoundError(f'No observation snapshot in {directory}')
    return json.loads(latest.read_text(encoding='utf-8'))
