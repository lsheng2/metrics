from __future__ import annotations

import json
import multiprocessing
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import (
    FilesystemLifecycleStateStore,
    LifecycleStateStoreError,
    PlatformOperationSet,
    ProcessProvenance,
    ProvenanceCapability,
    ServiceLifecycleEngine,
    ServiceSpec,
    ServiceState,
    StopResult,
)


def test_shouldIsolateStatePathsByProjectInstanceAndService(tmp_path):
    store = FilesystemLifecycleStateStore(tmp_path)

    first = store.state_path("project", "one", "api")
    second = store.state_path("project", "two", "api")

    assert first != second
    assert first.name == "project-one-api.json"
    assert second.name == "project-two-api.json"


def test_shouldWriteAndReadSchemaVersionedStateAtomically(tmp_path):
    store = FilesystemLifecycleStateStore(tmp_path)
    path = store.state_path("project", "default", "api")

    store.write_json_atomic(path, {"service": "api"})

    assert store.read_json(path) == {"schema_version": 1, "service": "api"}


def test_shouldAppendLedgerRecordsInOrder(tmp_path):
    store = FilesystemLifecycleStateStore(tmp_path)
    path = store.ledger_path("termination-ledger")

    store.append_jsonl(path, {"sequence": 1})
    store.append_jsonl(path, {"sequence": 2})

    assert [json.loads(line)["sequence"] for line in path.read_text(encoding="utf-8").splitlines()] == [1, 2]


def test_shouldShareFilesystemLocksAcrossStoreInstances(tmp_path):
    first = FilesystemLifecycleStateStore(tmp_path)
    second = FilesystemLifecycleStateStore(tmp_path)

    assert first._lock_for("project:default:state") is second._lock_for("project:default:state")


def test_shouldShareFilesystemLocksAcrossProcesses(tmp_path):
    state_directory = tmp_path / "state"
    first = multiprocessing.Process(target=write_service_in_separate_process, args=(state_directory, "api", 8100))
    second = multiprocessing.Process(target=write_service_in_separate_process, args=(state_directory, "worker", 8200))

    first.start()
    second.start()
    first.join(20)
    second.join(20)

    assert first.exitcode == 0
    assert second.exitcode == 0
    payload = json.loads((state_directory / "project-default.json").read_text(encoding="utf-8"))
    assert set(payload["services"]) == {"api", "worker"}


def test_shouldFailClosedWhenStateIsCorrupt(tmp_path):
    store = FilesystemLifecycleStateStore(tmp_path)
    path = store.state_path("project", "default", "api")
    path.parent.mkdir(parents=True)
    path.write_text("{", encoding="utf-8")

    try:
        store.read_json(path)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("corrupt state should fail closed")
    assert path.exists()


def test_shouldRejectUnsupportedSchemaVersion(tmp_path):
    store = FilesystemLifecycleStateStore(tmp_path)
    path = store.state_path("project", "default", "api")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")

    try:
        store.read_json(path)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "unsupported_schema"
    else:
        raise AssertionError("unsupported schema should fail closed")


def test_engine_shouldFailClosedWhenServicesPayloadIsNotMapping(tmp_path):
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.state_file.write_text(json.dumps({"schema_version": 1, "services": []}), encoding="utf-8")

    try:
        lifecycle.stop_all(graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("semantic corrupt services payload should fail closed")
    assert lifecycle.state_file.exists()


def test_engine_shouldFailClosedWhenServiceRecordIsNotMapping(tmp_path):
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.state_file.write_text(json.dumps({"schema_version": 1, "services": {"api": []}}), encoding="utf-8")

    try:
        lifecycle.stop_all(graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("semantic corrupt service record should fail closed")
    assert lifecycle.state_file.exists()


def test_engine_shouldFailClosedWhenServiceRecordMissesRequiredFields(tmp_path):
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.state_file.write_text(json.dumps({"schema_version": 1, "services": {"api": {"pid": 12345}}}), encoding="utf-8")

    try:
        lifecycle.stop_all(graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("service record missing required fields should fail closed")
    assert lifecycle.state_file.exists()


def test_engine_shouldFailClosedWhenServiceRecordHasInvalidLifecycleState(tmp_path):
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.state_file.write_text(
        json.dumps({"schema_version": 1, "services": {"api": {"pid": 12345, "port": 8100, "lifecycle_state": "future"}}}),
        encoding="utf-8",
    )

    try:
        lifecycle.stop_all(graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("service record with invalid lifecycle_state should fail closed")
    assert lifecycle.state_file.exists()


def test_engine_shouldFailClosedWhenServiceRecordHasInvalidProvenance(tmp_path):
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.state_file.write_text(
        json.dumps({
            "schema_version": 1,
            "services": {
                "api": {
                    "pid": 12345,
                    "port": 8100,
                    "lifecycle_state": "ready",
                    "provenance": {"wrapper_pid": "not-an-int"},
                }
            },
        }),
        encoding="utf-8",
    )

    try:
        lifecycle.stop_all(graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("service record with invalid provenance should fail closed")
    assert lifecycle.state_file.exists()


def test_engine_shouldFailClosedWhenServiceRecordHasNonMappingProvenance(tmp_path):
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.state_file.write_text(
        json.dumps({
            "schema_version": 1,
            "services": {
                "api": {
                    "pid": 12345,
                    "port": 8100,
                    "lifecycle_state": "ready",
                    "provenance": "not-a-mapping",
                }
            },
        }),
        encoding="utf-8",
    )

    try:
        lifecycle.stop_all(graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("service record with non-mapping provenance should fail closed")
    assert lifecycle.state_file.exists()


def test_engine_shouldFailClosedWhenServiceRecordHasUnknownProvenanceCapability(tmp_path):
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state")
    lifecycle.state_file.write_text(
        json.dumps({
            "schema_version": 1,
            "services": {
                "api": {
                    "pid": 12345,
                    "port": 8100,
                    "lifecycle_state": "ready",
                    "provenance": {
                        "wrapper_pid": 12345,
                        "capability": "future_capability",
                    },
                }
            },
        }),
        encoding="utf-8",
    )

    try:
        lifecycle.stop_all(graceful_timeout_seconds=0.1)
    except LifecycleStateStoreError as error:
        assert error.failure_kind == "state_corrupt"
    else:
        raise AssertionError("service record with unknown provenance capability should fail closed")
    assert lifecycle.state_file.exists()


def test_engine_shouldNotDeleteFilesystemStateWhenCustomStoreIsInjected(tmp_path):
    store = InMemoryStateStore()
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", state_store=store)
    lifecycle.state_file.parent.mkdir(parents=True, exist_ok=True)
    lifecycle.state_file.write_text(json.dumps({"schema_version": 1, "services": {"api": {"pid": 1, "port": 1, "lifecycle_state": "ready"}}}), encoding="utf-8")

    results = lifecycle.stop_all(graceful_timeout_seconds=0.1)

    assert results == []
    assert lifecycle.state_file.exists()


def test_engine_shouldWriteJsonPrimitiveServiceStateToCustomStore(tmp_path):
    store = JsonRoundTripStateStore()
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(12345),
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_command_line=lambda pid: "python api.py",
        process_start_marker=lambda pid: "started:12345",
        http_status_ok=lambda url: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", state_store=store, platform_ops=operations)
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"], health_url="http://{host}:{port}/health")

    state = lifecycle.start_service(spec, port=8100)

    persisted_state = lifecycle.read_state()["api"]
    assert state.lifecycle_state.value == "ready"
    assert persisted_state["lifecycle_state"] == "ready"
    assert persisted_state["provenance"]["capability"] == "registered_process"


def test_engine_shouldWritePrimitiveServiceStateToNonNormalizingCustomStore(tmp_path):
    store = InMemoryStateStore()
    operations = PlatformOperationSet(
        start_process=lambda *args, **kwargs: FakeProcess(12345),
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        process_command_line=lambda pid: "python api.py",
        process_start_marker=lambda pid: "started:12345",
        http_status_ok=lambda url: True,
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", state_store=store, platform_ops=operations)
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"], health_url="http://{host}:{port}/health")

    lifecycle.start_service(spec, port=8100)

    persisted_state = lifecycle.read_state()["api"]
    assert persisted_state["lifecycle_state"] == "ready"
    assert persisted_state["provenance"]["capability"] == "registered_process"


def test_engine_shouldWritePrimitiveTerminationProvenanceToNonNormalizingCustomStore(tmp_path):
    store = InMemoryStateStore()
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", state_store=store)
    provenance = ProcessProvenance(wrapper_pid=12345, listener_pid=12345, capability=ProvenanceCapability.REGISTERED_PROCESS)

    lifecycle.write_termination_record(StopResult("api", 8100, 12345, True, False, "terminated", provenance=provenance))

    termination_records = [record for _, record in store.ledgers if "reason" in record]
    assert termination_records[0]["provenance"]["capability"] == "registered_process"


def test_engine_shouldReportListenerIdentityChangedInDiagnostics(tmp_path):
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        http_status_ok=lambda url: True,
        http_probe=lambda url: {"body_sha256": "observed"},
    )
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", platform_ops=operations)
    lifecycle.write_state({
        "api": {
            "pid": 12345,
            "port": 8100,
            "lifecycle_state": "ready",
            "command": ["python", "api.py"],
            "health_url": "http://127.0.0.1:8100/health",
            "listener_identity_url": "http://127.0.0.1:8100/identity",
            "listener_identity_fingerprint": "expected",
            "provenance": {
                "wrapper_pid": 12345,
                "listener_pid": 12345,
                "capability": "http_identity",
            },
        }
    })
    spec = ServiceSpec.from_values("api", [8100], ["python", "api.py"])

    diagnostics = lifecycle.diagnose_services((spec,))

    assert diagnostics[0]["status"] == "listener_identity_changed"
    assert diagnostics[0]["provenance"]["capability"] == "http_identity"


def test_engine_shouldUseInjectedStateStoreForSnapshotsAndLedgers(tmp_path):
    store = InMemoryStateStore()
    lifecycle = ServiceLifecycleEngine("project", tmp_path, state_directory=tmp_path / "state", state_store=store)

    lifecycle.write_state({"api": {"pid": 12345, "port": 8100, "lifecycle_state": "ready"}})
    lifecycle.write_startup_record("start:api", 0.1, "completed", run_id="run-1")
    lifecycle.write_termination_record(StopResult("api", 8100, 12345, True, False, "terminated"))

    assert lifecycle.read_state()["api"]["port"] == 8100
    assert len(store.writes) == 1
    assert [record["event"] for _, record in store.ledgers if "event" in record] == ["step_timing"]
    assert [record["reason"] for _, record in store.ledgers if "reason" in record] == ["terminated"]
    assert "project:default:state" in store.locked_keys
    assert "project:default:startup-ledger" in store.locked_keys
    assert "project:default:termination-ledger" in store.locked_keys


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


class JsonRoundTripStateStore(InMemoryStateStore):
    def write_json_atomic(self, path, payload):
        stored = json.loads(json.dumps({"schema_version": self.schema_version, **dict(payload)}))
        self.payloads[str(path)] = stored
        self.writes.append((str(path), stored))


class FakeProcess:
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        return None


def write_service_in_separate_process(state_directory: Path, service_name: str, port: int) -> None:
    lifecycle = ServiceLifecycleEngine("project", state_directory.parent, state_directory=state_directory)
    lifecycle._write_service_state(
        ServiceState(
            service_name,
            "127.0.0.1",
            port,
            port,
            ("python", service_name),
            "now",
            "out",
            "err",
            "authority",
            (),
            None,
            None,
            None,
            0.0,
        )
    )
