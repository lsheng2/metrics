"""Native serve entry for failed runtime-store shutdown recovery proof."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ai_host.exit_inventory import install_exit_capture

install_exit_capture()

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from importlib import metadata
import hashlib
import inspect
import json
import threading
import time
from urllib.parse import urlsplit

from ai_host.tests.runtime_recovery_entry import terminal, wire
from ai_host.tests.failed_shutdown_observations import ObservationSnapshots
from ai_host.tests.serve_test_entry import main


CLIENT_RUN_KEY = "failed-stop-task"
CLIENT_MESSAGE_KEY = "failed-stop-chat"
SESSION_KEY = "conformance.failed-stop"
PRINCIPAL_ID = "failed-stop-owner"
PROOF_FILE = "failed-shutdown-state.json"
_OBSERVATIONS = None


def write_observation(**values):
    _OBSERVATIONS.publish(**values)


def configure(temp):
    endpoint = sys.argv[6]
    if urlsplit(endpoint).hostname != "127.0.0.1":
        raise ValueError("Synthetic model must use loopback")
    root = Path(sys.argv[1])
    return {
        "METRICS_STATE_DIR": str(root / "durable-state"),
        "DATABASES": {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(root / "catalog.sqlite3")}},
        "METRICS_AI_MODEL_BASE_URL": endpoint,
        "METRICS_AI_MODEL_NAME": "scripted",
        "METRICS_AI_MODEL_API_KEY": "scripted-test-key",
    }


def runtime_identity(handle):
    store = handle._runtime._store
    assert store is not None, "runtime store is not open"
    resources_path = Path(inspect.getfile(type(store))).resolve()
    return {
        "runtime_version": metadata.version("ai-base-runtime"),
        "resources_path": str(resources_path),
        "resources_sha256": hashlib.sha256(resources_path.read_bytes()).hexdigest(),
    }


def request_for(deadline):
    from ai_base_runtime.apps import RunSubmit
    from ai_base_runtime.contracts import canonical_digest

    content = {"number": 7}
    return RunSubmit(
        app_id="conformance", profile_id="conformance.summary", profile_version="1",
        input=content, input_sha256=canonical_digest(content), client_run_key=CLIENT_RUN_KEY,
        deadline_at=deadline, limits={}, minimum_result_retention_seconds=600,
    )


def principal():
    from ai_base_runtime.spi import Principal

    return Principal(id=PRINCIPAL_ID, display_name="Synthetic Failed Stop Owner")


def context_ref():
    from ai_base_runtime.apps import ContextRef

    return ContextRef("conformance.item", {"id": "one"})


def seed_public_state(handle, state):
    from ai_base_runtime.apps import ChatMessageRequest

    owner = principal()
    deadline = datetime.now(timezone.utc) + timedelta(seconds=120)
    ports = handle.blocking
    request = request_for(deadline)
    admitted = ports.task_runs.start(owner, request, timeout=3)
    terminal(ports.task_runs, owner, admitted.run_id)
    session = ports.chat.open_session(
        owner, app_id="conformance", agent="agent", session_key=SESSION_KEY,
        context_ref=context_ref(), timeout=3,
    )
    chat = ports.chat.message(owner, ChatMessageRequest(
        session_id=session.session_id, content="Apply the synthetic change.",
        client_message_key=CLIENT_MESSAGE_KEY, deadline_at=deadline,
    ), timeout=3)
    wait_until = time.monotonic() + 15
    while not (pending := ports.approvals.list_pending(owner, app_id="conformance", limit=10, timeout=3)):
        assert time.monotonic() < wait_until, "approval was not created"
        time.sleep(0.01)
    assert len(pending) == 1
    approval_id = pending[0].approval_id
    ports.approvals.decide(owner, approval_id, "approve", timeout=3)
    terminal(ports.chat, owner, chat.run_id, chat=True)
    proof = {
        "deadline": deadline.isoformat(),
        "task_run_id": admitted.run_id,
        "chat_run_id": chat.run_id,
        "session_id": session.session_id,
        "approval_id": approval_id,
        "task_result": wire(ports.task_runs.result(owner, admitted.run_id, timeout=3)),
        "chat_result": wire(ports.chat.get_run(owner, chat.run_id, timeout=3)),
        "session": wire(ports.chat.get_session(owner, session.session_id, timeout=3)),
        "approval": wire(ports.approvals.get(owner, approval_id, timeout=3)),
        "history": wire(ports.chat.history(owner, session.session_id, limit=10, timeout=3)),
        "state_counts": dict(state),
    }
    assert state["effects"] == 1, state
    path = Path(sys.argv[1]) / PROOF_FILE
    path.write_text(json.dumps(proof, sort_keys=True, indent=2), encoding="utf-8")
    return proof


def verify_recovered_state(handle, state, *, mutate_identity=False):
    from ai_base_runtime.apps import ChatMessageRequest

    owner = principal()
    ports = handle.blocking
    saved = json.loads((Path(sys.argv[1]) / PROOF_FILE).read_text(encoding="utf-8"))
    deadline = datetime.fromisoformat(saved["deadline"])
    assert wire(ports.task_runs.result(owner, saved["task_run_id"], timeout=3)) == saved["task_result"]
    assert wire(ports.chat.get_run(owner, saved["chat_run_id"], timeout=3)) == saved["chat_result"]
    assert wire(ports.chat.get_session(owner, saved["session_id"], timeout=3)) == saved["session"]
    assert wire(ports.approvals.get(owner, saved["approval_id"], timeout=3)) == saved["approval"]
    assert wire(ports.chat.history(owner, saved["session_id"], limit=10, timeout=3)) == saved["history"]

    again = ports.task_runs.start(owner, request_for(deadline), timeout=3)
    expected_task_id = saved["task_run_id"] + "-mutated" if mutate_identity else saved["task_run_id"]
    if again.run_id != expected_task_id:
        write_observation(mutation={
            "kind": "task_identity", "expected": expected_task_id, "actual": again.run_id,
        })
        raise AssertionError(f"recovered task identity mismatch: expected {expected_task_id}, got {again.run_id}")
    session = ports.chat.open_session(
        owner, app_id="conformance", agent="agent", session_key=SESSION_KEY, timeout=3,
    )
    expected_session_id = saved["session_id"] + "-mutated" if mutate_identity else saved["session_id"]
    if session.session_id != expected_session_id:
        write_observation(mutation={
            "kind": "session_identity", "expected": expected_session_id, "actual": session.session_id,
        })
        raise AssertionError(
            f"recovered session identity mismatch: expected {expected_session_id}, got {session.session_id}"
        )
    repeated = ports.chat.message(owner, ChatMessageRequest(
        session_id=saved["session_id"], content="Apply the synthetic change.",
        client_message_key=CLIENT_MESSAGE_KEY, deadline_at=deadline,
    ), timeout=3)
    assert repeated.run_id == saved["chat_run_id"]
    assert wire(ports.chat.history(owner, saved["session_id"], limit=10, timeout=3)) == saved["history"]
    assert state["effects"] == 0, state
    readback = {
        "reacquired_runtime": True,
        "state_lock_present": handle._runtime._lock is not None,
        "task_run_id": again.run_id,
        "chat_run_id": repeated.run_id,
        "session_id": session.session_id,
        "new_effects": state["effects"],
        "new_resolves": state["resolves"],
    }
    (Path(sys.argv[1]) / "failed-shutdown-read.json").write_text(
        json.dumps(readback, sort_keys=True, indent=2), encoding="utf-8",
    )
    return readback


def inject_store_fault(handle):
    from ai_host import settings

    store = handle._runtime._store
    assert store is not None, "runtime store is not open"
    entered = threading.Event()

    def held_io():
        entered.set()
        threading.Event().wait(settings.HOST_WATCHDOG_SECONDS)

    future = store._submit(held_io)
    assert entered.wait(settings.RUNTIME_STOP_TIMEOUT_SECONDS), "controlled store I/O did not enter"
    return {
        "entered": True,
        "future_done": future.done(),
        "pending_work_count": store.pending_work_count(),
        "outer_bound_seconds": settings.HOST_WATCHDOG_SECONDS,
    }


def observe_store_close_until(handle):
    store = handle._runtime._store
    assert store is not None, "runtime store is not open"
    original = store.close_until

    def observed_close_until(deadline):
        entered = {
            "entered": True,
            "pending_at_enter": store.pending_work_count(),
            "deadline_remaining_at_enter": None if deadline is None else max(0.0, deadline - time.monotonic()),
        }
        write_observation(store_close=entered)
        result = original(deadline)
        write_observation(store_close={**entered, "returned": True, "result": bool(result)})
        return result

    store.close_until = observed_close_until


def prepare():
    global _OBSERVATIONS
    from ai_base_runtime.testkit.host_support._domain_assertions import _package
    from ai_host import package
    from ai_host.management.commands.serve import Command

    mode = sys.argv[4]
    if mode not in {"write-failed", "write-clean-control", "read-normal", "read-mutated-identity"}:
        raise ValueError("unregistered failed-shutdown recovery mode")
    _OBSERVATIONS = ObservationSnapshots(Path(sys.argv[5]))
    state = {"effects": 0, "resolves": 0}
    package.METRICS_APP = _package(state, approval=True)
    original_wait = Command._wait_for_stop
    original_with_runtime_stop_result = Command._with_runtime_stop_result

    def observed_wait(command, stop_event, stop_file, deadline, handle):
        write_observation(mode=mode, identity=runtime_identity(handle))
        if mode.startswith("write-"):
            proof = seed_public_state(handle, state)
            write_observation(seed={"proof": proof, "state_counts": dict(state)})
            if mode == "write-failed":
                observe_store_close_until(handle)
                write_observation(fault=inject_store_fault(handle))
        else:
            readback = verify_recovered_state(handle, state, mutate_identity=mode == "read-mutated-identity")
            write_observation(readback=readback)
        write_observation(ready_for_stop=True)
        return original_wait(command, stop_event, stop_file, deadline, handle)

    def observed_with_runtime_stop_result(command, outcome, stop_result):
        result = original_with_runtime_stop_result(command, outcome, stop_result)
        write_observation(stop={
            "outcome": asdict(outcome),
            "stop_result": None if stop_result is None else asdict(stop_result),
            "result": asdict(result),
        })
        return result

    Command._wait_for_stop = observed_wait
    Command._with_runtime_stop_result = observed_with_runtime_stop_result


if __name__ == "__main__":
    raise SystemExit(main(configure=configure, prepare=prepare, diagnose_errors=False))
