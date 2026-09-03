from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Mapping, Protocol

from .models import LifecycleStateStoreError


class LifecycleStateStore(Protocol):
    def read_json(self, path: str | Path) -> dict[str, object]:
        ...

    def write_json_atomic(self, path: str | Path, payload: Mapping[str, object]) -> None:
        ...

    def append_jsonl(self, path: str | Path, record: Mapping[str, object]) -> None:
        ...

    def lock(self, key: str) -> Iterator[None]:
        ...


class FilesystemLifecycleStateStore:
    schema_version = 1

    def __init__(self, base_directory: str | Path) -> None:
        self.base_directory = Path(base_directory)
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.RLock()

    def state_path(self, project_name: str, instance_name: str, service_name: str) -> Path:
        return self.base_directory / "services" / f"{project_name}-{instance_name}-{service_name}.json"

    def ledger_path(self, name: str) -> Path:
        return self.base_directory / f"{name}.jsonl"

    def lock_key(self, project_name: str, instance_name: str, service_name: str) -> str:
        return f"{project_name}:{instance_name}:{service_name}"

    @contextmanager
    def lock(self, key: str) -> Iterator[None]:
        lock = self._lock_for(key)
        with lock:
            yield

    def read_json(self, path: str | Path) -> dict[str, object]:
        state_path = Path(path)
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise LifecycleStateStoreError(f"Lifecycle state is corrupt: {state_path}", "state_corrupt") from error
        except OSError as error:
            raise LifecycleStateStoreError(f"Lifecycle state is unavailable: {state_path}", "state_unavailable") from error
        if not isinstance(payload, dict):
            raise LifecycleStateStoreError(f"Lifecycle state is not an object: {state_path}", "state_corrupt")
        schema_version = payload.get("schema_version")
        if schema_version != self.schema_version:
            raise LifecycleStateStoreError(f"Unsupported lifecycle state schema: {schema_version}", "unsupported_schema")
        return dict(payload)

    def write_json_atomic(self, path: str | Path, payload: Mapping[str, object]) -> None:
        state_path = Path(path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        payload_with_schema = {"schema_version": self.schema_version, **dict(payload)}
        temp_path = state_path.with_name(f"{state_path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
        temp_path.write_text(json.dumps(payload_with_schema, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, state_path)

    def append_jsonl(self, path: str | Path, record: Mapping[str, object]) -> None:
        ledger_path = Path(path)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps(dict(record), sort_keys=True) + "\n")

    def _lock_for(self, key: str) -> threading.RLock:
        with self._locks_guard:
            if key not in self._locks:
                self._locks[key] = threading.RLock()
            return self._locks[key]
