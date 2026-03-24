"""Unit tests for browser analysis snapshot caching."""

import json

from AIAgentic.tools import browser_analysis_tools


class DummyDriver:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.session_id = "driver-1"
        self.execute_script_calls = 0

    def execute_script(self, code):
        self.execute_script_calls += 1
        return json.dumps(self.snapshot)


class DummySelenium:
    def __init__(self, driver):
        self.driver = driver

    def get_element_count(self, locator):
        return 3


class FallbackDriver:
    def __init__(self):
        self.session_id = "driver-fallback"
        self.title = "Fallback Example"
        self.current_url = "https://fallback.test"
        self.execute_script_calls = []

    def execute_script(self, code):
        self.execute_script_calls.append(code)
        if len(self.execute_script_calls) == 1:
            raise RuntimeError("javascript error: missing ) after argument list")
        return "Recovered text"


def sample_snapshot():
    return {
        "title": "Example",
        "url": "https://example.test",
        "text": "Hello world",
        "interactive_elements": [
            {"tag": "button", "type": "submit", "locator": "id=submit", "text": "Submit"}
        ],
        "headings": [{"level": "H1", "text": "Welcome"}],
        "forms": [
            {
                "index": 0,
                "id": "login",
                "method": "post",
                "fields": 2,
                "form_fields": [
                    {"name": "username", "tag": "input", "required": True, "placeholder": "Email"},
                    {"name": "password", "tag": "input", "required": True, "placeholder": "Password"},
                ],
            }
        ],
        "nav_items": [{"text": "Home", "href": "https://example.test/home"}],
        "main_sections": [{"tag": "main", "preview": "Hello"}],
        "links": [{"text": "Home", "href": "https://example.test/home"}],
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
        ],
        "browser_errors": [],
    }


def test_browser_analysis_tools_share_cached_snapshot(monkeypatch):
    browser_analysis_tools.invalidate_page_snapshot_cache()
    driver = DummyDriver(sample_snapshot())
    monkeypatch.setattr(
        browser_analysis_tools,
        "_get_selenium",
        lambda: DummySelenium(driver),
    )

    snapshot = browser_analysis_tools.get_page_snapshot()
    interactive = browser_analysis_tools.get_interactive_elements()
    structure = browser_analysis_tools.get_page_structure()
    text = browser_analysis_tools.get_page_text_content()

    assert "Page: Example" in snapshot
    assert "Possible blockers (1)" in snapshot
    assert "Found 1 interactive elements" in interactive
    assert "Headings (1)" in structure
    assert "Hello world" in text
    assert driver.execute_script_calls == 1


def test_browser_analysis_cache_invalidation_forces_refresh(monkeypatch):
    browser_analysis_tools.invalidate_page_snapshot_cache()
    driver = DummyDriver(sample_snapshot())
    monkeypatch.setattr(
        browser_analysis_tools,
        "_get_selenium",
        lambda: DummySelenium(driver),
    )

    browser_analysis_tools.get_page_snapshot()
    browser_analysis_tools.invalidate_page_snapshot_cache(driver)
    browser_analysis_tools.get_page_snapshot()

    assert driver.execute_script_calls == 2


def test_get_form_fields_uses_snapshot_for_default_form(monkeypatch):
    browser_analysis_tools.invalidate_page_snapshot_cache()
    driver = DummyDriver(sample_snapshot())
    monkeypatch.setattr(
        browser_analysis_tools,
        "_get_selenium",
        lambda: DummySelenium(driver),
    )

    fields = browser_analysis_tools.get_form_fields()

    assert "Form fields (2)" in fields
    assert "username (input) [REQUIRED]: Email" in fields
    assert driver.execute_script_calls == 1


def test_browser_analysis_tools_fallback_to_minimal_snapshot(monkeypatch):
    browser_analysis_tools.invalidate_page_snapshot_cache()
    driver = FallbackDriver()
    monkeypatch.setattr(
        browser_analysis_tools,
        "_get_selenium",
        lambda: DummySelenium(driver),
    )

    snapshot = browser_analysis_tools.get_page_snapshot()
    structure = browser_analysis_tools.get_page_structure()
    text = browser_analysis_tools.get_page_text_content()

    assert "Page: Fallback Example" in snapshot
    assert "Recovered text" in snapshot
    assert "Page: Fallback Example" in structure
    assert "Recovered text" in text
    assert len(driver.execute_script_calls) == 2
