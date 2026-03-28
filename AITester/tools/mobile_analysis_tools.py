# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Mobile analysis tools — structured Appium screen inspection helpers.

These tools provide the AI agent with richer state inspection for native and
hybrid mobile applications, similar to the browser analysis layer used for web.
"""

from collections import Counter

from strands import tool

from . import mobile_tools
from .common_tools import instrument_tool_list


def _format_interactive_elements(elements) -> str:
    if not elements:
        return "No interactive elements detected on the current screen"

    lines = [f"Found {len(elements)} interactive elements:"]
    for index, item in enumerate(elements[:25], start=1):
        parts = [f"{index}. {item['kind']}"]
        if item.get("label"):
            parts.append(f"label={item['label']}")
        if item.get("locator"):
            parts.append(f"locator={item['locator']}")
        if item.get("hint"):
            parts.append(f"hint={item['hint']}")
        if item.get("checked"):
            parts.append("checked=true")
        if item.get("selected"):
            parts.append("selected=true")
        if item.get("enabled") is False:
            parts.append("enabled=false")
        lines.append("  - " + ", ".join(parts))
    return "\n".join(lines)


def _format_context_kind(context_name: str) -> str:
    lowered = str(context_name or "").lower()
    if lowered.startswith("native"):
        return "native"
    if "webview" in lowered or "chromium" in lowered or "browser" in lowered:
        return "webview"
    return "custom"


@tool
def appium_get_loading_state(refresh: bool = False) -> str:
    """Reports whether the current mobile screen still appears busy."""
    snapshot = mobile_tools._get_mobile_snapshot_data(force_refresh=bool(refresh))
    indicators = snapshot.get("loading_indicators", [])
    if not indicators:
        return "Loading state: ready; indicators=none"

    lines = [f"Loading state: busy; indicators={len(indicators)}"]
    for item in indicators[:5]:
        detail = item.get("kind", "loading")
        label = item.get("label")
        locator = item.get("locator")
        if label:
            detail += f' label="{label[:60]}"'
        if locator:
            detail += f" locator={locator}"
        lines.append("  - " + detail)
    return "\n".join(lines)


@tool
def appium_get_interactive_elements(refresh: bool = False) -> str:
    """Lists structured interactive elements detected on the current screen."""
    snapshot = mobile_tools._get_mobile_snapshot_data(force_refresh=bool(refresh))
    return _format_interactive_elements(snapshot.get("interactive_elements", []))


@tool
def appium_get_screen_structure(refresh: bool = False) -> str:
    """Summarizes the current mobile screen layout and important controls."""
    snapshot = mobile_tools._get_mobile_snapshot_data(force_refresh=bool(refresh))
    elements = snapshot.get("interactive_elements", [])
    counts = Counter(item.get("kind", "interactive") for item in elements)

    lines = [
        "Current mobile screen structure:",
        f"Interactive elements: {len(elements)}",
        f"Input fields: {counts.get('input', 0) + counts.get('password', 0)}",
        f"Buttons: {counts.get('button', 0)}",
        f"Tabs: {counts.get('tab', 0)}",
        f"Switches / checkboxes: {counts.get('switch', 0) + counts.get('checkbox', 0)}",
        f"Pickers: {counts.get('picker', 0)}",
        f"Scrollable containers: {counts.get('scrollable', 0)}",
        f"Loading indicators: {len(snapshot.get('loading_indicators', []))}",
        f"Possible interruptions: {len(snapshot.get('interruptions', []))}",
    ]

    contexts = snapshot.get("contexts", [])
    if contexts:
        lines.append("Contexts: " + ", ".join(contexts))

    if elements:
        lines.append("")
        lines.append("Primary controls:")
        for item in elements[:10]:
            label = item.get("label") or "(no label)"
            locator = item.get("locator") or "(no locator)"
            lines.append(f"  - {item['kind']}: {label} [{locator}]")
    return "\n".join(lines)


@tool
def appium_get_context_inventory(refresh: bool = False) -> str:
    """Lists the currently available Appium contexts for hybrid apps."""
    snapshot = mobile_tools._get_mobile_snapshot_data(force_refresh=bool(refresh))
    current_context = snapshot.get("context") or "unknown"
    contexts = list(snapshot.get("contexts", []))
    if current_context != "unknown" and current_context not in contexts:
        contexts.insert(0, current_context)

    lines = [f"Current context: {current_context}"]
    if not contexts:
        lines.append("Available contexts: none reported by driver")
        return "\n".join(lines)

    lines.append(f"Available contexts ({len(contexts)}):")
    for context_name in contexts:
        suffix = " [current]" if context_name == current_context else ""
        lines.append(
            f"  - {context_name} ({_format_context_kind(context_name)}){suffix}"
        )
    return "\n".join(lines)


MOBILE_ANALYSIS_TOOLS = instrument_tool_list([
    mobile_tools.appium_get_source,
    mobile_tools.appium_get_view_snapshot,
    appium_get_loading_state,
    appium_get_interactive_elements,
    appium_get_screen_structure,
    appium_get_context_inventory,
])
