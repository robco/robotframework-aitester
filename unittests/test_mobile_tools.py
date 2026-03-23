"""Unit tests for adaptive mobile tool helpers."""

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

    def get_source(self):
        if len(self._sources) > 1:
            return self._sources.pop(0)
        return self._sources[0]

    def click_element(self, locator):
        self.clicked.append(locator)


def test_appium_get_view_snapshot_reports_possible_interruptions(monkeypatch):
    dummy = DummyAppium([PERMISSION_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_get_view_snapshot()

    assert "Screen text preview:" in result
    assert "Possible interruptions (1):" in result
    assert "permission: While using the app (allow)" in result


def test_appium_handle_common_interruptions_clicks_permission(monkeypatch):
    dummy = DummyAppium([PERMISSION_SOURCE, EMPTY_SOURCE])
    monkeypatch.setattr(mobile_tools, "_get_appium", lambda: dummy)

    result = mobile_tools.appium_handle_common_interruptions()

    assert "Handled 1 common interruption" in result
    assert "permission -> While using the app" in result
    assert dummy.clicked
    assert "While using the app" in dummy.clicked[0]
