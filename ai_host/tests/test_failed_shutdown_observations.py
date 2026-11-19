import json

import pytest

from ai_host.tests.failed_shutdown_observations import ObservationSnapshots, read_observation


def test_publication_does_not_replace_a_snapshot_held_by_reader(tmp_path):
    directory = tmp_path / 'observations'
    writer = ObservationSnapshots(directory)
    writer.publish(seed='original')
    with (directory / '00000001.json').open(encoding='utf-8') as reader:
        writer.publish(ready_for_stop=True)
        assert json.load(reader) == {'seed': 'original'}
        assert read_observation(directory) == {'seed': 'original', 'ready_for_stop': True}
    assert len(list(directory.glob('*.json'))) == 2


def test_incomplete_latest_snapshot_is_not_replaced_by_stale_success(tmp_path):
    directory = tmp_path / 'observations'
    writer = ObservationSnapshots(directory)
    writer.publish(ready_for_stop=True)
    (directory / '00000002.json').write_text('{"stop":', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        read_observation(directory)


def test_existing_observation_set_cannot_be_overwritten(tmp_path):
    directory = tmp_path / 'observations'
    writer = ObservationSnapshots(directory)
    writer.publish(seed='preserved')
    with pytest.raises(FileExistsError):
        ObservationSnapshots(directory)
    assert read_observation(directory) == {'seed': 'preserved'}


def test_no_snapshot_is_not_ready(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_observation(tmp_path)
