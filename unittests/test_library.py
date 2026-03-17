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


def test_extract_user_defined_steps_from_list_objective():
    agentic = AIAgentic()
    objective = [
        "Strictly follow specified test steps.",
        "1. Click Login",
        "2. Verify dashboard is visible",
    ]
    objective_text, steps, steps_text = agentic._extract_user_defined_steps(
        test_objective=objective,
        test_steps=None,
    )
    assert steps_text is None
    assert "1. Click Login" in objective_text
    assert steps == ["Click Login", "Verify dashboard is visible"]


def test_validate_user_step_completion_fails_on_missing():
    agentic = AIAgentic()
    from AIAgentic.executor import create_session

    session = create_session(
        objective="Test",
        app_context="App",
        test_mode="web",
        max_iterations=1,
        high_level_steps=["Step A", "Step B"],
    )
    msg = agentic._validate_user_step_completion(session)
    assert msg is not None
    assert "No recorded actions" in msg
