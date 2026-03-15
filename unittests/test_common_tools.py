# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for common tools module."""

import pytest
from strands import tool

from AIAgentic.executor import StepStatus, create_session, set_active_session
from AIAgentic.tools import common_tools


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


def test_record_step_records_session(active_session):
    result = common_tools.record_step(
        action="click",
        description="Click button",
        status="PASS",
        duration_ms="12.5",
        screenshot_path="/tmp/ss.png",
        assertion_message="ok",
    )
    assert "Recorded step: click - Click button (passed)" in result
    assert active_session.total_steps == 1
    step = active_session.steps[0]
    assert step.action == "click"
    assert step.status is StepStatus.PASSED
    assert step.duration_ms == 12.5
    assert step.screenshot_path == "/tmp/ss.png"
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
    assert step.screenshot_path == "/tmp/shot.png"
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
