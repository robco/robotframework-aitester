# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Browser analysis tools — Specialized tools for understanding page state.

These tools help the AI agent understand the current state of a web page
by parsing the DOM and extracting structured information about interactive
elements, page structure, and visible content.
"""

import json
import logging
from strands import tool
from robot.libraries.BuiltIn import BuiltIn

logger = logging.getLogger(__name__)


def _get_selenium():
    """Get the SeleniumLibrary instance from Robot Framework."""
    return BuiltIn().get_library_instance("SeleniumLibrary")


@tool
def get_interactive_elements() -> str:
    """Extracts all interactive elements from the current page.

    Finds buttons, links, inputs, selects, textareas, and elements
    with click handlers. Returns structured data the agent can use
    to decide what to interact with.

    Returns:
        JSON-formatted list of interactive elements with their locators,
        types, text, and attributes.
    """
    sl = _get_selenium()
    driver = sl.driver

    js_code = """
    function getInteractiveElements() {
        const selectors = [
            'a[href]',
            'button',
            'input',
            'select',
            'textarea',
            '[role="button"]',
            '[role="link"]',
            '[role="tab"]',
            '[role="menuitem"]',
            '[onclick]',
            '[tabindex]',
        ];

        const elements = [];
        const seen = new Set();

        selectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (seen.has(el)) return;
                seen.add(el);

                const rect = el.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0 &&
                                  window.getComputedStyle(el).display !== 'none' &&
                                  window.getComputedStyle(el).visibility !== 'hidden';

                if (!isVisible) return;

                const info = {
                    tag: el.tagName.toLowerCase(),
                    type: el.type || null,
                    id: el.id || null,
                    name: el.name || null,
                    text: (el.textContent || '').trim().substring(0, 100),
                    value: el.value || null,
                    placeholder: el.placeholder || null,
                    href: el.href || null,
                    'aria-label': el.getAttribute('aria-label'),
                    'data-testid': el.getAttribute('data-testid'),
                    role: el.getAttribute('role'),
                    disabled: el.disabled || false,
                    class: el.className ? el.className.substring(0, 80) : null,
                };

                // Build best locator
                if (info.id) {
                    info.locator = 'id=' + info.id;
                } else if (info['data-testid']) {
                    info.locator = 'css=[data-testid="' + info['data-testid'] + '"]';
                } else if (info.name) {
                    info.locator = 'name=' + info.name;
                } else if (info['aria-label']) {
                    info.locator = 'css=[aria-label="' + info['aria-label'] + '"]';
                }

                elements.push(info);
            });
        });

        return elements.slice(0, 100);  // Limit to prevent huge outputs
    }
    return JSON.stringify(getInteractiveElements());
    """

    result = driver.execute_script(js_code)
    try:
        elements = json.loads(result)
        summary_lines = [f"Found {len(elements)} interactive elements:"]
        for i, el in enumerate(elements, 1):
            locator = el.get("locator", "no-locator")
            tag = el.get("tag", "?")
            text = el.get("text", "")[:50]
            el_type = el.get("type", "")
            desc = f"  {i}. <{tag}"
            if el_type:
                desc += f" type={el_type}"
            desc += f"> locator={locator}"
            if text:
                desc += f' text="{text}"'
            summary_lines.append(desc)
        return "\n".join(summary_lines)
    except (json.JSONDecodeError, TypeError):
        return f"Raw interactive elements: {result}"


@tool
def get_page_structure() -> str:
    """Gets a high-level structural overview of the current page.

    Returns headings, main landmarks, forms, and navigation elements
    to help the agent understand page layout.

    Returns:
        Structured overview of the page.
    """
    sl = _get_selenium()
    driver = sl.driver

    js_code = """
    function getPageStructure() {
        const structure = {
            title: document.title,
            url: window.location.href,
            headings: [],
            forms: [],
            nav_items: [],
            main_sections: [],
        };

        // Headings
        document.querySelectorAll('h1, h2, h3').forEach(h => {
            const text = (h.textContent || '').trim().substring(0, 100);
            if (text) structure.headings.push({level: h.tagName, text: text});
        });

        // Forms
        document.querySelectorAll('form').forEach((f, i) => {
            const inputs = f.querySelectorAll('input, select, textarea');
            structure.forms.push({
                index: i,
                id: f.id || null,
                action: f.action || null,
                method: f.method || 'get',
                fields: inputs.length,
            });
        });

        // Navigation
        document.querySelectorAll('nav a, [role="navigation"] a').forEach(a => {
            const text = (a.textContent || '').trim().substring(0, 50);
            if (text) structure.nav_items.push({text: text, href: a.href});
        });

        // Main content areas
        document.querySelectorAll('main, [role="main"], article, section').forEach(s => {
            const text = (s.textContent || '').trim().substring(0, 200);
            structure.main_sections.push({
                tag: s.tagName.toLowerCase(),
                id: s.id || null,
                role: s.getAttribute('role'),
                preview: text.substring(0, 100),
            });
        });

        return structure;
    }
    return JSON.stringify(getPageStructure());
    """

    result = driver.execute_script(js_code)
    try:
        structure = json.loads(result)
        lines = [
            f"Page: {structure.get('title', 'Untitled')}",
            f"URL: {structure.get('url', 'unknown')}",
            "",
            f"Headings ({len(structure.get('headings', []))}):",
        ]
        for h in structure.get("headings", []):
            lines.append(f"  {h['level']}: {h['text']}")
        lines.append(f"\nForms ({len(structure.get('forms', []))}):")
        for f in structure.get("forms", []):
            lines.append(f"  Form #{f['index']}: id={f['id']}, method={f['method']}, fields={f['fields']}")
        lines.append(f"\nNavigation ({len(structure.get('nav_items', []))}):")
        for n in structure.get("nav_items", [])[:20]:
            lines.append(f"  {n['text']} → {n['href']}")
        return "\n".join(lines)
    except (json.JSONDecodeError, TypeError):
        return f"Raw page structure: {result}"


@tool
def get_page_text_content() -> str:
    """Gets the visible text content of the current page.

    Returns:
        The visible text content (truncated for large pages).
    """
    sl = _get_selenium()
    driver = sl.driver

    js_code = """
    return document.body ? document.body.innerText.substring(0, 5000) : '';
    """
    text = driver.execute_script(js_code)
    if text and len(text) > 5000:
        text = text[:5000] + "\n... [truncated]"
    return f"Page text content:\n{text}"


@tool
def get_element_count(locator: str) -> str:
    """Counts the number of elements matching a locator.

    Args:
        locator: CSS selector or XPath to count.

    Returns:
        The count of matching elements.
    """
    sl = _get_selenium()
    count = sl.get_element_count(locator)
    return f"Found {count} elements matching: {locator}"


@tool
def get_all_links() -> str:
    """Gets all links on the current page with their text and URLs.

    Returns:
        List of links with their text and href attributes.
    """
    sl = _get_selenium()
    driver = sl.driver

    js_code = """
    const links = [];
    document.querySelectorAll('a[href]').forEach(a => {
        const text = (a.textContent || '').trim().substring(0, 80);
        if (text && a.href) {
            links.push({text: text, href: a.href});
        }
    });
    return JSON.stringify(links.slice(0, 50));
    """
    result = driver.execute_script(js_code)
    try:
        links = json.loads(result)
        lines = [f"Found {len(links)} links:"]
        for i, link in enumerate(links, 1):
            lines.append(f"  {i}. [{link['text']}] → {link['href']}")
        return "\n".join(lines)
    except (json.JSONDecodeError, TypeError):
        return f"Raw links data: {result}"


@tool
def get_form_fields(form_locator: str = "css=form") -> str:
    """Gets all input fields within a form element.

    Args:
        form_locator: Locator for the form element (defaults to first form).

    Returns:
        List of form fields with their types, names, and attributes.
    """
    sl = _get_selenium()
    driver = sl.driver

    # Convert RF locator to CSS if needed
    css = form_locator
    if form_locator.startswith("css="):
        css = form_locator[4:]
    elif form_locator.startswith("id="):
        css = f"#{form_locator[3:]}"

    js_code = f"""
    const form = document.querySelector('{css}');
    if (!form) return JSON.stringify([]);
    const fields = [];
    form.querySelectorAll('input, select, textarea, button').forEach(el => {{
        fields.push({{
            tag: el.tagName.toLowerCase(),
            type: el.type || null,
            name: el.name || null,
            id: el.id || null,
            placeholder: el.placeholder || null,
            required: el.required || false,
            value: el.value || null,
            label: el.labels && el.labels.length > 0 ? el.labels[0].textContent.trim() : null,
        }});
    }});
    return JSON.stringify(fields);
    """

    result = driver.execute_script(js_code)
    try:
        fields = json.loads(result)
        lines = [f"Form fields ({len(fields)}):"]
        for f in fields:
            name = f.get("name") or f.get("id") or "unnamed"
            ftype = f.get("type") or f.get("tag")
            label = f.get("label") or f.get("placeholder") or ""
            req = " [REQUIRED]" if f.get("required") else ""
            lines.append(f"  - {name} ({ftype}){req}: {label}")
        return "\n".join(lines)
    except (json.JSONDecodeError, TypeError):
        return f"Raw form fields: {result}"


@tool
def check_page_errors() -> str:
    """Checks for JavaScript console errors and failed network requests.

    Returns:
        List of errors found or 'No errors detected'.
    """
    sl = _get_selenium()
    driver = sl.driver

    try:
        logs = driver.get_log("browser")
        errors = [log for log in logs if log.get("level") in ("SEVERE", "ERROR")]
        if errors:
            lines = [f"Found {len(errors)} browser errors:"]
            for err in errors[:20]:
                lines.append(f"  [{err.get('level')}] {err.get('message', '')[:200]}")
            return "\n".join(lines)
        return "No browser console errors detected"
    except Exception:
        return "Unable to retrieve browser console logs (may not be supported by the driver)"


# ---------------------------------------------------------------------------
# Tool list export
# ---------------------------------------------------------------------------

BROWSER_ANALYSIS_TOOLS = [
    get_interactive_elements,
    get_page_structure,
    get_page_text_content,
    get_element_count,
    get_all_links,
    get_form_fields,
    check_page_errors,
]
