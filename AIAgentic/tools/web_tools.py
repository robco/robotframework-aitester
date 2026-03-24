# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Web tools — Strands @tool wrappers around SeleniumLibrary keywords.

These tools provide the AI agent with full browser automation capabilities
via SeleniumLibrary's battle-tested Selenium/WebDriver integration.
"""

import logging
from urllib.parse import urlsplit, urlunsplit
from strands import tool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .common_tools import instrument_tool_list, _normalize_screenshot_filename
from .browser_analysis_tools import (
    _get_page_snapshot_data,
    invalidate_page_snapshot_cache,
)
from ..executor import get_active_session

logger = logging.getLogger(__name__)


def _get_selenium():
    """Get the SeleniumLibrary instance from Robot Framework."""
    bi = BuiltIn()
    lib_name = "SeleniumLibrary"
    try:
        override = bi.get_variable_value("${AIAGENTIC_SELENIUM_LIBRARY}")
        if override:
            lib_name = override
    except RobotNotRunningError:
        pass
    try:
        return bi.get_library_instance(lib_name)
    except Exception as exc:
        raise RuntimeError(
            f"SeleniumLibrary instance '{lib_name}' not found. "
            "Ensure SeleniumLibrary is imported or set selenium_library "
            "when importing AIAgentic."
        ) from exc


def _should_scroll_into_view() -> bool:
    session = get_active_session()
    if not session:
        return True
    return bool(session.scroll_into_view)


def _maybe_scroll_into_view(sl, locator: str) -> None:
    if not locator or not _should_scroll_into_view():
        return
    try:
        sl.scroll_element_into_view(locator)
    except Exception as exc:
        logger.debug("Unable to scroll element into view (%s): %s", locator, exc)


def _collect_blocker_actions(snapshot) -> list[dict]:
    actions = []
    for blocker in snapshot.get("possible_blockers", []):
        category = blocker.get("category", "unknown")
        preview = blocker.get("preview", "")
        for action in blocker.get("actions", []):
            locator = action.get("locator")
            if not locator:
                continue
            actions.append(
                {
                    "category": category,
                    "preview": preview,
                    "label": action.get("label", locator),
                    "locator": locator,
                    "kind": action.get("kind", "other"),
                    "score": int(action.get("score", 0)),
                }
            )

    def _priority(item: dict) -> tuple[int, int]:
        if item["category"] == "cookie/consent":
            label = str(item["label"]).lower()
            if item["kind"] in {"accept", "allow"}:
                return (3, item["score"])
            if any(token in label for token in ("accept", "agree", "allow")):
                return (2, item["score"])
        return (1, item["score"])

    actions.sort(key=_priority, reverse=True)
    return actions


def _has_active_browser_start_state(session) -> bool:
    if not session or not session.start_state_summary:
        return False
    summary = str(session.start_state_summary).lower()
    return (
        "active browser session detected" in summary
        and "no active browser session detected" not in summary
    )


def _normalize_url(url: str) -> str:
    parts = urlsplit(str(url).strip())
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def _is_explicit_user_url(url: str) -> bool:
    session = get_active_session()
    if not session or not session.allowed_direct_urls:
        return False
    normalized = _normalize_url(url)
    return any(_normalize_url(candidate) == normalized for candidate in session.allowed_direct_urls)


def _assert_direct_url_navigation_allowed(action_name: str, url: str) -> None:
    session = get_active_session()
    if not session or session.test_mode != "web":
        return

    if _is_explicit_user_url(url):
        return

    if _has_active_browser_start_state(session):
        raise AssertionError(
            f"Direct URL navigation via {action_name} is not allowed when the run "
            "starts with an active browser session. Continue from the current page "
            "and navigate like a real user by clicking visible links, buttons, "
            f"menus, or tabs instead of jumping to '{url}'."
        )

    if session.direct_url_navigations_used > 0 or session.ui_interactions_total > 0:
        raise AssertionError(
            f"Direct URL navigation via {action_name} is blocked by default after "
            "the flow has started. Navigate like a real user by clicking visible "
            "controls instead of jumping directly to "
            f"'{url}', unless the user explicitly requested that exact URL."
        )


def _record_direct_url_navigation() -> None:
    session = get_active_session()
    if not session or session.test_mode != "web":
        return
    session.direct_url_navigations_used += 1


def _assert_browser_termination_allowed(action_name: str, sl=None) -> None:
    session = get_active_session()
    if not session or session.test_mode != "web":
        return
    if getattr(session, "allow_browser_termination", False):
        return
    sl = sl or _get_selenium()
    try:
        browser_ids = sl.get_browser_ids()
    except Exception as exc:
        logger.debug("Unable to detect open browser windows for %s: %s", action_name, exc)
        browser_ids = []
    if not browser_ids:
        return
    raise AssertionError(
        f"{action_name} is blocked while a browser session is open. Preserve the "
        "current browser to avoid losing login state and pre-set test "
        "environment. Close or restart the browser only when the user "
        "explicitly requests it."
    )


# ---------------------------------------------------------------------------
# Browser control
# ---------------------------------------------------------------------------

@tool
def selenium_open_browser(url: str, browser: str = "chrome") -> str:
    """Opens a browser and navigates to the specified URL.

    Args:
        url: The URL to navigate to.
        browser: Browser type (chrome, firefox, edge). Defaults to chrome.

    Returns:
        Confirmation message with the navigated URL.
    """
    sl = _get_selenium()
    session = get_active_session()
    reuse_only = bool(session and session.reuse_existing_session)
    if reuse_only and session.start_state_summary:
        summary = session.start_state_summary.lower()
        if (
            "active mobile session detected" in summary
            and "active browser session detected" not in summary
        ):
            raise AssertionError(
                "Active mobile session detected. Refusing to open a new desktop "
                "browser session. Reuse the existing mobile session."
            )
    try:
        existing_browser_ids = sl.get_browser_ids()
    except Exception as exc:
        existing_browser_ids = []
        logger.debug("Unable to detect existing browser session: %s", exc)
    if existing_browser_ids:
        _assert_direct_url_navigation_allowed("selenium_open_browser", url)
        sl.go_to(url)
        _record_direct_url_navigation()
        return f"Browser already open; navigated to {url}"
    if reuse_only:
        raise AssertionError(
            "Reuse of an existing browser session is required, but no active "
            "browser session was detected. Refusing to open a new browser. "
            "Ensure SeleniumLibrary is attached to the existing session (use "
            "the selenium_library alias if needed)."
        )
    _assert_direct_url_navigation_allowed("selenium_open_browser", url)
    sl.open_browser(url, browser)
    _record_direct_url_navigation()
    return f"Browser opened and navigated to {url}"


@tool
def selenium_close_browser() -> str:
    """Closes the current browser window.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _assert_browser_termination_allowed("selenium_close_browser", sl)
    sl.close_browser()
    return "Browser closed"


@tool
def selenium_close_all_browsers() -> str:
    """Closes all open browser windows.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _assert_browser_termination_allowed("selenium_close_all_browsers", sl)
    sl.close_all_browsers()
    return "All browsers closed"


@tool
def selenium_go_to(url: str) -> str:
    """Navigates the current browser to the specified URL.

    Args:
        url: The URL to navigate to.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _assert_direct_url_navigation_allowed("selenium_go_to", url)
    sl.go_to(url)
    _record_direct_url_navigation()
    return f"Navigated to {url}"


@tool
def selenium_go_back() -> str:
    """Navigates the browser back to the previous page.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    sl.go_back()
    return "Navigated back to previous page"


@tool
def selenium_reload_page() -> str:
    """Reloads the current page.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    sl.reload_page()
    return "Page reloaded"


# ---------------------------------------------------------------------------
# Element interaction
# ---------------------------------------------------------------------------

@tool
def selenium_click_element(locator: str) -> str:
    """Clicks on a web element identified by the locator.

    Args:
        locator: Element locator (e.g., id=login-btn, css=.submit, xpath=//button).

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.click_element(locator)
    return f"Clicked element: {locator}"


@tool
def selenium_click_button(locator: str) -> str:
    """Clicks a button element identified by the locator.

    Args:
        locator: Button locator (id, name, value, or xpath).

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.click_button(locator)
    return f"Clicked button: {locator}"


@tool
def selenium_click_link(locator: str) -> str:
    """Clicks a link identified by the locator, id, or href.

    Args:
        locator: Link text, partial link text, id, or href.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.click_link(locator)
    return f"Clicked link: {locator}"


@tool
def selenium_input_text(locator: str, text: str) -> str:
    """Types text into an input field identified by the locator.

    Args:
        locator: Element locator for the input field.
        text: The text to type.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.input_text(locator, text)
    return f"Typed '{text}' into element: {locator}"


@tool
def selenium_input_password(locator: str, password: str) -> str:
    """Types a password into an input field (masked in logs).

    Args:
        locator: Element locator for the password field.
        password: The password to type.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.input_password(locator, password)
    return f"Typed password into element: {locator}"


@tool
def selenium_clear_element_text(locator: str) -> str:
    """Clears the text content of an input field.

    Args:
        locator: Element locator for the input field.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.clear_element_text(locator)
    return f"Cleared text in element: {locator}"


@tool
def selenium_select_from_list_by_label(locator: str, label: str) -> str:
    """Selects an option from a dropdown by its visible label text.

    Args:
        locator: Element locator for the select/dropdown element.
        label: The visible text of the option to select.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.select_from_list_by_label(locator, label)
    return f"Selected '{label}' from dropdown: {locator}"


@tool
def selenium_select_from_list_by_value(locator: str, value: str) -> str:
    """Selects an option from a dropdown by its value attribute.

    Args:
        locator: Element locator for the select/dropdown element.
        value: The value attribute of the option to select.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.select_from_list_by_value(locator, value)
    return f"Selected value '{value}' from dropdown: {locator}"


@tool
def selenium_select_checkbox(locator: str) -> str:
    """Selects (checks) a checkbox element.

    Args:
        locator: Element locator for the checkbox.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.select_checkbox(locator)
    return f"Selected checkbox: {locator}"


@tool
def selenium_unselect_checkbox(locator: str) -> str:
    """Unselects (unchecks) a checkbox element.

    Args:
        locator: Element locator for the checkbox.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.unselect_checkbox(locator)
    return f"Unselected checkbox: {locator}"


@tool
def selenium_mouse_over(locator: str) -> str:
    """Moves the mouse pointer over an element (hover).

    Args:
        locator: Element locator to hover over.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    _maybe_scroll_into_view(sl, locator)
    sl.mouse_over(locator)
    return f"Hovered over element: {locator}"


@tool
def selenium_press_keys(locator: str, *keys: str) -> str:
    """Sends keyboard keys to an element or the page.

    Args:
        locator: Element locator (use None/NONE for page-level keys).
        keys: One or more key names (e.g., ENTER, TAB, ESCAPE, CTRL+A).

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    target = None
    if locator is not None and str(locator).upper() != "NONE":
        target = locator
    _maybe_scroll_into_view(sl, target)
    sl.press_keys(target, *keys)
    return f"Pressed keys {keys} on: {locator}"


@tool
def selenium_scroll_element_into_view(locator: str) -> str:
    """Scrolls the page so the element is visible in the viewport.

    Args:
        locator: Element locator to scroll into view.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    sl.scroll_element_into_view(locator)
    return f"Scrolled element into view: {locator}"


@tool
def selenium_handle_common_blockers(max_actions: int = 2) -> str:
    """Dismisses common blocking UI overlays on the current page.

    This is intended for transient UI interruptions such as cookie banners,
    consent dialogs, newsletter popups, and tutorial overlays that prevent
    the requested action from continuing.

    Args:
        max_actions: Maximum number of blocker actions to perform.

    Returns:
        Summary of handled blockers or a no-op message.
    """
    sl = _get_selenium()
    max_actions = max(1, min(int(max_actions), 3))
    handled = []
    attempted = set()

    while len(handled) < max_actions:
        snapshot = _get_page_snapshot_data(force_refresh=bool(handled))
        candidates = _collect_blocker_actions(snapshot)
        if not candidates:
            break

        clicked = False
        for candidate in candidates:
            locator = candidate["locator"]
            if locator in attempted:
                continue
            attempted.add(locator)
            try:
                _maybe_scroll_into_view(sl, locator)
                sl.click_element(locator)
                handled.append(
                    f"{candidate['category']} -> {candidate['label']}"
                )
                invalidate_page_snapshot_cache(sl.driver)
                clicked = True
                break
            except Exception as exc:
                logger.debug(
                    "Failed to clear blocker with %s (%s): %s",
                    locator,
                    candidate["label"],
                    exc,
                )
        if not clicked:
            break

    if not handled:
        return "No common blockers detected on the page"
    count = len(handled)
    noun = "blocker" if count == 1 else "blockers"
    return f"Handled {count} common {noun}: " + "; ".join(handled)


# ---------------------------------------------------------------------------
# Element state queries
# ---------------------------------------------------------------------------

@tool
def selenium_get_text(locator: str) -> str:
    """Gets the visible text of an element.

    Args:
        locator: Element locator.

    Returns:
        The visible text content of the element.
    """
    sl = _get_selenium()
    text = sl.get_text(locator)
    return f"Text content: {text}"


@tool
def selenium_get_element_attribute(locator: str, attribute: str) -> str:
    """Gets the value of an element's attribute.

    Args:
        locator: Element locator.
        attribute: Name of the attribute to retrieve.

    Returns:
        The attribute value.
    """
    sl = _get_selenium()
    value = sl.get_element_attribute(locator, attribute)
    return f"Attribute '{attribute}' of {locator}: {value}"


@tool
def selenium_get_value(locator: str) -> str:
    """Gets the value attribute of an input element.

    Args:
        locator: Element locator for the input field.

    Returns:
        The input value.
    """
    sl = _get_selenium()
    value = sl.get_value(locator)
    return f"Value of {locator}: {value}"


@tool
def selenium_element_should_be_visible(locator: str) -> str:
    """Asserts that an element is visible on the page.

    Args:
        locator: Element locator.

    Returns:
        PASS if visible, raises error if not.
    """
    sl = _get_selenium()
    sl.element_should_be_visible(locator)
    return f"PASS: Element is visible: {locator}"


@tool
def selenium_element_should_not_be_visible(locator: str) -> str:
    """Asserts that an element is NOT visible on the page.

    Args:
        locator: Element locator.

    Returns:
        PASS if not visible, raises error if visible.
    """
    sl = _get_selenium()
    sl.element_should_not_be_visible(locator)
    return f"PASS: Element is not visible: {locator}"


@tool
def selenium_element_should_contain(locator: str, expected: str) -> str:
    """Asserts that an element's text contains the expected substring.

    Args:
        locator: Element locator.
        expected: Expected text substring.

    Returns:
        PASS with actual text, or raises assertion error.
    """
    sl = _get_selenium()
    sl.element_should_contain(locator, expected)
    return f"PASS: Element {locator} contains '{expected}'"


@tool
def selenium_element_text_should_be(locator: str, expected: str) -> str:
    """Asserts that an element's text exactly matches the expected value.

    Args:
        locator: Element locator.
        expected: Expected exact text.

    Returns:
        PASS with actual text, or raises assertion error.
    """
    sl = _get_selenium()
    sl.element_text_should_be(locator, expected)
    return f"PASS: Element {locator} text is '{expected}'"


@tool
def selenium_page_should_contain(text: str) -> str:
    """Asserts that the page contains the specified text.

    Args:
        text: Expected text to find on the page.

    Returns:
        PASS if found, raises error if not.
    """
    sl = _get_selenium()
    sl.page_should_contain(text)
    return f"PASS: Page contains '{text}'"


@tool
def selenium_page_should_not_contain(text: str) -> str:
    """Asserts that the page does NOT contain the specified text.

    Args:
        text: Text that should not be present.

    Returns:
        PASS if not found, raises error if found.
    """
    sl = _get_selenium()
    sl.page_should_not_contain(text)
    return f"PASS: Page does not contain '{text}'"


@tool
def selenium_title_should_be(expected_title: str) -> str:
    """Asserts that the page title matches the expected value.

    Args:
        expected_title: Expected page title.

    Returns:
        PASS with title, or raises assertion error.
    """
    sl = _get_selenium()
    sl.title_should_be(expected_title)
    return f"PASS: Page title is '{expected_title}'"


@tool
def selenium_get_location() -> str:
    """Gets the current browser URL.

    Returns:
        The current URL.
    """
    sl = _get_selenium()
    url = sl.get_location()
    return f"Current URL: {url}"


@tool
def selenium_location_should_be(expected_url: str) -> str:
    """Asserts that the current URL matches the expected value.

    Args:
        expected_url: Expected URL.

    Returns:
        PASS with URL, or raises assertion error.
    """
    sl = _get_selenium()
    sl.location_should_be(expected_url)
    return f"PASS: Current URL is '{expected_url}'"


@tool
def selenium_location_should_contain(expected: str) -> str:
    """Asserts that the current URL contains the expected substring.

    Args:
        expected: Expected URL substring.

    Returns:
        PASS with URL, or raises assertion error.
    """
    sl = _get_selenium()
    sl.location_should_contain(expected)
    return f"PASS: Current URL contains '{expected}'"


# ---------------------------------------------------------------------------
# Wait keywords
# ---------------------------------------------------------------------------

@tool
def selenium_wait_until_element_is_visible(locator: str, timeout: str = "10s") -> str:
    """Waits until an element becomes visible on the page.

    Args:
        locator: Element locator to wait for.
        timeout: Maximum time to wait (e.g., '10s', '30s').

    Returns:
        Confirmation when element becomes visible.
    """
    sl = _get_selenium()
    sl.wait_until_element_is_visible(locator, timeout)
    return f"Element is now visible: {locator}"


@tool
def selenium_wait_until_element_is_enabled(locator: str, timeout: str = "10s") -> str:
    """Waits until an element becomes enabled (clickable).

    Args:
        locator: Element locator to wait for.
        timeout: Maximum time to wait.

    Returns:
        Confirmation when element becomes enabled.
    """
    sl = _get_selenium()
    sl.wait_until_element_is_enabled(locator, timeout)
    return f"Element is now enabled: {locator}"


@tool
def selenium_wait_until_page_contains(text: str, timeout: str = "10s") -> str:
    """Waits until the page contains the specified text.

    Args:
        text: Text to wait for.
        timeout: Maximum time to wait.

    Returns:
        Confirmation when text appears.
    """
    sl = _get_selenium()
    sl.wait_until_page_contains(text, timeout)
    return f"Page now contains: '{text}'"


@tool
def selenium_wait_until_page_contains_element(locator: str, timeout: str = "10s") -> str:
    """Waits until the page contains the specified element.

    Args:
        locator: Element locator to wait for.
        timeout: Maximum time to wait.

    Returns:
        Confirmation when element appears.
    """
    sl = _get_selenium()
    sl.wait_until_page_contains_element(locator, timeout)
    return f"Page now contains element: {locator}"


# ---------------------------------------------------------------------------
# Screenshots
# ---------------------------------------------------------------------------

@tool
def selenium_capture_page_screenshot(filename: str = None) -> str:
    """Captures a screenshot of the current page.

    Args:
        filename: Optional filename for the screenshot. Auto-generated if not provided.

    Returns:
        Path to the saved screenshot file.
    """
    sl = _get_selenium()
    if filename:
        normalized = _normalize_screenshot_filename(filename)
        if normalized != filename:
            logger.debug(
                "Normalized screenshot filename to .png to avoid WebDriver warnings: %s",
                normalized,
            )
        path = sl.capture_page_screenshot(normalized)
    else:
        path = sl.capture_page_screenshot()
    return f"Screenshot captured: {path}"


# ---------------------------------------------------------------------------
# JavaScript execution
# ---------------------------------------------------------------------------

@tool
def selenium_execute_javascript(code: str) -> str:
    """Executes JavaScript code in the current browser context.

    Args:
        code: JavaScript code to execute.

    Returns:
        Result of the JavaScript execution.
    """
    sl = _get_selenium()
    result = sl.execute_javascript(code)
    return f"JavaScript result: {result}"


# ---------------------------------------------------------------------------
# Frame / window management
# ---------------------------------------------------------------------------

@tool
def selenium_switch_window(locator: str = "MAIN") -> str:
    """Switches to a different browser window or tab.

    Args:
        locator: Window title, handle, or 'MAIN' for the main window.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    sl.switch_window(locator)
    return f"Switched to window: {locator}"


@tool
def selenium_select_frame(locator: str) -> str:
    """Switches focus to an iframe or frame.

    Args:
        locator: Frame locator (name, id, index, or element locator).

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    sl.select_frame(locator)
    return f"Switched to frame: {locator}"


@tool
def selenium_unselect_frame() -> str:
    """Switches focus back from an iframe to the main page.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    sl.unselect_frame()
    return "Switched back to main frame"


# ---------------------------------------------------------------------------
# Tool list export
# ---------------------------------------------------------------------------

WEB_TOOLS = instrument_tool_list([
    selenium_open_browser,
    selenium_close_browser,
    selenium_close_all_browsers,
    selenium_go_to,
    selenium_go_back,
    selenium_reload_page,
    selenium_click_element,
    selenium_click_button,
    selenium_click_link,
    selenium_input_text,
    selenium_input_password,
    selenium_clear_element_text,
    selenium_select_from_list_by_label,
    selenium_select_from_list_by_value,
    selenium_select_checkbox,
    selenium_unselect_checkbox,
    selenium_mouse_over,
    selenium_press_keys,
    selenium_scroll_element_into_view,
    selenium_handle_common_blockers,
    selenium_get_text,
    selenium_get_element_attribute,
    selenium_get_value,
    selenium_element_should_be_visible,
    selenium_element_should_not_be_visible,
    selenium_element_should_contain,
    selenium_element_text_should_be,
    selenium_page_should_contain,
    selenium_page_should_not_contain,
    selenium_title_should_be,
    selenium_get_location,
    selenium_location_should_be,
    selenium_location_should_contain,
    selenium_wait_until_element_is_visible,
    selenium_wait_until_element_is_enabled,
    selenium_wait_until_page_contains,
    selenium_wait_until_page_contains_element,
    selenium_capture_page_screenshot,
    selenium_execute_javascript,
    selenium_switch_window,
    selenium_select_frame,
    selenium_unselect_frame,
])
