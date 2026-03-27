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
        "document_ready_state": "complete",
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
        "frames": [
            {
                "path": "1",
                "depth": 0,
                "locator": "id=checkout-frame",
                "id": "checkout-frame",
                "name": "checkout",
                "title": "Checkout",
                "src": "/frames/checkout",
                "same_origin_accessible": True,
                "document_title": "Checkout Widget",
                "document_url": "https://example.test/frames/checkout",
                "text_preview": "Card number Expiry Submit order",
                "interactive_elements": 3,
                "forms": 1,
                "child_frames": 0,
                "headings": [{"level": "H2", "text": "Payment"}],
            },
            {
                "path": "2",
                "depth": 0,
                "locator": "xpath=//html[1]/body[1]/iframe[2]",
                "id": None,
                "name": "ads",
                "title": "Ads",
                "src": "https://ads.example.test/widget",
                "same_origin_accessible": False,
                "document_title": None,
                "document_url": None,
                "text_preview": None,
                "interactive_elements": 0,
                "forms": 0,
                "child_frames": 0,
                "headings": [],
                "access_error": "cross-origin or inaccessible",
            },
        ],
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
        "loading_indicators": [],
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
    assert "Document readyState: complete" in snapshot
    assert "Frames: 2" in snapshot
    assert "Possible blockers (1)" in snapshot
    assert "Found 1 interactive elements" in interactive
    assert "Headings (1)" in structure
    assert "Frames (2)" in structure
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


def test_get_form_fields_reports_dropdown_metadata_from_snapshot(monkeypatch):
    browser_analysis_tools.invalidate_page_snapshot_cache()
    snapshot = sample_snapshot()
    snapshot["forms"][0]["form_fields"].append(
        {
            "name": "country",
            "tag": "select",
            "type": "select-one",
            "required": False,
            "placeholder": None,
            "label": "Country",
            "control_kind": "native-select",
            "selected_text": "France",
            "options": [
                {"text": "France", "value": "fr"},
                {"text": "Germany", "value": "de"},
            ],
        }
    )
    driver = DummyDriver(snapshot)
    monkeypatch.setattr(
        browser_analysis_tools,
        "_get_selenium",
        lambda: DummySelenium(driver),
    )

    fields = browser_analysis_tools.get_form_fields()

    assert "country (select-one/native-select): Country" in fields
    assert "selected: France" in fields
    assert "options: France, Germany" in fields


def test_get_interactive_elements_reports_dropdown_kind_and_options(monkeypatch):
    browser_analysis_tools.invalidate_page_snapshot_cache()
    snapshot = sample_snapshot()
    snapshot["interactive_elements"] = [
        {
            "tag": "div",
            "type": None,
            "locator": "id=status",
            "text": "Status",
            "control_kind": "custom-dropdown",
            "selected_text": "Open",
            "options": [
                {"text": "Open", "value": "open"},
                {"text": "Closed", "value": "closed"},
            ],
        }
    ]
    driver = DummyDriver(snapshot)
    monkeypatch.setattr(
        browser_analysis_tools,
        "_get_selenium",
        lambda: DummySelenium(driver),
    )

    interactive = browser_analysis_tools.get_interactive_elements()

    assert "kind=custom-dropdown" in interactive
    assert 'selected="Open"' in interactive
    assert "options=[Open, Closed]" in interactive


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


def test_get_frame_inventory_uses_snapshot_frame_metadata(monkeypatch):
    browser_analysis_tools.invalidate_page_snapshot_cache()
    driver = DummyDriver(sample_snapshot())
    monkeypatch.setattr(
        browser_analysis_tools,
        "_get_selenium",
        lambda: DummySelenium(driver),
    )

    inventory = browser_analysis_tools.get_frame_inventory()

    assert "Frames (2)" in inventory
    assert "locator=id=checkout-frame" in inventory
    assert "same-origin" in inventory
    assert "cross-origin or inaccessible" in inventory
    assert driver.execute_script_calls == 1


def test_get_loading_state_reports_detected_indicators(monkeypatch):
    browser_analysis_tools.invalidate_page_snapshot_cache()
    snapshot = sample_snapshot()
    snapshot["document_ready_state"] = "interactive"
    snapshot["loading_indicators"] = [
        {
            "kind": "spinner",
            "locator": "css=.spinner",
            "role": "progressbar",
            "text": "Loading profile",
            "signals": ["role=progressbar", "loading-related id/class/text"],
        }
    ]
    driver = DummyDriver(snapshot)
    monkeypatch.setattr(
        browser_analysis_tools,
        "_get_selenium",
        lambda: DummySelenium(driver),
    )

    state = browser_analysis_tools.get_loading_state()
    page_snapshot = browser_analysis_tools.get_page_snapshot()

    assert "Loading indicators (1) (readyState=interactive):" in state
    assert "locator=css=.spinner" in state
    assert 'text="Loading profile"' in state
    assert "signals=role=progressbar, loading-related id/class/text" in state
    assert "Loading indicators (1) (readyState=interactive):" in page_snapshot
