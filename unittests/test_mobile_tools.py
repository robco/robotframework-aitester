"""Unit tests for adaptive mobile tool helpers."""

import pytest

from AIAgentic.executor import create_session, set_active_session
from AIAgentic.tools import mobile_tools


PERMISSION_SOURCE = """
<hierarchy>
  <android.widget.FrameLayout resource-id="permission-dialog">
    <android.widget.TextView text="Allow location access?" />
    <android.widget.Button text="While using the app" clickable="true" />
    <android.widget.Button text="Don't allow" clickable="true" />
  </android.widget.FrameLayout>
</hierarchy>
""".strip()

EMPTY_SOURCE = """
<hierarchy>
  <android.widget.FrameLayout>
    <android.widget.TextView text="Home" />
  </android.widget.FrameLayout>
</hierarchy>
""".strip()


class DummyAppium:
    def __init__(self, sources):
        self._sources = list(sources)
        self.clicked = []
        self.source_calls = 0
        self.closed = 0
        self.closed_all = 0
        self.reset = 0
        self._driver = type("Driver", (), {"session_id": "mobile-session"})()

    def get_source(self):
        self.source_calls += 1
        if len(self._sources) > 1:
            return self._sources.pop(0)
        return self._sources[0]

    def click_element(self, locator):
        self.clicked.append(locator)

    def _current_application(self):
        return self._driver

    def close_application(self):
        self.closed += 1

    def close_all_applications(self):
        self.closed_all += 1

    def reset_application(self):
        self.reset += 1


def test_appium_get_view_snapshot_reports_possible_interruptions(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([PERMISSION_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_get_view_snapshot()

    assert "Screen text preview:" in result
    assert "Possible interruptions (1):" in result
    assert "permission: While using the app (allow)" in result


def test_appium_handle_common_interruptions_clicks_permission(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([PERMISSION_SOURCE, EMPTY_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_handle_common_interruptions()

    assert "Handled 1 common interruption" in result
    assert "permission -> While using the app" in result
    assert dummy.clicked
    assert "While using the app" in dummy.clicked[0]


def test_appium_get_source_reuses_cached_snapshot(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([PERMISSION_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    snapshot = mobile_tools.appium_get_view_snapshot()
    source = mobile_tools.appium_get_source()

    assert "Screen text preview:" in snapshot
    assert source.startswith("Page source:\n<hierarchy>")
    assert dummy.source_calls == 1


def test_appium_close_application_blocks_when_not_explicitly_requested(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    session = create_session("test", "app", test_mode="mobile")
    dummy = DummyAppium([EMPTY_SOURCE])
    set_active_session(session)
    try:
        monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

        with pytest.raises(AssertionError, match="only when the user explicitly requests"):
            mobile_tools.appium_close_application()

        assert dummy.closed == 0
    finally:
        set_active_session(None)


def test_appium_reset_application_allows_explicit_user_requested_restart(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    session = create_session(
        "restart app",
        "app",
        test_mode="mobile",
        allow_browser_termination=True,
    )
    dummy = DummyAppium([EMPTY_SOURCE])
    set_active_session(session)
    try:
        monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

        result = mobile_tools.appium_reset_application()

        assert result == "Application reset"
        assert dummy.reset == 1
    finally:
        set_active_session(None)
