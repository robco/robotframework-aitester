# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""Unit tests for API tools."""

import json

import pytest

from AITester.tools import api_tools, common_tools


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class FakeRequests:
    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.deleted = False

    def get_on_session(self, alias, url, params=None, headers=None, expected_status=None):
        return self.response

    def delete_all_sessions(self):
        self.deleted = True


@pytest.fixture(autouse=True)
def clear_api_response_cache(monkeypatch):
    api_tools._API_RESPONSE_CACHE.clear()
    monkeypatch.setattr(common_tools, "_log_ai_step_to_rf", lambda **kwargs: None)
    yield
    api_tools._API_RESPONSE_CACHE.clear()


def test_api_get_returns_compact_response_summary_and_caches_body(monkeypatch):
    body = json.dumps(
        {
            "data": {
                "user": {
                    "name": "Alice",
                    "role": "admin",
                    "notes": "x" * 1200,
                }
            }
        }
    )
    fake_requests = FakeRequests(
        FakeResponse(
            status_code=200,
            text=body,
            headers={"Content-Type": "application/json"},
        )
    )
    monkeypatch.setattr(api_tools, "_get_requests", lambda: fake_requests)

    result = api_tools.api_get("api", "/users/1")

    assert "GET /users/1" in result
    assert "status=200" in result
    assert "resp_id=" in result
    assert "body_preview=" in result
    assert "type=application/json" in result
    assert len(result) < len(body)
    cached = api_tools._resolve_cached_response(result)
    assert cached is not None
    assert cached["body"] == body


def test_api_validation_tools_accept_cached_response_summary(monkeypatch):
    body = json.dumps({"data": {"user": {"name": "Alice", "role": "admin"}}})
    fake_requests = FakeRequests(
        FakeResponse(
            status_code=200,
            text=body,
            headers={"Content-Type": "application/json"},
        )
    )
    monkeypatch.setattr(api_tools, "_get_requests", lambda: fake_requests)
    response_summary = api_tools.api_get("api", "/users/1")

    assert api_tools.api_status_should_be(200, response_summary) == "PASS: Status code is 200"
    assert api_tools.api_response_should_contain(response_summary, '"name": "Alice"') == (
        "PASS: Response contains '\"name\": \"Alice\"'"
    )
    assert api_tools.api_extract_json_field(response_summary, "data.user.role") == (
        'Extracted \'data.user.role\': "admin"'
    )


def test_api_delete_all_sessions_clears_cached_responses(monkeypatch):
    fake_requests = FakeRequests(
        FakeResponse(
            status_code=204,
            text="",
            headers={"Content-Type": "application/json"},
        )
    )
    monkeypatch.setattr(api_tools, "_get_requests", lambda: fake_requests)
    api_tools._API_RESPONSE_CACHE["deadbeef"] = {"body": "cached"}

    result = api_tools.api_delete_all_sessions()

    assert result == "All sessions deleted"
    assert fake_requests.deleted is True
    assert api_tools._API_RESPONSE_CACHE == {}
