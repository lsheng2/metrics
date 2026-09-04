from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import (
    LifecycleState,
    PlatformOperationSet,
    ProvenanceCapability,
    ServiceLifecycleEngine,
    ServiceSpec,
    StopSource,
    capture_process_provenance,
)


def test_conformance_shouldPersistOwnedListenerProvenanceForWrapperListenerSplit(tmp_path):
    events = []
    store = InMemoryStateStore()
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(111),
        process_exists=lambda pid: pid in {111, 222},
        process_matches_command=lambda pid, command: pid == 111,
        process_command_line=lambda pid: "python wrapper.py" if pid == 111 else "python listener.py",
        process_start_marker=lambda pid: f"started:{pid}",
        get_listening_process_ids=lambda host, port: (222,),
        process_group_id=lambda pid: 7 if pid in {111, 222} else None,
        http_status_ok=lambda url: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations, state_store=store, event_handler=events.append)
    spec = ServiceSpec.from_values("api", [8100], ["python", "wrapper.py"], health_url="http://{host}:{port}/health")

    lifecycle.start_service(spec, port=8100)

    state = lifecycle.read_state()["api"]
    assert state["lifecycle_state"] == LifecycleState.READY.value
    assert state["provenance"]["wrapper_pid"] == 111
    assert state["provenance"]["listener_pid"] == 222
    assert state["provenance"]["capability"] == ProvenanceCapability.ENDPOINT_GRADE.value
    assert events[-1].provenance.listener_pid == 222


def test_conformance_shouldNotTreatStaleRegisteredPidAsOwnedWhenCommandDiffers(tmp_path):
    stopped_pids = []
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(222),
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: pid == 222,
        process_command_line=lambda pid: "python new-api.py",
        process_start_marker=lambda pid: f"started:{pid}",
        terminate_process=lambda pid: stopped_pids.append(pid),
        http_status_ok=lambda url: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "pid": 111,
            "port": 8100,
            "host": "127.0.0.1",
            "command": ["python", "old-api.py"],
            "lifecycle_state": "ready",
        }
    })
    spec = ServiceSpec.from_values("api", [8100], ["python", "new-api.py"], health_url="http://{host}:{port}/health")

    state = lifecycle.start_service(spec, port=8100)

    assert state.pid == 222
    assert stopped_pids == []


def test_conformance_shouldResolveEndpointGradeProvenanceForSoleReachableListener():
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 222,
        process_matches_command=lambda pid, command: False,
        process_command_line=lambda pid: "",
        process_start_marker=lambda pid: "",
        get_listening_process_ids=lambda host, port: (222,),
        http_status_ok=lambda url: True,
    )

    provenance = capture_process_provenance(operations, 111, ("python", "wrapper.py"), "127.0.0.1", 8100, health_url="http://127.0.0.1:8100/health")

    assert provenance.wrapper_pid == 111
    assert provenance.listener_pid == 222
    assert provenance.capability == ProvenanceCapability.ENDPOINT_GRADE


def test_conformance_shouldUseInjectedStateStoreForSnapshotsAndLedgers(tmp_path):
    store = InMemoryStateStore()
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(111),
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_command_line=lambda pid: "python api.py",
        process_start_marker=lambda pid: "started:111",
        http_status_ok=lambda url: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations, state_store=store)
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"], health_url="http://{host}:{port}/health")

    lifecycle.start_service(spec, port=8100)
    lifecycle.write_startup_record("adapter-check", 0.1, "completed", run_id="run-1")

    assert store.writes
    assert any(record.get("event") == "step_timing" for _, record in store.ledgers)
    assert "project:default:state" in store.locked_keys
    assert "project:default:startup-ledger" in store.locked_keys


def test_conformance_shouldKeepForceRequestSeparateFromKillEscalation(tmp_path):
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        terminate_process=lambda pid: None,
        wait_process_exit=lambda pid, timeout: True,
        get_listening_process_ids=lambda host, port: (777,),
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"])

    result = lifecycle.force_stop_by_ports((spec,), graceful_timeout_seconds=0.1)[0]

    assert result.stop_source == StopSource.FORCE_BY_PORT
    assert result.force_requested is True
    assert result.forced is False
    assert result.reason == "force_by_port:terminated"


class InMemoryStateStore:
    schema_version = 1

    def __init__(self):
        self.payloads = {}
        self.writes = []
        self.ledgers = []
        self.locked_keys = []

    def read_json(self, path):
        return dict(self.payloads[str(path)])

    def exists(self, path):
        return str(path) in self.payloads

    def write_json_atomic(self, path, payload):
        stored = {"schema_version": self.schema_version, **dict(payload)}
        self.payloads[str(path)] = stored
        self.writes.append((str(path), stored))

    def append_jsonl(self, path, record):
        self.ledgers.append((str(path), dict(record)))

    def lock(self, key):
        self.locked_keys.append(key)
        return NullLock()


class NullLock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeProcess:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None
