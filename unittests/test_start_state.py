# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for start-state detection in AIAgentic."""

from AIAgentic.library import AIAgentic


class DummySelenium:
    def __init__(
        self,
        browser_ids=None,
        url="http://example.com",
        title="Example",
        raise_location=False,
        raise_title=False,
    ):
        self._browser_ids = browser_ids if browser_ids is not None else []
        self._url = url
        self._title = title
        self._raise_location = raise_location
        self._raise_title = raise_title

    def get_browser_ids(self):
        return self._browser_ids

    def get_location(self):
        if self._raise_location:
            raise RuntimeError("no location")
        return self._url

    def get_title(self):
        if self._raise_title:
            raise RuntimeError("no title")
        return self._title


class DummyDriver:
    def __init__(
        self,
        session_id="abc123",
        context="NATIVE_APP",
        activity="MainActivity",
        package="com.example.app",
        capabilities=None,
    ):
        self.session_id = session_id
        self._context = context
        self._activity = activity
        self._package = package
        self.capabilities = capabilities or {}

    @property
    def current_context(self):
        return self._context

    @property
    def current_activity(self):
        return self._activity

    @property
    def current_package(self):
        return self._package


class DummyCache:
    def __init__(self, open_apps=None):
        self._open_apps = open_apps or []

    def get_open_browsers(self):
        return self._open_apps


class DummyAppium:
    def __init__(self, driver=None, open_apps=None, raise_current=False):
        self._driver = driver
        self._raise_current = raise_current
        self._cache = DummyCache(open_apps)

    def _current_application(self):
        if self._raise_current:
            raise RuntimeError("No application is open")
        return self._driver


def test_web_start_state_no_library(monkeypatch):
    agentic = AIAgentic()
    monkeypatch.setattr(agentic, "_get_library_instance", lambda name: None)
    result = agentic._build_web_start_state()
    assert "No active browser session detected" in result


def test_web_start_state_active(monkeypatch):
    agentic = AIAgentic()
    dummy = DummySelenium(browser_ids=[1], url="https://example.test", title="Example")
    monkeypatch.setattr(agentic, "_get_library_instance", lambda name: dummy)
    result = agentic._build_web_start_state()
    assert "Active browser session detected" in result
    assert "Open browsers: 1" in result
    assert "Current URL: https://example.test" in result
    assert "Title: Example" in result


def test_mobile_start_state_no_library(monkeypatch):
    agentic = AIAgentic()
    monkeypatch.setattr(agentic, "_get_library_instance", lambda name: None)
    result = agentic._build_mobile_start_state()
    assert "No active mobile session detected" in result


def test_mobile_start_state_active(monkeypatch):
    agentic = AIAgentic()
    caps = {
        "platformName": "Android",
        "platformVersion": "14",
        "deviceName": "Pixel 8",
        "automationName": "UiAutomator2",
        "app": "/tmp/app.apk",
        "appPackage": "com.example.app",
        "appActivity": "MainActivity",
        "udid": "emulator-5554",
    }
    driver = DummyDriver(
        session_id="session-1",
        context="NATIVE_APP",
        activity="MainActivity",
        package="com.example.app",
        capabilities=caps,
    )
    dummy = DummyAppium(driver=driver, open_apps=[driver])
    monkeypatch.setattr(agentic, "_get_library_instance", lambda name: dummy)
    result = agentic._build_mobile_start_state()
    assert "Active mobile session detected" in result
    assert "Open applications: 1" in result
    assert "Session ID: session-1" in result
    assert "Current context: NATIVE_APP" in result
    assert "Current activity: MainActivity" in result
    assert "Current package: com.example.app" in result
    assert "Platform: Android" in result
    assert "Platform version: 14" in result
    assert "Device: Pixel 8" in result
    assert "Automation: UiAutomator2" in result
    assert "App: /tmp/app.apk" in result
    assert "App package: com.example.app" in result
    assert "App activity: MainActivity" in result
    assert "UDID: emulator-5554" in result


def test_merge_app_context_includes_start_state():
    agentic = AIAgentic()
    merged = agentic._merge_app_context("Base context", "Start State: Active")
    assert "Base context" in merged
    assert "Start State: Active" in merged
