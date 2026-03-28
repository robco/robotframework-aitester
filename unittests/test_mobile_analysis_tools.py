"""Unit tests for structured mobile analysis tools."""

from AITester.tools import mobile_analysis_tools, mobile_tools


ANALYSIS_SOURCE = """
<hierarchy>
  <android.widget.FrameLayout resource-id="root">
    <android.widget.TextView text="Welcome" />
    <android.widget.EditText
        resource-id="com.example:id/email"
        hint="Email"
        clickable="true"
        focusable="true"
    />
    <android.widget.Button
        text="Continue"
        content-desc="Continue"
        clickable="true"
        enabled="true"
    />
    <android.widget.Switch
        text="Biometrics"
        clickable="true"
        checked="true"
    />
    <android.widget.ProgressBar resource-id="loader" />
  </android.widget.FrameLayout>
</hierarchy>
""".strip()


class DummyDriver:
    def __init__(self, contexts=None, current_context="NATIVE_APP"):
        self.session_id = "mobile-analysis-session"
        self.current_context = current_context
        self.contexts = list(contexts or [current_context])
        self.capabilities = {}
        self.current_activity = ""
        self.current_package = ""

    def get_window_size(self):
        return {"width": 1080, "height": 2400}


class DummyAppium:
    def __init__(self, source, contexts=None, current_context="NATIVE_APP"):
        self._source = source
        self.source_calls = 0
        self._driver = DummyDriver(contexts=contexts, current_context=current_context)

    def get_source(self):
        self.source_calls += 1
        return self._source

    def _current_application(self):
        return self._driver


def test_appium_get_interactive_elements_reports_structured_controls(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium(ANALYSIS_SOURCE)
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_analysis_tools.appium_get_interactive_elements()

    assert "Found 3 interactive elements:" in result
    assert "input, locator=id=com.example:id/email, hint=Email" in result
    assert "button, label=Continue, locator=accessibility_id=Continue" in result
    assert "switch, label=Biometrics" in result


def test_appium_get_loading_state_reports_busy_indicator(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium(ANALYSIS_SOURCE)
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_analysis_tools.appium_get_loading_state()

    assert "Loading state: busy; indicators=1" in result
    assert "locator=id=loader" in result


def test_appium_get_screen_structure_summarizes_controls(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium(
        ANALYSIS_SOURCE,
        contexts=["NATIVE_APP", "WEBVIEW_com.example"],
    )
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_analysis_tools.appium_get_screen_structure()

    assert "Interactive elements: 3" in result
    assert "Input fields: 1" in result
    assert "Buttons: 1" in result
    assert "Switches / checkboxes: 1" in result
    assert "Loading indicators: 1" in result
    assert "Contexts: NATIVE_APP, WEBVIEW_com.example" in result


def test_appium_get_context_inventory_lists_available_contexts(monkeypatch):
    mobile_tools.invalidate_mobile_snapshot_cache()
    dummy = DummyAppium(
        ANALYSIS_SOURCE,
        contexts=["NATIVE_APP", "WEBVIEW_com.example"],
        current_context="NATIVE_APP",
    )
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_analysis_tools.appium_get_context_inventory()

    assert "Current context: NATIVE_APP" in result
    assert "Available contexts (2):" in result
    assert "NATIVE_APP (native) [current]" in result
    assert "WEBVIEW_com.example (webview)" in result
