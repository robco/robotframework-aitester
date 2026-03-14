# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for executor module."""

import pytest
import time
from AIAgentic.executor import (
    TestStep,
    TestScenario,
    TestSession,
    SessionStatus,
    StepStatus,
    SafetyGuard,
    create_session,
    record_step,
)


class TestTestStep:
    """Tests for TestStep dataclass."""

    def test_create_step(self):
        step = TestStep(
            step_number=1,
            action="selenium_click_element",
            description="Click login button",
            status=StepStatus.PASSED,
            duration_ms=150.5,
        )
        assert step.step_number == 1
        assert step.status == StepStatus.PASSED
        assert step.screenshot_path is None

    def test_step_with_evidence(self):
        step = TestStep(
            step_number=2,
            action="selenium_capture_screenshot",
            description="Capture login page",
            status=StepStatus.PASSED,
            duration_ms=50.0,
            screenshot_path="/tmp/screenshot_001.png",
            assertion_message="Screenshot captured successfully",
        )
        assert step.screenshot_path == "/tmp/screenshot_001.png"
        assert step.assertion_message is not None


class TestTestSession:
    """Tests for TestSession dataclass."""

    def test_create_session(self):
        session = create_session(
            objective="Test login",
            app_context="Web app",
            test_mode="web",
            max_iterations=30,
        )
        assert session.objective == "Test login"
        assert session.test_mode == "web"
        assert session.max_iterations == 30
        assert session.status == SessionStatus.RUNNING
        assert len(session.session_id) == 8

    def test_session_add_step(self):
        session = create_session("test", "app")
        step = TestStep(
            step_number=1,
            action="click",
            description="Click button",
            status=StepStatus.PASSED,
            duration_ms=100,
        )
        session.add_step(step)
        assert session.total_steps == 1
        assert session.passed_steps == 1

    def test_session_pass_rate(self):
        session = create_session("test", "app")
        for i in range(7):
            session.add_step(TestStep(i + 1, "action", "desc", StepStatus.PASSED, 100))
        for i in range(3):
            session.add_step(TestStep(i + 8, "action", "desc", StepStatus.FAILED, 100))
        assert session.pass_rate == 70.0

    def test_session_pass_rate_empty(self):
        session = create_session("test", "app")
        assert session.pass_rate == 0.0

    def test_session_finalize_success(self):
        session = create_session("test", "app")
        session.add_step(TestStep(1, "action", "desc", StepStatus.PASSED, 100))
        session.finalize()
        assert session.status == SessionStatus.COMPLETED
        assert session.end_time is not None

    def test_session_finalize_failure(self):
        session = create_session("test", "app")
        session.add_step(TestStep(1, "action", "desc", StepStatus.FAILED, 100))
        session.finalize()
        assert session.status == SessionStatus.FAILED

    def test_session_finalize_override(self):
        session = create_session("test", "app")
        session.finalize(SessionStatus.ABORTED)
        assert session.status == SessionStatus.ABORTED

    def test_session_to_dict(self):
        session = create_session("Test login", "Web app", "web", 50)
        session.add_step(TestStep(1, "click", "Click button", StepStatus.PASSED, 100))
        session.finalize()
        data = session.to_dict()
        assert data["objective"] == "Test login"
        assert data["total_steps"] == 1
        assert data["status"] == "completed"
        assert "steps" in data

    def test_record_step_function(self):
        session = create_session("test", "app")
        step = record_step(
            session, "selenium_click", "Click element", StepStatus.PASSED, 150.0
        )
        assert step.step_number == 1
        assert session.total_steps == 1

    def test_session_tracks_screenshots(self):
        session = create_session("test", "app")
        step = TestStep(1, "screenshot", "Capture", StepStatus.PASSED, 50,
                        screenshot_path="/tmp/ss.png")
        session.add_step(step)
        assert len(session.screenshots) == 1
        assert session.screenshots[0] == "/tmp/ss.png"

    def test_session_tracks_errors(self):
        session = create_session("test", "app")
        step = TestStep(1, "click", "Click", StepStatus.ERROR, 50,
                        error_message="Element not found")
        session.add_step(step)
        assert len(session.errors) == 1


class TestSafetyGuard:
    """Tests for SafetyGuard."""

    def test_iteration_limit(self):
        guard = SafetyGuard(max_iterations=10)
        session = create_session("test", "app", max_iterations=10)
        assert guard.check_iteration_limit(session) is True
        session.iterations_used = 10
        assert guard.check_iteration_limit(session) is False

    def test_timeout(self):
        guard = SafetyGuard(timeout_seconds=1)
        session = create_session("test", "app")
        assert guard.check_timeout(session) is True
        session.start_time = time.time() - 2
        assert guard.check_timeout(session) is False

    def test_cost_limit(self):
        guard = SafetyGuard(max_cost_usd=1.0)
        session = create_session("test", "app")
        assert guard.check_cost_limit(session) is True
        session.cost_usd = 1.5
        assert guard.check_cost_limit(session) is False

    def test_cost_limit_none(self):
        guard = SafetyGuard(max_cost_usd=None)
        session = create_session("test", "app")
        session.cost_usd = 999.0
        assert guard.check_cost_limit(session) is True

    def test_action_whitelist(self):
        guard = SafetyGuard(action_whitelist=["click", "type"])
        assert guard.is_action_allowed("click") is True
        assert guard.is_action_allowed("delete") is False

    def test_action_blacklist(self):
        guard = SafetyGuard(action_blacklist=["delete_all", "drop_table"])
        assert guard.is_action_allowed("click") is True
        assert guard.is_action_allowed("delete_all") is False

    def test_retry_tracking(self):
        guard = SafetyGuard(max_retries_per_action=2)
        assert guard.can_retry("click") is True
        guard.record_retry("click")
        assert guard.can_retry("click") is True
        guard.record_retry("click")
        assert guard.can_retry("click") is False

    def test_validate_session_ok(self):
        guard = SafetyGuard(max_iterations=50, timeout_seconds=600)
        session = create_session("test", "app", max_iterations=50)
        is_safe, reason = guard.validate_session(session)
        assert is_safe is True
        assert reason is None

    def test_validate_session_iteration_exceeded(self):
        guard = SafetyGuard(max_iterations=10)
        session = create_session("test", "app", max_iterations=10)
        session.iterations_used = 10
        is_safe, reason = guard.validate_session(session)
        assert is_safe is False
        assert reason == "iteration_limit_exceeded"
