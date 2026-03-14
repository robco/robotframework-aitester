# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Mobile tools — Strands @tool wrappers around AppiumLibrary keywords.

These tools provide the AI agent with mobile application testing capabilities
via robotframework-appiumlibrary.
"""

import logging
from strands import tool
from robot.libraries.BuiltIn import BuiltIn

logger = logging.getLogger(__name__)


def _get_appium():
    """Get the AppiumLibrary instance from Robot Framework."""
    return BuiltIn().get_library_instance("AppiumLibrary")


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
    al.close_application()
    return "Application closed"


@tool
def appium_close_all_applications() -> str:
    """Closes all open application sessions.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
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
    al.reset_application()
    return "Application reset"


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
    al.swipe(start_x, start_y, offset_x, offset_y, duration)
    return f"Swiped from ({start_x},{start_y}) by offset ({offset_x},{offset_y})"


@tool
def appium_scroll_down(locator: str = None) -> str:
    """Scrolls the screen downward.

    Args:
        locator: Optional element locator to scroll within.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    al.swipe(500, 1500, 500, 500, 800)
    return "Scrolled down"


@tool
def appium_scroll_up(locator: str = None) -> str:
    """Scrolls the screen upward.

    Args:
        locator: Optional element locator to scroll within.

    Returns:
        Confirmation message.
    """
    al = _get_appium()
    al.swipe(500, 500, 500, 1500, 800)
    return "Scrolled up"


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
        path = al.capture_page_screenshot(filename)
    else:
        path = al.capture_page_screenshot()
    return f"Screenshot captured: {path}"


# ---------------------------------------------------------------------------
# Screen analysis
# ---------------------------------------------------------------------------

@tool
def appium_get_source() -> str:
    """Gets the page/screen source XML of the current mobile view.

    Returns:
        The page source XML (may be truncated for very large screens).
    """
    al = _get_appium()
    source = al.get_source()
    if len(source) > 5000:
        return source[:5000] + "\n... [truncated]"
    return f"Page source:\n{source}"


# ---------------------------------------------------------------------------
# Tool list export
# ---------------------------------------------------------------------------

MOBILE_TOOLS = [
    appium_open_application,
    appium_close_application,
    appium_close_all_applications,
    appium_background_app,
    appium_reset_application,
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
    appium_get_source,
]
