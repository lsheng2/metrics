from pathlib import Path
import signal
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ai_host.tests.serve_test_entry import main


def prepare():
    from ai_host.management.commands.serve import Command
    from ai_host import lifecycle
    from ai_host.wiring import RequestTracker

    marker = Path(sys.argv[4])
    phase, trigger = sys.argv[5:7]

    def hold(*args, **kwargs):
        marker.write_text(phase, encoding='utf-8')
        # Hold an actual host cleanup boundary, keeping its watchdog and
        # installed native signal handlers in control of process termination.
        while True:
            time.sleep(0.02)

    if phase == 'drain':
        RequestTracker.wait_empty = hold
    elif phase == 'flush':
        lifecycle._flush_waitress_channels = hold
    elif phase == 'final':
        original = Command._write_stop_event

        def final(command, result):
            original(command, result)
            hold()

        Command._write_stop_event = final
    elif phase != 'normal':
        raise ValueError('Unknown native signal test phase')

    if trigger == 'lifetime':
        original_run = Command._run_bound_server

        def lifetime_run(command, listener, options):
            return original_run(command, listener, {**options, 'lifetime_seconds': 4.0})

        Command._run_bound_server = lifetime_run
    elif trigger in {'SIGINT', 'SIGTERM'}:
        def signal_when_requested():
            while not marker.with_suffix('.signal').exists():
                time.sleep(0.02)
            signal.raise_signal(getattr(signal, trigger))

        threading.Thread(target=signal_when_requested, name='test-first-signal', daemon=True).start()
    elif trigger not in {'stop-file', 'CTRL_BREAK_EVENT'}:
        raise ValueError('Unknown native signal test trigger')


if __name__ == '__main__':
    raise SystemExit(main(prepare=prepare))
