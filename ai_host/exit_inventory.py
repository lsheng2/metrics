"""Capture interpreter-exit ownership before Django or runtime imports."""
import atexit
import sys
import threading


_CAPTURE = None


class ExitCapture:
    def __init__(self):
        self.callbacks = []
        self.thread_callbacks = []
        self.preexisting_callbacks = atexit._ncallbacks()
        self.registration_count = 0
        self.preexisting_thread_callbacks = tuple(threading._threading_atexits)
        self._lock = threading.RLock()
        self.original_register = atexit.register
        self.original_unregister = atexit.unregister
        self.original_thread_register = threading._register_atexit

        def register(callback, *args, **kwargs):
            registrant = sys._getframe(1).f_globals.get('__name__', '<unknown>')
            with self._lock:
                result = self.original_register(callback, *args, **kwargs)
                self.registration_count += 1
                self.callbacks.append((callback, args, kwargs, registrant))
                return result

        def unregister(callback):
            with self._lock:
                self.original_unregister(callback)
                self.callbacks[:] = [row for row in self.callbacks if row[0] != callback]

        def register_thread(callback, *args, **kwargs):
            registrant = sys._getframe(1).f_globals.get('__name__', '<unknown>')
            with self._lock:
                result = self.original_thread_register(callback, *args, **kwargs)
                self.thread_callbacks.append((callback, args, kwargs, registrant))
                return result

        self.register = register
        self.unregister = unregister
        self.register_thread = register_thread
        atexit.register = register
        atexit.unregister = unregister
        threading._register_atexit = register_thread


def install_exit_capture():
    global _CAPTURE
    if _CAPTURE is None:
        _CAPTURE = ExitCapture()
    return _CAPTURE


def get_exit_capture():
    return _CAPTURE


def _identity(callback):
    return f'{getattr(callback, "__module__", "<unknown>")}.{getattr(callback, "__qualname__", type(callback).__name__)}'


def _matches(callback, module, qualname):
    value = sys.modules.get(module)
    owner = None
    for component in qualname.split('.'):
        owner, value = value, getattr(value, component, None)
    if value is None:
        return False
    if getattr(callback, '__func__', callback) is not getattr(value, '__func__', value):
        return False
    bound = getattr(callback, '__self__', None)
    expected_bound = getattr(value, '__self__', None)
    if expected_bound is not None:
        return bound is expected_bound
    return bound is None or type(bound) is owner


def _callback_rows(entries, rules, errors, category, *, resources_clear, cleanups):
    rows = []
    for callback, args, kwargs, registrant in entries:
        action = next((
            action for module, qualname, origin, action in rules
            if registrant == origin and not args and not kwargs and _matches(callback, module, qualname)
        ), None)
        row = {'callback': _identity(callback), 'registrant': registrant, 'cleanup': action or 'unknown'}
        rows.append(row)
        if action is None:
            errors.append(f'unknown_{category}_callback')
        elif action == 'empty_lock_registry':
            import os
            module = sys.modules['portalocker.utils']
            held = [lock for lock, owner in tuple(module._exit_releases.items())
                    if owner == os.getpid() and lock.fh is not None]
            row['cleanup'] = 'blocked_by_live_locks' if held else 'not_required_empty'
            if held:
                errors.append('unreleased_file_lock')
        elif action == 'required':
            if not resources_clear:
                row['cleanup'] = 'blocked_by_live_resources'
                errors.append('required_cleanup_blocked')
                continue
            cleanups.append((row, callback))
    return rows


def _finalizers(rules, errors, cleanups):
    import weakref

    rows = []
    for finalizer in tuple(weakref.finalize._registry):
        info = finalizer.peek()
        if not finalizer.atexit or info is None:
            continue
        callback = info[1]
        action = next((action for module, qualname, action in rules
                       if _matches(callback, module, qualname)), None)
        row = {'callback': _identity(callback), 'cleanup': 'unknown'}
        rows.append(row)
        if action is None:
            errors.append('unknown_finalizer')
            continue
        if action == 'memory_only':
            row['cleanup'] = 'not_required_memory_only'
            continue
        row['cleanup'] = 'required'
        cleanups.append((row, finalizer))
    return rows


class ExitInventory:
    def __init__(self, report, errors, callbacks, finalizers):
        self.report, self.errors = report, errors
        self._callbacks, self._finalizers = callbacks, finalizers

    def cleanup_callbacks(self):
        self._run(self._callbacks, 'required_cleanup_failed')

    def cleanup_finalizers(self):
        self._run(self._finalizers, 'finalizer_cleanup_failed')

    def _run(self, pending, error_code):
        while pending:
            row, callback = pending.pop()
            try:
                callback()
                row['cleanup'] = 'completed'
            except Exception:
                row['cleanup'] = 'failed'
                if error_code not in self.errors:
                    self.errors.append(error_code)


def collect_exit_inventory():
    from ai_host.settings import HOST_EXIT_CALLBACKS, HOST_EXIT_FINALIZERS, HOST_EXIT_LOG_HANDLERS
    import logging
    from ai_host.exit_processes import living_children

    errors = []
    capture = get_exit_capture()
    if capture is None:
        errors.append('exit_capture_missing')
    elif (capture.preexisting_callbacks or capture.preexisting_thread_callbacks
          or atexit.register is not capture.register or atexit.unregister is not capture.unregister
          or threading._register_atexit is not capture.register_thread
          or atexit._ncallbacks() != capture.registration_count
          or len(threading._threading_atexits) != len(capture.thread_callbacks)):
        errors.append('exit_capture_incomplete')
    threads = [
        {'name': thread.name, 'ident': thread.ident}
        for thread in threading.enumerate()
        if thread is not threading.main_thread() and not thread.daemon and thread.is_alive()
    ]
    if threads:
        errors.append('unresolved_thread')
    children = []
    try:
        children = living_children()
    except (OSError, NotImplementedError):
        errors.append('child_inventory_failed')
    if children:
        errors.append('unresolved_child')
    handlers = []
    for reference in tuple(logging._handlerList):
        handler = reference()
        if handler is None:
            continue
        allowed = any(_matches(type(handler), module, qualname) for module, qualname in HOST_EXIT_LOG_HANDLERS)
        handlers.append({'class': _identity(type(handler)), 'cleanup': 'logging.shutdown' if allowed else 'unknown'})
        if not allowed:
            errors.append('unknown_log_handler')
    resources_clear = not threads and not children
    callback_cleanups, finalizer_cleanups = [], []
    report = {
        'schema_version': 1, 'event': 'serve_exit_inventory',
        'threads': threads, 'children': children, 'handlers': handlers,
        'atexit': _callback_rows(
            () if capture is None else tuple(capture.callbacks), HOST_EXIT_CALLBACKS,
            errors, 'atexit', resources_clear=resources_clear, cleanups=callback_cleanups,
        ),
        'threading_atexit': _callback_rows(
            () if capture is None else tuple(capture.thread_callbacks), HOST_EXIT_CALLBACKS,
            errors, 'threading_atexit', resources_clear=resources_clear, cleanups=callback_cleanups,
        ),
        'finalizers': _finalizers(HOST_EXIT_FINALIZERS, errors, finalizer_cleanups),
    }
    errors[:] = dict.fromkeys(errors)
    report['errors'] = errors
    return ExitInventory(report, errors, callback_cleanups, finalizer_cleanups)
