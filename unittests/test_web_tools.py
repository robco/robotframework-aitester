"""Unit tests for adaptive web tool helpers."""

from AIAgentic.tools import web_tools


class DummySelenium:
    def __init__(self):
        self.driver = object()
        self.clicked = []

    def click_element(self, locator):
        self.clicked.append(locator)


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
