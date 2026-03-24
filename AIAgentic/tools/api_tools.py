# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
API tools — Strands @tool wrappers around RequestsLibrary keywords.

These tools provide the AI agent with REST API testing capabilities
via robotframework-requests (RequestsLibrary).
"""

import json
import logging
from strands import tool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .common_tools import instrument_tool_list

logger = logging.getLogger(__name__)


def _get_requests():
    """Get the RequestsLibrary instance from Robot Framework."""
    bi = BuiltIn()
    lib_name = "RequestsLibrary"
    try:
        override = bi.get_variable_value("${AIAGENTIC_REQUESTS_LIBRARY}")
        if override:
            lib_name = override
    except RobotNotRunningError:
        pass
    try:
        return bi.get_library_instance(lib_name)
    except Exception as exc:
        raise RuntimeError(
            f"RequestsLibrary instance '{lib_name}' not found. "
            "Ensure RequestsLibrary is imported or set requests_library "
            "when importing AIAgentic."
        ) from exc


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

@tool
def api_create_session(alias: str, base_url: str, headers: str = None) -> str:
    """Creates an HTTP session with a base URL for subsequent requests.

    Args:
        alias: Unique name for the session.
        base_url: Base URL for all requests in this session.
        headers: Optional JSON string of default headers (e.g., '{"Content-Type": "application/json"}').

    Returns:
        Confirmation message with session details.
    """
    rl = _get_requests()
    h = json.loads(headers) if headers else None
    rl.create_session(alias, base_url, headers=h)
    return f"Session '{alias}' created with base URL: {base_url}"


@tool
def api_delete_all_sessions() -> str:
    """Deletes all active HTTP sessions.

    Returns:
        Confirmation message.
    """
    rl = _get_requests()
    rl.delete_all_sessions()
    return "All sessions deleted"


# ---------------------------------------------------------------------------
# HTTP methods
# ---------------------------------------------------------------------------

@tool
def api_get(alias: str, url: str, params: str = None, headers: str = None) -> str:
    """Sends an HTTP GET request.

    Args:
        alias: Session alias to use.
        url: URL path (appended to session base URL).
        params: Optional JSON string of query parameters.
        headers: Optional JSON string of request headers.

    Returns:
        Response status code and body.
    """
    rl = _get_requests()
    p = json.loads(params) if params else None
    h = json.loads(headers) if headers else None
    resp = rl.get_on_session(alias, url, params=p, headers=h, expected_status="any")
    body = _format_response_body(resp)
    return f"GET {url} → Status: {resp.status_code}\nResponse: {body}"


@tool
def api_post(alias: str, url: str, data: str = None, json_data: str = None, headers: str = None) -> str:
    """Sends an HTTP POST request.

    Args:
        alias: Session alias to use.
        url: URL path (appended to session base URL).
        data: Optional request body as string.
        json_data: Optional JSON request body as string (auto-parsed).
        headers: Optional JSON string of request headers.

    Returns:
        Response status code and body.
    """
    rl = _get_requests()
    h = json.loads(headers) if headers else None
    j = json.loads(json_data) if json_data else None
    resp = rl.post_on_session(alias, url, data=data, json=j, headers=h, expected_status="any")
    body = _format_response_body(resp)
    return f"POST {url} → Status: {resp.status_code}\nResponse: {body}"


@tool
def api_put(alias: str, url: str, data: str = None, json_data: str = None, headers: str = None) -> str:
    """Sends an HTTP PUT request.

    Args:
        alias: Session alias to use.
        url: URL path (appended to session base URL).
        data: Optional request body as string.
        json_data: Optional JSON request body as string (auto-parsed).
        headers: Optional JSON string of request headers.

    Returns:
        Response status code and body.
    """
    rl = _get_requests()
    h = json.loads(headers) if headers else None
    j = json.loads(json_data) if json_data else None
    resp = rl.put_on_session(alias, url, data=data, json=j, headers=h, expected_status="any")
    body = _format_response_body(resp)
    return f"PUT {url} → Status: {resp.status_code}\nResponse: {body}"


@tool
def api_patch(alias: str, url: str, data: str = None, json_data: str = None, headers: str = None) -> str:
    """Sends an HTTP PATCH request.

    Args:
        alias: Session alias to use.
        url: URL path (appended to session base URL).
        data: Optional request body as string.
        json_data: Optional JSON request body as string (auto-parsed).
        headers: Optional JSON string of request headers.

    Returns:
        Response status code and body.
    """
    rl = _get_requests()
    h = json.loads(headers) if headers else None
    j = json.loads(json_data) if json_data else None
    resp = rl.patch_on_session(alias, url, data=data, json=j, headers=h, expected_status="any")
    body = _format_response_body(resp)
    return f"PATCH {url} → Status: {resp.status_code}\nResponse: {body}"


@tool
def api_delete(alias: str, url: str, headers: str = None) -> str:
    """Sends an HTTP DELETE request.

    Args:
        alias: Session alias to use.
        url: URL path (appended to session base URL).
        headers: Optional JSON string of request headers.

    Returns:
        Response status code and body.
    """
    rl = _get_requests()
    h = json.loads(headers) if headers else None
    resp = rl.delete_on_session(alias, url, headers=h, expected_status="any")
    body = _format_response_body(resp)
    return f"DELETE {url} → Status: {resp.status_code}\nResponse: {body}"


@tool
def api_head(alias: str, url: str, headers: str = None) -> str:
    """Sends an HTTP HEAD request (returns headers only, no body).

    Args:
        alias: Session alias to use.
        url: URL path (appended to session base URL).
        headers: Optional JSON string of request headers.

    Returns:
        Response status code and headers.
    """
    rl = _get_requests()
    h = json.loads(headers) if headers else None
    resp = rl.head_on_session(alias, url, headers=h, expected_status="any")
    resp_headers = dict(resp.headers) if resp.headers else {}
    return f"HEAD {url} → Status: {resp.status_code}\nHeaders: {json.dumps(resp_headers, indent=2)}"


@tool
def api_options(alias: str, url: str, headers: str = None) -> str:
    """Sends an HTTP OPTIONS request to discover allowed methods.

    Args:
        alias: Session alias to use.
        url: URL path (appended to session base URL).
        headers: Optional JSON string of request headers.

    Returns:
        Response status code, Allow header, and response headers.
    """
    rl = _get_requests()
    h = json.loads(headers) if headers else None
    resp = rl.options_on_session(alias, url, headers=h, expected_status="any")
    allow = resp.headers.get("Allow", "Not specified")
    return f"OPTIONS {url} → Status: {resp.status_code}\nAllowed methods: {allow}"


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

@tool
def api_status_should_be(expected_status: int, response_status: int) -> str:
    """Asserts that the response status code matches the expected value.

    Args:
        expected_status: Expected HTTP status code.
        response_status: Actual HTTP status code received.

    Returns:
        PASS or FAIL with details.
    """
    if int(response_status) == int(expected_status):
        return f"PASS: Status code is {expected_status}"
    else:
        return f"FAIL: Expected status {expected_status}, got {response_status}"


@tool
def api_response_should_contain(response_body: str, expected_text: str) -> str:
    """Asserts that the response body contains the expected text.

    Args:
        response_body: The response body text.
        expected_text: Text that should be present in the response.

    Returns:
        PASS or FAIL with details.
    """
    if expected_text in response_body:
        return f"PASS: Response contains '{expected_text}'"
    else:
        return f"FAIL: Response does not contain '{expected_text}'. Body preview: {response_body[:500]}"


@tool
def api_extract_json_field(response_body: str, json_path: str) -> str:
    """Extracts a field value from a JSON response body using dot notation.

    Args:
        response_body: JSON response body string.
        json_path: Dot-separated path (e.g., 'data.user.name', 'items.0.id').

    Returns:
        The extracted value as a string.
    """
    try:
        data = json.loads(response_body)
        keys = json_path.split(".")
        value = data
        for key in keys:
            if isinstance(value, list):
                value = value[int(key)]
            elif isinstance(value, dict):
                value = value[key]
            else:
                return f"ERROR: Cannot traverse into {type(value).__name__} at key '{key}'"
        return f"Extracted '{json_path}': {json.dumps(value)}"
    except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
        return f"ERROR: Failed to extract '{json_path}': {e}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_response_body(resp) -> str:
    """Format response body for agent consumption, truncating if very large."""
    try:
        body = resp.text
        if len(body) > 3000:
            return body[:3000] + "\n... [truncated]"
        return body
    except Exception:
        return "<unable to read response body>"


# ---------------------------------------------------------------------------
# Tool list export
# ---------------------------------------------------------------------------

API_TOOLS = instrument_tool_list([
    api_create_session,
    api_delete_all_sessions,
    api_get,
    api_post,
    api_put,
    api_patch,
    api_delete,
    api_head,
    api_options,
    api_status_should_be,
    api_response_should_contain,
    api_extract_json_field,
])
