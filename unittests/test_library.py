# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for library module."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from AITester.executor import SessionStatus, StepStatus, TestStep, create_session
from AITester.library import AITester


def test_ai_step_pass_returns_summary():
    tester = AITester()
    result = tester.ai_step(
        action="click",
        description="Click login",
        status="PASS",
        duration_ms="42",
        screenshot_path="/tmp/ss.png",
    )
    assert result == "click - Click login (PASS)"


def test_ai_step_fail_raises_assertion():
    tester = AITester()
    with pytest.raises(AssertionError) as exc:
        tester.ai_step(
            action="submit",
            description="Submit form",
            status="FAIL",
            assertion_message="Validation failed",
        )
    assert "Validation failed" in str(exc.value)


def test_libdoc_docs_render_cleanly(tmp_path):
    output = tmp_path / "libdoc.json"
    repo_root = Path(__file__).resolve().parents[1]

    subprocess.run(
        [sys.executable, "-m", "robot.libdoc", "AITester", str(output)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    spec = json.loads(output.read_text())
    init_doc = spec["inits"][0]["doc"]
    run_test_doc = next(kw["doc"] for kw in spec["keywords"] if kw["name"] == "Run AI Test")
    exploration_doc = next(
        kw["doc"] for kw in spec["keywords"] if kw["name"] == "Run AI Exploration"
    )

    assert "Args:" not in init_doc
    assert "<li><code>platform</code>" in init_doc
    assert "platform=Manual" in init_doc
    assert "AI provider base URL override" in init_doc
    assert "<pre>" not in run_test_doc
    assert "test_objective=${API_OBJECTIVE}" in run_test_doc
    assert "test_steps=${AI_STEPS}" in run_test_doc
    assert "manual intervention" not in run_test_doc.lower()
    assert "test_mode=mobile" in exploration_doc


def test_extract_user_defined_steps_from_list_objective():
    tester = AITester()
    objective = [
        "Strictly follow specified test steps.",
        "1. Click Login",
        "2. Verify dashboard is visible",
    ]
    objective_text, steps, steps_text, steps_source = tester._extract_user_defined_steps(
        test_objective=objective,
        test_steps=None,
    )
    assert steps_text is None
    assert steps_source is None
    assert "1. Click Login" in objective_text
    assert steps == ["Click Login", "Verify dashboard is visible"]


def test_validate_user_step_completion_fails_on_missing():
    tester = AITester()

    session = create_session(
        objective="Test",
        app_context="App",
        test_mode="web",
        max_iterations=1,
        high_level_steps=["Step A", "Step B"],
    )
    msg = tester._validate_user_step_completion(session)
    assert msg is not None
    assert "No recorded actions" in msg


def test_validate_user_step_completion_ignores_diagnostic_passes():
    tester = AITester()

    session = create_session(
        objective="Test",
        app_context="App",
        test_mode="web",
        max_iterations=1,
        high_level_steps=["Verify order finished successfully"],
    )
    session.current_high_level_step = 1
    session.current_high_level_step_description = "Verify order finished successfully"
    session.add_step(
        TestStep(
            step_number=1,
            action="get_page_snapshot",
            description="refresh=False",
            status=StepStatus.PASSED,
            duration_ms=10,
            high_level_step_number=1,
            high_level_step_description="Verify order finished successfully",
        )
    )

    msg = tester._validate_user_step_completion(session)

    assert msg is not None
    assert "No passed actions" in msg


def test_validate_user_step_completion_ignores_rf_variable_passes():
    tester = AITester()

    session = create_session(
        objective="Test",
        app_context="App",
        test_mode="web",
        max_iterations=1,
        high_level_steps=["Complete gated sign-in flow"],
    )
    session.current_high_level_step = 1
    session.current_high_level_step_description = "Complete gated sign-in flow"
    session.add_step(
        TestStep(
            step_number=1,
            action="get_rf_variable",
            description="variable_name=${OTP_CODE}",
            status=StepStatus.PASSED,
            duration_ms=10,
            high_level_step_number=1,
            high_level_step_description="Complete gated sign-in flow",
        )
    )

    msg = tester._validate_user_step_completion(session)

    assert msg is not None
    assert "No passed actions" in msg


def test_validate_ui_action_coverage_allows_leave_empty_state_checks():
    tester = AITester()

    session = create_session(
        objective="Test",
        app_context="App",
        test_mode="web",
        max_iterations=1,
        high_level_steps=["Contact phone number field leave empty"],
    )
    session.ui_state_checks_total = 2
    session.ui_state_checks_by_step[1] = 2

    msg = tester._validate_ui_action_coverage(session)

    assert msg is None


def test_validate_ui_action_coverage_requires_interaction_for_action_step():
    tester = AITester()

    session = create_session(
        objective="Test",
        app_context="App",
        test_mode="web",
        max_iterations=1,
        high_level_steps=["Click submit button"],
    )
    session.ui_state_checks_total = 1
    session.ui_state_checks_by_step[1] = 1

    msg = tester._validate_ui_action_coverage(session)

    assert msg is not None
    assert "1. Click submit button" in msg


def test_finalize_session_allows_recovered_high_level_step():
    tester = AITester()

    session = create_session(
        objective="Test",
        app_context="App",
        test_mode="web",
        max_iterations=1,
        high_level_steps=["Verify order finished successfully"],
    )
    session.ui_state_checks_total = 1
    session.ui_state_checks_by_step[1] = 1
    session.current_high_level_step = 1
    session.current_high_level_step_description = "Verify order finished successfully"
    session.add_step(
        TestStep(
            step_number=1,
            action="selenium_page_should_contain",
            description="text=Objednávka byla úspěšně odeslána",
            status=StepStatus.FAILED,
            duration_ms=10,
            error_message="Page should have contained text 'Objednávka byla úspěšně odeslána' but did not.",
            high_level_step_number=1,
            high_level_step_description="Verify order finished successfully",
        )
    )
    session.add_step(
        TestStep(
            step_number=2,
            action="selenium_page_should_contain",
            description="text=Děkujeme. Úspěšně jsme přijali vaši objednávku.",
            status=StepStatus.PASSED,
            duration_ms=10,
            high_level_step_number=1,
            high_level_step_description="Verify order finished successfully",
        )
    )

    tester._finalize_session(session)

    assert session.status == SessionStatus.COMPLETED


def test_extract_user_defined_steps_from_numbered_list():
    tester = AITester()
    steps_list = [
        "1. Click button",
        "2. Verify result",
    ]
    objective, steps, _, steps_source = tester._extract_user_defined_steps(
        test_objective="Test objective",
        test_steps=steps_list,
    )
    assert steps == ["Click button", "Verify result"]
    assert steps_source == "argument"
    assert "1. Click button" in objective


def test_extract_user_defined_steps_uses_ai_steps_variable(monkeypatch):
    tester = AITester()

    class DummyBuiltIn:
        def get_variable_value(self, variable_name):
            if variable_name == "${AI_STEPS}":
                return [
                    "Execute these test steps.",
                    "Make sure to create screenshot after each executed step.",
                    "1. Open Internet section",
                    "2. Verify address availability",
                ]
            return None

    monkeypatch.setattr("AITester.library.BuiltIn", lambda: DummyBuiltIn())

    objective, steps, steps_text, steps_source = tester._extract_user_defined_steps(
        test_objective="",
        test_steps=None,
    )

    assert steps_source == "${AI_STEPS}"
    assert "Make sure to create screenshot after each executed step." in objective
    assert steps == ["Open Internet section", "Verify address availability"]
    assert steps_text is not None


def test_extract_user_defined_steps_handles_stringified_list_steps():
    tester = AITester()

    stringified_steps = (
        "['Execute these test steps.', "
        "'Make sure to create screenshot after each executed step.', "
        "'1. Open Internet section', "
        "'2. Verify address availability']"
    )

    objective, steps, steps_text, steps_source = tester._extract_user_defined_steps(
        test_objective="Verify address coverage",
        test_steps=stringified_steps,
    )

    assert steps_source == "argument"
    assert "1. Open Internet section" in objective
    assert "Make sure to create screenshot after each executed step." in objective
    assert steps == ["Open Internet section", "Verify address availability"]
    assert steps_text is not None


def test_run_ai_test_requires_objective_or_steps(monkeypatch):
    tester = AITester()
    monkeypatch.setattr(tester, "_ensure_orchestrator", lambda: None)

    with pytest.raises(ValueError, match="requires a non-empty test_objective or numbered test_steps"):
        tester.run_ai_test(test_objective="")


def test_detect_failure_in_result():
    tester = AITester()
    assert tester._detect_failure_in_result(
        "The test execution completed with **FAILED** status."
    )
    assert tester._detect_failure_in_result("Status: FAILED")
    assert tester._detect_failure_in_result("Test execution failed due to error")
    assert tester._detect_failure_in_result("completed with failed status")
    assert tester._detect_failure_in_result("completed successfully") is None


def test_extract_explicit_urls_deduplicates_user_requested_targets():
    tester = AITester()

    urls = tester._extract_explicit_urls(
        "Open https://example.test/login and later https://example.test/settings.",
        ["Repeat https://example.test/login", "Ignore plain text"],
    )

    assert urls == [
        "https://example.test/login",
        "https://example.test/settings",
    ]


def test_allows_explicit_browser_termination_for_restart_request():
    tester = AITester()

    allowed = tester._allows_explicit_browser_termination(
        "If page analysis gets stuck, restart the browser and continue."
    )

    assert allowed is True


def test_allows_explicit_browser_termination_respects_negation():
    tester = AITester()

    allowed = tester._allows_explicit_browser_termination(
        "Do not close the browser. Preserve the logged in session."
    )

    assert allowed is False


def test_allows_explicit_session_termination_for_app_restart_request():
    tester = AITester()

    allowed = tester._allows_explicit_session_termination(
        "Reset the app and relaunch it before retrying onboarding."
    )

    assert allowed is True


def test_prepare_screenshot_artifact_reuses_cached_copy(tmp_path, monkeypatch):
    tester = AITester()
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

    monkeypatch.setattr(tester, "_get_output_dir", lambda: str(output_dir))
    monkeypatch.setattr("AITester.library.shutil.copy2", tracking_copy2)

    first_artifact = tester._prepare_screenshot_artifact(str(source_path))
    second_artifact = tester._prepare_screenshot_artifact(str(source_path))

    assert first_artifact is not None
    assert second_artifact is not None
    assert first_artifact["target_path"] == second_artifact["target_path"]
    assert os.path.exists(first_artifact["target_path"])
    assert len(copy_calls) == 1
