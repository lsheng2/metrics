from __future__ import annotations

from pathlib import Path
import os
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def wrapper_arguments(values):
    remaining = list(values)
    launch_id = take_option(remaining, '--qualify-launch-id')
    exit_file = Path(take_option(remaining, '--qualify-exit-file'))
    return launch_id, exit_file, remaining


def take_option(values, name):
    index = values.index(name)
    try:
        value = values[index + 1]
    except IndexError:
        raise SystemExit(2) from None
    del values[index:index + 2]
    return value


def main():
    launch_id, exit_file, command = wrapper_arguments(sys.argv[1:])
    if command and command[0] == 'serve':
        from ai_host.exit_inventory import install_exit_capture
        install_exit_capture()
    from django.core.management import execute_from_command_line
    from scripts.validation.project_full_stack_identity import write_exit_receipt

    original_exit = os._exit

    def observed_exit(exit_code):
        try:
            write_exit_receipt(
                exit_file, service='project-app', launch_id=launch_id, pid=os.getpid(), exit_code=exit_code,
            )
        finally:
            original_exit(exit_code)

    if command and command[0] == 'serve':
        os._exit = observed_exit
    code = 0
    try:
        execute_from_command_line([str(ROOT / 'manage.py'), *command])
    except SystemExit as error:
        code = error.code if type(error.code) is int else 1
    except BaseException:
        code = 1
        raise
    finally:
        os._exit = original_exit
        write_exit_receipt(exit_file, service='project-app', launch_id=launch_id, pid=os.getpid(), exit_code=code)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
