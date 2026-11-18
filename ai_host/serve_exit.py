import json
import logging
import os


def explicit_exit(code, stdout, stderr, *, message=None):
    from django.db import connections
    from ai_host.exit_inventory import collect_exit_inventory

    primary_message = message
    inventory = None
    try:
        inventory = collect_exit_inventory()
        report, errors = inventory.report, inventory.errors
    except Exception:
        errors = ['exit_inventory_failed']
        report = {'schema_version': 1, 'event': 'serve_exit_inventory', 'errors': errors}
    stdout.write(json.dumps(report, separators=(',', ':')))
    if inventory is not None:
        inventory.cleanup_callbacks()
    try:
        connections.close_all()
    except Exception:
        errors.append('database_close_failed')
    # logging.shutdown suppresses some I/O errors. Observe each required
    # flush/close first so a failed write cannot become a successful host exit.
    for reference in tuple(logging._handlerList):
        handler = reference()
        if handler is None:
            continue
        try:
            handler.acquire()
            try:
                handler.flush()
                handler.close()
            finally:
                handler.release()
        except Exception:
            errors.append('log_close_failed')
    try:
        logging.shutdown()
    except Exception:
        errors.append('logging_shutdown_failed')
    if inventory is not None:
        inventory.cleanup_finalizers()
    stdout.write(json.dumps({
        'schema_version': 1, 'event': 'serve_exit_cleanup',
        'errors': errors,
        'finalizers': report.get('finalizers', []),
    }, separators=(',', ':')))
    if errors:
        code = 3
    if code == 3:
        message = 'serve cleanup failed.' + (f' ({",".join(dict.fromkeys(errors))})' if errors else '')
    elif message is None:
        message = 'serve stopped.' if code == 0 else 'serve startup failed (startup_failed).'
    try:
        if code == 3 and primary_message and primary_message != message:
            stdout.write(primary_message)
        stdout.write(message)
        stdout.flush()
        stderr.flush()
    except Exception:
        code = 3
    os._exit(code)
