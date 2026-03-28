"""Unit tests for adaptive mobile tool helpers."""

import pytest

from AITester.executor import create_session, set_active_session
from AITester.tools import mobile_tools


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


class DummySwitchTo:
    def __init__(self, driver):
        self.driver = driver

    def context(self, name):
        self.driver.current_context = name
        self.driver.switched_contexts.append(name)


class DummyDriver:
    def __init__(self, contexts=None, current_context="NATIVE_APP", window_size=None):
        self.session_id = "mobile-session"
        self.current_context = current_context
        self.contexts = list(contexts or [current_context])
        self.capabilities = {}
        self.current_activity = ""
        self.current_package = ""
        self.switched_contexts = []
        self._window_size = window_size or {"width": 1000, "height": 2000}
        self.switch_to = DummySwitchTo(self)

    def get_window_size(self):
        return dict(self._window_size)


class DummyAppium:
    def __init__(self, sources, contexts=None, current_context="NATIVE_APP", window_size=None):
        self._sources = list(sources)
        self.clicked = []
        self.source_calls = 0
        self.closed = 0
        self.closed_all = 0
        self.reset = 0
        self.swipes = []
        self.back = 0
        self.hidden_keyboard = []
        self.keyboard_shown = False
        self.keycodes = []
        self.long_keycodes = []
        self.waited_page_contains_element = []
        self.waited_page_does_not_contain = []
        self.waited_page_does_not_contain_element = []
        self.element_hidden_checks = 0
        self.hide_after = 0
        self._driver = DummyDriver(
            contexts=contexts,
            current_context=current_context,
            window_size=window_size,
        )

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

    def swipe(self, **kwargs):
        self.swipes.append(kwargs)

    def go_back(self):
        self.back += 1

    def hide_keyboard(self, key_name=None):
        self.hidden_keyboard.append(key_name)

    def is_keyboard_shown(self):
        return self.keyboard_shown

    def press_keycode(self, keycode, metastate=None):
        self.keycodes.append((keycode, metastate))

    def long_press_keycode(self, keycode, metastate=None):
        self.long_keycodes.append((keycode, metastate))

    def wait_until_page_contains_element(self, locator, timeout, error=None):
        self.waited_page_contains_element.append((locator, timeout))

    def wait_until_page_does_not_contain(self, text, timeout, error=None):
        self.waited_page_does_not_contain.append((text, timeout))

    def wait_until_page_does_not_contain_element(self, locator, timeout, error=None):
        self.waited_page_does_not_contain_element.append((locator, timeout))

    def element_should_not_be_visible(self, locator):
        self.element_hidden_checks += 1
        if self.element_hidden_checks < self.hide_after:
            raise AssertionError(f"{locator} still visible")


class FaultySourceAppium(DummyAppium):
    def __init__(self):
        super().__init__([EMPTY_SOURCE])

    def get_source(self):
        self.source_calls += 1
        raise RuntimeError("socket hang up")


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


def test_appium_get_view_snapshot_falls_back_when_source_unavailable(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = FaultySourceAppium()
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    snapshot = mobile_tools.appium_get_view_snapshot()
    source = mobile_tools.appium_get_source()

    assert "Screen analysis note: Unable to retrieve Appium page source: socket hang up" in snapshot
    assert "Screen text preview:" in snapshot
    assert source == "Page source unavailable: Unable to retrieve Appium page source: socket hang up"
    assert dummy.source_calls == 1


def test_appium_switch_context_selects_webview_and_invalidates_cache(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium(
        [EMPTY_SOURCE],
        contexts=["NATIVE_APP", "WEBVIEW_com.example"],
    )
    invalidations = []
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)
    monkeypatch.setattr(
        mobile_tools,
        "invalidate_mobile_snapshot_cache",
        lambda driver=None: invalidations.append(driver),
    )

    result = mobile_tools.appium_switch_context("webview")

    assert result == "Switched mobile context to WEBVIEW_com.example"
    assert dummy._driver.current_context == "WEBVIEW_com.example"
    assert dummy._driver.switched_contexts == ["WEBVIEW_com.example"]
    assert invalidations == [dummy._driver, None]


def test_appium_scroll_down_uses_viewport_dimensions(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE], window_size={"width": 1000, "height": 2000})
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_scroll_down()

    assert result == "Scrolled down using viewport gesture"
    assert dummy.swipes == [
        {
            "start_x": 500,
            "start_y": 1640,
            "end_x": 500,
            "end_y": 700,
            "duration": 800,
        }
    ]


def test_appium_scroll_up_uses_viewport_dimensions(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE], window_size={"width": 1000, "height": 2000})
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_scroll_up()

    assert result == "Scrolled up using viewport gesture"
    assert dummy.swipes == [
        {
            "start_x": 500,
            "start_y": 700,
            "end_x": 500,
            "end_y": 1640,
            "duration": 800,
        }
    ]


def test_appium_go_back_uses_navigation_helper(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_go_back()

    assert result == "Navigated back in the mobile app"
    assert dummy.back == 1


def test_appium_hide_keyboard_accepts_optional_key_name(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_hide_keyboard("Done")

    assert result == "On-screen keyboard hidden"
    assert dummy.hidden_keyboard == ["Done"]


def test_appium_is_keyboard_shown_reports_state(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE])
    dummy.keyboard_shown = True
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_is_keyboard_shown()

    assert result == "Keyboard shown: True"


def test_appium_press_keycode_supports_long_press(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_press_keycode(66, metastate=2, long_press=True)

    assert result == "Long-pressed Android keycode 66"
    assert dummy.keycodes == []
    assert dummy.long_keycodes == [(66, 2)]


def test_appium_select_picker_option_clicks_trigger_then_option(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)
    monkeypatch.setattr(mobile_tools, "_maybe_scroll_into_view", lambda al, locator: None)

    result = mobile_tools.appium_select_picker_option("id=country-picker", "Slovakia")

    option_locator = (
        'xpath=//*[@text="Slovakia" or @label="Slovakia" or @name="Slovakia" '
        'or @content-desc="Slovakia" or @contentDescription="Slovakia" or @value="Slovakia"]'
    )
    assert result == f"Selected 'Slovakia' from picker: id=country-picker via {option_locator}"
    assert dummy.clicked == ["id=country-picker", option_locator]
    assert dummy.waited_page_contains_element == [(option_locator, 5.0)]


def test_appium_wait_until_page_contains_element_passes_timeout(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_wait_until_page_contains_element("id=login", timeout="7s")

    assert result == "Screen now contains element: id=login"
    assert dummy.waited_page_contains_element == [("id=login", 7.0)]


def test_appium_wait_until_element_is_not_visible_retries_until_hidden(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE])
    dummy.hide_after = 3
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    class FakeClock:
        def __init__(self):
            self.now = 0.0

        def monotonic(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    fake_clock = FakeClock()
    monkeypatch.setattr(mobile_tools.time, "monotonic", fake_clock.monotonic)
    monkeypatch.setattr(mobile_tools.time, "sleep", fake_clock.sleep)

    result = mobile_tools.appium_wait_until_element_is_not_visible(
        "id=loader",
        timeout="5s",
        poll_interval="500ms",
    )

    assert result == "Element is no longer visible: id=loader"
    assert dummy.element_hidden_checks == 3


def test_appium_wait_until_page_does_not_contain_and_element(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium([EMPTY_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result_text = mobile_tools.appium_wait_until_page_does_not_contain("Saving", timeout="4s")
    result_element = mobile_tools.appium_wait_until_page_does_not_contain_element(
        "id=toast",
        timeout="4s",
    )

    assert result_text == "Screen no longer contains: 'Saving'"
    assert result_element == "Screen no longer contains element: id=toast"
    assert dummy.waited_page_does_not_contain == [("Saving", 4.0)]
    assert dummy.waited_page_does_not_contain_element == [("id=toast", 4.0)]


def test_appium_wait_for_loading_to_finish_uses_snapshot_until_stable(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()

    snapshots = iter(
        [
            {"loading_indicators": [{"kind": "spinner", "label": "Loading"}], "context": "NATIVE_APP"},
            {"loading_indicators": [], "context": "NATIVE_APP"},
            {"loading_indicators": [], "context": "NATIVE_APP"},
        ]
    )
    monkeypatch.setattr(
        mobile_tools,
        "_get_mobile_snapshot_data",
        lambda force_refresh=False: next(snapshots),
    )

    class FakeClock:
        def __init__(self):
            self.now = 0.0

        def monotonic(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    fake_clock = FakeClock()
    monkeypatch.setattr(mobile_tools.time, "monotonic", fake_clock.monotonic)
    monkeypatch.setattr(mobile_tools.time, "sleep", fake_clock.sleep)

    result = mobile_tools.appium_wait_for_loading_to_finish()

    assert result == "Mobile loading indicators cleared after 3 checks (stable_polls=2)"
