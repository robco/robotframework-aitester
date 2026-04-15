# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
API tools — Strands @tool wrappers around RequestsLibrary keywords.

These tools provide the AI agent with REST API testing capabilities
via robotframework-requests (RequestsLibrary).
"""

import json
import logging
import re
import uuid
from collections import OrderedDict
from strands import tool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .common_tools import instrument_tool_list

logger = logging.getLogger(__name__)
_API_RESPONSE_CACHE = OrderedDict()
_API_RESPONSE_CACHE_LIMIT = 50
_API_RESPONSE_ID_PATTERN = re.compile(r"\bresp_id[:=]\s*([a-f0-9]{8,32})\b", re.IGNORECASE)


def _get_requests():
    """Get the RequestsLibrary instance from Robot Framework."""
    bi = BuiltIn()
    lib_name = "RequestsLibrary"
    try:
        override = bi.get_variable_value("${AITESTER_REQUESTS_LIBRARY}")
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
            "when importing AITester."
        ) from exc


def _cache_api_response(method: str, url: str, resp) -> dict:
    body = _read_response_body(resp)
    response_id = uuid.uuid4().hex[:8]
    record = {
        "id": response_id,
        "method": method.upper(),
        "url": url,
        "status_code": int(getattr(resp, "status_code", 0) or 0),
        "headers": dict(getattr(resp, "headers", {}) or {}),
        "body": body,
    }
    _API_RESPONSE_CACHE[response_id] = record
    _API_RESPONSE_CACHE.move_to_end(response_id)
    while len(_API_RESPONSE_CACHE) > _API_RESPONSE_CACHE_LIMIT:
        _API_RESPONSE_CACHE.popitem(last=False)
    return record


def _resolve_cached_response(response_ref: str) -> dict | None:
    if not response_ref:
        return None
    match = _API_RESPONSE_ID_PATTERN.search(str(response_ref))
    if not match:
        return None
    response_id = match.group(1).lower()
    return _API_RESPONSE_CACHE.get(response_id)


def _truncate_text(value: str, limit: int = 600) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 16] + "... [truncated]"


def _read_response_body(resp) -> str:
    try:
        return resp.text
    except Exception:
        return "<unable to read response body>"


def _resolve_response_body(response_body_or_ref: str) -> str:
    cached = _resolve_cached_response(response_body_or_ref)
    if cached:
        return cached.get("body", "")
    return str(response_body_or_ref or "")


def _resolve_response_status(response_status_or_ref) -> int:
    if isinstance(response_status_or_ref, int):
        return int(response_status_or_ref)
    cached = _resolve_cached_response(response_status_or_ref)
    if cached:
        return int(cached.get("status_code", 0))
    text = str(response_status_or_ref or "").strip()
    if text.isdigit():
        return int(text)
    match = re.search(r"\bstatus(?:\s*code)?[:=]\s*(\d{3})\b", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    raise ValueError(f"Unable to determine response status from: {text[:120]}")


def _format_cached_response_summary(record: dict) -> str:
    headers = record.get("headers") or {}
    content_type = headers.get("Content-Type", "unknown")
    body = record.get("body", "")
    preview = _truncate_text(body, 600).replace("\n", "\\n")
    return (
        f"{record['method']} {record['url']} -> status={record['status_code']} "
        f"resp_id={record['id']} type={content_type} bytes={len(body)}\n"
        f"body_preview={preview}"
    )


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
    _API_RESPONSE_CACHE.clear()
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
    record = _cache_api_response("GET", url, resp)
    return _format_cached_response_summary(record)


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
    record = _cache_api_response("POST", url, resp)
    return _format_cached_response_summary(record)


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
    record = _cache_api_response("PUT", url, resp)
    return _format_cached_response_summary(record)


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
    record = _cache_api_response("PATCH", url, resp)
    return _format_cached_response_summary(record)


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
    record = _cache_api_response("DELETE", url, resp)
    return _format_cached_response_summary(record)


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
    record = _cache_api_response("HEAD", url, resp)
    return _format_cached_response_summary(record)


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
    record = _cache_api_response("OPTIONS", url, resp)
    summary = _format_cached_response_summary(record)
    allow = record["headers"].get("Allow", "Not specified")
    return summary + f"\nallow={allow}"


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------

@tool
def api_status_should_be(expected_status: int, response_status: int) -> str:
    """Asserts that the response status code matches the expected value.

    Args:
        expected_status: Expected HTTP status code.
        response_status: Actual HTTP status code or a cached response summary/reference.

    Returns:
        PASS or FAIL with details.
    """
    actual_status = _resolve_response_status(response_status)
    if actual_status == int(expected_status):
        return f"PASS: Status code is {expected_status}"
    else:
        return f"FAIL: Expected status {expected_status}, got {actual_status}"


@tool
def api_response_should_contain(response_body: str, expected_text: str) -> str:
    """Asserts that the response body contains the expected text.

    Args:
        response_body: The response body text or a cached response summary/reference.
        expected_text: Text that should be present in the response.

    Returns:
        PASS or FAIL with details.
    """
    resolved_body = _resolve_response_body(response_body)
    if expected_text in resolved_body:
        return f"PASS: Response contains '{expected_text}'"
    else:
        preview = _truncate_text(resolved_body, 500)
        return f"FAIL: Response does not contain '{expected_text}'. Body preview: {preview}"


@tool
def api_extract_json_field(response_body: str, json_path: str) -> str:
    """Extracts a field value from a JSON response body using dot notation.

    Args:
        response_body: JSON response body string or a cached response summary/reference.
        json_path: Dot-separated path (e.g., 'data.user.name', 'items.0.id').

    Returns:
        The extracted value as a string.
    """
    try:
        data = json.loads(_resolve_response_body(response_body))
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
