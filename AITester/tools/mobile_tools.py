# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Mobile tools — Strands @tool wrappers around AppiumLibrary keywords.

These tools provide the AI agent with mobile application testing capabilities
via robotframework-appiumlibrary.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict
from strands import tool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .common_tools import instrument_tool_list, _normalize_screenshot_filename
from ..executor import get_active_session

logger = logging.getLogger(__name__)
_MOBILE_SNAPSHOT_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_appium():
    """Get the AppiumLibrary instance from Robot Framework."""
    bi = BuiltIn()
    lib_name = "AppiumLibrary"
    try:
        override = bi.get_variable_value("${AITESTER_APPIUM_LIBRARY}")
        if override:
            lib_name = override
    except RobotNotRunningError:
        pass
    try:
        return bi.get_library_instance(lib_name)
    except Exception as exc:
        raise RuntimeError(
            f"AppiumLibrary instance '{lib_name}' not found. "
            "Ensure AppiumLibrary is imported or set appium_library "
            "when importing AITester."
        ) from exc


def _should_scroll_into_view() -> bool:
    session = get_active_session()
    if not session:
        return True
    return bool(session.scroll_into_view)


def _get_snapshot_cache_key(driver) -> str:
    return str(getattr(driver, "session_id", None) or id(driver))


def invalidate_mobile_snapshot_cache(driver=None) -> None:
    if driver is None:
        _MOBILE_SNAPSHOT_CACHE.clear()
        return
    _MOBILE_SNAPSHOT_CACHE.pop(_get_snapshot_cache_key(driver), None)


def _maybe_scroll_into_view(al, locator: str) -> None:
    if not locator or not _should_scroll_into_view():
        return
    if not hasattr(al, "scroll_element_into_view"):
        logger.debug("AppiumLibrary has no scroll_element_into_view; skipping scroll.")
        return
    try:
        al.scroll_element_into_view(locator)
    except Exception as exc:
        logger.debug("Unable to scroll element into view (%s): %s", locator, exc)


def _xml_attr(node, *names: str) -> str:
    for name in names:
        value = node.attrib.get(name)
        if value:
            return str(value).strip()
    return ""


def _is_true_like(value: str) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def _xpath_literal(value: str) -> str:
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return 'concat(' + ', \'"\', '.join(f'"{part}"' for part in parts) + ')'


def _build_mobile_snapshot(source: str) -> dict:
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        snapshot = _empty_mobile_snapshot()
        snapshot["parse_error"] = "Unable to parse Appium page source"
        return snapshot

    text_preview = []
    interruptions = []
    interactive_elements = []
    loading_indicators = []
    seen_text = set()
    seen_interruptions = set()
    seen_interactive = set()
    seen_loading = set()

    def visit(node, ancestor_context: str = "") -> None:
        label = _xml_attr(
            node,
            "text",
            "label",
            "name",
            "content-desc",
            "contentDescription",
            "value",
        )
        node_context = " ".join(
            part
            for part in [
                ancestor_context,
                _xml_attr(node, "resource-id", "resourceId"),
                _xml_attr(node, "class", "type"),
                _xml_attr(node, "hint"),
                label,
            ]
            if part
        )
        if label and label.lower() not in seen_text and len(text_preview) < 12:
            seen_text.add(label.lower())
            text_preview.append(label)

        candidate = _classify_mobile_interruption(label, node_context, node)
        if candidate:
            key = (candidate["category"], candidate["label"].lower())
            if key not in seen_interruptions and len(interruptions) < 8:
                seen_interruptions.add(key)
                interruptions.append(candidate)

        interactive = _build_mobile_interactive_element(node, label, node_context)
        if interactive:
            key = interactive["locator"] or (
                interactive["kind"],
                interactive["label"].lower(),
                interactive["resource_id"],
            )
            if key not in seen_interactive and len(interactive_elements) < 80:
                seen_interactive.add(key)
                interactive_elements.append(interactive)

        loading = _classify_mobile_loading_indicator(label, node_context, node)
        if loading:
            key = loading["locator"] or (loading["kind"], loading["label"].lower())
            if key not in seen_loading and len(loading_indicators) < 8:
                seen_loading.add(key)
                loading_indicators.append(loading)

        for child in list(node):
            visit(child, node_context)

    visit(root)
    interruptions.sort(key=lambda item: item["score"], reverse=True)
    return {
        "text_preview": text_preview,
        "interruptions": interruptions,
        "interactive_elements": interactive_elements,
        "loading_indicators": loading_indicators,
        "parse_error": None,
    }


def _empty_mobile_snapshot() -> Dict[str, Any]:
    return {
        "text_preview": [],
        "interruptions": [],
        "interactive_elements": [],
        "loading_indicators": [],
        "parse_error": None,
    }


def _get_mobile_snapshot_data(force_refresh: bool = False) -> Dict[str, Any]:
    al = _get_appium()
    driver = al._current_application()
    cache_key = _get_snapshot_cache_key(driver)
    if force_refresh or cache_key not in _MOBILE_SNAPSHOT_CACHE:
        try:
            source = al.get_source()
            snapshot = _build_mobile_snapshot(source)
        except Exception as exc:
            logger.warning("Mobile source retrieval failed, using fallback snapshot: %s", exc)
            source = ""
            snapshot = _empty_mobile_snapshot()
            snapshot["parse_error"] = f"Unable to retrieve Appium page source: {exc}"
        snapshot.update(
            {
                "source": source,
                "context": _read_driver_value(driver, "current_context"),
                "contexts": _read_driver_contexts(driver),
                "activity": _read_driver_value(driver, "current_activity"),
                "package": _read_driver_value(driver, "current_package"),
                "platform": _read_driver_capability(
                    driver,
                    "platformName",
                    "appium:platformName",
                    "platform",
                ),
                "device": _read_driver_capability(
                    driver,
                    "deviceName",
                    "appium:deviceName",
                ),
                "window_size": _read_driver_window_size(driver),
            }
        )
        _MOBILE_SNAPSHOT_CACHE[cache_key] = snapshot
    return _MOBILE_SNAPSHOT_CACHE[cache_key]


def _read_driver_value(driver, attr_name: str) -> str:
    if driver is None:
        return ""
    try:
        value = getattr(driver, attr_name, None)
        if callable(value):
            value = value()
        return str(value).strip() if value else ""
    except Exception as exc:
        logger.debug("Unable to read driver attribute %s: %s", attr_name, exc)
        return ""


def _read_driver_capability(driver, *keys: str) -> str:
    caps = getattr(driver, "capabilities", None) or getattr(driver, "desired_capabilities", None)
    if not isinstance(caps, dict):
        return ""
    normalized = {str(key).lower(): value for key, value in caps.items()}
    for key in keys:
        if key in caps and caps[key]:
            return str(caps[key]).strip()
        lowered = str(key).lower()
        if lowered in normalized and normalized[lowered]:
            return str(normalized[lowered]).strip()
    return ""


def _read_driver_contexts(driver) -> list[str]:
    if driver is None:
        return []
    try:
        contexts = getattr(driver, "contexts", None)
        if callable(contexts):
            contexts = contexts()
    except Exception as exc:
        logger.debug("Unable to read mobile contexts: %s", exc)
        contexts = None

    normalized = []
    seen = set()
    if isinstance(contexts, (list, tuple, set)):
        for value in contexts:
            item = str(value).strip()
            if item and item not in seen:
                normalized.append(item)
                seen.add(item)

    current_context = _read_driver_value(driver, "current_context")
    if current_context and current_context not in seen:
        normalized.insert(0, current_context)
    return normalized


def _read_driver_window_size(driver) -> Dict[str, int]:
    if driver is None:
        return {}
    try:
        raw = driver.get_window_size()
    except Exception as exc:
        logger.debug("Unable to read mobile window size: %s", exc)
        return {}
    if not isinstance(raw, dict):
        return {}
    try:
        width = int(raw.get("width", 0))
        height = int(raw.get("height", 0))
    except (TypeError, ValueError):
        return {}
    if width <= 0 or height <= 0:
        return {}
    return {"width": width, "height": height}


def _classify_mobile_interruption(label: str, context: str, node):
    if not label:
        return None
    label_lower = label.lower()
    context_lower = context.lower()
    control_hint = " ".join(
        [
            node.tag,
            _xml_attr(node, "class", "type"),
            _xml_attr(node, "resource-id", "resourceId"),
        ]
    ).lower()
    clickable = (
        _is_true_like(node.attrib.get("clickable"))
        or _is_true_like(node.attrib.get("focusable"))
        or "button" in control_hint
    )
    if not clickable:
        return None

    category = None
    action = None
    score = 0

    if (
        label_lower in {
            "allow",
            "while using the app",
            "only this time",
            "allow once",
            "continue",
        }
        or (
            "allow" in label_lower
            and "don't" not in label_lower
            and "do not" not in label_lower
        )
    ):
        category = "permission"
        action = "allow"
        score = 140
    elif any(
        phrase in label_lower
        for phrase in ("accept", "agree", "continue")
    ) and any(
        phrase in context_lower
        for phrase in ("consent", "privacy", "cookie", "terms")
    ):
        category = "consent"
        action = "accept"
        score = 130
    elif any(
        phrase in label_lower
        for phrase in ("not now", "later", "skip", "dismiss", "close", "got it")
    ):
        category = "interruption"
        action = "dismiss"
        score = 125
    elif any(
        phrase in label_lower
        for phrase in ("continue", "next", "start")
    ) and any(
        phrase in context_lower
        for phrase in ("tutorial", "onboarding", "tour", "welcome", "coach")
    ):
        category = "tutorial"
        action = "continue"
        score = 120
    elif label_lower in {"ok", "okay"}:
        category = "dialog"
        action = "dismiss"
        score = 110

    if not category or not action:
        return None

    locator = _build_mobile_text_locator(label)
    return {
        "category": category,
        "action": action,
        "label": label,
        "locator": locator,
        "score": score,
    }


def _build_mobile_text_locator(label: str) -> str:
    literal = _xpath_literal(label)
    return (
        "xpath=//*[@text="
        + literal
        + " or @label="
        + literal
        + " or @name="
        + literal
        + " or @content-desc="
        + literal
        + " or @contentDescription="
        + literal
        + " or @value="
        + literal
        + "]"
    )


def _build_mobile_locator(node, label: str) -> str:
    resource_id = _xml_attr(node, "resource-id", "resourceId")
    if resource_id:
        return f"id={resource_id}"

    accessibility = _xml_attr(
        node,
        "content-desc",
        "contentDescription",
        "label",
        "name",
    )
    if accessibility:
        return f"accessibility_id={accessibility}"

    if label:
        return _build_mobile_text_locator(label)

    class_name = _xml_attr(node, "class", "type")
    if class_name:
        return f"class_name={class_name}"
    return ""


def _classify_mobile_control_kind(node, control_hint: str) -> str | None:
    hint = control_hint.lower()
    if any(token in hint for token in ("edittext", "textfield", "textinput", "searchview")):
        return "input"
    if any(token in hint for token in ("password", "secure")):
        return "password"
    if any(token in hint for token in ("imagebutton", "button")):
        return "button"
    if "switch" in hint:
        return "switch"
    if "checkbox" in hint or _is_true_like(node.attrib.get("checkable")):
        return "checkbox"
    if any(token in hint for token in ("spinner", "picker")):
        return "picker"
    if "tab" in hint:
        return "tab"
    if _is_true_like(node.attrib.get("scrollable")):
        return "scrollable"
    if (
        _is_true_like(node.attrib.get("clickable"))
        or _is_true_like(node.attrib.get("focusable"))
        or _is_true_like(node.attrib.get("long-clickable"))
    ):
        return "interactive"
    return None


def _build_mobile_interactive_element(node, label: str, context: str):
    control_hint = " ".join(
        part
        for part in [
            node.tag,
            _xml_attr(node, "class", "type"),
            _xml_attr(node, "resource-id", "resourceId"),
            _xml_attr(node, "hint"),
            context,
        ]
        if part
    )
    kind = _classify_mobile_control_kind(node, control_hint)
    if not kind:
        return None

    enabled_value = node.attrib.get("enabled")
    return {
        "kind": kind,
        "label": label or "",
        "locator": _build_mobile_locator(node, label),
        "resource_id": _xml_attr(node, "resource-id", "resourceId"),
        "class_name": _xml_attr(node, "class", "type"),
        "hint": _xml_attr(node, "hint", "placeholder"),
        "enabled": True if enabled_value is None else _is_true_like(enabled_value),
        "selected": _is_true_like(node.attrib.get("selected")),
        "checked": _is_true_like(node.attrib.get("checked")),
    }


def _classify_mobile_loading_indicator(label: str, context: str, node):
    control_hint = " ".join(
        part
        for part in [
            node.tag,
            _xml_attr(node, "class", "type"),
            _xml_attr(node, "resource-id", "resourceId"),
            context,
            label,
        ]
        if part
    ).lower()

    signals = [
        token
        for token in (
            "loading",
            "spinner",
            "progress",
            "please wait",
            "processing",
            "saving",
            "syncing",
            "updating",
        )
        if token in control_hint
    ]
    if not signals and not any(
        token in control_hint
        for token in ("progressbar", "activityindicator", "progress_bar")
    ):
        return None

    if any(token in control_hint for token in ("progressbar", "progress_bar", "progress")):
        kind = "progress"
    elif any(token in control_hint for token in ("activityindicator", "spinner")):
        kind = "spinner"
    else:
        kind = "loading"

    indicator_label = (
        label
        or _xml_attr(node, "resource-id", "resourceId")
        or _xml_attr(node, "class", "type")
        or node.tag
    )
    return {
        "kind": kind,
        "label": indicator_label,
        "locator": _build_mobile_locator(node, label),
        "signals": signals or [kind],
    }


def _assert_application_termination_allowed(action_name: str, al=None) -> None:
    session = get_active_session()
    if not session or session.test_mode != "mobile":
        return
    if getattr(session, "allow_browser_termination", False):
        return
    al = al or _get_appium()
    try:
        al._current_application()
    except Exception:
        return
    raise AssertionError(
        f"{action_name} is blocked while a mobile app session is open. Preserve "
        "the current application state to avoid losing login state, navigation "
        "progress, and pre-set test data. Close, reset, or relaunch the app only "
        "when the user explicitly requests that action."
    )


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@tool
def appium_open_application(
    remote_url: str,
    platform_name: str,
    app: str = None,
    automation_name: str = None,
    device_name: str = None,
) -> str:
    """Opens a mobile application using Appium.

    Args:
        remote_url: Appium server URL (e.g., 'http://localhost:4723/wd/hub').
        platform_name: Target platform ('Android' or 'iOS').
        app: App package/activity or .ipa/.apk path.
        automation_name: Automation driver (e.g., 'UiAutomator2', 'XCUITest').
        device_name: Target device name or emulator.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    session = get_active_session()
    reuse_only = bool(session and session.reuse_existing_session)
    if reuse_only and session.start_state_summary:
        summary = session.start_state_summary.lower()
        if (
            "active browser session detected" in summary
            and "active mobile session detected" not in summary
        ):
            raise AssertionError(
                "Active web session detected. Refusing to open a new mobile "
                "session. Reuse the existing web session."
            )
    try:
        al._current_application()
        return "Application already open; using existing session"
    except Exception as e:
        logger.debug("No active Appium session detected: %s", e)
    if reuse_only:
        raise AssertionError(
            "Reuse of an existing Appium session is required, but no active "
            "mobile session was detected. Refusing to open a new session. "
            "Ensure AppiumLibrary is attached to the existing session (use "
            "the appium_library alias if needed)."
        )
    kwargs = {"platformName": platform_name}
    if app:
        kwargs["app"] = app
    if automation_name:
        kwargs["automationName"] = automation_name
    if device_name:
        kwargs["deviceName"] = device_name
    al.open_application(remote_url, **kwargs)
    return f"Application opened: platform={platform_name}, app={app}"


@tool
def appium_close_application() -> str:
    """Closes the currently active application.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    _assert_application_termination_allowed("appium_close_application", al)
    al.close_application()
    return "Application closed"


@tool
def appium_close_all_applications() -> str:
    """Closes all open application sessions.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    _assert_application_termination_allowed("appium_close_all_applications", al)
    al.close_all_applications()
    return "All applications closed"


@tool
def appium_background_app(seconds: int = 5) -> str:
    """Sends the app to background for a specified duration then brings it back.

    Args:
        seconds: Duration in seconds to keep app in background.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    al.background_app(seconds)
    return f"App was in background for {seconds} seconds and resumed"


@tool
def appium_reset_application() -> str:
    """Resets the current application (clears data/state).

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    _assert_application_termination_allowed("appium_reset_application", al)
    al.reset_application()
    return "Application reset"


# ---------------------------------------------------------------------------
# Context management
# ---------------------------------------------------------------------------

def _resolve_requested_context(contexts: list[str], requested: str) -> str:
    if not contexts:
        raise AssertionError("No Appium contexts are available on the current session.")

    requested_value = str(requested or "").strip()
    if not requested_value:
        raise AssertionError("Context name must not be empty.")

    requested_lower = requested_value.lower()
    for context_name in contexts:
        if context_name.lower() == requested_lower:
            return context_name

    if requested_lower in {"native", "native_app"}:
        for context_name in contexts:
            if context_name.lower().startswith("native"):
                return context_name

    if requested_lower in {"web", "webview", "browser", "chromium"}:
        for context_name in contexts:
            lowered = context_name.lower()
            if "webview" in lowered or "chromium" in lowered or "browser" in lowered:
                return context_name

    matches = [context_name for context_name in contexts if requested_lower in context_name.lower()]
    if len(matches) == 1:
        return matches[0]

    available = ", ".join(contexts)
    raise AssertionError(
        f"Unable to match mobile context '{requested_value}'. Available contexts: {available}"
    )


@tool
def appium_switch_context(context: str) -> str:
    """Switches the active mobile driver context.

    Args:
        context: Exact or partial context name. Supports shortcuts such as
            ``native`` and ``webview``.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    driver = al._current_application()
    contexts = _read_driver_contexts(driver)
    target = _resolve_requested_context(contexts, context)
    current_context = _read_driver_value(driver, "current_context")
    if current_context == target:
        return f"Context already active: {target}"

    switch_to = getattr(driver, "switch_to", None)
    if switch_to is not None and hasattr(switch_to, "context"):
        switch_to.context(target)
    elif hasattr(driver, "switch_to_context"):
        driver.switch_to_context(target)
    else:
        raise AssertionError(
            "The current Appium driver does not expose context switching support."
        )

    invalidate_mobile_snapshot_cache(driver)
    return f"Switched mobile context to {target}"


# ---------------------------------------------------------------------------
# Element interaction
# ---------------------------------------------------------------------------

@tool
def appium_click_element(locator: str) -> str:
    """Taps on a mobile element identified by the locator.

    Args:
        locator: Element locator (accessibility_id, id, xpath, class_name).

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    _maybe_scroll_into_view(al, locator)
    al.click_element(locator)
    return f"Tapped element: {locator}"


@tool
def appium_input_text(locator: str, text: str) -> str:
    """Types text into a mobile input field.

    Args:
        locator: Element locator for the input field.
        text: The text to type.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    _maybe_scroll_into_view(al, locator)
    al.input_text(locator, text)
    return f"Typed '{text}' into element: {locator}"


@tool
def appium_clear_text(locator: str) -> str:
    """Clears text from a mobile input field.

    Args:
        locator: Element locator for the input field.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    _maybe_scroll_into_view(al, locator)
    al.clear_text(locator)
    return f"Cleared text in element: {locator}"


@tool
def appium_long_press(locator: str, duration: int = 1000) -> str:
    """Performs a long press on a mobile element.

    Args:
        locator: Element locator to long press.
        duration: Press duration in milliseconds.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    _maybe_scroll_into_view(al, locator)
    al.long_press(locator, duration)
    return f"Long pressed element: {locator} for {duration}ms"


# ---------------------------------------------------------------------------
# Gestures
# ---------------------------------------------------------------------------

@tool
def appium_swipe(
    start_x: int, start_y: int, offset_x: int, offset_y: int, duration: int = 1000
) -> str:
    """Performs a swipe gesture on the screen.

    Args:
        start_x: Starting X coordinate.
        start_y: Starting Y coordinate.
        offset_x: Horizontal offset to swipe.
        offset_y: Vertical offset to swipe.
        duration: Swipe duration in milliseconds.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    al.swipe(
        start_x=int(start_x),
        start_y=int(start_y),
        end_x=int(offset_x),
        end_y=int(offset_y),
        duration=duration,
    )
    return f"Swiped from ({start_x},{start_y}) by offset ({offset_x},{offset_y})"


def _perform_viewport_swipe(al, *, direction: str, locator: str = None, duration: int = 800) -> str:
    driver = al._current_application()
    size = _read_driver_window_size(driver)
    if not size:
        raise AssertionError(
            "Unable to determine mobile viewport size for scrolling. "
            "Ensure the Appium driver exposes get_window_size()."
        )

    center_x = int(size["width"] * 0.5)
    start_y = int(size["height"] * 0.82)
    end_y = int(size["height"] * 0.35)
    if direction == "up":
        start_y, end_y = end_y, start_y

    al.swipe(
        start_x=center_x,
        start_y=start_y,
        end_x=center_x,
        end_y=end_y,
        duration=duration,
    )
    if locator:
        return f"Scrolled {direction} using viewport gesture near: {locator}"
    return f"Scrolled {direction} using viewport gesture"


@tool
def appium_scroll_down(locator: str = None) -> str:
    """Scrolls the screen downward.

    Args:
        locator: Optional element locator to scroll within.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    return _perform_viewport_swipe(al, direction="down", locator=locator, duration=800)


@tool
def appium_scroll_up(locator: str = None) -> str:
    """Scrolls the screen upward.

    Args:
        locator: Optional element locator to scroll within.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    return _perform_viewport_swipe(al, direction="up", locator=locator, duration=800)


# ---------------------------------------------------------------------------
# Element state queries
# ---------------------------------------------------------------------------

@tool
def appium_get_text(locator: str) -> str:
    """Gets the text of a mobile element.

    Args:
        locator: Element locator.

    Returns:
        The element's text content.
    """
    al = _get_appium()
    text = al.get_text(locator)
    return f"Text content: {text}"


@tool
def appium_get_element_attribute(locator: str, attribute: str) -> str:
    """Gets an attribute value of a mobile element.

    Args:
        locator: Element locator.
        attribute: Attribute name to retrieve.

    Returns:
        The attribute value.
    """
    al = _get_appium()
    value = al.get_element_attribute(locator, attribute)
    return f"Attribute '{attribute}' of {locator}: {value}"


@tool
def appium_element_should_be_visible(locator: str) -> str:
    """Asserts that a mobile element is visible on the screen.

    Args:
        locator: Element locator.

    Returns:
        PASS if visible, raises error if not.
    """
    al = _get_appium()
    al.element_should_be_visible(locator)
    return f"PASS: Element is visible: {locator}"


@tool
def appium_element_should_not_be_visible(locator: str) -> str:
    """Asserts that a mobile element is NOT visible on the screen.

    Args:
        locator: Element locator.

    Returns:
        PASS if not visible, raises error if visible.
    """
    al = _get_appium()
    al.element_should_not_be_visible(locator)
    return f"PASS: Element is not visible: {locator}"


@tool
def appium_element_should_contain_text(locator: str, expected: str) -> str:
    """Asserts that a mobile element contains the expected text.

    Args:
        locator: Element locator.
        expected: Expected text substring.

    Returns:
        PASS or raises assertion error.
    """
    al = _get_appium()
    al.element_should_contain_text(locator, expected)
    return f"PASS: Element {locator} contains '{expected}'"


@tool
def appium_page_should_contain_text(text: str) -> str:
    """Asserts that the current screen contains the specified text.

    Args:
        text: Expected text to find.

    Returns:
        PASS if found, raises error if not.
    """
    al = _get_appium()
    al.page_should_contain_text(text)
    return f"PASS: Screen contains '{text}'"


@tool
def appium_page_should_not_contain_text(text: str) -> str:
    """Asserts that the current screen does NOT contain the specified text.

    Args:
        text: Text that should not be present.

    Returns:
        PASS if not found, raises error if found.
    """
    al = _get_appium()
    al.page_should_not_contain_text(text)
    return f"PASS: Screen does not contain '{text}'"


# ---------------------------------------------------------------------------
# Wait keywords
# ---------------------------------------------------------------------------

@tool
def appium_wait_until_element_is_visible(locator: str, timeout: int = 10) -> str:
    """Waits until a mobile element becomes visible.

    Args:
        locator: Element locator to wait for.
        timeout: Maximum wait time in seconds.

    Returns:
        Confirmation when element becomes visible.
    """
    al = _get_appium()
    al.wait_until_element_is_visible(locator, timeout)
    return f"Element is now visible: {locator}"


@tool
def appium_wait_until_page_contains(text: str, timeout: int = 10) -> str:
    """Waits until the screen contains the specified text.

    Args:
        text: Text to wait for.
        timeout: Maximum wait time in seconds.

    Returns:
        Confirmation when text appears.
    """
    al = _get_appium()
    al.wait_until_page_contains(text, timeout)
    return f"Screen now contains: '{text}'"


# ---------------------------------------------------------------------------
# Screenshots
# ---------------------------------------------------------------------------

@tool
def appium_capture_page_screenshot(filename: str = None) -> str:
    """Captures a screenshot of the current mobile screen.

    Args:
        filename: Optional filename for the screenshot.

    Returns:
        Path to the saved screenshot file.
    """
    al = _get_appium()
    if filename:
        normalized = _normalize_screenshot_filename(filename)
        if normalized != filename:
            logger.debug(
                "Normalized screenshot filename to .png to avoid WebDriver warnings: %s",
                normalized,
            )
        path = al.capture_page_screenshot(normalized)
    else:
        path = al.capture_page_screenshot()
    return f"Screenshot captured: {path}"


# ---------------------------------------------------------------------------
# Screen analysis
# ---------------------------------------------------------------------------

@tool
def appium_get_source(refresh: bool = False) -> str:
    """Gets the page/screen source XML of the current mobile view.

    Args:
        refresh: Whether to force a fresh Appium source fetch.

    Returns:
        The page source XML (may be truncated for very large screens).
    """
    snapshot = _get_mobile_snapshot_data(force_refresh=bool(refresh))
    source = snapshot.get("source", "")
    if not source:
        note = snapshot.get("parse_error")
        if note:
            return f"Page source unavailable: {note}"
        return "Page source unavailable"
    if len(source) > 5000:
        source = source[:5000] + "\n... [truncated]"
    return f"Page source:\n{source}"


@tool
def appium_get_view_snapshot(refresh: bool = False) -> str:
    """Gets a compact summary of the current mobile screen."""
    snapshot = _get_mobile_snapshot_data(force_refresh=bool(refresh))
    lines = []
    if snapshot.get("platform"):
        lines.append(f"Platform: {snapshot['platform']}")
    if snapshot.get("device"):
        lines.append(f"Device: {snapshot['device']}")
    if snapshot.get("context"):
        lines.append(f"Context: {snapshot['context']}")
    if snapshot.get("contexts"):
        lines.append("Available contexts: " + ", ".join(snapshot["contexts"]))
    if snapshot.get("activity"):
        lines.append(f"Activity: {snapshot['activity']}")
    if snapshot.get("package"):
        lines.append(f"Package: {snapshot['package']}")
    lines.append(f"Interactive elements: {len(snapshot.get('interactive_elements', []))}")
    loading_indicators = snapshot.get("loading_indicators", [])
    if loading_indicators:
        lines.append(f"Loading indicators: {len(loading_indicators)}")
    else:
        lines.append("Loading indicators: none")
    if snapshot.get("parse_error"):
        lines.append(f"Screen analysis note: {snapshot['parse_error']}")
    if lines:
        lines.append("")

    lines.append("Screen text preview:")
    preview = snapshot["text_preview"][:10]
    if preview:
        for text in preview:
            lines.append(f"  - {text}")
    else:
        lines.append("  - none")

    lines.append("")
    interruptions = snapshot["interruptions"]
    if interruptions:
        lines.append(f"Possible interruptions ({len(interruptions)}):")
        for item in interruptions[:5]:
            lines.append(
                f"  - {item['category']}: {item['label']} ({item['action']})"
            )
    else:
        lines.append("Possible interruptions: none")
    return "\n".join(lines)


@tool
def appium_handle_common_interruptions(
    max_actions: int = 2,
    allow_permissions: bool = True,
) -> str:
    """Clears common transient mobile interruptions.

    Args:
        max_actions: Maximum number of interruptions to handle.
        allow_permissions: Whether permission-approval actions are allowed.

    Returns:
        Summary of handled interruptions or a no-op message.
    """
    al = _get_appium()
    max_actions = max(1, min(int(max_actions), 3))
    handled = []
    attempted = set()
    driver = al._current_application()

    while len(handled) < max_actions:
        snapshot = _get_mobile_snapshot_data(force_refresh=bool(handled))
        candidates = [
            item
            for item in snapshot["interruptions"]
            if allow_permissions or item["category"] != "permission"
        ]
        if not candidates:
            break

        clicked = False
        for candidate in candidates:
            locator = candidate["locator"]
            if locator in attempted:
                continue
            attempted.add(locator)
            try:
                al.click_element(locator)
                handled.append(
                    f"{candidate['category']} -> {candidate['label']}"
                )
                invalidate_mobile_snapshot_cache(driver)
                clicked = True
                break
            except Exception as exc:
                logger.debug(
                    "Failed to clear mobile interruption with %s (%s): %s",
                    locator,
                    candidate["label"],
                    exc,
                )
        if not clicked:
            break

    if not handled:
        return "No common interruptions detected on the current screen"
    count = len(handled)
    noun = "interruption" if count == 1 else "interruptions"
    return f"Handled {count} common {noun}: " + "; ".join(handled)


# ---------------------------------------------------------------------------
# Tool list export
# ---------------------------------------------------------------------------

MOBILE_TOOLS = instrument_tool_list([
    appium_open_application,
    appium_close_application,
    appium_close_all_applications,
    appium_background_app,
    appium_reset_application,
    appium_switch_context,
    appium_click_element,
    appium_input_text,
    appium_clear_text,
    appium_long_press,
    appium_swipe,
    appium_scroll_down,
    appium_scroll_up,
    appium_get_text,
    appium_get_element_attribute,
    appium_element_should_be_visible,
    appium_element_should_not_be_visible,
    appium_element_should_contain_text,
    appium_page_should_contain_text,
    appium_page_should_not_contain_text,
    appium_wait_until_element_is_visible,
    appium_wait_until_page_contains,
    appium_capture_page_screenshot,
    appium_handle_common_interruptions,
])
