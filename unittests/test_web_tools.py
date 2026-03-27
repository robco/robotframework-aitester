"""Unit tests for adaptive web tool helpers."""

import pytest

from AIAgentic.executor import create_session, set_active_session
from AIAgentic.tools import web_tools


class DummySelenium:
    def __init__(self, browser_ids=None):
        self.driver = object()
        self.browser_ids = browser_ids or []
        self.clicked = []
        self.navigated = []
        self.opened = []
        self.closed = 0
        self.closed_all = 0
        self.waited_not_visible = []
        self.waited_text_gone = []
        self.waited_element_gone = []

    def click_element(self, locator):
        self.clicked.append(locator)

    def get_browser_ids(self):
        return list(self.browser_ids)

    def go_to(self, url):
        self.navigated.append(url)

    def open_browser(self, url, browser):
        self.opened.append((url, browser))

    def close_browser(self):
        self.closed += 1

    def close_all_browsers(self):
        self.closed_all += 1

    def wait_until_element_is_not_visible(self, locator, timeout):
        self.waited_not_visible.append((locator, timeout))

    def wait_until_page_does_not_contain(self, text, timeout):
        self.waited_text_gone.append((text, timeout))

    def wait_until_page_does_not_contain_element(self, locator, timeout):
        self.waited_element_gone.append((locator, timeout))


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_selenium_handle_common_blockers_clicks_detected_action(monkeypatch):
    dummy = DummySelenium()
    snapshots = iter(
        [
            {
                "possible_blockers": [
                    {
                        "category": "cookie/consent",
                        "preview": "We use cookies",
                        "actions": [
                            {
                                "label": "Accept All",
                                "locator": "id=accept-cookies",
                                "kind": "accept",
                                "score": 140,
                            }
                        ],
                    }
                ]
            },
            {"possible_blockers": []},
        ]
    )

    monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)
    monkeypatch.setattr(web_tools, "_maybe_scroll_into_view", lambda sl, locator: None)
    monkeypatch.setattr(
        web_tools,
        "_get_page_snapshot_data",
        lambda force_refresh=False: next(snapshots),
    )
    monkeypatch.setattr(
        web_tools,
        "invalidate_page_snapshot_cache",
        lambda driver=None: None,
    )

    result = web_tools.selenium_handle_common_blockers()

    assert "Handled 1 common blocker" in result
    assert dummy.clicked == ["id=accept-cookies"]


def test_collect_blocker_actions_prefers_cookie_acceptance_over_dismissal():
    actions = web_tools._collect_blocker_actions(
        {
            "possible_blockers": [
                {
                    "category": "cookie/consent",
                    "preview": "We use cookies",
                    "actions": [
                        {
                            "label": "Close",
                            "locator": "id=close-cookie-banner",
                            "kind": "dismiss",
                            "score": 400,
                        },
                        {
                            "label": "Accept all cookies",
                            "locator": "id=accept-cookies",
                            "kind": "accept",
                            "score": 100,
                        },
                    ],
                }
            ]
        }
    )

    assert [action["locator"] for action in actions] == [
        "id=accept-cookies",
        "id=close-cookie-banner",
    ]


def test_selenium_handle_common_blockers_prefers_cookie_acceptance(monkeypatch):
    dummy = DummySelenium()
    snapshots = iter(
        [
            {
                "possible_blockers": [
                    {
                        "category": "cookie/consent",
                        "preview": "We use cookies",
                        "actions": [
                            {
                                "label": "Close",
                                "locator": "id=close-cookie-banner",
                                "kind": "dismiss",
                                "score": 400,
                            },
                            {
                                "label": "Accept all cookies",
                                "locator": "id=accept-cookies",
                                "kind": "accept",
                                "score": 100,
                            },
                        ],
                    }
                ]
            },
            {"possible_blockers": []},
        ]
    )

    monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)
    monkeypatch.setattr(web_tools, "_maybe_scroll_into_view", lambda sl, locator: None)
    monkeypatch.setattr(
        web_tools,
        "_get_page_snapshot_data",
        lambda force_refresh=False: next(snapshots),
    )
    monkeypatch.setattr(
        web_tools,
        "invalidate_page_snapshot_cache",
        lambda driver=None: None,
    )

    result = web_tools.selenium_handle_common_blockers()

    assert "Handled 1 common blocker" in result
    assert dummy.clicked == ["id=accept-cookies"]


def test_selenium_handle_common_blockers_noop_when_no_candidates(monkeypatch):
    dummy = DummySelenium()
    monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)
    monkeypatch.setattr(
        web_tools,
        "_get_page_snapshot_data",
        lambda force_refresh=False: {"possible_blockers": []},
    )

    result = web_tools.selenium_handle_common_blockers()

    assert result == "No common blockers detected on the page"
    assert dummy.clicked == []


def test_selenium_go_to_allows_initial_entry_only(monkeypatch):
    session = create_session("test", "app", test_mode="web")
    dummy = DummySelenium()
    set_active_session(session)
    try:
        monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

        result = web_tools.selenium_go_to("https://example.test")

        assert result == "Navigated to https://example.test"
        assert dummy.navigated == ["https://example.test"]
        assert session.direct_url_navigations_used == 1
    finally:
        set_active_session(None)


def test_selenium_go_to_blocks_after_user_interaction(monkeypatch):
    session = create_session("test", "app", test_mode="web")
    session.ui_interactions_total = 1
    dummy = DummySelenium()
    set_active_session(session)
    try:
        monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

        with pytest.raises(AssertionError, match="blocked by default after the flow has started"):
            web_tools.selenium_go_to("https://example.test/settings")

        assert dummy.navigated == []
    finally:
        set_active_session(None)


def test_selenium_go_to_blocks_when_reusing_active_browser_session(monkeypatch):
    session = create_session(
        "test",
        "app",
        test_mode="web",
        reuse_existing_session=True,
        start_state_summary="Start State: Active browser session detected.",
    )
    dummy = DummySelenium()
    set_active_session(session)
    try:
        monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

        with pytest.raises(AssertionError, match="starts with an active browser session"):
            web_tools.selenium_go_to("https://example.test/account")

        assert dummy.navigated == []
    finally:
        set_active_session(None)


def test_selenium_go_to_allows_explicit_user_requested_url_after_interaction(monkeypatch):
    session = create_session(
        "test",
        "app",
        test_mode="web",
        allowed_direct_urls=["https://example.test/settings"],
    )
    session.ui_interactions_total = 3
    dummy = DummySelenium()
    set_active_session(session)
    try:
        monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

        result = web_tools.selenium_go_to("https://example.test/settings")

        assert result == "Navigated to https://example.test/settings"
        assert dummy.navigated == ["https://example.test/settings"]
        assert session.direct_url_navigations_used == 1
    finally:
        set_active_session(None)


def test_selenium_go_to_allows_explicit_user_requested_url_with_active_session(monkeypatch):
    session = create_session(
        "test",
        "app",
        test_mode="web",
        reuse_existing_session=True,
        start_state_summary="Start State: Active browser session detected.",
        allowed_direct_urls=["https://example.test/account"],
    )
    dummy = DummySelenium()
    set_active_session(session)
    try:
        monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

        result = web_tools.selenium_go_to("https://example.test/account")

        assert result == "Navigated to https://example.test/account"
        assert dummy.navigated == ["https://example.test/account"]
    finally:
        set_active_session(None)


def test_selenium_open_browser_records_initial_direct_navigation(monkeypatch):
    session = create_session("test", "app", test_mode="web")
    dummy = DummySelenium()
    set_active_session(session)
    try:
        monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

        result = web_tools.selenium_open_browser("https://example.test", "chrome")

        assert result == "Browser opened and navigated to https://example.test"
        assert dummy.opened == [("https://example.test", "chrome")]
        assert session.direct_url_navigations_used == 1
    finally:
        set_active_session(None)


def test_selenium_close_all_browsers_blocks_when_not_explicitly_requested(monkeypatch):
    session = create_session("test", "app", test_mode="web")
    dummy = DummySelenium(browser_ids=[1])
    set_active_session(session)
    try:
        monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

        with pytest.raises(AssertionError, match="only when the user explicitly requests it"):
            web_tools.selenium_close_all_browsers()

        assert dummy.closed_all == 0
    finally:
        set_active_session(None)


def test_selenium_close_browser_allows_explicit_user_requested_restart(monkeypatch):
    session = create_session(
        "restart browser",
        "app",
        test_mode="web",
        allow_browser_termination=True,
    )
    dummy = DummySelenium(browser_ids=[1])
    set_active_session(session)
    try:
        monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

        result = web_tools.selenium_close_browser()

        assert result == "Browser closed"
        assert dummy.closed == 1
    finally:
        set_active_session(None)


def test_selenium_wait_until_element_is_not_visible(monkeypatch):
    dummy = DummySelenium()
    monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

    result = web_tools.selenium_wait_until_element_is_not_visible("css=.spinner", "30s")

    assert result == "Element is no longer visible: css=.spinner"
    assert dummy.waited_not_visible == [("css=.spinner", "30s")]


def test_selenium_wait_until_page_does_not_contain(monkeypatch):
    dummy = DummySelenium()
    monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

    result = web_tools.selenium_wait_until_page_does_not_contain("Loading...", "20s")

    assert result == "Page no longer contains: 'Loading...'"
    assert dummy.waited_text_gone == [("Loading...", "20s")]


def test_selenium_wait_until_page_does_not_contain_element(monkeypatch):
    dummy = DummySelenium()
    monkeypatch.setattr(web_tools, "_get_selenium", lambda: dummy)

    result = web_tools.selenium_wait_until_page_does_not_contain_element(
        "css=.loading-overlay", "45s"
    )

    assert result == "Page no longer contains element: css=.loading-overlay"
    assert dummy.waited_element_gone == [("css=.loading-overlay", "45s")]


def test_selenium_wait_for_loading_to_finish_after_indicators_disappear(monkeypatch):
    states = [
        {
            "document_ready_state": "loading",
            "loading_indicators": [{"kind": "spinner", "locator": "css=.spinner"}],
        },
        {
            "document_ready_state": "complete",
            "loading_indicators": [{"kind": "spinner", "locator": "css=.spinner"}],
        },
        {
            "document_ready_state": "complete",
            "loading_indicators": [],
        },
        {
            "document_ready_state": "complete",
            "loading_indicators": [],
        },
    ]
    calls = []
    clock = FakeClock()

    def fake_snapshot(force_refresh=False):
        calls.append(force_refresh)
        index = min(len(calls) - 1, len(states) - 1)
        return states[index]

    monkeypatch.setattr(web_tools, "_get_page_snapshot_data", fake_snapshot)
    monkeypatch.setattr(web_tools.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(web_tools.time, "sleep", clock.sleep)

    result = web_tools.selenium_wait_for_loading_to_finish(
        timeout="5s", poll_interval="200ms", stable_polls=2
    )

    assert "Page appears stable" in result
    assert "observed_loading=yes" in result
    assert "readyState=complete, indicators=none" in result
    assert calls == [True, True, True, True]


def test_selenium_wait_for_loading_to_finish_times_out_with_last_detected_state(monkeypatch):
    clock = FakeClock()

    monkeypatch.setattr(
        web_tools,
        "_get_page_snapshot_data",
        lambda force_refresh=False: {
            "document_ready_state": "loading",
            "loading_indicators": [{"kind": "spinner", "locator": "css=.spinner"}],
        },
    )
    monkeypatch.setattr(web_tools.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(web_tools.time, "sleep", clock.sleep)

    with pytest.raises(AssertionError, match="Loading did not finish within 500ms"):
        web_tools.selenium_wait_for_loading_to_finish(
            timeout="500ms", poll_interval="200ms", stable_polls=2
        )
