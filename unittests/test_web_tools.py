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

    def click_element(self, locator):
        self.clicked.append(locator)

    def get_browser_ids(self):
        return list(self.browser_ids)

    def go_to(self, url):
        self.navigated.append(url)

    def open_browser(self, url, browser):
        self.opened.append((url, browser))


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
