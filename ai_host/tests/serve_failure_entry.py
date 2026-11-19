"""Native fault injection around the real installed runtime, for host tests."""
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ai_host.exit_inventory import install_exit_capture

install_exit_capture()

import asyncio
from dataclasses import asdict
from importlib.metadata import version
import json
import threading
import time

from ai_host.tests.serve_test_entry import main


def write_observation(value):
    path = Path(sys.argv[5])
    path.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")


def configure(temp):
    return {"METRICS_STATE_DIR": str(Path(sys.argv[1]) / "durable-state")}


def prepare():
    import ai_base_runtime
    from ai_base_runtime import AgentRuntime
    from ai_host.management.commands.serve import Command
    from ai_host import settings

    mode = sys.argv[4]
    if mode == "normal":
        return
    if mode == "ended":
        original_wait = Command._wait_for_stop

        def observed_wait(command, stop_event, stop_file, deadline, handle):
            timing = {}
            original_end = handle._worker._on_exit

            def observed_end():
                timing["ended_at"] = time.monotonic()
                original_end()

            handle._worker.set_on_exit(observed_end)

            def end_runtime():
                trigger = Path(sys.argv[6])
                while not trigger.exists():
                    time.sleep(0.02)
                handle.stop()

            threading.Thread(target=end_runtime, name="test-runtime-end", daemon=True).start()
            result = original_wait(command, stop_event, stop_file, deadline, handle)
            write_observation({
                "mode": mode, "observed_at": time.monotonic(), "ended": handle.ended.is_set(),
                "ended_at": timing.get("ended_at"),
                "end_code": handle.end_code,
                "stop_result": asdict(handle.stop_result) if handle.stop_result is not None else None,
            })
            return result

        Command._wait_for_stop = observed_wait
        return
    if mode == "loop-fault":
        original_wait = Command._wait_for_stop
        original_with_runtime_stop_result = Command._with_runtime_stop_result
        observation = {}
        stop_calls = []

        def write_loop_observation(extra):
            observation.update(extra)
            write_observation(observation)

        def observed_wait(command, stop_event, stop_file, deadline, handle):
            original_end = handle._worker._on_exit
            original_stop = handle.stop

            def observed_stop(*args, **kwargs):
                stop_calls.append({
                    "called_at": time.monotonic(),
                    "ended_before_call": handle.ended.is_set(),
                    "thread": threading.current_thread().name,
                })
                return original_stop(*args, **kwargs)

            def observed_end():
                observation["ended_at"] = time.monotonic()
                original_end()

            handle.stop = observed_stop
            handle._worker.set_on_exit(observed_end)

            def end_runtime_loop():
                trigger = Path(sys.argv[6])
                while not trigger.exists():
                    time.sleep(0.02)

                def injected_fault():
                    observation.update({
                        "fault_entered_at": time.monotonic(),
                        "fault_thread": threading.current_thread().name,
                        "fault_loop": type(asyncio.get_running_loop()).__name__,
                    })
                    handle._worker.loop.stop()

                handle._worker.loop.call_soon_threadsafe(injected_fault)

            threading.Thread(target=end_runtime_loop, name="test-runtime-loop-fault", daemon=True).start()
            result = original_wait(command, stop_event, stop_file, deadline, handle)
            write_loop_observation({
                "mode": mode,
                "runtime_version": version("ai-base-runtime"),
                "observed_at": time.monotonic(),
                "ended": handle.ended.is_set(),
                "end_code": handle.end_code,
                "loop_closed_after_wait": handle._worker.loop.is_closed(),
                "stop_calls": list(stop_calls),
                "wait_result": result,
            })
            return result

        def observed_with_runtime_stop_result(command, outcome, stop_result):
            result = original_with_runtime_stop_result(command, outcome, stop_result)
            write_loop_observation({
                "final_observed_at": time.monotonic(),
                "outcome_exit_code": outcome.exit_code,
                "outcome_cleanup_errors": list(outcome.cleanup_errors),
                "result_exit_code": result.exit_code,
                "result_cleanup_errors": list(result.cleanup_errors),
                "stop_result": asdict(stop_result) if stop_result is not None else None,
                "stop_calls": list(stop_calls),
            })
            return result

        Command._wait_for_stop = observed_wait
        Command._with_runtime_stop_result = observed_with_runtime_stop_result
        return
    if mode not in {"timeout-clean", "timeout-stuck"}:
        raise ValueError("unregistered native fault")
    settings.RUNTIME_START_SECONDS = 2.0
    entered = {}

    async def hold_commit(runtime, *, deadline=None):
        entered.update(
            lock_owned=runtime._lock is not None,
            loop=type(asyncio.get_running_loop()).__name__,
            thread=threading.current_thread().name,
        )
        await asyncio.Event().wait()

    AgentRuntime._commit_running = hold_commit
    if mode == "timeout-stuck":
        async def hold_rollback(runtime, reason_code, *, deadline=None):
            entered["rollback_entered"] = True
            threading.Event().wait(30)

        AgentRuntime._rollback = hold_rollback
    original_start = ai_base_runtime.start_blocking

    def start(*args, **kwargs):
        context = original_start(*args, **kwargs)

        class ObservedContext:
            @property
            def startup_failure(self):
                return context.startup_failure

            def __enter__(self):
                began = time.monotonic()
                try:
                    return context.__enter__()
                except ai_base_runtime.RuntimeStartTimeout:
                    write_observation({
                        "mode": mode, "elapsed": time.monotonic() - began, "injection": entered,
                        "failure": asdict(context.startup_failure),
                        "loop_alive": context._worker.thread_alive(),
                    })
                    raise

            def __exit__(self, *args):
                return context.__exit__(*args)

        return ObservedContext()

    ai_base_runtime.start_blocking = start


if __name__ == "__main__":
    raise SystemExit(main(configure=configure, prepare=prepare, diagnose_errors=False))
