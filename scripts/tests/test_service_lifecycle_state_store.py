from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import FilesystemLifecycleStateStore, LifecycleStateStoreError


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
