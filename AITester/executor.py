# Apache License 2.0
#
# Copyright (c) 2026 Róbert Malovec
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Test execution engine and state management for robotframework-aitester.

Manages the lifecycle of an agentic test session, including state tracking,
evidence collection, error handling, and iteration management.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Active session context (shared across tools)
# ---------------------------------------------------------------------------

_ACTIVE_SESSION: Optional["TestSession"] = None


def set_active_session(session: Optional["TestSession"]) -> None:
    """Set the active session for tool-level step recording."""
    global _ACTIVE_SESSION
    _ACTIVE_SESSION = session


def get_active_session() -> Optional["TestSession"]:
    """Get the current active session for tool-level step recording."""
    return _ACTIVE_SESSION


class StepStatus(Enum):
    """Status of an individual test step."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class SessionStatus(Enum):
    """Status of a test session."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    TIMEOUT = "timeout"


@dataclass
class TestStep:
    """Represents a single test step executed by an agent.

    Attributes:
        step_number: Sequential step number within the session.
        action: The tool/action invoked (e.g., 'selenium_click_element').
        description: Human-readable description of what the step does.
        status: Result status (passed, failed, skipped, error).
        duration_ms: Execution time in milliseconds.
        screenshot_path: Path to evidence screenshot (if captured).
        assertion_message: Assertion details for pass/fail.
        error_message: Error details if step failed with an exception.
        metadata: Additional key-value metadata for the step.
    """
    __test__ = False
    step_number: int
    action: str
    description: str
    status: StepStatus
    duration_ms: float
    screenshot_path: Optional[str] = None
    assertion_message: Optional[str] = None
    error_message: Optional[str] = None
    high_level_step_number: Optional[int] = None
    high_level_step_description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestScenario:
    """Represents a planned test scenario with its execution steps.

    Attributes:
        scenario_id: Unique identifier for the scenario.
        name: Scenario name.
        description: What the scenario tests.
        priority: Priority level (critical, high, medium, low).
        preconditions: Required preconditions.
        steps: Executed test steps.
        status: Overall scenario status.
    """
    __test__ = False
    scenario_id: str
    name: str
    description: str
    priority: str = "medium"
    preconditions: str = ""
    steps: List[TestStep] = field(default_factory=list)
    status: str = "pending"


@dataclass
class TestSession:
    """Encapsulates the full state of an agentic test session.

    Attributes:
        session_id: Unique session identifier.
        objective: The test objective provided by the user.
        app_context: Application context description.
        test_mode: Testing mode (web, api, mobile).
        start_time: Session start timestamp.
        end_time: Session end timestamp (set on completion).
        scenarios: Planned test scenarios.
        steps: All executed steps across scenarios.
        iterations_used: Number of agent iterations consumed.
        max_iterations: Maximum allowed iterations.
        status: Current session status.
        cost_usd: Approximate accumulated cost in USD.
        screenshots: Paths to all captured screenshots.
        errors: List of error messages encountered.
        agent_log: Raw agent conversation/action log entries.
        high_level_steps: User-defined high-level test steps (optional).
        current_high_level_step: Current high-level step number, if any.
        current_high_level_step_description: Current high-level step text, if any.
        reuse_existing_session: Whether to reuse an existing browser/app session.
        start_state_summary: Start-state summary captured at session start.
        scroll_into_view: Scroll UI elements into view before interacting.
        direct_url_navigations_used: Count of direct browser URL navigations used
            to enter the application.
        allowed_direct_urls: Concrete URLs explicitly requested by the user.
        allow_browser_termination: Whether the user explicitly allowed closing,
            resetting, or restarting the current browser/app session.
        ui_interactions_total: Count of UI interaction tool calls.
        ui_state_checks_total: Count of UI state validation tool calls.
        ui_interactions_by_step: UI interaction counts per high-level step.
        ui_state_checks_by_step: UI state validation counts per high-level step.
    """
    __test__ = False
    session_id: str
    objective: str
    app_context: str
    test_mode: str = "web"
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    scenarios: List[TestScenario] = field(default_factory=list)
    steps: List[TestStep] = field(default_factory=list)
    iterations_used: int = 0
    max_iterations: int = 50
    timeout_seconds: float = 600.0
    status: SessionStatus = SessionStatus.RUNNING
    cost_usd: float = 0.0
    max_cost_usd: Optional[float] = None
    screenshots: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    agent_log: List[Dict[str, Any]] = field(default_factory=list)
    high_level_steps: List[str] = field(default_factory=list)
    current_high_level_step: Optional[int] = None
    current_high_level_step_description: Optional[str] = None
    reuse_existing_session: bool = False
    start_state_summary: Optional[str] = None
    scroll_into_view: bool = True
    direct_url_navigations_used: int = 0
    allowed_direct_urls: List[str] = field(default_factory=list)
    allow_browser_termination: bool = False
    ui_interactions_total: int = 0
    ui_state_checks_total: int = 0
    ui_interactions_by_step: Dict[int, int] = field(default_factory=dict)
    ui_state_checks_by_step: Dict[int, int] = field(default_factory=dict)
    agent_iterations_by_agent: Dict[str, int] = field(default_factory=dict)
    action_history: List[str] = field(default_factory=list)
    last_tool_action: Optional[str] = None
    last_tool_status: Optional[str] = None
    last_observation_summary: Optional[str] = None
    last_ui_snapshot_fingerprint: Optional[str] = None
    last_ui_snapshot_summary: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """Calculate session duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def total_steps(self) -> int:
        """Total number of executed steps."""
        return len(self.steps)

    @property
    def passed_steps(self) -> int:
        """Count of passed steps."""
        return sum(1 for s in self.steps if s.status == StepStatus.PASSED)

    @property
    def failed_steps(self) -> int:
        """Count of failed steps."""
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as a percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.passed_steps / self.total_steps) * 100.0

    def add_step(self, step: TestStep):
        """Add a test step to the session.

        Args:
            step: TestStep to record.
        """
        self.steps.append(step)
        if step.screenshot_path:
            self.screenshots.append(step.screenshot_path)
        if step.error_message:
            self.errors.append(step.error_message)

    def finalize(self, status: SessionStatus = None):
        """Finalize the session, setting end time and final status.

        Args:
            status: Override status. If None, auto-determined from steps.
        """
        self.end_time = time.time()
        if status:
            self.status = status
        elif self.failed_steps > 0:
            self.status = SessionStatus.FAILED
        else:
            self.status = SessionStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to a dictionary for reporting.

        Returns:
            Dictionary representation of the session.
        """
        return {
            "session_id": self.session_id,
            "objective": self.objective,
            "app_context": self.app_context,
            "test_mode": self.test_mode,
            "status": self.status.value,
            "duration_seconds": round(self.duration_seconds, 2),
            "iterations_used": self.iterations_used,
            "max_iterations": self.max_iterations,
            "timeout_seconds": round(self.timeout_seconds, 2),
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "pass_rate": round(self.pass_rate, 1),
            "cost_usd": round(self.cost_usd, 4),
            "max_cost_usd": self.max_cost_usd,
            "screenshots": self.screenshots,
            "errors": self.errors,
            "high_level_steps": self.high_level_steps,
            "direct_url_navigations_used": self.direct_url_navigations_used,
            "allowed_direct_urls": self.allowed_direct_urls,
            "allow_browser_termination": self.allow_browser_termination,
            "agent_iterations_by_agent": self.agent_iterations_by_agent,
            "action_history": self.action_history,
            "last_tool_action": self.last_tool_action,
            "last_tool_status": self.last_tool_status,
            "last_observation_summary": self.last_observation_summary,
            "last_ui_snapshot_fingerprint": self.last_ui_snapshot_fingerprint,
            "last_ui_snapshot_summary": self.last_ui_snapshot_summary,
            "scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "name": s.name,
                    "description": s.description,
                    "priority": s.priority,
                    "status": s.status,
                    "steps_count": len(s.steps),
                }
                for s in self.scenarios
            ],
            "steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "description": s.description,
                    "status": s.status.value,
                    "duration_ms": round(s.duration_ms, 2),
                    "screenshot_path": s.screenshot_path,
                    "assertion_message": s.assertion_message,
                    "error_message": s.error_message,
                    "high_level_step_number": s.high_level_step_number,
                    "high_level_step_description": s.high_level_step_description,
                }
                for s in self.steps
            ],
        }


class SafetyGuard:
    """Enforces safety mechanisms for autonomous test execution.

    Implements multiple guard rails:
    - Iteration limit: Hard stop after max_iterations.
    - Timeout: Session-level timeout enforcement.
    - Cost tracking: Approximate token cost accumulation.
    - Error recovery: Retry budget per action.
    - Action whitelist/blacklist: Configurable tool restrictions.
    """

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_TIMEOUT_SECONDS = 600  # 10 minutes per session

    def __init__(
        self,
        max_iterations: int = 50,
        timeout_seconds: float = None,
        max_retries_per_action: int = None,
        action_whitelist: List[str] = None,
        action_blacklist: List[str] = None,
        max_cost_usd: float = None,
    ):
        """Initialize SafetyGuard.

        Args:
            max_iterations: Maximum allowed agent iterations.
            timeout_seconds: Session timeout in seconds.
            max_retries_per_action: Max retries per failed action.
            action_whitelist: If set, only these tools are allowed.
            action_blacklist: If set, these tools are blocked.
            max_cost_usd: Maximum session cost in USD.
        """
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        self.max_retries_per_action = max_retries_per_action or self.DEFAULT_MAX_RETRIES
        self.action_whitelist = set(action_whitelist) if action_whitelist else None
        self.action_blacklist = set(action_blacklist) if action_blacklist else set()
        self.max_cost_usd = max_cost_usd
        self._retry_counts: Dict[str, int] = {}

    def check_iteration_limit(self, session: TestSession) -> bool:
        """Check if iteration limit has been reached.

        Args:
            session: Current test session.

        Returns:
            True if within limits, False if exceeded.
        """
        if session.iterations_used >= session.max_iterations:
            logger.warning(
                "Iteration limit reached: %d/%d",
                session.iterations_used,
                session.max_iterations,
            )
            return False
        return True

    def check_timeout(self, session: TestSession) -> bool:
        """Check if session has timed out.

        Args:
            session: Current test session.

        Returns:
            True if within timeout, False if exceeded.
        """
        elapsed = time.time() - session.start_time
        if elapsed >= self.timeout_seconds:
            logger.warning(
                "Session timeout: %.1f seconds elapsed (limit: %.1f)",
                elapsed,
                self.timeout_seconds,
            )
            return False
        return True

    def check_cost_limit(self, session: TestSession) -> bool:
        """Check if cost limit has been reached.

        Args:
            session: Current test session.

        Returns:
            True if within cost limit, False if exceeded.
        """
        if self.max_cost_usd and session.cost_usd >= self.max_cost_usd:
            logger.warning(
                "Cost limit reached: $%.4f (limit: $%.4f)",
                session.cost_usd,
                self.max_cost_usd,
            )
            return False
        return True

    def is_action_allowed(self, action_name: str) -> bool:
        """Check if an action/tool is allowed.

        Args:
            action_name: Name of the tool to check.

        Returns:
            True if allowed, False if blocked.
        """
        if action_name in self.action_blacklist:
            logger.warning("Action blocked by blacklist: %s", action_name)
            return False
        if self.action_whitelist and action_name not in self.action_whitelist:
            logger.warning("Action not in whitelist: %s", action_name)
            return False
        return True

    def can_retry(self, action_name: str) -> bool:
        """Check if an action can be retried.

        Args:
            action_name: Name of the tool to check.

        Returns:
            True if retries remaining, False if exhausted.
        """
        count = self._retry_counts.get(action_name, 0)
        return count < self.max_retries_per_action

    def record_retry(self, action_name: str):
        """Record a retry attempt for an action.

        Args:
            action_name: Name of the tool being retried.
        """
        self._retry_counts[action_name] = self._retry_counts.get(action_name, 0) + 1

    def validate_session(self, session: TestSession) -> tuple:
        """Run all safety checks on the session.

        Args:
            session: Current test session.

        Returns:
            Tuple of (is_safe, reason_if_not_safe).
        """
        if not self.check_iteration_limit(session):
            return False, "iteration_limit_exceeded"
        if not self.check_timeout(session):
            return False, "session_timeout"
        if not self.check_cost_limit(session):
            return False, "cost_limit_exceeded"
        return True, None


def create_session(
    objective: str,
    app_context: str,
    test_mode: str = "web",
    max_iterations: int = 50,
    timeout_seconds: float = 600.0,
    high_level_steps: Optional[List[str]] = None,
    reuse_existing_session: bool = False,
    start_state_summary: Optional[str] = None,
    scroll_into_view: bool = True,
    allowed_direct_urls: Optional[List[str]] = None,
    allow_browser_termination: bool = False,
    max_cost_usd: Optional[float] = None,
) -> TestSession:
    """Factory function to create a new test session.

    Args:
        objective: The test objective.
        app_context: Application context description.
        test_mode: Testing mode (web, api, mobile).
        max_iterations: Maximum agent iterations.

    Returns:
        Initialized TestSession instance.
    """
    session_id = str(uuid.uuid4())[:8]
    logger.info(
        "Creating test session %s: mode=%s, max_iterations=%d",
        session_id,
        test_mode,
        max_iterations,
    )
    return TestSession(
        session_id=session_id,
        objective=objective,
        app_context=app_context,
        test_mode=test_mode,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        high_level_steps=high_level_steps or [],
        reuse_existing_session=reuse_existing_session,
        start_state_summary=start_state_summary,
        scroll_into_view=scroll_into_view,
        allowed_direct_urls=allowed_direct_urls or [],
        allow_browser_termination=allow_browser_termination,
        max_cost_usd=max_cost_usd,
    )


def get_runtime_limit_violation(session: Optional[TestSession]) -> Optional[str]:
    """Return a human-readable runtime limit violation, if any."""
    if not session:
        return None

    elapsed = time.time() - session.start_time
    timeout_seconds = float(getattr(session, "timeout_seconds", 0.0) or 0.0)
    if timeout_seconds > 0 and elapsed >= timeout_seconds:
        return (
            "Session timeout reached: "
            f"{elapsed:.1f}s elapsed (limit: {timeout_seconds:.1f}s)."
        )

    max_cost_usd = getattr(session, "max_cost_usd", None)
    if max_cost_usd is not None and session.cost_usd >= max_cost_usd:
        return (
            "Session cost limit reached: "
            f"${session.cost_usd:.4f} spent (limit: ${float(max_cost_usd):.4f})."
        )

    return None


def record_step(
    session: TestSession,
    action: str,
    description: str,
    status: StepStatus,
    duration_ms: float,
    screenshot_path: str = None,
    assertion_message: str = None,
    error_message: str = None,
) -> TestStep:
    """Record a test step in the session.

    Args:
        session: Current test session.
        action: Tool/action name.
        description: What the step does.
        status: Step result.
        duration_ms: Execution time.
        screenshot_path: Optional evidence screenshot.
        assertion_message: Assertion detail.
        error_message: Error detail.

    Returns:
        The recorded TestStep.
    """
    high_level_number = session.current_high_level_step
    high_level_description = session.current_high_level_step_description
    step = TestStep(
        step_number=len(session.steps) + 1,
        action=action,
        description=description,
        status=status,
        duration_ms=duration_ms,
        screenshot_path=screenshot_path,
        assertion_message=assertion_message,
        error_message=error_message,
        high_level_step_number=high_level_number,
        high_level_step_description=high_level_description,
    )
    session.add_step(step)
    return step
