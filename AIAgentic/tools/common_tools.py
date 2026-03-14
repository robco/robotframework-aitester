# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Common tools — Shared utility tools available to all executor agents.

These tools provide general-purpose functionality like screenshots,
assertions, logging, timing, and optional aivision integration.
"""

import json
import logging
import os
import time
from strands import tool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.api import logger as rf_logger

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
    sleep_seconds,
    parse_json,
    get_current_timestamp,
    analyze_screenshot,
    get_rf_variable,
]
