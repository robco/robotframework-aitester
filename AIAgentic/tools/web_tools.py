# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Web tools — Strands @tool wrappers around SeleniumLibrary keywords.

These tools provide the AI agent with full browser automation capabilities
via SeleniumLibrary's battle-tested Selenium/WebDriver integration.
"""

import logging
from strands import tool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .common_tools import instrument_tool_list
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
        if sl.get_browser_ids():
            sl.go_to(url)
            return f"Browser already open; navigated to {url}"
    except Exception as e:
        logger.debug("Unable to detect existing browser session: %s", e)
    if reuse_only:
        raise AssertionError(
            "Reuse of an existing browser session is required, but no active "
            "browser session was detected. Refusing to open a new browser. "
            "Ensure SeleniumLibrary is attached to the existing session (use "
            "the selenium_library alias if needed)."
        )
    sl.open_browser(url, browser)
    return f"Browser opened and navigated to {url}"


@tool
def selenium_close_browser() -> str:
    """Closes the current browser window.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
    sl.close_browser()
    return "Browser closed"


@tool
def selenium_close_all_browsers() -> str:
    """Closes all open browser windows.

    Returns:
        Confirmation message.
    """
    sl = _get_selenium()
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
    sl.go_to(url)
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
    target = None if locator.upper() == "NONE" else locator
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
        path = sl.capture_page_screenshot(filename)
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
