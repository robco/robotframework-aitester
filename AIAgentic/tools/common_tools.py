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
import shutil
from typing import Any, Iterable, Optional
from strands import tool
from strands.tools.decorator import DecoratedFunctionTool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from robot.api import logger as rf_logger

from ..executor import StepStatus, record_step as record_step_impl, get_active_session

logger = logging.getLogger(__name__)
_SCREENSHOT_OUTPUT_CACHE = {}

WEB_UI_INTERACTION_ACTIONS = {
    "selenium_open_browser",
    "selenium_go_to",
    "selenium_go_back",
    "selenium_reload_page",
    "selenium_click_element",
    "selenium_click_button",
    "selenium_click_link",
    "selenium_input_text",
    "selenium_input_password",
    "selenium_clear_element_text",
    "selenium_select_from_list_by_label",
    "selenium_select_from_list_by_value",
    "selenium_select_checkbox",
    "selenium_unselect_checkbox",
    "selenium_mouse_over",
    "selenium_press_keys",
    "selenium_scroll_element_into_view",
    "selenium_handle_common_blockers",
    "selenium_switch_window",
    "selenium_select_frame",
    "selenium_unselect_frame",
}

WEB_UI_STATE_ACTIONS = {
    "selenium_get_text",
    "selenium_get_element_attribute",
    "selenium_get_value",
    "selenium_element_should_be_visible",
    "selenium_element_should_not_be_visible",
    "selenium_element_should_contain",
    "selenium_element_text_should_be",
    "selenium_page_should_contain",
    "selenium_page_should_not_contain",
    "selenium_title_should_be",
    "selenium_get_location",
    "selenium_location_should_be",
    "selenium_location_should_contain",
    "selenium_wait_until_element_is_visible",
    "selenium_wait_until_element_is_enabled",
    "selenium_wait_until_page_contains",
    "selenium_wait_until_page_contains_element",
    "selenium_capture_page_screenshot",
    "selenium_execute_javascript",
    "get_page_snapshot",
    "get_page_structure",
    "get_interactive_elements",
    "get_page_text_content",
    "get_all_links",
    "get_frame_inventory",
    "get_form_fields",
    "check_page_errors",
}

MOBILE_UI_INTERACTION_ACTIONS = {
    "appium_open_application",
    "appium_close_application",
    "appium_close_all_applications",
    "appium_click_element",
    "appium_input_text",
    "appium_clear_text",
    "appium_long_press",
    "appium_swipe",
    "appium_scroll_down",
    "appium_scroll_up",
    "appium_background_app",
    "appium_reset_application",
    "appium_handle_common_interruptions",
}

MOBILE_UI_STATE_ACTIONS = {
    "appium_get_text",
    "appium_get_element_attribute",
    "appium_element_should_be_visible",
    "appium_element_should_not_be_visible",
    "appium_element_should_contain_text",
    "appium_page_should_contain_text",
    "appium_page_should_not_contain_text",
    "appium_wait_until_element_is_visible",
    "appium_wait_until_page_contains",
    "appium_capture_page_screenshot",
    "appium_get_view_snapshot",
    "appium_get_source",
}

WEB_UI_MUTATION_ACTIONS = {
    "selenium_open_browser",
    "selenium_close_browser",
    "selenium_close_all_browsers",
    "selenium_go_to",
    "selenium_go_back",
    "selenium_reload_page",
    "selenium_click_element",
    "selenium_click_button",
    "selenium_click_link",
    "selenium_input_text",
    "selenium_input_password",
    "selenium_clear_element_text",
    "selenium_select_from_list_by_label",
    "selenium_select_from_list_by_value",
    "selenium_select_checkbox",
    "selenium_unselect_checkbox",
    "selenium_mouse_over",
    "selenium_press_keys",
    "selenium_scroll_element_into_view",
    "selenium_handle_common_blockers",
    "selenium_wait_until_element_is_visible",
    "selenium_wait_until_element_is_enabled",
    "selenium_wait_until_page_contains",
    "selenium_wait_until_page_contains_element",
    "selenium_execute_javascript",
    "selenium_switch_window",
    "selenium_select_frame",
    "selenium_unselect_frame",
}

MOBILE_UI_MUTATION_ACTIONS = {
    "appium_open_application",
    "appium_close_application",
    "appium_close_all_applications",
    "appium_click_element",
    "appium_input_text",
    "appium_clear_text",
    "appium_long_press",
    "appium_swipe",
    "appium_scroll_down",
    "appium_scroll_up",
    "appium_background_app",
    "appium_reset_application",
    "appium_handle_common_interruptions",
}


def _track_ui_action(session, action_name: str, status: StepStatus) -> None:
    if not session or status is not StepStatus.PASSED:
        return
    if session.test_mode == "web":
        interaction_set = WEB_UI_INTERACTION_ACTIONS
        state_set = WEB_UI_STATE_ACTIONS
    elif session.test_mode == "mobile":
        interaction_set = MOBILE_UI_INTERACTION_ACTIONS
        state_set = MOBILE_UI_STATE_ACTIONS
    else:
        return

    step_number = session.current_high_level_step
    if action_name in interaction_set:
        session.ui_interactions_total += 1
        if step_number:
            session.ui_interactions_by_step[step_number] = (
                session.ui_interactions_by_step.get(step_number, 0) + 1
            )
    if action_name in state_set:
        session.ui_state_checks_total += 1
        if step_number:
            session.ui_state_checks_by_step[step_number] = (
                session.ui_state_checks_by_step.get(step_number, 0) + 1
            )


def _invalidate_browser_snapshot_cache(action_name: str, status: StepStatus) -> None:
    if status is not StepStatus.PASSED or action_name not in WEB_UI_MUTATION_ACTIONS:
        return
    try:
        from .browser_analysis_tools import invalidate_page_snapshot_cache

        invalidate_page_snapshot_cache()
    except Exception as exc:
        logger.debug("Unable to invalidate browser analysis cache: %s", exc)


def _invalidate_mobile_snapshot_cache(action_name: str, status: StepStatus) -> None:
    if status is not StepStatus.PASSED or action_name not in MOBILE_UI_MUTATION_ACTIONS:
        return
    try:
        from .mobile_tools import invalidate_mobile_snapshot_cache

        invalidate_mobile_snapshot_cache()
    except Exception as exc:
        logger.debug("Unable to invalidate mobile analysis cache: %s", exc)


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
    high_level_step_number: Optional[int] = None,
    high_level_step_description: str = None,
) -> None:
    """Emit an agentic step as a Robot Framework keyword entry."""
    try:
        bi = BuiltIn()
        normalized_screenshot_path = screenshot_path or ""
        if normalized_screenshot_path:
            try:
                copied_target = _ensure_screenshot_in_output_dir(normalized_screenshot_path)
                if copied_target:
                    normalized_screenshot_path = copied_target
            except Exception as exc:
                logger.debug("Unable to normalize screenshot path before RF logging: %s", exc)
        args = [
            action,
            description,
            status.value,
            f"{duration_ms:.0f}",
            assertion_message or "",
            error_message or "",
            normalized_screenshot_path,
        ]
        if high_level_step_number is not None or high_level_step_description:
            args.extend(
                [
                    str(high_level_step_number or ""),
                    high_level_step_description or "",
                ]
            )
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


def _log_high_level_step_to_rf(step_number: int, step_description: str) -> None:
    """Emit a high-level step marker into the RF log."""
    try:
        bi = BuiltIn()
        bi.run_keyword("Agentic High Level Step", str(step_number), step_description or "")
    except RobotNotRunningError:
        rf_logger.info(f"[HIGH LEVEL STEP] {step_number}. {step_description}")
    except Exception as exc:
        logger.debug("Unable to log high-level step to RF: %s", exc)


def _resolve_high_level_step_description(
    session, step_number: int, step_description: str
) -> str:
    if session and session.high_level_steps:
        if 1 <= step_number <= len(session.high_level_steps):
            return session.high_level_steps[step_number - 1]
    return step_description or ""


def _ensure_screenshot_in_output_dir(screenshot_path: Optional[str]) -> Optional[str]:
    if not screenshot_path:
        return None
    filename = os.path.basename(screenshot_path)
    normalized_source = os.path.abspath(
        os.path.expanduser(os.path.expandvars(str(screenshot_path)))
    )
    try:
        output_dir = BuiltIn().get_variable_value("${OUTPUT_DIR}")
    except RobotNotRunningError:
        output_dir = os.getcwd()
    if not output_dir:
        output_dir = os.getcwd()
    target = os.path.join(output_dir, filename)
    if os.path.abspath(normalized_source) == os.path.abspath(target):
        return target
    try:
        source_stat = os.stat(normalized_source)
    except OSError:
        source_stat = None
    cache_key = None
    if source_stat is not None:
        cache_key = (
            os.path.realpath(normalized_source),
            os.path.realpath(target),
            int(source_stat.st_mtime_ns),
            int(source_stat.st_size),
        )
        cached_target = _SCREENSHOT_OUTPUT_CACHE.get(cache_key)
        if cached_target and os.path.exists(cached_target):
            return cached_target
    try:
        if os.path.exists(normalized_source):
            should_copy = True
            if os.path.exists(target) and source_stat is not None:
                target_stat = os.stat(target)
                should_copy = (
                    int(target_stat.st_mtime_ns) < int(source_stat.st_mtime_ns)
                    or int(target_stat.st_size) != int(source_stat.st_size)
                )
            if should_copy:
                shutil.copy2(normalized_source, target)
            if cache_key is not None:
                _SCREENSHOT_OUTPUT_CACHE[cache_key] = target
    except Exception as exc:
        logger.debug("Unable to copy screenshot to output dir: %s", exc)
    return target


def _normalize_screenshot_filename(filename: Optional[str]) -> Optional[str]:
    if not filename:
        return filename
    base, ext = os.path.splitext(filename)
    if not ext:
        return f"{filename}.png"
    if ext.lower() != ".png":
        return f"{base}.png"
    return filename


def _set_high_level_step(
    session, step_number: int, step_description: str, source: str = "tool"
) -> bool:
    if session:
        if (
            session.current_high_level_step == step_number
            and session.current_high_level_step_description == step_description
        ):
            return False
        session.current_high_level_step = step_number
        session.current_high_level_step_description = step_description
    _log_high_level_step_to_rf(step_number, step_description)
    return True


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
    normalized_screenshot = _ensure_screenshot_in_output_dir(screenshot_path)
    if session and session.high_level_steps and session.current_high_level_step is None:
        _set_high_level_step(
            session=session,
            step_number=1,
            step_description=session.high_level_steps[0],
            source="auto",
        )
    if session:
        record_step_impl(
            session=session,
            action=action,
            description=description,
            status=status,
            duration_ms=duration_ms,
            screenshot_path=normalized_screenshot,
            assertion_message=assertion_message,
            error_message=error_message,
        )
        _track_ui_action(session, action, status)
    _invalidate_browser_snapshot_cache(action, status)
    _invalidate_mobile_snapshot_cache(action, status)
    _log_agentic_step_to_rf(
        action=action,
        description=description,
        status=status,
        duration_ms=duration_ms,
        screenshot_path=normalized_screenshot,
        assertion_message=assertion_message,
        error_message=error_message,
        high_level_step_number=session.current_high_level_step if session else None,
        high_level_step_description=session.current_high_level_step_description if session else None,
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
    normalized_screenshot = _ensure_screenshot_in_output_dir(screenshot_path)
    if session and session.high_level_steps and session.current_high_level_step is None:
        _set_high_level_step(
            session=session,
            step_number=1,
            step_description=session.high_level_steps[0],
            source="auto",
        )
    if session:
        record_step_impl(
            session=session,
            action=action,
            description=description,
            status=step_status,
            duration_ms=duration,
            screenshot_path=normalized_screenshot,
            assertion_message=assertion_message,
            error_message=error_message,
        )
    _log_agentic_step_to_rf(
        action=action,
        description=description,
        status=step_status,
        duration_ms=duration,
        screenshot_path=normalized_screenshot,
        assertion_message=assertion_message,
        error_message=error_message,
        high_level_step_number=session.current_high_level_step if session else None,
        high_level_step_description=session.current_high_level_step_description if session else None,
    )
    return f"Recorded step: {action} - {description} ({step_status.value})"


@tool
def start_high_level_step(step_number: str, step_description: str = "") -> str:
    """Starts a user-defined high-level test step for reporting.

    Args:
        step_number: 1-based high-level step index.
        step_description: Optional step text. If a session-defined list exists,
            the stored step text overrides this value.

    Returns:
        Confirmation message.
    """
    try:
        number = int(step_number)
    except (TypeError, ValueError):
        return f"ERROR: step_number must be an integer, got '{step_number}'"

    session = get_active_session()
    description = _resolve_high_level_step_description(
        session=session,
        step_number=number,
        step_description=step_description,
    )
    changed = _set_high_level_step(
        session=session,
        step_number=number,
        step_description=description,
        source="tool",
    )
    if not changed:
        return f"High-level step {number} already active"
    return f"High-level step {number}: {description}"

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
    start_high_level_step,
    sleep_seconds,
    parse_json,
    get_current_timestamp,
    analyze_screenshot,
    get_rf_variable,
]
