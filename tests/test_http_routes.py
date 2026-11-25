#!/usr/bin/env python3
"""
HTTP route tests for the FastAPI app.

These run in a fresh interpreter because the other test modules replace
fastapi and starlette with mocks in sys.modules.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

REPO = os.path.join(os.path.dirname(__file__), '..')

PROBE = textwrap.dedent('''
    import json, sys, types
    try:
        import pymetasploit3.msfrpc  # noqa: F401
    except ImportError:
        stub = types.ModuleType("pymetasploit3.msfrpc")
        stub.MsfRpcError = type("MsfRpcError", (Exception,), {})
        stub.MsfRpcClient = object
        stub.MsfConsole = object
        sys.modules["pymetasploit3"] = types.ModuleType("pymetasploit3")
        sys.modules["pymetasploit3.msfrpc"] = stub
    from starlette.testclient import TestClient
    import MetasploitMCP

    client = TestClient(MetasploitMCP.app)
    files = client.get("/files/missing.bin")
    is_json = files.headers.get("content-type", "").startswith("application/json")
    print(json.dumps({
        "healthz": client.get("/healthz").status_code,
        "files": files.status_code,
        "files_detail": files.json().get("detail") if is_json else files.text,
        "messages": client.post("/messages/?session_id=deadbeef", json={}).status_code,
    }))
''')


@pytest.fixture(scope="module")
def routes():
    env = dict(os.environ, MCP_AUTH_TOKEN="")
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_healthz_reaches_its_handler(routes):
    """503 means the health handler ran and found no Metasploit client; 404 means it was never reached."""
    assert routes["healthz"] == 503


def test_files_reaches_its_handler(routes):
    assert routes["files"] == 404
    assert routes["files_detail"] == "Payload not found."


def test_mcp_endpoints_still_mounted(routes):
    """An unknown SSE session gets the MCP transport's 400, so /messages/ is still routed."""
    assert routes["messages"] == 400
