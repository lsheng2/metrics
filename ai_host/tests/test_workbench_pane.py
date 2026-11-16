from contextlib import contextmanager
import threading
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import RequestFactory, override_settings

from ai_base_runtime import RuntimeCallTimeout, RuntimeNotRunning
from ai_base_runtime.apps import SessionView
from ai_host.state import attach, detach
from ai_host.tests.test_workbench_context_ref import page_state


class Chat:
    def __init__(self, *, failure=None):
        self.opened = []
        self.bound = []
        self.failure = failure

    @classmethod
    def timed_out(cls):
        return cls(failure=RuntimeCallTimeout())

    def open_session(self, principal, *, app_id, agent, context_ref, session_key, timeout):
        self.opened.append((principal.id, session_key, timeout))
        if self.failure:
            raise self.failure
        return SessionView(
            session_id='session-1', app_id=app_id, agent=agent, context_ref=None,
            session_key=session_key, embed_path='/ai/embed/session-1',
        )

    def bind_context(self, principal, session_id, context_ref, *, timeout):
        self.bound.append((principal.id, session_id, context_ref, timeout))


@contextmanager
def host(chat=None, **settings):
    handle = SimpleNamespace(
        blocking=SimpleNamespace(chat=chat or Chat()),
        ui=SimpleNamespace(asset_url=lambda name: '/ai/assets/embed-host-hash.js'),
        ended=threading.Event(),
    )
    with override_settings(
        METRICS_BASIC_AUTH_USERS=None,
        METRICS_AI_MODEL_BASE_URL='http://127.0.0.1:49999/v1',
        METRICS_AI_MODEL_NAME='synthetic',
        METRICS_AI_MODEL_API_KEY='synthetic-secret',
        **settings,
    ):
        attach(handle)
        try:
            yield handle
        finally:
            detach(handle)


def test_pane_rebinds_restored_session_before_exposing_embed_path():
    from ai_host.pane import workbench_pane

    with host() as handle:
        pane = workbench_pane(RequestFactory().get('/workbench/'), page_state())
    assert pane['status'] == 'ready'
    assert pane['embed_path'] == '/ai/embed/session-1'
    assert pane['embed_host_url'] == '/ai/assets/embed-host-hash.js'
    assert handle.blocking.chat.opened[0][:2] == ('local_operator', 'metrics.workbench.sample-jira')
    assert handle.blocking.chat.bound[0][2].values['begin'] == '2026-11-01'
    assert 0 < handle.blocking.chat.bound[0][3] <= handle.blocking.chat.opened[0][2] <= 1
    assert pane['approval_requires_basic'] is True
    assert 'synthetic-secret' not in repr(pane)


def test_pane_accepts_full_length_profile_session_key_without_rewriting():
    from ai_host.pane import workbench_pane

    with host() as handle:
        pane = workbench_pane(RequestFactory().get('/workbench/'), page_state(profile_id='p-' + 'x' * 158))
    assert pane['status'] == 'ready'
    assert handle.blocking.chat.opened[0][1] == 'metrics.workbench.p-' + 'x' * 158


@pytest.mark.parametrize(('failure', 'status'), [
    (RuntimeCallTimeout(), 'temporarily_unavailable'), (RuntimeNotRunning(), 'not_running'),
])
def test_pane_fails_locally_without_exposing_runtime_exception(failure, status):
    from ai_host.pane import workbench_pane

    with host(Chat(failure=failure)):
        pane = workbench_pane(RequestFactory().get('/workbench/'), page_state())
    assert pane['status'] == status
    assert pane['embed_path'] == ''


def test_pane_busy_gate_never_waits_on_runtime():
    from ai_host.pane import workbench_pane

    with host() as handle, patch('ai_host.pane._SLOTS', threading.BoundedSemaphore(0)):
        pane = workbench_pane(RequestFactory().get('/workbench/'), page_state())
    assert pane['status'] == 'temporarily_unavailable'
    assert handle.blocking.chat.opened == []


def test_pane_reports_missing_names_only_and_unresolved_binding_has_no_context():
    from ai_host.pane import workbench_pane

    with host():
        with override_settings(METRICS_AI_MODEL_API_KEY=''):
            pane = workbench_pane(RequestFactory().get('/workbench/'), page_state())
        unresolved = workbench_pane(RequestFactory().get('/workbench/'), page_state(profile_id=''))
    assert pane['status'] == 'not_configured'
    assert pane['missing_settings'] == ('METRICS_AI_MODEL_API_KEY',)
    assert unresolved['binding_status'] == 'binding_unresolved'
    assert unresolved['context_ref'] is None
    assert unresolved['embed_path'] == ''


def test_no_attached_host_reports_not_running():
    from ai_host.pane import workbench_pane

    assert workbench_pane(RequestFactory().get('/workbench/'), page_state())['status'] == 'not_running'
