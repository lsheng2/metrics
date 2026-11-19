import socket
from types import SimpleNamespace

import pytest

from ui_web.tests import report_authoring_browser_support as support
from ui_web.tests import test_report_template_browser as templates


class InjectedFailure(RuntimeError):
    pass


class BrowserResources:
    def __init__(self, stage):
        self.stage = stage
        self.active = False
        self.stops = 0
        self.page = SimpleNamespace(
            route=lambda *args: None,
            goto=lambda *args, **kwargs: self.fail("goto"),
            wait_for_selector=lambda *args: self.fail("wait"),
        )
        self.context = SimpleNamespace(
            new_page=self.new_page, add_cookies=lambda *args: None,
        )
        self.browser = SimpleNamespace(new_context=self.new_context, close=self.close_browser)
        self.chromium = SimpleNamespace(launch=self.launch)

    def fail(self, stage):
        if self.stage == stage:
            raise InjectedFailure(stage)

    def __enter__(self):
        self.fail("start")
        self.active = True
        return self

    def start(self):
        return self.__enter__()

    def __exit__(self, *args):
        self.stop()

    def stop(self):
        if self.active:
            self.stops += 1
            self.active = False

    def launch(self, **kwargs):
        self.fail("launch")
        return self.browser

    def new_context(self, **kwargs):
        self.fail("context")
        return self.context

    def new_page(self):
        self.fail("page")
        return self.page

    def close_browser(self):
        assert self.active, "The browser must close before its driver"
        self.fail("close")


CASES = [
    (kind, stage) for kind in ("browser", "project")
    for stage in (None, "body", "start", "launch", "context", "page", "goto", "close")
] + [("browser", "wait")]


@pytest.mark.parametrize(("kind", "stage"), CASES)
def test_report_browser_cleanup_survives_every_owned_failure(monkeypatch, kind, stage):
    resources = BrowserResources(stage)
    original_connect = socket.socket.connect
    monkeypatch.setattr(support, "sync_playwright", lambda: resources)
    factory = support.BrowserPage if kind == "browser" else templates.ProjectPage
    try:
        if stage is None:
            with factory("http://127.0.0.1:1/") as page:
                assert page is resources.page
        else:
            with pytest.raises(InjectedFailure, match=stage):
                with factory("http://127.0.0.1:1/") as page:
                    assert page is resources.page
                    resources.fail("body")
        assert resources.active is False
        assert resources.stops == (0 if stage == "start" else 1)
        assert socket.socket.connect is original_connect
    finally:
        resources.stop()
        socket.socket.connect = original_connect
