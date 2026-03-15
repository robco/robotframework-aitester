# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for library module."""

import pytest

from AIAgentic.library import AIAgentic


def test_agentic_step_pass_returns_summary():
    agentic = AIAgentic()
    result = agentic.agentic_step(
        action="click",
        description="Click login",
        status="PASS",
        duration_ms="42",
        screenshot_path="/tmp/ss.png",
    )
    assert result == "click - Click login (PASS)"


def test_agentic_step_fail_raises_assertion():
    agentic = AIAgentic()
    with pytest.raises(AssertionError) as exc:
        agentic.agentic_step(
            action="submit",
            description="Submit form",
            status="FAIL",
            assertion_message="Validation failed",
        )
    assert "Validation failed" in str(exc.value)
