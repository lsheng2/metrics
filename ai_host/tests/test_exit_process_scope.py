import ctypes
from types import SimpleNamespace

import pytest

from ai_host import exit_processes


class Snapshot:
    def __init__(self, parents):
        self.entries = iter(parents.items())
        self.closed = []

    def CreateToolhelp32Snapshot(self, flags, pid):
        assert flags == 2 and pid == 0
        return 901

    def Process32FirstW(self, snapshot, pointer):
        return self.Process32NextW(snapshot, pointer)

    def Process32NextW(self, snapshot, pointer):
        assert snapshot == 901
        try:
            pid, parent = next(self.entries)
        except StopIteration:
            ctypes.set_last_error(18)
            return False
        pointer._obj.th32ProcessID = pid
        pointer._obj.th32ParentProcessID = parent
        pointer._obj.szExeFile = f'process-{pid}.exe'
        return True

    def CloseHandle(self, handle):
        self.closed.append(handle)


def install_inventory(monkeypatch, times):
    snapshot = Snapshot({100: 1, 200: 100, 201: 200, 202: 201, 300: 100})
    queried = []

    def created_at(api, pid):
        assert api is snapshot
        queried.append(pid)
        value = times[pid]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(exit_processes, '_windows_api', lambda: snapshot)
    monkeypatch.setattr(exit_processes, '_created_at', created_at)
    monkeypatch.setattr(exit_processes, 'os', SimpleNamespace(getpid=lambda: 100))
    return snapshot, queried


def test_explicit_root_does_not_inspect_unreadable_sibling(monkeypatch):
    snapshot, queried = install_inventory(monkeypatch, {
        100: 10, 200: 20, 201: 30, 202: 40, 300: PermissionError('unrelated sibling'),
    })
    assert exit_processes.living_children(root_pid=200) == [
        {'pid': 201, 'parent_pid': 200, 'created': 30},
        {'pid': 202, 'parent_pid': 201, 'created': 40},
    ]
    assert queried == [200, 201, 202]
    assert snapshot.closed == [901]


def test_default_root_still_refuses_unobservable_owned_process(monkeypatch):
    install_inventory(monkeypatch, {
        100: 10, 200: 20, 201: 30, 202: 40, 300: PermissionError('owned sibling'),
    })
    with pytest.raises(PermissionError, match='owned sibling'):
        exit_processes.living_children()


def test_explicit_root_preserves_owned_child_access_errors(monkeypatch):
    install_inventory(monkeypatch, {200: 20, 201: PermissionError('owned child')})
    with pytest.raises(PermissionError, match='owned child') as raised:
        exit_processes.living_children(root_pid=200)
    assert any('root PID 200' in note and 'process-201.exe' in note for note in raised.value.__notes__)


@pytest.mark.parametrize('child_started', [None, 15])
def test_exited_or_reused_parent_cannot_adopt_descendants(monkeypatch, child_started):
    _, queried = install_inventory(monkeypatch, {200: 20, 201: child_started})
    assert exit_processes.living_children(root_pid=200) == []
    assert queried == [200, 201]


def test_disappeared_root_is_not_a_clean_empty_inventory(monkeypatch):
    install_inventory(monkeypatch, {200: None})
    with pytest.raises(ProcessLookupError, match='200'):
        exit_processes.living_children(root_pid=200)


@pytest.mark.parametrize('root_pid', [0, -1, True, '200'])
def test_invalid_root_is_rejected_before_native_inspection(monkeypatch, root_pid):
    def forbidden():
        raise AssertionError('invalid root reached native API')

    monkeypatch.setattr(exit_processes, '_windows_api', forbidden)
    with pytest.raises(ValueError, match='root_pid'):
        exit_processes.living_children(root_pid=root_pid)


def test_access_denied_preserves_error_and_identifies_pid():
    def denied(*args):
        ctypes.set_last_error(5)
        return 0

    with pytest.raises(PermissionError) as raised:
        exit_processes._created_at(SimpleNamespace(OpenProcess=denied), 4521)
    assert raised.value.winerror == 5
    assert any('4521' in note for note in getattr(raised.value, '__notes__', []))
