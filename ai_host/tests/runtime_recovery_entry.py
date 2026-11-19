"""Prove durable public runtime state across immediate process exit."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ai_host.exit_inventory import install_exit_capture

install_exit_capture()

from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import os
import time
from urllib.parse import urlsplit

from ai_host.tests.serve_test_entry import main


def wire(value):
    if is_dataclass(value):
        return {field.name: wire(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, Enum):
        return value.value
    return value


def configure(temp):
    root = Path(sys.argv[1])
    return {
        "METRICS_STATE_DIR": str(root / "durable-state"),
        "DATABASES": {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(root / "catalog.sqlite3")}},
    }


def terminal(port, principal, run_id, *, chat=False):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        result = (port.get_run if chat else port.get)(principal, run_id, timeout=2)
        if result.status not in {"queued", "running"}:
            assert result.status == "succeeded", wire(result)
            return result
        time.sleep(0.01)
    raise AssertionError("synthetic public runtime operation did not complete")


def prepare():
    from pydantic import SecretStr
    from ai_base_runtime import start_blocking
    from ai_base_runtime.apps import ChatMessageRequest, ContextRef, RunSubmit
    from ai_base_runtime.contracts import canonical_digest
    from ai_base_runtime.spi import ModelConfig, Principal, PROVIDER_OPENAI_COMPATIBLE
    from ai_base_runtime.testkit.host_support._domain_assertions import _package
    from ai_host.host import MetricsHost
    from ai_host.settings import build_host_config, build_runtime_settings

    root, mode, endpoint = Path(sys.argv[1]), sys.argv[4], sys.argv[5]
    if mode not in {"write", "read"} or urlsplit(endpoint).hostname != "127.0.0.1":
        raise ValueError("invalid native recovery fixture input")
    proof_path = root / "recovery-state.json"
    saved = json.loads(proof_path.read_text(encoding="utf-8")) if mode == "read" else None
    deadline = datetime.fromisoformat(saved["deadline"]) if saved else datetime.now(timezone.utc) + timedelta(seconds=120)
    state = {"effects": 0, "resolves": 0}
    package = _package(state, approval=True)
    principal = Principal(id="recovery-owner", display_name="Synthetic Recovery Owner")
    config = replace(
        build_host_config(),
        model=ModelConfig(provider=PROVIDER_OPENAI_COMPATIBLE, name="scripted", base_url=endpoint,
                          api_key=SecretStr("scripted-test-key")),
    )
    config.state_dir.mkdir(parents=True, exist_ok=True)
    request = RunSubmit(
        app_id="conformance", profile_id="conformance.summary", profile_version="1",
        input={"number": 7}, input_sha256=canonical_digest({"number": 7}),
        client_run_key="hard-exit-task", deadline_at=deadline, limits={},
        minimum_result_retention_seconds=600,
    )
    context = start_blocking(build_runtime_settings(), MetricsHost(config), [package], start_timeout=15)
    with context as handle:
        ports = handle.blocking
        if mode == "write":
            admitted = ports.task_runs.start(principal, request, timeout=3)
            terminal(ports.task_runs, principal, admitted.run_id)
            session = ports.chat.open_session(
                principal, app_id="conformance", agent="agent",
                session_key="conformance.hard-exit",
                context_ref=ContextRef("conformance.item", {"id": "one"}), timeout=3,
            )
            chat = ports.chat.message(principal, ChatMessageRequest(
                session_id=session.session_id, content="Apply the synthetic change.",
                client_message_key="hard-exit-chat", deadline_at=deadline,
            ), timeout=3)
            wait_until = time.monotonic() + 15
            while not (pending := ports.approvals.list_pending(principal, app_id="conformance", limit=10, timeout=3)):
                assert time.monotonic() < wait_until, "approval was not created"
                time.sleep(0.01)
            assert len(pending) == 1
            approval_id = pending[0].approval_id
            ports.approvals.decide(principal, approval_id, "approve", timeout=3)
            terminal(ports.chat, principal, chat.run_id, chat=True)
            proof = {
                "deadline": deadline.isoformat(), "task_run_id": admitted.run_id, "chat_run_id": chat.run_id,
                "session_id": session.session_id, "approval_id": approval_id,
                "task_result": wire(ports.task_runs.result(principal, admitted.run_id, timeout=3)),
                "session": wire(ports.chat.get_session(principal, session.session_id, timeout=3)),
                "approval": wire(ports.approvals.get(principal, approval_id, timeout=3)),
                "history": wire(ports.chat.history(principal, session.session_id, limit=10, timeout=3)),
            }
            assert state["effects"] == 1
            proof_path.write_text(json.dumps(proof, sort_keys=True, indent=2), encoding="utf-8")
        else:
            assert wire(ports.task_runs.result(principal, saved["task_run_id"], timeout=3)) == saved["task_result"]
            assert wire(ports.chat.get_session(principal, saved["session_id"], timeout=3)) == saved["session"]
            assert wire(ports.approvals.get(principal, saved["approval_id"], timeout=3)) == saved["approval"]
            assert wire(ports.chat.history(principal, saved["session_id"], limit=10, timeout=3)) == saved["history"]
            again = ports.task_runs.start(principal, request, timeout=3)
            assert again.run_id == saved["task_run_id"]
            session = ports.chat.open_session(
                principal, app_id="conformance", agent="agent", session_key="conformance.hard-exit", timeout=3,
            )
            assert session.session_id == saved["session_id"]
            assert state["effects"] == 0
            (root / "recovery-read.json").write_text(json.dumps({
                "reacquired_runtime": True, "task_run_id": again.run_id,
                "session_id": session.session_id, "new_effects": state["effects"],
            }), encoding="utf-8")
    os._exit(0 if handle.stop_result is not None and handle.stop_result.completed else 3)


if __name__ == "__main__":
    raise SystemExit(main(configure=configure, prepare=prepare, diagnose_errors=False))
