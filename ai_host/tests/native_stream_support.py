from contextlib import contextmanager, ExitStack
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

from ai_host.exit_processes import living_children
from ai_host.tests.conformance_server import MetricsConformanceStream
from ai_host.tests.conformance_runtime_probe import Events
from ai_host.tests.test_serve_native_signal import send_native_break
from scripts.service_lifecycle_engine.process_exit import observe_process_exit


ROOT = Path(__file__).resolve().parents[2]


class NativeHost:
    def __init__(self, root, process, port, log_path, stop, trigger):
        self.root, self.process, self.port = root, process, port
        self.log_path, self.stop_file, self.trigger = log_path, stop, trigger
        self.triggered_at = None

    def records(self):
        result = []
        for line in self.log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                result.append(value)
        return result

    def request(self, method, path, payload=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            body = None if payload is None else json.dumps(payload).encode()
            connection.request(method, path, body, {"Content-Type": "application/json", "Connection": "close"})
            response = connection.getresponse()
            data = response.read()
            assert response.status == 200, (response.status, data)
            return json.loads(data)
        finally:
            connection.close()

    def snapshot(self):
        return self.request("GET", "/ai/apps/metrics/api/qualification/snapshot")

    def stream(self, path):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=4)
        connection.connect()
        connection.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        try:
            connection.request("GET", path, headers={"Connection": "close"})
            response = connection.getresponse()
            assert response.status == 200, (response.status, response.read())
            return MetricsConformanceStream(connection, response)
        except BaseException:
            connection.close()
            raise

    def trigger_stop(self):
        self.triggered_at = time.monotonic()
        if self.trigger == "stop-file":
            self.stop_file.touch()
        elif self.trigger == "CTRL_BREAK_EVENT":
            self.triggered_at = send_native_break(self.process)["sent_at"]
        elif self.trigger in {"SIGINT", "SIGTERM"}:
            (self.root / "signal").touch()
        elif self.trigger == "lifetime":
            ready = next(row for row in self.records() if row.get("event") == "stream_host_ready")
            self.triggered_at = ready["deadline"]
            assert time.monotonic() < self.triggered_at
        else:
            raise AssertionError("Unknown stream stop trigger")
        return self.triggered_at

    def wait_stopped(self):
        assert self.triggered_at is not None
        remaining = self.triggered_at + 10 - time.monotonic()
        code = self.process.wait(timeout=max(0.1, remaining))
        exited_at = time.monotonic()
        assert code == 0, self.log_path.read_text(encoding="utf-8", errors="replace")
        assert exited_at - self.triggered_at <= 10
        return exited_at


@contextmanager
def native_stream_host(root, *, endpoint="-", trigger="stop-file"):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    stop, log_path = root / "stop", root / "serve.log"
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    command = [
        sys.executable, "-I", str(ROOT / "ai_host/tests/serve_stream_entry.py"),
        str(root), str(port), str(stop), endpoint, trigger,
    ]
    with log_path.open("wb") as log, ExitStack() as observations:
        process = subprocess.Popen(
            command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, startupinfo=startup,
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        host = NativeHost(root, process, port, log_path, stop, trigger)
        forced = False
        try:
            deadline = time.monotonic() + 40
            while True:
                assert process.poll() is None, log_path.read_text(encoding="utf-8", errors="replace")
                try:
                    host.request("GET", "/ai/api/apps")
                    break
                except (OSError, HTTPException):
                    assert time.monotonic() < deadline
                    time.sleep(0.05)
            inventory, family = living_children(), {process.pid}
            for _ in inventory:
                family.update(row["pid"] for row in inventory if row["parent_pid"] in family)
            descendants = [row for row in inventory if row["pid"] in family - {process.pid}]
            exits = {row["pid"]: observations.enter_context(observe_process_exit(row["pid"])) for row in descendants}
            assert all(item.wait is not None for item in exits.values())
            yield host
        finally:
            if process.poll() is None:
                stop.touch()
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    forced = True
                    process.kill()
                    process.wait(timeout=3)
            for observer in locals().get("exits", {}).values():
                assert observer.wait(2), "Owned descendant survived host"
            (root / "process.json").write_text(json.dumps({
                "argv": command, "pid": process.pid, "port": port, "returncode": process.returncode,
                "forced_cleanup": forced, "descendants": locals().get("descendants", []),
                "descendant_exit_codes": {pid: item() for pid, item in locals().get("exits", {}).items()},
            }, indent=2), encoding="utf-8")
        assert not forced and process.returncode == 0, log_path.read_text(encoding="utf-8", errors="replace")
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(("127.0.0.1", port)) != 0
    records = host.records()
    cleaned = next(row for row in records if row.get("event") == "serve_exit_cleanup")
    assert not cleaned["errors"], cleaned
    stopped = next(row for row in records if row.get("event") == "project_runtime_stopped")
    assert stopped["stopped"] and not stopped["unresolved"] and stopped["active_operation_id"] is None
    assert not tuple((root / "tmp_ui_validation").iterdir())


class EventReader:
    def __init__(self, stream):
        self.stream = stream
        self.events, self.error, self.eof_at = [], None, None
        self.thread = threading.Thread(target=self._read, name="test-stream-reader", daemon=True)

    def start(self):
        self.thread.start()
        return self

    def _read(self):
        reader = Events(self.stream)
        try:
            while (event := reader.next(timeout=15)) is not None:
                self.events.append({"at": time.monotonic(), "payload": event})
            self.eof_at = time.monotonic()
        except Exception as error:
            self.error = repr(error)

    def finish(self):
        self.thread.join(timeout=12)
        assert not self.thread.is_alive()
        assert self.error is None, self.error
        assert self.eof_at is not None
        terminals = [item for item in self.events if item["payload"]["type"] == "stream.terminated"]
        assert len(terminals) == 1, [item["payload"]["type"] for item in self.events]
        assert self.events[-1] == terminals[0]
        assert terminals[0]["at"] <= self.eof_at
        assert terminals[0]["payload"]["reason"] == "http_closing"
        return {"events": self.events, "eof_at": self.eof_at, "terminal_at": terminals[0]["at"]}
