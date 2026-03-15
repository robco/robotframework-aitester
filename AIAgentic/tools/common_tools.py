# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Common tools — Shared utility tools available to all executor agents.

These tools provide general-purpose functionality like screenshots,
assertions, logging, timing, and optional aivision integration.
"""

import functools
import inspect
import json
import logging
import os
import time
from typing import Any, Iterable, Optional
from strands import tool
from strands.tools.decorator import DecoratedFunctionTool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.api import logger as rf_logger

from ..executor import StepStatus, record_step as record_step_impl, get_active_session

logger = logging.getLogger(__name__)


def _get_rf_output_dir():
    """Returns Robot Framework output directory path."""
    try:
        return BuiltIn().get_variable_value("${OUTPUT_DIR}")
    except RobotNotRunningError:
        return os.getcwd()


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

@tool
def assert_equal(actual: str, expected: str) -> str:
    """Asserts that two values are equal.

    Args:
        actual: The actual value.
        expected: The expected value.

    Returns:
        PASS or FAIL with details.
    """
    if str(actual).strip() == str(expected).strip():
        return f"PASS: '{actual}' equals '{expected}'"
    else:
        return f"FAIL: Expected '{expected}', but got '{actual}'"


@tool
def assert_contains(text: str, substring: str) -> str:
    """Asserts that text contains the expected substring.

    Args:
        text: The text to search in.
        substring: The expected substring.

    Returns:
        PASS or FAIL with details.
    """
    if substring in text:
        return f"PASS: Text contains '{substring}'"
    else:
        return f"FAIL: Text does not contain '{substring}'. Text: {text[:500]}"


@tool
def assert_not_contains(text: str, substring: str) -> str:
    """Asserts that text does NOT contain the specified substring.

    Args:
        text: The text to search in.
        substring: The text that should not be present.

    Returns:
        PASS or FAIL with details.
    """
    if substring not in text:
        return f"PASS: Text does not contain '{substring}'"
    else:
        return f"FAIL: Text unexpectedly contains '{substring}'"


@tool
def assert_greater_than(actual: str, threshold: str) -> str:
    """Asserts that a numeric value is greater than a threshold.

    Args:
        actual: The actual numeric value (as string).
        threshold: The threshold value (as string).

    Returns:
        PASS or FAIL with details.
    """
    try:
        a = float(actual)
        t = float(threshold)
        if a > t:
            return f"PASS: {a} > {t}"
        else:
            return f"FAIL: {a} is not greater than {t}"
    except ValueError:
        return f"ERROR: Cannot compare non-numeric values: '{actual}' and '{threshold}'"


@tool
def assert_matches_pattern(text: str, pattern: str) -> str:
    """Asserts that text matches a regex pattern.

    Args:
        text: The text to match.
        pattern: Regular expression pattern.

    Returns:
        PASS or FAIL with details.
    """
    import re
    if re.search(pattern, text):
        return f"PASS: Text matches pattern '{pattern}'"
    else:
        return f"FAIL: Text does not match pattern '{pattern}'. Text: {text[:500]}"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

@tool
def log_message(message: str, level: str = "INFO") -> str:
    """Logs a message to the Robot Framework log.

    Args:
        message: Message to log.
        level: Log level (DEBUG, INFO, WARN, ERROR).

    Returns:
        Confirmation message.
    """
    try:
        rf_logger.write(message, level.upper())
    except Exception:
        logger.info(message)
    return f"Logged [{level}]: {message}"


@tool
def log_step_result(step_description: str, status: str, details: str = "") -> str:
    """Records a test step result for reporting purposes.

    Args:
        step_description: What the step tested.
        status: PASS, FAIL, or SKIP.
        details: Additional details or assertion message.

    Returns:
        Formatted step result.
    """
    result = f"STEP: {step_description}\nSTATUS: {status}"
    if details:
        result += f"\nDETAILS: {details}"
    try:
        rf_logger.info(result)
    except Exception:
        logger.info(result)
    return result


# ---------------------------------------------------------------------------
# Agentic step recording
# ---------------------------------------------------------------------------

def _normalize_step_status(status: str) -> StepStatus:
    """Normalize free-form status string into StepStatus."""
    value = str(status).strip().lower()
    if value in ("pass", "passed", "ok", "success"):
        return StepStatus.PASSED
    if value in ("fail", "failed"):
        return StepStatus.FAILED
    if value in ("skip", "skipped", "ignored", "ignore"):
        return StepStatus.SKIPPED
    return StepStatus.ERROR


def _coerce_float(value, default: float = 0.0) -> float:
    """Best-effort float coercion for tool inputs."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _log_agentic_step_to_rf(
    action: str,
    description: str,
    status: StepStatus,
    duration_ms: float,
    screenshot_path: str = None,
    assertion_message: str = None,
    error_message: str = None,
) -> None:
    """Emit an agentic step as a Robot Framework keyword entry."""
    try:
        bi = BuiltIn()
        args = [
            action,
            description,
            status.value,
            f"{duration_ms:.0f}",
            assertion_message or "",
            error_message or "",
            screenshot_path or "",
        ]
        if status in (StepStatus.FAILED, StepStatus.ERROR):
            bi.run_keyword_and_ignore_error("Agentic Step", *args)
        else:
            bi.run_keyword("Agentic Step", *args)
    except RobotNotRunningError:
        # Fallback when running outside RF
        rf_logger.info(
            f"[AGENTIC STEP] {action} - {description} ({status.value})"
        )
    except Exception as exc:
        logger.debug("Unable to log agentic step to RF: %s", exc)


def _is_sensitive_key(name: str) -> bool:
    lowered = name.lower()
    return any(
        token in lowered
        for token in (
            "password",
            "passwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "authorization",
            "auth",
            "bearer",
        )
    )


def _truncate(value: Any, limit: int = 120) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _build_description(action: str, func, args, kwargs) -> str:
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        parts = []
        for name, value in bound.arguments.items():
            if name == "tool_context":
                continue
            if value is None:
                continue
            display = "***" if _is_sensitive_key(name) else _truncate(value)
            parts.append(f"{name}={display}")
        if parts:
            return ", ".join(parts)
    except Exception:
        pass

    arg_text = ", ".join(_truncate(a) for a in args if a is not None)
    if arg_text:
        return arg_text
    return action


def _status_from_result(result: Any) -> Optional[StepStatus]:
    if not isinstance(result, str):
        return None
    text = result.strip()
    if not text:
        return None
    upper = text.upper()
    if upper.startswith("PASS:"):
        return StepStatus.PASSED
    if upper.startswith("FAIL:"):
        return StepStatus.FAILED
    if upper.startswith("SKIP:"):
        return StepStatus.SKIPPED
    if upper.startswith("ERROR:"):
        return StepStatus.ERROR
    return None


def _extract_assertion_message(result: Any, status: StepStatus) -> Optional[str]:
    if not isinstance(result, str):
        return None
    if status in (StepStatus.FAILED, StepStatus.ERROR, StepStatus.SKIPPED):
        return _truncate(result, 500)
    if result.strip().startswith(("PASS:", "FAIL:", "ERROR:", "SKIP:")):
        return _truncate(result, 500)
    if "Status:" in result or "Response:" in result:
        return _truncate(result, 500)
    return None


def _extract_screenshot_path(result: Any) -> Optional[str]:
    if not isinstance(result, str):
        return None
    marker = "Screenshot captured:"
    if marker in result:
        return result.split(marker, 1)[1].strip()
    return None


def _record_tool_step(
    action: str,
    description: str,
    status: StepStatus,
    duration_ms: float,
    screenshot_path: str = None,
    assertion_message: str = None,
    error_message: str = None,
) -> None:
    session = get_active_session()
    if session:
        record_step_impl(
            session=session,
            action=action,
            description=description,
            status=status,
            duration_ms=duration_ms,
            screenshot_path=screenshot_path,
            assertion_message=assertion_message,
            error_message=error_message,
        )
    _log_agentic_step_to_rf(
        action=action,
        description=description,
        status=status,
        duration_ms=duration_ms,
        screenshot_path=screenshot_path,
        assertion_message=assertion_message,
        error_message=error_message,
    )


def instrument_tool(tool_obj: Any) -> Any:
    if not isinstance(tool_obj, DecoratedFunctionTool):
        return tool_obj
    if getattr(tool_obj, "_agentic_instrumented", False):
        return tool_obj

    original_func = tool_obj._tool_func
    action_name = tool_obj.tool_name or original_func.__name__

    @functools.wraps(original_func)
    def wrapped(*args, **kwargs):
        start = time.time()
        error = None
        result = None
        try:
            result = original_func(*args, **kwargs)
            return result
        except Exception as exc:
            error = exc
            raise
        finally:
            duration_ms = max((time.time() - start) * 1000.0, 0.0)
            if error is None:
                status = StepStatus.PASSED
                derived = _status_from_result(result)
                if derived:
                    status = derived
                error_message = None
            else:
                status = StepStatus.FAILED if isinstance(error, AssertionError) else StepStatus.ERROR
                if isinstance(error, AssertionError):
                    error_message = str(error)
                else:
                    error_message = f"{type(error).__name__}: {error}"

            description = _build_description(action_name, original_func, args, kwargs)
            assertion_message = _extract_assertion_message(result, status)
            screenshot_path = _extract_screenshot_path(result)

            _record_tool_step(
                action=action_name,
                description=description,
                status=status,
                duration_ms=duration_ms,
                screenshot_path=screenshot_path,
                assertion_message=assertion_message,
                error_message=error_message,
            )

    tool_obj._tool_func = wrapped
    tool_obj._agentic_instrumented = True
    return tool_obj


def instrument_tool_list(tools: Iterable[Any]) -> list[Any]:
    return [instrument_tool(tool_obj) for tool_obj in tools]


@tool
def record_step(
    action: str,
    description: str,
    status: str,
    duration_ms: str = "0",
    screenshot_path: str = None,
    assertion_message: str = None,
    error_message: str = None,
) -> str:
    """Records a test step in the active session and RF log.

    Args:
        action: Tool/action name.
        description: Human-readable step description.
        status: PASS/FAIL/SKIP/ERROR (case-insensitive).
        duration_ms: Execution time in milliseconds.
        screenshot_path: Optional screenshot path.
        assertion_message: Assertion detail.
        error_message: Error detail.

    Returns:
        Confirmation message.
    """
    step_status = _normalize_step_status(status)
    duration = _coerce_float(duration_ms)
    session = get_active_session()
    if session:
        record_step_impl(
            session=session,
            action=action,
            description=description,
            status=step_status,
            duration_ms=duration,
            screenshot_path=screenshot_path,
            assertion_message=assertion_message,
            error_message=error_message,
        )
    _log_agentic_step_to_rf(
        action=action,
        description=description,
        status=step_status,
        duration_ms=duration,
        screenshot_path=screenshot_path,
        assertion_message=assertion_message,
        error_message=error_message,
    )
    return f"Recorded step: {action} - {description} ({step_status.value})"

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------


@tool
def sleep_seconds(seconds: float) -> str:
    """Pauses execution for the specified number of seconds.

    Args:
        seconds: Number of seconds to sleep (max 30).

    Returns:
        Confirmation message.
    """
    seconds = min(seconds, 30)  # Safety cap
    time.sleep(seconds)
    return f"Waited {seconds} seconds"


# ---------------------------------------------------------------------------
# Data utilities
# ---------------------------------------------------------------------------

@tool
def parse_json(json_string: str) -> str:
    """Parses a JSON string and returns a formatted representation.

    Args:
        json_string: JSON string to parse.

    Returns:
        Formatted JSON or error message.
    """
    try:
        data = json.loads(json_string)
        formatted = json.dumps(data, indent=2)
        if len(formatted) > 3000:
            return formatted[:3000] + "\n... [truncated]"
        return formatted
    except json.JSONDecodeError as e:
        return f"ERROR: Invalid JSON: {e}"


@tool
def get_current_timestamp() -> str:
    """Returns the current timestamp in ISO format.

    Returns:
        Current timestamp string.
    """
    from datetime import datetime
    return f"Current timestamp: {datetime.now().isoformat()}"


# ---------------------------------------------------------------------------
# Screenshot analysis (AIVision integration)
# ---------------------------------------------------------------------------

@tool
def analyze_screenshot(screenshot_path: str, question: str) -> str:
    """Analyzes a screenshot using AI vision to answer a question.

    Requires robotframework-aivision to be loaded. Falls back to a simple
    description if AIVision is not available.

    Args:
        screenshot_path: Path to the screenshot file.
        question: What to analyze in the screenshot.

    Returns:
        AI-generated analysis of the screenshot.
    """
    try:
        aivision = BuiltIn().get_library_instance("AIVision")
        result = aivision.genai.generate_ai_response(
            instructions=question,
            image_paths=[screenshot_path],
        )
        return f"Visual analysis: {result}"
    except RuntimeError:
        return "AIVision library not loaded. Visual analysis unavailable. Use DOM analysis tools instead."
    except Exception as e:
        return f"Visual analysis error: {e}"


@tool
def get_rf_variable(variable_name: str) -> str:
    """Gets the value of a Robot Framework variable.

    Args:
        variable_name: Variable name with RF syntax (e.g., '${MY_VAR}', '%{ENV_VAR}').

    Returns:
        The variable value or error message.
    """
    try:
        value = BuiltIn().get_variable_value(variable_name)
        if value is None:
            return f"Variable {variable_name} is not defined"
        return f"Variable {variable_name} = {value}"
    except Exception as e:
        return f"ERROR getting variable {variable_name}: {e}"


# ---------------------------------------------------------------------------
# Tool list export
# ---------------------------------------------------------------------------

COMMON_TOOLS = [
    assert_equal,
    assert_contains,
    assert_not_contains,
    assert_greater_than,
    assert_matches_pattern,
    log_message,
    log_step_result,
    record_step,
    sleep_seconds,
    parse_json,
    get_current_timestamp,
    analyze_screenshot,
    get_rf_variable,
]
