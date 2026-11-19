import threading
import time

from django.conf import settings

from ai_base_runtime import RuntimeCallTimeout, RuntimeNotRunning
from ai_base_runtime.contracts import RuntimeFault
from ai_base_runtime.spi import Principal

from ai_host.settings import (
    AI_PANE_CONCURRENCY_LIMIT, AI_PANE_TIMEOUT_SECONDS, APP_ID,
    build_host_config, missing_model_settings, runtime_mount_path,
)
from ai_host.state import get_running_handle
from ai_host.workbench_context import build_context_ref, context_payload
from metrics.auth import check_basic_authorization


_SLOTS = threading.BoundedSemaphore(AI_PANE_CONCURRENCY_LIMIT)


def runtime_status():
    handle = get_running_handle()
    missing = missing_model_settings()
    return {
        'status': 'not_running' if handle is None else ('not_configured' if missing else 'ready'),
        'missing_settings': missing,
        'root_path': runtime_mount_path() + '/',
    }


def workbench_pane(request, state, *, ticket_ids=()):
    pane = {
        **runtime_status(), 'binding_status': 'resolved', 'context_ref': None,
        'embed_path': '', 'embed_host_url': '', 'session_id': '',
        'approval_requires_basic': False,
    }
    ref = build_context_ref(state, ticket_ids=ticket_ids)
    if ref is None:
        pane['binding_status'] = 'binding_unresolved'
        return pane
    if pane['status'] != 'ready':
        return pane
    identity = check_basic_authorization(
        settings.METRICS_BASIC_AUTH_USERS, request.META.get('HTTP_AUTHORIZATION'),
    )
    if identity is None:
        pane['status'] = 'not_running'
        return pane
    principal = Principal(id=identity.username, display_name=identity.username, anonymous=identity.anonymous)
    pane['approval_requires_basic'] = principal.anonymous and not build_host_config().allow_anonymous_approval
    if not _SLOTS.acquire(blocking=False):
        pane['status'] = 'temporarily_unavailable'
        return pane
    try:
        handle = get_running_handle()
        if handle is None:
            raise RuntimeNotRunning()
        deadline = time.monotonic() + AI_PANE_TIMEOUT_SECONDS
        session = handle.blocking.chat.open_session(
            principal, app_id=APP_ID, agent='dashboard', context_ref=ref,
            session_key=f'metrics.workbench.{state.profile_id}', timeout=AI_PANE_TIMEOUT_SECONDS,
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeCallTimeout()
        # Keyed opens restore the persisted context; update it before notifying
        # the preserved iframe, whose protocol carries only the session id.
        handle.blocking.chat.bind_context(principal, session.session_id, ref, timeout=remaining)
        pane.update(
            context_ref=context_payload(ref), session_id=session.session_id,
            embed_path=session.embed_path, embed_host_url=handle.ui.asset_url('embed-host.js'),
        )
    except RuntimeNotRunning:
        pane['status'] = 'not_running'
    except RuntimeFault as error:
        if error.code == 'context_boundary_violation':
            pane['binding_status'] = 'binding_unresolved'
        else:
            pane['status'] = 'temporarily_unavailable'
    finally:
        _SLOTS.release()
    return pane
