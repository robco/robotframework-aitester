# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for common tools module."""

import os
import shutil
import pytest
from strands import tool

from AITester.executor import StepStatus, create_session, set_active_session
from AITester.tools import browser_analysis_tools, common_tools, mobile_tools


@pytest.fixture
def active_session():
    session = create_session("test", "app")
    set_active_session(session)
    yield session
    set_active_session(None)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("PASS", StepStatus.PASSED),
        ("passed", StepStatus.PASSED),
        ("ok", StepStatus.PASSED),
        ("success", StepStatus.PASSED),
        ("FAIL", StepStatus.FAILED),
        ("failed", StepStatus.FAILED),
        ("skip", StepStatus.SKIPPED),
        ("ignored", StepStatus.SKIPPED),
        ("unknown", StepStatus.ERROR),
    ],
)
def test_normalize_step_status(value, expected):
    assert common_tools._normalize_step_status(value) is expected


@pytest.mark.parametrize(
    "screenshot_path,expected_name",
    [
        ("/tmp/ss.png", "ss.png"),
        ("/tmp/ss.jpg", "ss.jpg"),
    ],
)
def test_record_step_records_session(active_session, screenshot_path, expected_name):
    result = common_tools.record_step(
        action="click",
        description="Click button",
        status="PASS",
        duration_ms="12.5",
        screenshot_path=screenshot_path,
        assertion_message="ok",
    )
    assert "Recorded step: click - Click button (passed)" in result
    assert active_session.total_steps == 1
    step = active_session.steps[0]
    assert step.action == "click"
    assert step.status is StepStatus.PASSED
    assert step.duration_ms == 12.5
    expected_path = os.path.join(os.getcwd(), expected_name)
    assert step.screenshot_path == expected_path
    assert step.assertion_message == "ok"


def test_instrument_tool_records_success(active_session):
    @tool
    def sample_tool(text: str, password: str = None) -> str:
        return "PASS: ok. Screenshot captured: /tmp/shot.png"

    common_tools.instrument_tool(sample_tool)
    result = sample_tool("hello", password="secret")

    assert "PASS:" in result
    assert active_session.total_steps == 1
    step = active_session.steps[0]
    assert step.action == "sample_tool"
    assert step.status is StepStatus.PASSED
    expected_path = os.path.join(os.getcwd(), "shot.png")
    assert step.screenshot_path == expected_path
    assert step.assertion_message.startswith("PASS:")
    assert "password=***" in step.description
    assert "secret" not in step.description


def test_instrument_tool_derives_failed_from_result(active_session):
    @tool
    def failing_tool() -> str:
        return "FAIL: nope"

    common_tools.instrument_tool(failing_tool)
    result = failing_tool()

    assert result.startswith("FAIL:")
    assert active_session.total_steps == 1
    step = active_session.steps[0]
    assert step.status is StepStatus.FAILED
    assert step.assertion_message.startswith("FAIL:")


def test_instrument_tool_records_assertion_error(active_session):
    @tool
    def assert_tool() -> str:
        raise AssertionError("Boom")

    common_tools.instrument_tool(assert_tool)
    with pytest.raises(AssertionError):
        assert_tool()

    assert active_session.total_steps == 1
    step = active_session.steps[0]
    assert step.status is StepStatus.FAILED
    assert step.error_message == "Boom"


def test_start_high_level_step_sets_session():
    session = create_session("test", "app", high_level_steps=["First", "Second"])
    set_active_session(session)
    try:
        result = common_tools.start_high_level_step("2", "")
        assert "High-level step 2" in result
        assert session.current_high_level_step == 2
        assert session.current_high_level_step_description == "Second"
    finally:
        set_active_session(None)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("/tmp/shot.png", "/tmp/shot.png"),
        ("/tmp/shot.PNG", "/tmp/shot.PNG"),
        ("/tmp/shot.jpg", "/tmp/shot.png"),
        ("/tmp/shot", "/tmp/shot.png"),
    ],
)
def test_normalize_screenshot_filename(value, expected):
    assert common_tools._normalize_screenshot_filename(value) == expected


def test_record_step_auto_starts_high_level_step():
    session = create_session("test", "app", high_level_steps=["Step 1"])
    set_active_session(session)
    try:
        common_tools.record_step(
            action="click",
            description="Click button",
            status="PASS",
            duration_ms="1",
        )
        assert session.current_high_level_step == 1
        assert session.current_high_level_step_description == "Step 1"
        step = session.steps[0]
        assert step.high_level_step_number == 1
        assert step.high_level_step_description == "Step 1"
    finally:
        set_active_session(None)


def test_record_tool_step_invalidates_browser_snapshot_cache(monkeypatch):
    invalidations = []
    monkeypatch.setattr(
        browser_analysis_tools,
        "invalidate_page_snapshot_cache",
        lambda driver=None: invalidations.append(driver),
    )
    monkeypatch.setattr(common_tools, "_log_ai_step_to_rf", lambda **kwargs: None)

    common_tools._record_tool_step(
        action="selenium_click_element",
        description="Click button",
        status=StepStatus.PASSED,
        duration_ms=5.0,
    )

    assert invalidations == [None]


def test_record_tool_step_invalidates_mobile_snapshot_cache(monkeypatch):
    invalidations = []
    monkeypatch.setattr(
        mobile_tools,
        "invalidate_mobile_snapshot_cache",
        lambda driver=None: invalidations.append(driver),
    )
    monkeypatch.setattr(common_tools, "_log_ai_step_to_rf", lambda **kwargs: None)

    common_tools._record_tool_step(
        action="appium_click_element",
        description="Tap button",
        status=StepStatus.PASSED,
        duration_ms=5.0,
    )

    assert invalidations == [None]


def test_record_tool_step_invalidates_mobile_snapshot_cache_for_context_switch(monkeypatch):
    invalidations = []
    monkeypatch.setattr(
        mobile_tools,
        "invalidate_mobile_snapshot_cache",
        lambda driver=None: invalidations.append(driver),
    )
    monkeypatch.setattr(common_tools, "_log_ai_step_to_rf", lambda **kwargs: None)

    common_tools._record_tool_step(
        action="appium_switch_context",
        description="Switch to WEBVIEW",
        status=StepStatus.PASSED,
        duration_ms=5.0,
    )

    assert invalidations == [None]


def test_track_ui_action_counts_mobile_swipe_and_state_checks():
    session = create_session("test", "app", test_mode="mobile", high_level_steps=["Swipe list"])

    common_tools._track_ui_action(session, "appium_swipe", StepStatus.PASSED)
    common_tools._track_ui_action(session, "appium_wait_until_page_contains", StepStatus.PASSED)
    common_tools._track_ui_action(session, "appium_get_source", StepStatus.PASSED)

    assert session.ui_interactions_total == 1
    assert session.ui_state_checks_total == 2


def test_track_ui_action_counts_mobile_context_switch_and_analysis():
    session = create_session("test", "app", test_mode="mobile", high_level_steps=["Open webview"])

    common_tools._track_ui_action(session, "appium_switch_context", StepStatus.PASSED)
    common_tools._track_ui_action(session, "appium_get_loading_state", StepStatus.PASSED)
    common_tools._track_ui_action(session, "appium_get_context_inventory", StepStatus.PASSED)

    assert session.ui_interactions_total == 1
    assert session.ui_state_checks_total == 2


def test_track_ui_action_counts_web_select_option_as_interaction():
    session = create_session(
        "test",
        "app",
        test_mode="web",
        high_level_steps=["Select country"],
    )

    common_tools._track_ui_action(session, "selenium_select_option", StepStatus.PASSED)

    assert session.ui_interactions_total == 1
    assert session.ui_state_checks_total == 0


def test_ensure_screenshot_in_output_dir_reuses_cached_copy(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_path = source_dir / "shot.png"
    source_path.write_bytes(b"png-data")

    class DummyBuiltIn:
        def get_variable_value(self, name):
            return str(tmp_path)

    copy_calls = []
    original_copy2 = shutil.copy2

    def tracking_copy2(src, dst):
        copy_calls.append((src, dst))
        return original_copy2(src, dst)

    common_tools._SCREENSHOT_OUTPUT_CACHE.clear()
    monkeypatch.setattr(common_tools, "BuiltIn", DummyBuiltIn)
    monkeypatch.setattr(common_tools.shutil, "copy2", tracking_copy2)

    first_target = common_tools._ensure_screenshot_in_output_dir(str(source_path))
    second_target = common_tools._ensure_screenshot_in_output_dir(str(source_path))

    assert first_target == second_target
    assert os.path.exists(first_target)
    assert len(copy_calls) == 1
