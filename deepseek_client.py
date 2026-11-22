#!/usr/bin/env python3
"""Minimal DeepSeek chat-completions client (standard library only).

Configuration (environment variables, read on every call):
    DEEPSEEK_API_KEY   required; sent as a Bearer token
    DEEPSEEK_BASE_URL  default https://api.deepseek.com (must be https)
    DEEPSEEK_MODEL     default deepseek-flash
    DEEPSEEK_TIMEOUT   request timeout in seconds, default 120

Command-line use:
    python deepseek_client.py "Explain what an SMB relay attack is"
    some_command | python deepseek_client.py "Summarize this output"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_TOKENS = 4096

logger = logging.getLogger("metasploit_mcp_server.deepseek")


class DeepSeekError(RuntimeError):
    """Raised when DeepSeek is misconfigured or a request fails."""


def _settings() -> Dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise DeepSeekError("DEEPSEEK_API_KEY is not set.")

    base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    if urllib.parse.urlparse(base_url).scheme != "https":
        raise DeepSeekError("DEEPSEEK_BASE_URL must use https:// so the API key is not sent in clear text.")

    try:
        timeout = float(os.getenv("DEEPSEEK_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError as error:
        raise DeepSeekError("DEEPSEEK_TIMEOUT must be a number of seconds.") from error

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        "timeout": timeout,
    }


def build_messages(prompt: str, context: str = "", system_prompt: str = "") -> List[Dict[str, str]]:
    """Return chat messages for a prompt plus optional context and system prompt."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("Prompt cannot be empty.")

    messages: List[Dict[str, str]] = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})

    content = prompt
    if context and context.strip():
        content = f"{prompt}\n\n--- BEGIN CONTEXT ---\n{context.strip()}\n--- END CONTEXT ---"
    messages.append({"role": "user", "content": content})
    return messages


def _api_error_message(error: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(error.read().decode("utf-8", errors="replace"))
        detail = body.get("error", {}).get("message") or body.get("message")
    except (ValueError, AttributeError, OSError):
        detail = None
    return f"DeepSeek API returned HTTP {error.code}: {detail or error.reason}"


def chat(
    prompt: str,
    *,
    context: str = "",
    system_prompt: str = "",
    model: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """Send one chat-completion request and return the reply text and usage."""
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1.")
    messages = build_messages(prompt, context, system_prompt)
    settings = _settings()

    payload: Dict[str, Any] = {
        "model": (model or "").strip() or settings["model"],
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature

    request = urllib.request.Request(
        f"{settings['base_url']}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    # Log sizes only: prompts may carry target data from Metasploit output.
    logger.info("DeepSeek request: model=%s, %d chars", payload["model"], sum(len(m["content"]) for m in messages))

    try:
        with urllib.request.urlopen(request, timeout=settings["timeout"]) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise DeepSeekError(_api_error_message(error)) from error
    except urllib.error.URLError as error:
        raise DeepSeekError(f"Could not reach DeepSeek API: {error.reason}") from error
    except TimeoutError as error:
        raise DeepSeekError(f"DeepSeek API did not respond within {settings['timeout']:g}s.") from error
    except ValueError as error:
        raise DeepSeekError("DeepSeek API returned a response that is not valid JSON.") from error

    try:
        choice = body["choices"][0]
        content = choice["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise DeepSeekError("DeepSeek API response did not contain a reply.") from error

    finish_reason = choice.get("finish_reason")
    if not content.strip() and finish_reason == "length":
        raise DeepSeekError(
            f"DeepSeek used all {max_tokens} max_tokens before writing a reply; retry with a larger max_tokens."
        )

    return {
        "model": body.get("model", payload["model"]),
        "response": content,
        "finish_reason": finish_reason,
        "usage": body.get("usage", {}),
    }


async def query(
    prompt: str,
    context: str = "",
    system_prompt: str = "",
    model: str = "",
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Dict[str, Any]:
    """Async wrapper for MCP tools: never raises, returns a status dictionary."""
    try:
        result = await asyncio.to_thread(
            chat,
            prompt,
            context=context,
            system_prompt=system_prompt,
            model=model or None,
            max_tokens=max_tokens,
        )
    except (DeepSeekError, ValueError) as error:
        logger.warning("DeepSeek query failed: %s", error)
        return {"status": "error", "message": str(error)}
    except Exception as error:  # Keep the MCP server alive on unexpected failures.
        logger.exception("Unexpected error during DeepSeek query.")
        return {"status": "error", "message": f"Unexpected error: {error}"}
    return {"status": "success", **result}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Send a prompt to the DeepSeek API.")
    parser.add_argument("prompt", help="The question or instruction.")
    parser.add_argument("--system", default="", help="Optional system prompt.")
    parser.add_argument("--model", default="", help=f"Model id (default: $DEEPSEEK_MODEL or {DEFAULT_MODEL}).")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args(argv)

    context = "" if sys.stdin.isatty() else sys.stdin.read()
    try:
        result = chat(
            args.prompt,
            context=context,
            system_prompt=args.system,
            model=args.model or None,
            max_tokens=args.max_tokens,
        )
    except (DeepSeekError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(result["response"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
