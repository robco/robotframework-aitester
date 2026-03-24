# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for library module."""

import os
import shutil
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


def test_extract_user_defined_steps_from_numbered_list():
    agentic = AIAgentic()
    steps_list = [
        "1. Click button",
        "2. Verify result",
    ]
    objective, steps, _ = agentic._extract_user_defined_steps(
        test_objective="Test objective",
        test_steps=steps_list,
    )
    assert steps == ["Click button", "Verify result"]
    assert "1. Click button" in objective


def test_detect_failure_in_result():
    agentic = AIAgentic()
    assert agentic._detect_failure_in_result(
        "The test execution completed with **FAILED** status."
    )
    assert agentic._detect_failure_in_result("Status: FAILED")
    assert agentic._detect_failure_in_result("Test execution failed due to error")
    assert agentic._detect_failure_in_result("completed with failed status")
    assert agentic._detect_failure_in_result("completed successfully") is None


def test_extract_explicit_urls_deduplicates_user_requested_targets():
    agentic = AIAgentic()

    urls = agentic._extract_explicit_urls(
        "Open https://example.test/login and later https://example.test/settings.",
        ["Repeat https://example.test/login", "Ignore plain text"],
    )

    assert urls == [
        "https://example.test/login",
        "https://example.test/settings",
    ]


def test_allows_explicit_browser_termination_for_restart_request():
    agentic = AIAgentic()

    allowed = agentic._allows_explicit_browser_termination(
        "If page analysis gets stuck, restart the browser and continue."
    )

    assert allowed is True


def test_allows_explicit_browser_termination_respects_negation():
    agentic = AIAgentic()

    allowed = agentic._allows_explicit_browser_termination(
        "Do not close the browser. Preserve the logged in session."
    )

    assert allowed is False


def test_prepare_screenshot_artifact_reuses_cached_copy(tmp_path, monkeypatch):
    agentic = AIAgentic()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    source_path = source_dir / "shot.png"
    source_path.write_bytes(b"png-data")

    copy_calls = []
    original_copy2 = shutil.copy2

    def tracking_copy2(src, dst):
        copy_calls.append((src, dst))
        return original_copy2(src, dst)

    monkeypatch.setattr(agentic, "_get_output_dir", lambda: str(output_dir))
    monkeypatch.setattr("AIAgentic.library.shutil.copy2", tracking_copy2)

    first_artifact = agentic._prepare_screenshot_artifact(str(source_path))
    second_artifact = agentic._prepare_screenshot_artifact(str(source_path))

    assert first_artifact is not None
    assert second_artifact is not None
    assert first_artifact["target_path"] == second_artifact["target_path"]
    assert os.path.exists(first_artifact["target_path"])
    assert len(copy_calls) == 1
