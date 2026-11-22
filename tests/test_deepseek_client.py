#!/usr/bin/env python3
"""Tests for the DeepSeek client used by the query_deepseek MCP tool."""

import io
import json
import os
import sys
import urllib.error
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import deepseek_client  # noqa: E402
from deepseek_client import DeepSeekError, build_messages, chat, query  # noqa: E402

TEST_KEY = "sk-test-not-a-real-key"


class FakeResponse:
    def __init__(self, body):
        self._data = json.dumps(body).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def reply(content="pong", finish_reason="stop", model="deepseek-flash"):
    return FakeResponse({
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
    })


def http_error(code, body):
    return urllib.error.HTTPError(
        "https://api.deepseek.com/chat/completions", code, "Error", {}, io.BytesIO(json.dumps(body).encode())
    )


@pytest.fixture
def env(monkeypatch):
    for name in ("DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DEEPSEEK_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", TEST_KEY)
    return monkeypatch


@pytest.fixture
def urlopen():
    with patch("deepseek_client.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = reply()
        yield mock_urlopen


def sent_request(mock_urlopen):
    request = mock_urlopen.call_args.args[0]
    return request, json.loads(request.data.decode("utf-8"))


class TestBuildMessages:
    def test_prompt_only(self):
        assert build_messages("  hi  ") == [{"role": "user", "content": "hi"}]

    def test_system_and_context(self):
        messages = build_messages("Summarize", context="line1\nline2", system_prompt="Be terse")
        assert messages[0] == {"role": "system", "content": "Be terse"}
        assert messages[1]["role"] == "user"
        assert messages[1]["content"].startswith("Summarize\n\n--- BEGIN CONTEXT ---\nline1\nline2")
        assert messages[1]["content"].endswith("--- END CONTEXT ---")

    def test_empty_prompt_rejected(self):
        with pytest.raises(ValueError):
            build_messages("   ")


class TestChat:
    def test_sends_expected_request(self, env, urlopen):
        result = chat("ping", system_prompt="sys")

        request, body = sent_request(urlopen)
        assert request.full_url == "https://api.deepseek.com/chat/completions"
        assert request.get_method() == "POST"
        assert request.get_header("Authorization") == f"Bearer {TEST_KEY}"
        assert body["model"] == "deepseek-flash"
        assert body["max_tokens"] == deepseek_client.DEFAULT_MAX_TOKENS
        assert "temperature" not in body
        assert body["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "ping"}]
        assert urlopen.call_args.kwargs["timeout"] == deepseek_client.DEFAULT_TIMEOUT
        assert result == {
            "model": "deepseek-flash",
            "response": "pong",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }

    def test_environment_overrides(self, env, urlopen):
        env.setenv("DEEPSEEK_BASE_URL", "https://proxy.example.com/v1/")
        env.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        env.setenv("DEEPSEEK_TIMEOUT", "5")

        chat("ping", temperature=0.2, max_tokens=50)

        request, body = sent_request(urlopen)
        assert request.full_url == "https://proxy.example.com/v1/chat/completions"
        assert body["model"] == "deepseek-v4-pro"
        assert body["temperature"] == 0.2
        assert body["max_tokens"] == 50
        assert urlopen.call_args.kwargs["timeout"] == 5.0

    def test_model_argument_beats_environment(self, env, urlopen):
        env.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        chat("ping", model="deepseek-flash")
        assert sent_request(urlopen)[1]["model"] == "deepseek-flash"

    def test_missing_key(self, env, urlopen):
        env.delenv("DEEPSEEK_API_KEY")
        with pytest.raises(DeepSeekError, match="DEEPSEEK_API_KEY"):
            chat("ping")
        urlopen.assert_not_called()

    def test_plain_http_base_url_rejected(self, env, urlopen):
        env.setenv("DEEPSEEK_BASE_URL", "http://api.deepseek.com")
        with pytest.raises(DeepSeekError, match="https"):
            chat("ping")
        urlopen.assert_not_called()

    def test_bad_wait_setting(self, env, urlopen):
        env.setenv("DEEPSEEK_TIMEOUT", "soon")
        with pytest.raises(DeepSeekError, match="DEEPSEEK_TIMEOUT"):
            chat("ping")

    def test_invalid_max_tokens(self, env, urlopen):
        with pytest.raises(ValueError, match="max_tokens"):
            chat("ping", max_tokens=0)

    def test_http_error_includes_api_message_not_key(self, env, urlopen):
        urlopen.side_effect = http_error(401, {"error": {"message": "Authentication Fails"}})
        with pytest.raises(DeepSeekError) as excinfo:
            chat("ping")
        assert "HTTP 401" in str(excinfo.value)
        assert "Authentication Fails" in str(excinfo.value)
        assert TEST_KEY not in str(excinfo.value)

    def test_http_error_without_json_body(self, env, urlopen):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://api.deepseek.com", 503, "Service Unavailable", {}, io.BytesIO(b"<html>")
        )
        with pytest.raises(DeepSeekError, match="HTTP 503: Service Unavailable"):
            chat("ping")

    def test_unreachable_host(self, env, urlopen):
        urlopen.side_effect = urllib.error.URLError("Name or service not known")
        with pytest.raises(DeepSeekError, match="Could not reach DeepSeek API"):
            chat("ping")

    def test_no_reply_in_time(self, env, urlopen):
        urlopen.side_effect = TimeoutError()
        with pytest.raises(DeepSeekError, match="did not respond"):
            chat("ping")

    def test_non_json_response(self, env, urlopen):
        urlopen.return_value.read = lambda: b"not json"
        with pytest.raises(DeepSeekError, match="not valid JSON"):
            chat("ping")

    def test_response_without_choices(self, env, urlopen):
        urlopen.return_value = FakeResponse({"choices": []})
        with pytest.raises(DeepSeekError, match="did not contain a reply"):
            chat("ping")

    def test_token_budget_spent_on_reasoning(self, env, urlopen):
        urlopen.return_value = reply(content="", finish_reason="length")
        with pytest.raises(DeepSeekError, match="larger max_tokens"):
            chat("ping", max_tokens=10)


class TestQuery:
    @pytest.mark.asyncio
    async def test_success(self, env, urlopen):
        result = await query("ping", context="ctx", model="deepseek-v4-pro", max_tokens=99)
        assert result["status"] == "success"
        assert result["response"] == "pong"
        body = sent_request(urlopen)[1]
        assert body["model"] == "deepseek-v4-pro"
        assert body["max_tokens"] == 99
        assert "ctx" in body["messages"][-1]["content"]

    @pytest.mark.asyncio
    async def test_empty_model_uses_default(self, env, urlopen):
        await query("ping", model="")
        assert sent_request(urlopen)[1]["model"] == "deepseek-flash"

    @pytest.mark.asyncio
    async def test_errors_become_status(self, env, urlopen):
        env.delenv("DEEPSEEK_API_KEY")
        assert await query("ping") == {"status": "error", "message": "DEEPSEEK_API_KEY is not set."}
        assert (await query(""))["status"] == "error"

    @pytest.mark.asyncio
    async def test_unexpected_errors_become_status(self, env, urlopen):
        urlopen.side_effect = RuntimeError("boom")
        assert await query("ping") == {"status": "error", "message": "Unexpected error: boom"}


class TestCli:
    def test_prints_reply(self, env, urlopen, capsys):
        with patch("sys.stdin.isatty", return_value=True):
            assert deepseek_client.main(["ping", "--model", "deepseek-v4-pro"]) == 0
        assert capsys.readouterr().out == "pong\n"
        assert sent_request(urlopen)[1]["model"] == "deepseek-v4-pro"

    def test_piped_stdin_becomes_context(self, env, urlopen):
        with patch("sys.stdin", io.StringIO("scan output")):
            assert deepseek_client.main(["Summarize"]) == 0
        assert "scan output" in sent_request(urlopen)[1]["messages"][-1]["content"]

    def test_error_exit_code(self, env, urlopen, capsys):
        env.delenv("DEEPSEEK_API_KEY")
        with patch("sys.stdin.isatty", return_value=True):
            assert deepseek_client.main(["ping"]) == 2
        assert "DEEPSEEK_API_KEY" in capsys.readouterr().err


def test_live_network_roundtrip():
    """Real API call; runs only with --run-network and DEEPSEEK_API_KEY set."""
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")
    result = chat("Reply with the single word: pong", max_tokens=200)
    assert "pong" in result["response"].lower()
